#!/usr/bin/env python3
"""Auto-sync Cam's home with all projects and repos it registers.

Inbound counterpart of the auto-update channels in the home build plan
(config/system/build-plan.json). Surveys the home repo and every registered
integration checkout, reports drift, and — only when asked — fast-forwards the
home and re-pins submodules. Report-first, offline-safe, never auto-merges.

Examples:
  python3 scripts/auto-sync.py                # report drift (offline-safe)
  python3 scripts/auto-sync.py --json --write # machine report + distillate
  python3 scripts/auto-sync.py --pull         # ff-only pull + submodule init sync
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "workspaces" / "registry.json"
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "auto-sync" / "latest.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:  # offline / timeout are expected, not fatal
        return 1, str(e)


def home_drift(fetch_timeout: int) -> dict:
    """Fetch origin/main when the network allows; report ahead/behind."""
    rc, branch = git(["branch", "--show-current"])
    fetched_rc, fetch_out = git(["fetch", "origin", "main"], timeout=fetch_timeout)
    counts = {"ahead": None, "behind": None}
    if fetched_rc == 0:
        rc, out = git(["rev-list", "--left-right", "--count", "HEAD...origin/main"])
        if rc == 0 and out:
            parts = out.split()
            if len(parts) == 2:
                counts = {"ahead": int(parts[0]), "behind": int(parts[1])}
    return {
        "branch": branch,
        "fetched": fetched_rc == 0,
        "fetch_note": None if fetched_rc == 0 else fetch_out[:200],
        **counts,
    }


def submodule_survey() -> list[dict]:
    """git submodule status: '-' uninitialized, '+' drifted from pinned SHA."""
    rc, out = git(["submodule", "status"])
    rows: list[dict] = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        line = line.rstrip()
        if not line:
            continue
        flag = line[0] if line[0] in "-+U" else " "
        body = line[1:].strip() if line[0] in "-+U " else line.strip()
        parts = body.split()
        if len(parts) < 2:
            continue
        rows.append(
            {
                "path": parts[1],
                "sha": parts[0][:12],
                "state": {
                    "-": "uninitialized",
                    "+": "drifted_from_pin",
                    "U": "merge_conflict",
                    " ": "in_sync",
                }[flag],
            }
        )
    return rows


def registry_coverage() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    layers = reg.get("layers") or {}
    integrations = layers.get("integrations") or []
    missing = []
    remote_only = []
    for item in integrations:
        rel = item.get("path") or ""
        if rel.startswith(("http://", "https://", "git@")):
            remote_only.append(item.get("id") or rel)
        elif rel and not (ROOT / rel).exists():
            missing.append(rel)
    return {
        "integrations_registered": len(integrations),
        "remote_only": remote_only,
        "coding_workspaces": len(layers.get("coding_workspaces") or []),
        "missing_paths": missing,
    }


def pull_home() -> dict:
    """Fast-forward only; never merge. Refuses on a dirty tree."""
    rc, out = git(["status", "--porcelain"])
    if rc != 0 or out:
        return {"pulled": False, "reason": "working tree not clean — refusing"}
    rc, out = git(["pull", "--ff-only", "origin", "main"], timeout=120)
    if rc != 0:
        return {"pulled": False, "reason": out[:200]}
    rc2, out2 = git(["submodule", "update", "--init", "--recursive"], timeout=600)
    return {
        "pulled": True,
        "detail": out[:200],
        "submodules_synced": rc2 == 0,
        "submodule_note": None if rc2 == 0 else out2[:200],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-sync home with all projects/repos")
    ap.add_argument("--json", action="store_true", help="print JSON report")
    ap.add_argument("--write", action="store_true", help="write mesh distillate")
    ap.add_argument(
        "--pull",
        action="store_true",
        help="ff-only pull home + re-pin submodules (never merges)",
    )
    ap.add_argument("--fetch-timeout", type=int, default=20)
    args = ap.parse_args()

    report = {
        "at": utc(),
        "mode": "pull" if args.pull else "report",
        "policy": {"report_first": True, "never_auto_merge": True},
        "home": home_drift(args.fetch_timeout),
        "submodules": submodule_survey(),
        "registry": registry_coverage(),
    }
    if args.pull:
        report["pull"] = pull_home()

    attention = [s for s in report["submodules"] if s["state"] != "in_sync"]
    report["ok"] = not report["registry"]["missing_paths"]
    report["needs_attention"] = len(attention)

    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        report["distillate"] = str(OUT.relative_to(ROOT))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        h = report["home"]
        drift = (
            f"ahead {h['ahead']} / behind {h['behind']}"
            if h["fetched"]
            else "offline (no fetch)"
        )
        print(f"auto-sync [{report['mode']}]: home {h['branch']} — {drift}")
        print(
            f"submodules: {len(report['submodules'])} tracked · "
            f"{report['needs_attention']} need attention"
        )
        for s in attention:
            print(f"  ! {s['path']} — {s['state']}")
        reg = report["registry"]
        print(
            f"registry: {reg['integrations_registered']} integrations · "
            f"{reg['coding_workspaces']} coding workspaces"
        )
        for m in reg["missing_paths"]:
            print(f"  FAIL: registered path missing {m}")
        if args.pull:
            print(f"pull: {report['pull']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
