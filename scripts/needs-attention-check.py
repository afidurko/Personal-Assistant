#!/usr/bin/env python3
"""Validate Needs Attention team + script + registry wiring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ROOT / "config/teams/needs-attention.json",
    ROOT / "scripts/needs-attention.py",
    ROOT / "server/workspaces/needs-attention.ts",
]


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.exists():
            errors.append(f"missing:{path.relative_to(ROOT)}")

    team_path = ROOT / "config/teams/needs-attention.json"
    if team_path.exists():
        team = json.loads(team_path.read_text(encoding="utf-8"))
        if team.get("id") != "team.needs-attention":
            errors.append("team_id_mismatch")
        if not team.get("cross_workspace"):
            errors.append("cross_workspace_false")
        if not team.get("all_coding_workspaces"):
            errors.append("all_coding_workspaces_false")
        roles = {m.get("role") for m in team.get("members") or []}
        for need in (
            "attention-triage",
            "workspace-connector",
            "attention-dispatcher",
            "aaron-escalator",
        ):
            if need not in roles:
                errors.append(f"missing_role:{need}")

    reg_path = ROOT / "config/workspaces/registry.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    teams = (reg.get("layers") or {}).get("agent_teams") or []
    if not any(t.get("id") == "team.needs-attention" for t in teams):
        errors.append("registry_missing_team.needs-attention")
    scans = (reg.get("layers") or {}).get("scan_workspaces") or []
    if not any(s.get("id") == "scan.needs_attention" for s in scans):
        errors.append("registry_missing_scan.needs_attention")

    types = (ROOT / "shared/types.ts").read_text(encoding="utf-8")
    if "needs_attention" not in types:
        errors.append("shared_types_missing_needs_attention")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True, "errors": []}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
