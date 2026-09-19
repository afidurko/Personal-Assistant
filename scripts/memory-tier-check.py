#!/usr/bin/env python3
"""Validate HMO tier config + report which mesh namespaces map where."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HMO = ROOT / "config" / "memory" / "hmo-tiers.json"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    cfg = json.loads(HMO.read_text(encoding="utf-8"))
    errors = []
    if cfg.get("status") != "applied":
        errors.append("hmo_not_applied")
    tiers = {t["id"]: t for t in cfg.get("tiers") or []}
    for need in ("primary", "secondary", "archive"):
        if need not in tiers:
            errors.append(f"missing_tier:{need}")
    report = {
        "ok": not errors,
        "errors": errors,
        "status": cfg.get("status"),
        "authorized_by": cfg.get("authorized_by"),
        "tiers": sorted(tiers),
        "primary_includes": tiers.get("primary", {}).get("includes"),
        "config": str(HMO.relative_to(ROOT)),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"memory-tier-check: {'PASS' if report['ok'] else 'FAIL'}")
        for e in errors:
            print(f"  HARD {e}")
        print(f"  tiers={','.join(report['tiers'])}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
