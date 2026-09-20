#!/usr/bin/env python3
"""Pack Higgsfield run-plan / result JSON into mesh/runs (+ optional LitServe handoff)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_payload(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("results JSON must be an object")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, help="path to higgsfield-run.py JSON")
    p.add_argument("--goal", help="override goal string recorded in mesh doc")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    path = Path(args.results)
    if not path.exists():
        print(f"missing results file: {path}", file=sys.stderr)
        return 1

    payload = load_payload(path)
    experiments = payload.get("experiments") or []
    primary = experiments[0]["experiment"] if experiments else None
    handoff = payload.get("litserve_handoff") or {}

    doc = {
        "namespace": "mesh/runs",
        "kind": "higgsfield_train_plan",
        "integration": "higgsfield",
        "motor": "motor.higgsfield",
        "goal": args.goal or payload.get("goal"),
        "mode": payload.get("mode"),
        "ok": payload.get("ok"),
        "experiment_file": payload.get("experiment_file"),
        "experiments": experiments,
        "primary_experiment": primary,
        "nodes": (payload.get("nodes") or {}).get("nodes") or [],
        "node_count": (payload.get("nodes") or {}).get("count")
        or len((payload.get("nodes") or {}).get("nodes") or []),
        "spend": payload.get("spend"),
        "enhance": payload.get("enhance"),
        "live_allowed": payload.get("live_allowed"),
        "litserve_handoff": handoff,
        "packed_at": datetime.now(timezone.utc).isoformat(),
        "source_at": payload.get("at"),
        "errors": payload.get("errors") or [],
    }

    text = json.dumps(doc, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
