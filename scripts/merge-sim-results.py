#!/usr/bin/env python3
"""Merge connectome simulation part JSON files into one summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("parts", nargs="+")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    parts = [json.loads(Path(x).read_text(encoding="utf-8")) for x in args.parts]
    n = sum(x["n"] for x in parts)
    elapsed = max(x["elapsed_s"] for x in parts)  # parallel wall approx
    summary = {
        "n": n,
        "parts": len(parts),
        "parallel_wall_s_approx": elapsed,
        "sum_cpu_s": sum(x["elapsed_s"] for x in parts),
        "passed": sum(x["passed"] for x in parts),
        "failed": sum(x["failed"] for x in parts),
        "kill_holds": sum(x["kill_holds"] for x in parts),
        "non_aaron_holds": sum(x["non_aaron_holds"] for x in parts),
        "feedback_ok": sum(x["feedback_ok"] for x in parts),
        "first_errors": [e for x in parts for e in x.get("first_errors", [])],
        "unlimited_subagents": True,
        "part_files": args.parts,
        "pass_rate": None,
    }
    summary["pass_rate"] = summary["passed"] / n if n else None
    Path(args.out).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
