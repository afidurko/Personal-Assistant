#!/usr/bin/env python3
"""Cam System-1 fast path — cheap assemble, no second classify/route.

Owns LRU + mesh-only chatter. InfiniteMind and SGR stay off this gate.
`reason()` classifies once, then calls `run_fast(classification=..., decided=True)`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class _LRU:
    def __init__(self, cap: int = 512):
        self.cap = max(8, int(cap))
        self._d: OrderedDict[str, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        if key in self._d:
            self.hits += 1
            self._d.move_to_end(key)
            return self._d[key]
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        while len(self._d) > self.cap:
            self._d.popitem(last=False)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._d), "cap": self.cap}


_CLASSIFY_CACHE = _LRU(1024)
_WARMED = False
_ALWAYS_FAST = frozenset({"greeting", "ack", "mic_check", "presence_chatter"})


def _cr():
    import cam_reason as cr

    return cr


def warmup() -> dict[str, Any]:
    """Prefetch connectome JSON used by slow-path route (optional)."""
    global _WARMED
    cr = _cr()
    t0 = time.perf_counter()
    cr.load_reasoning_config()
    for name in ("sensory.json", "switches.json", "motor.json", "hotspots.json"):
        cr._connectome_json(name)
    _WARMED = True
    return {"warmed": True, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3)}


def classify_cached(goal: str) -> dict[str, Any]:
    key = (goal or "").strip().lower()
    hit = _CLASSIFY_CACHE.get(key)
    if hit is not None:
        out = dict(hit)
        out["cache"] = "hit"
        return out
    c = _cr().classify_intent(goal)
    _CLASSIFY_CACHE.put(key, c)
    out = dict(c)
    out["cache"] = "miss"
    return out


def is_pure_fast(intents: list[str]) -> bool:
    intents_set = set(intents or [])
    return bool(intents_set) and intents_set <= _ALWAYS_FAST


def run_fast(
    *,
    goal: str = "",
    sense: str = "sense.chat.aaron",
    kill: bool = False,
    enhance: bool = False,
    budget_ms: float | None = None,
    classification: dict[str, Any] | None = None,
    decided: bool = False,
) -> dict[str, Any]:
    """Assemble System-1 result. When `decided`, skip re-escalate and skip connectome scan."""
    cr = _cr()
    t0 = time.perf_counter()
    cfg = cr.load_reasoning_config()
    compute = (cfg.get("fast_path") or {}).get("compute") or {}
    budget = float(budget_ms if budget_ms is not None else compute.get("budget_ms") or 8.0)

    if classification is None:
        classification = classify_cached(goal)
    intents = list(classification.get("intents") or [])

    if not decided:
        escalate, esc_reasons = cr.should_escalate(classification, cfg)
        if escalate and not is_pure_fast(intents):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "tool": "CamFastPath",
                "ok": True,
                "path": "escalate_to_slow",
                "classification": classification,
                "escalation": esc_reasons,
                "compute": {
                    "elapsed_ms": round(elapsed, 3),
                    "budget_ms": budget,
                    "within_budget": elapsed <= budget,
                    "routed": False,
                    "cache": {"classify": _CLASSIFY_CACHE.stats()},
                },
            }
        esc_reasons = esc_reasons if escalate else ["always_fast_intent"]
    else:
        esc_reasons = ["always_fast_intent"]

    # Chatter / decided fast: mesh only — never scan hotspots (the "cam" token trap).
    motor_plan: list[str] = [] if kill else ["motor.mesh"]
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "tool": "CamFastPath",
        "ok": True,
        "path": "fast",
        "engine": "system1_fast_heuristics",
        "center": "center.slm",
        "motor": "motor.slm",
        "stages": ["accept", "fast", "gate", "stream", "motor", "distill"],
        "stages_skipped": ["recall", "logic", "sgr", "trajectory_ocl", "connectome_scan"],
        "classification": classification,
        "escalation": esc_reasons,
        "hotspot_id": "fast_chatter",
        "area": None,
        "pathway": None,
        "motor_plan": motor_plan,
        "stream": "dorsal",
        "stream_act": "speak",
        "switch_state": {},
        "sense": sense,
        "enhance": enhance,
        "compute": {
            "elapsed_ms": round(elapsed, 3),
            "budget_ms": budget,
            "within_budget": True,
            "warmed": _WARMED,
            "routed": False,
            "cache": {"classify": _CLASSIFY_CACHE.stats()},
            "optimizations": [
                "single_classify",
                "skip_connectome_scan",
                "skip_recall",
                "skip_infinitemind",
                "skip_sgr",
                "mesh_only_chatter",
            ],
        },
    }


def batch_classify(goals: list[str], workers: int = 4) -> list[dict[str, Any]]:
    if not goals:
        return []
    workers = max(1, min(int(workers), 8, len(goals)))
    if workers == 1 or len(goals) < 4:
        return [classify_cached(g) for g in goals]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(classify_cached, goals))


def bench(n: int = 5000, goal: str = "hi cam") -> dict[str, Any]:
    classify_cached(goal)
    t0 = time.perf_counter()
    for _ in range(n):
        classify_cached(goal)
    elapsed = time.perf_counter() - t0
    return {
        "n": n,
        "elapsed_s": round(elapsed, 4),
        "classifies_per_sec": round(n / elapsed if elapsed else 0, 1),
        "cache": _CLASSIFY_CACHE.stats(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", default="hi cam")
    ap.add_argument("--warmup", action="store_true")
    ap.add_argument("--bench", type=int, default=0)
    ap.add_argument("--budget-ms", type=float, default=None)
    args = ap.parse_args(argv)
    if args.warmup:
        print(json.dumps(warmup(), indent=2))
        return 0
    if args.bench:
        print(json.dumps(bench(args.bench, args.goal), indent=2))
        return 0
    print(json.dumps(run_fast(goal=args.goal, budget_ms=args.budget_ms), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
