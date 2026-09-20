#!/usr/bin/env python3
"""Shared live-activity emitter for Cam cortex DTI viz.

Appends vault/10-Mesh-Distillates/activity-events.jsonl and optionally
refreshes live-activity.json so the 3D mesh sees real agent/task fire.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"
FEED = ROOT / "scripts" / "live-activity-feed.py"
_DUAL_CACHE: dict | None = None


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(
    *,
    neuron: str,
    area: str,
    intensity: float = 0.8,
    tracts: list[str] | None = None,
    reason: str = "",
    kind: str = "agent",
    source: str = "activity_emit",
    refresh: bool = False,
) -> dict:
    row = {
        "ts": utc(),
        "neuron": neuron,
        "kind": kind,
        "area": area,
        "intensity": float(intensity),
        "tracts": tracts or [],
        "reason": reason,
        "source": source,
    }
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    if refresh:
        refresh_live_activity()
    return row


def refresh_live_activity() -> None:
    """Rebuild live-activity.json in-process (no python3 spawn)."""
    if not FEED.exists():
        return
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import cam_inproc

        cam_inproc.load_script("live-activity-feed.py").write_live_activity()
    except Exception:
        pass


def dual_stream(act: str) -> dict:
    """Resolve dorsal/ventral winner from mesh-params (cached)."""
    global _DUAL_CACHE
    if _DUAL_CACHE is None:
        params_path = ROOT / "config" / "connectome" / "mesh-params.json"
        try:
            params = json.loads(params_path.read_text(encoding="utf-8"))
        except Exception:
            params = {}
        _DUAL_CACHE = params.get("language_dual_stream") or {}
    dual = _DUAL_CACHE
    policy = dual.get("conflict_policy") or {}
    winner = policy.get(act) or policy.get("default") or "dorsal"
    chosen = dual.get(winner) or {}
    return {
        "act": act,
        "winner": winner,
        "tracts": chosen.get("tracts") or [],
        "cam": chosen.get("cam"),
        "function": chosen.get("function"),
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neuron", required=True)
    ap.add_argument("--area", required=True)
    ap.add_argument("--intensity", type=float, default=0.8)
    ap.add_argument("--reason", default="")
    ap.add_argument("--source", default="cli")
    ap.add_argument("--tract", action="append", default=[])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    print(
        json.dumps(
            emit(
                neuron=args.neuron,
                area=args.area,
                intensity=args.intensity,
                tracts=args.tract,
                reason=args.reason,
                source=args.source,
                refresh=args.refresh,
            ),
            indent=2,
        )
    )
