#!/usr/bin/env python3
"""One-process static CI gate. 1M fuzz stays in ci-connectome.sh."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_inproc  # noqa: E402

CHECKS: list[tuple[str, str, list[str]]] = [
    ("connectome-check", "connectome-check.py", []),
    ("workspace-integration-check", "workspace-integration-check.py", []),
    ("connectome-anatomy-check", "connectome-anatomy-check.py", []),
    ("trajectory-policy-check", "trajectory-policy-check.py", []),
    ("memory-tier-check", "memory-tier-check.py", []),
    ("aaron-voice-gate-check", "aaron-voice-gate-check.py", []),
    ("public-apis-check", "public-apis-check.py", []),
    ("public-apis-addon-doctor", "public-apis-addon.py", ["doctor"]),
    ("google-trends-check", "google-trends-check.py", []),
    ("google-trends-addon-doctor", "google-trends-addon.py", ["doctor"]),
    ("inkbox-check", "inkbox-check.py", []),
    ("higgsfield-check", "higgsfield-check.py", []),
    ("presence-check", "presence-check.py", []),
    ("converse-overlays-check", "converse-overlays-check.py", []),
    ("loop-check", "loop-check.py", []),
    ("loop-run-dry", "loop-run.py", ["--pattern", "daily-triage", "--level", "L1", "--dry-run"]),
    ("flight-envelope", "flight-envelope.py", ["--offline-only"]),
]


def cam_system_inventory() -> dict:
    mod = cam_inproc.load_script("cam-system.py")
    inv = mod.inventory()
    missing = mod.hard_paths()
    ok = bool(inv.get("ok")) and not missing
    return {
        "id": "cam-system-inventory",
        "ok": ok,
        "exit": 0 if ok else 1,
        "hard_missing": missing,
        "overall": inv.get("overall"),
        "piece_count": inv.get("piece_count"),
    }


def run_checks() -> dict:
    results = [cam_system_inventory()]
    failed: list[str] = []
    if not results[0]["ok"]:
        failed.append("cam-system-inventory")
    for name, filename, argv in CHECKS:
        try:
            code = cam_inproc.run_main(filename, argv)
            row = {"id": name, "ok": code == 0, "exit": code}
        except Exception as exc:  # noqa: BLE001
            row = {
                "id": name,
                "ok": False,
                "exit": 1,
                "error": str(exc),
                "traceback": traceback.format_exc()[-800:],
            }
        results.append(row)
        if not row["ok"]:
            failed.append(name)
    return {
        "ok": not failed,
        "failed": failed,
        "results": results,
        "count": len(results),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    report = run_checks()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"ci-static-gate: {'PASS' if report['ok'] else 'FAIL'} ({report['count']} steps)")
        for row in report["results"]:
            mark = "OK" if row["ok"] else "FAIL"
            print(f"  {mark}: {row['id']}")
        if report["failed"]:
            print("  failed: " + ", ".join(report["failed"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
