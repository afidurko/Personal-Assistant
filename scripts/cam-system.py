#!/usr/bin/env python3
"""Cam overall system — status, smoke, and distill for all wired pieces.

Confirms connectome, swarm, tools, workspaces, system bridge inventory, and
key scripts compose one live bus. Does not require network.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIECES = ROOT / "config" / "system" / "pieces.json"
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "system-integration-latest.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:
        return 1, str(e)


def path_status(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return "missing"
    if p.is_dir() and rel.startswith("integrations/") and not any(p.iterdir()):
        return "empty"
    return "ok"


def inventory() -> dict:
    cfg = json.loads(PIECES.read_text(encoding="utf-8"))
    reports = []
    for piece in cfg.get("pieces") or []:
        paths = piece.get("paths") or []
        statuses = {rel: path_status(rel) for rel in paths}
        vals = list(statuses.values())
        if any(v == "missing" for v in vals) and all(v == "missing" for v in vals):
            status = "critical"
        elif any(v in ("missing", "empty") for v in vals):
            status = "warning"
        else:
            status = "healthy"
        reports.append(
            {
                "id": piece["id"],
                "title": piece.get("title"),
                "layer": piece.get("layer"),
                "status": status,
                "paths": statuses,
            }
        )
    ranks = {"healthy": 0, "warning": 1, "critical": 2}
    overall = "healthy"
    for r in reports:
        if ranks.get(r["status"], 0) > ranks.get(overall, 0):
            overall = r["status"]
    return {
        "at": utc(),
        "overall": overall,
        "ok": overall != "critical",
        "assistant": cfg.get("assistant", "Cam"),
        "bus": cfg.get("bus") or {},
        "boot_order": cfg.get("boot_order") or [],
        "pieces": reports,
        "piece_count": len(reports),
    }


def smoke_checks() -> list[dict]:
    checks = []
    for name, cmd in [
        ("connectome-check", [sys.executable, "scripts/connectome-check.py"]),
        ("swarm-check", [sys.executable, "scripts/swarm-check.py"]),
        ("connectors-check", [sys.executable, "scripts/connectors-check.py"]),
        ("swarm-runtime-doctor", [sys.executable, "scripts/cam_swarm.py", "doctor"]),
        (
            "workspace-integration-check",
            [sys.executable, "scripts/workspace-integration-check.py"],
        ),
        (
            "connectome-route-chat",
            [
                sys.executable,
                "scripts/connectome-route.py",
                "--sense",
                "sense.chat.aaron",
                "--goal",
                "system smoke",
            ],
        ),
    ]:
        code, out = run(cmd)
        checks.append(
            {
                "id": name,
                "ok": code == 0,
                "exit": code,
                "preview": out[:240],
            }
        )
    return checks


def hard_paths() -> list[str]:
    required = [
        "config/system/pieces.json",
        "server/core/system-bridge.ts",
        "scripts/cam-system.py",
        "docs/SYSTEM_INTEGRATION.md",
        "config/connectome/sensory.json",
        "config/connectome/motor.json",
        "config/tools/registry.json",
        "config/workspaces/registry.json",
        "config/swarm/privileges.json",
        "server/index.ts",
        "src/App.tsx",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON only")
    parser.add_argument("--smoke", action="store_true", help="run subsystem smokes")
    parser.add_argument("--no-write", action="store_true", help="skip distillate write")
    args = parser.parse_args()

    missing = hard_paths()
    inv = inventory()
    smokes = smoke_checks() if args.smoke else []
    report = {
        **inv,
        "hard_missing": missing,
        "smokes": smokes,
        "smoke_ok": all(s["ok"] for s in smokes) if smokes else None,
    }
    if missing:
        report["ok"] = False
        report["overall"] = "critical"

    if not args.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"cam-system: {report['overall'].upper()} · "
            f"{report['piece_count']} pieces · ok={report['ok']}"
        )
        for p in report["pieces"]:
            mark = {"healthy": "✓", "warning": "!", "critical": "✗"}.get(p["status"], "?")
            print(f"  {mark} {p['id']} ({p['layer']}) {p['status']}")
        if missing:
            print("  HARD missing:")
            for m in missing:
                print(f"    - {m}")
        if smokes:
            print("  smokes:")
            for s in smokes:
                print(f"    {'OK' if s['ok'] else 'FAIL'}: {s['id']}")

    return 0 if report["ok"] and (report["smoke_ok"] in (True, None)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
