#!/usr/bin/env python3
"""Dual-stream language router — dorsal AF vs ventral EmC conflict policy.

Reads mesh-params.language_dual_stream.conflict_policy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import activity_emit  # noqa: E402

PARAMS = ROOT / "config" / "connectome" / "mesh-params.json"


def route_act(act: str) -> dict:
    params = json.loads(PARAMS.read_text(encoding="utf-8")) if PARAMS.exists() else {}
    dual = params.get("language_dual_stream") or {}
    policy = dual.get("conflict_policy") or {}
    winner = policy.get(act) or policy.get("default") or "dorsal"
    streams = {
        "dorsal": dual.get("dorsal") or {},
        "ventral": dual.get("ventral") or {},
    }
    chosen = streams.get(winner) or {}
    return {
        "act": act,
        "winner": winner,
        "tracts": chosen.get("tracts") or [],
        "cam": chosen.get("cam"),
        "function": chosen.get("function"),
        "policy": policy,
        "at": activity_emit.utc(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "act",
        choices=["speak", "docs", "research", "careers", "default"],
        help="act kind to route",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-emit", action="store_true")
    args = ap.parse_args()

    result = route_act(args.act)
    if not args.no_emit:
        winner = result["winner"]
        activity_emit.emit(
            neuron="neuron.speak_loop" if args.act == "speak" else "neuron.semantic",
            kind="loop",
            area="area.broca" if winner == "dorsal" else "area.temporal",
            intensity=0.8,
            tracts=(result.get("tracts") or [])[:4],
            reason=f"dual_stream:{winner}:{args.act}",
            source="dual_stream_router",
            refresh=True,
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
