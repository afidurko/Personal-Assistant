#!/usr/bin/env python3
"""Cam System-1 fast path — compute-speed layer (Phase C).

Fast gate ≠ InfiniteMind. This module is the cheap path:

  classify → light route → mesh/speak → done

Budget-minded: caches, stage skips, batch classify. No SGR, no InfiniteMind
logic engines, no LitServe (yet). Inspired by InfiniteMind's multi-level
cache / batch patterns — without torch or qiskit.
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

REASONING_CFG = ROOT / "config" / "enhancement" / "reasoning-logic.json"


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
_ROUTE_CACHE = _LRU(256)
_WARMED = False


def load_fast_cfg() -> dict[str, Any]:
    if not REASONING_CFG.exists():
        return {}
    cfg = json.loads(REASONING_CFG.read_text(encoding="utf-8"))
    return dict(cfg.get("fast_path") or {})


def warmup() -> dict[str, Any]:
    """Prefetch connectome JSON used by every fast turn."""
    global _WARMED
    import cam_reason as cr  # local import — avoid cycle at module load

    t0 = time.perf_counter()
    for name in ("sensory.json", "switches.json", "motor.json", "hotspots.json"):
        cr._connectome_json(name)
    cr.load_reasoning_config()
    _WARMED = True
    return {"warmed": True, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3)}


def classify_cached(goal: str) -> dict[str, Any]:
    import cam_reason as cr

    key = (goal or "").strip().lower()
    hit = _CLASSIFY_CACHE.get(key)
    if hit is not None:
        out = dict(hit)
        out["cache"] = "hit"
        return out
    c = cr.classify_intent(goal)
    _CLASSIFY_CACHE.put(key, c)
    out = dict(c)
    out["cache"] = "miss"
    return out


def is_pure_fast(intents: list[str], cfg: dict | None = None) -> bool:
    cfg = cfg or load_fast_cfg()
    always = set((cfg.get("always_fast_intents") if "always_fast_intents" in cfg else None) or [])
    if not always:
        # fall back to reasoning escalation list
        import cam_reason as cr

        esc = (cr.load_reasoning_config().get("escalation") or {})
        always = set(esc.get("always_fast_intents") or [])
    intents_set = set(intents or [])
    return bool(intents_set) and intents_set <= always


def quick_route(
    *,
    sense: str,
    goal: str,
    kill: bool = False,
    enhance: bool = False,
    hotspot_id: str | None = None,
) -> dict[str, Any]:
    """Light connectome route with LRU — default mesh-only for chatter."""
    import cam_reason as cr

    cache_key = f"{sense}|{kill}|{enhance}|{hotspot_id or ''}|{(goal or '')[:80].lower()}"
    hit = _ROUTE_CACHE.get(cache_key)
    if hit is not None:
        out = dict(hit)
        out["cache"] = "hit"
        return out
    route = cr.connectome_route_tool(
        sense,
        goal,
        kill=kill,
        enhance=enhance,
        not_aaron=False,
        hotspot_id=hotspot_id,
    )
    _ROUTE_CACHE.put(cache_key, route)
    out = dict(route)
    out["cache"] = "miss"
    return out


def run_fast(
    *,
    goal: str = "",
    sense: str = "sense.chat.aaron",
    kill: bool = False,
    enhance: bool = False,
    budget_ms: float | None = None,
) -> dict[str, Any]:
    """Execute System-1 turn under a latency budget. Never calls InfiniteMind/SGR."""
    import cam_reason as cr

    if not _WARMED:
        warmup()

    cfg = load_fast_cfg()
    compute = cfg.get("compute") or {}
    budget = float(budget_ms if budget_ms is not None else compute.get("budget_ms") or 8.0)
    t0 = time.perf_counter()
    stages_skipped = ["recall", "logic", "sgr"]
    stages = ["accept", "fast", "gate", "stream", "motor", "distill"]

    classification = classify_cached(goal)
    intents = list(classification.get("intents") or [])
    escalate, esc_reasons = cr.should_escalate(classification, cr.load_reasoning_config())

    # Fast gate: only proceed as System-1 when escalate is false
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
                "cache": {
                    "classify": _CLASSIFY_CACHE.stats(),
                    "route": _ROUTE_CACHE.stats(),
                },
            },
        }

    # Chatter: force capability/mesh — avoid enhance hotspot on "cam" token
    route_goal = "capability complete task mesh" if is_pure_fast(intents) else goal
    hotspot = "hotspot.capability" if is_pure_fast(intents) else None
    route = quick_route(
        sense=sense,
        goal=route_goal,
        kill=kill,
        enhance=enhance,
        hotspot_id=hotspot,
    )
    if is_pure_fast(intents) and not kill:
        route["motor_plan"] = ["motor.mesh"]
        route["behavior"] = route.get("behavior") or "fast_presence_ack"
        route["hotspot_id"] = route.get("hotspot_id") or "fast_chatter"
        stages_skipped.append("trajectory_ocl")  # mesh-only; OCL noop

    if kill or (route.get("switch_state") or {}).get("switch.kill") == "act":
        motor_plan: list[str] = []
        stages_skipped = ["recall", "logic", "sgr", "stream"]
    else:
        motor_plan = list(route.get("motor_plan") or ["motor.mesh"])

    # Skip dual-stream file load — dorsal/speak is the fast default
    stream = "dorsal"
    stream_act = "speak"

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "tool": "CamFastPath",
        "ok": True,
        "path": "fast",
        "engine": "system1_fast_heuristics",
        "center": "center.slm",
        "motor": "motor.slm",
        "stages": stages,
        "stages_skipped": stages_skipped,
        "classification": classification,
        "escalation": esc_reasons if escalate else ["always_fast_intent"],
        "hotspot_id": route.get("hotspot_id"),
        "motor_plan": motor_plan,
        "stream": stream,
        "stream_act": stream_act,
        "switch_state": route.get("switch_state"),
        "compute": {
            "elapsed_ms": round(elapsed, 3),
            "budget_ms": budget,
            "within_budget": elapsed <= budget * 3,  # warm cold-start allowance ×3 once
            "warmed": _WARMED,
            "cache": {
                "classify": _CLASSIFY_CACHE.stats(),
                "route": _ROUTE_CACHE.stats(),
            },
            "optimizations": [
                "lru_classify",
                "lru_route",
                "skip_recall",
                "skip_infinitemind",
                "skip_sgr",
                "skip_dual_stream_io",
                "mesh_only_chatter",
            ],
        },
    }


def batch_classify(goals: list[str], workers: int = 4) -> list[dict[str, Any]]:
    """Parallel classify — InfiniteMind-style batch pattern for throughput."""
    if not goals:
        return []
    workers = max(1, min(int(workers), 8, len(goals)))
    if workers == 1 or len(goals) < 4:
        return [classify_cached(g) for g in goals]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(classify_cached, goals))


def bench(n: int = 5000, goal: str = "hi cam") -> dict[str, Any]:
    warmup()
    # prime caches
    run_fast(goal=goal)
    t0 = time.perf_counter()
    for _ in range(n):
        classify_cached(goal)
    elapsed = time.perf_counter() - t0
    per_s = n / elapsed if elapsed > 0 else 0
    return {
        "n": n,
        "elapsed_s": round(elapsed, 4),
        "classifies_per_sec": round(per_s, 1),
        "cache": _CLASSIFY_CACHE.stats(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", default="hi cam")
    ap.add_argument("--warmup", action="store_true")
    ap.add_argument("--bench", type=int, default=0, help="run N cached classifies")
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
