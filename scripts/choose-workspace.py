#!/usr/bin/env python3
"""CLI for Cam workspace chooser (task-type → registry workspace)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goal", default="", help="Aaron goal / task text")
    p.add_argument("--workspace-id", help="force registry id")
    p.add_argument("--path", help="force filesystem path")
    p.add_argument("--role", default=None, help="Cam role for allowlist filter")
    p.add_argument("--list", action="store_true", help="list registry + existence")
    p.add_argument("--mesh-projects", action="store_true", help="emit mesh/projects doc")
    p.add_argument("--mesh-cline", action="store_true", help="emit mesh/cline workspaces doc")
    args = p.parse_args()

    if args.list:
        print(json.dumps(cw.mesh_projects_doc(), indent=2, sort_keys=True))
        return 0
    if args.mesh_projects:
        print(json.dumps(cw.mesh_projects_doc(), indent=2, sort_keys=True))
        return 0
    if args.mesh_cline:
        print(json.dumps(cw.mesh_cline_workspaces_doc(), indent=2, sort_keys=True))
        return 0

    choice = cw.choose_workspace(
        goal=args.goal,
        workspace_id=args.workspace_id,
        explicit_path=args.path,
        role=args.role,
    )
    print(json.dumps(choice, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
