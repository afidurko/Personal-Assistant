#!/usr/bin/env python3
"""Static connectome graph check — O(hotspots), no billion fuzz.

Corrective gate before/after campaigns. Exit 0 only if pathways, inventories,
required switches, and feedback edges are sound.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "connectome_simulate", ROOT / "scripts" / "connectome-simulate.py"
)
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


def build_report() -> dict:
    sense_ids, by_sense, known, motors, edges, hard, soft = sim.build_tables()
    missing = [
        e
        for e in soft
        if e.startswith("missing_edge:") or e.startswith("missing_feedback_edge:")
    ]
    return {
        "senses": len(sense_ids),
        "hotspot_options": sum(len(v) for v in by_sense.values()),
        "known_nodes": len(known),
        "motors": len(motors),
        "edges": len(edges),
        "hard_errors": hard,
        "missing_edges": missing,
        "soft_warnings": soft,
        "ok": not hard and not missing,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"connectome-check: {status}")
        print(
            f"  senses={report['senses']} options={report['hotspot_options']} "
            f"edges={report['edges']} hard={len(report['hard_errors'])} "
            f"missing={len(report['missing_edges'])}"
        )
        for e in report["hard_errors"][:20]:
            print(f"  HARD {e}")
        for e in report["missing_edges"][:20]:
            print(f"  MISS {e}")
    out = (
        ROOT
        / "vault"
        / "10-Mesh-Distillates"
        / "qa-cycles"
        / "connectome-check-latest.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
