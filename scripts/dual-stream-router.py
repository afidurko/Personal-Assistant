#!/usr/bin/env python3
"""Dual-stream language router — dorsal AF vs ventral EmC conflict policy.

Reads mesh-params.language_dual_stream.conflict_policy.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "config" / "connectome" / "mesh-params.json"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "act",
        choices=["speak", "docs", "research", "careers", "default"],
        help="act kind to route",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    params = json.loads(PARAMS.read_text(encoding="utf-8"))
    dual = params.get("language_dual_stream") or {}
    policy = dual.get("conflict_policy") or {}
    winner = policy.get(args.act) or policy.get("default") or "dorsal"
    streams = {
        "dorsal": dual.get("dorsal") or {},
        "ventral": dual.get("ventral") or {},
    }
    chosen = streams.get(winner) or {}
    result = {
        "act": args.act,
        "winner": winner,
        "tracts": chosen.get("tracts") or [],
        "cam": chosen.get("cam"),
        "function": chosen.get("function"),
        "policy": policy,
        "at": utc(),
    }

    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": utc(),
                    "neuron": "neuron.speak_loop" if args.act == "speak" else "neuron.semantic",
                    "kind": "loop",
                    "area": "area.broca" if winner == "dorsal" else "area.temporal",
                    "intensity": 0.8,
                    "tracts": result["tracts"][:4],
                    "reason": f"dual_stream:{winner}:{args.act}",
                    "source": "dual_stream_router",
                }
            )
            + "\n"
        )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
