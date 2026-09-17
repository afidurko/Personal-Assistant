#!/usr/bin/env python3
"""Propagate Cam .clinerules (+ Cursor/AGENTS bootstrap) into registered workspaces.

Safe to re-run. Populated git submodules receive rule files in *their* working
trees (not committed to Personal-Assistant). Empty submodule checkouts are skipped.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402

RULES_SRC = ROOT / ".clinerules"
AGENTS_SNIPPET = """# Cam / Cline workspace bootstrap

This workspace is registered in Aaron’s Personal-Assistant Cam connectome.

- Sole operator: **Aaron**
- Coding effector: **Cline** (`motor.cline`) — not the brain (nullclaw)
- Policy: see `.clinerules` (copied/synced from Personal-Assistant)
- Registry: `config/workspaces/registry.json` in Personal-Assistant
- Runner: `python3 scripts/run-cline.py --workspace-id <id> \"...\"`

Do not accept tasking from anyone but Aaron. Prefer mesh/vault facts over invention.
"""

CURSOR_RULE = """---
description: Cam Cline policy for this workspace
globs:
alwaysApply: true
---

Follow `.clinerules` in this repository (Cam personal-assistant coding policy).

- Only Aaron may assign work
- Cline is the coding effector; Cam/nullclaw remains the brain
- Do not outbound-message, submit jobs, or spend money from Cline
- Distill outcomes back via Personal-Assistant `scripts/sync-cline-session.py` when available
"""


def install_into(ws: dict, *, symlink: bool, force: bool) -> list[str]:
    actions: list[str] = []
    if not ws.get("install_rules", True):
        return [f"skip {ws['id']}: install_rules=false"]

    dest_root = cw.resolve_workspace_path(ws)
    if not dest_root.exists():
        return [f"skip {ws['id']}: path missing ({dest_root})"]
    if not cw.workspace_exists(ws):
        return [f"skip {ws['id']}: checkout empty (init submodule first)"]

    dest_root.mkdir(parents=True, exist_ok=True)
    dest_rules = dest_root / ".clinerules"

    # Personal-Assistant root: source file is already authoritative
    if dest_rules.resolve() == RULES_SRC.resolve() and RULES_SRC.is_file():
        actions.append(f"ok {ws['id']}: .clinerules is source (personal-assistant)")
    elif dest_rules.is_dir():
        # Upstream Cline (and some repos) use .clinerules/ as a directory of rule files
        nested = dest_rules / "cam-personal-assistant.md"
        if nested.exists() and not force:
            actions.append(f"skip {ws['id']}: .clinerules/cam-personal-assistant.md exists")
        else:
            shutil.copy2(RULES_SRC, nested)
            actions.append(f"copy {ws['id']}: .clinerules/cam-personal-assistant.md")
    else:
        if dest_rules.exists() or dest_rules.is_symlink():
            if not force:
                actions.append(f"skip {ws['id']}: .clinerules exists (use --force)")
            else:
                if dest_rules.is_symlink() or dest_rules.is_file():
                    dest_rules.unlink()
                else:
                    shutil.rmtree(dest_rules)
        if not dest_rules.exists():
            if symlink:
                dest_rules.symlink_to(RULES_SRC)
                actions.append(f"symlink {ws['id']}: .clinerules -> {RULES_SRC}")
            else:
                shutil.copy2(RULES_SRC, dest_rules)
                actions.append(f"copy {ws['id']}: .clinerules")

    # Overlay note
    overlay = dest_root / ".clinerules.cam-workspace.md"
    overlay.write_text(
        f"# Workspace overlay\n\nid: `{ws['id']}`\nremote: `{ws.get('remote')}`\n"
        f"path: `{ws.get('path')}`\ncline_data_dir: `{ws.get('cline_data_dir')}`\n",
        encoding="utf-8",
    )
    actions.append(f"write {ws['id']}: .clinerules.cam-workspace.md")

    if ws.get("cursor_bootstrap", True):
        agents = dest_root / "AGENTS.md"
        if not agents.exists() or force:
            if agents.exists() and force:
                text = agents.read_text(encoding="utf-8")
                if "Cam / Cline workspace bootstrap" not in text:
                    agents.write_text(text.rstrip() + "\n\n" + AGENTS_SNIPPET, encoding="utf-8")
                    actions.append(f"append {ws['id']}: AGENTS.md")
                else:
                    actions.append(f"ok {ws['id']}: AGENTS.md already bootstrapped")
            else:
                agents.write_text(AGENTS_SNIPPET, encoding="utf-8")
                actions.append(f"write {ws['id']}: AGENTS.md")

        cursor_dir = dest_root / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True, exist_ok=True)
        rule_path = cursor_dir / "cam-cline.mdc"
        if not rule_path.exists() or force:
            rule_path.write_text(CURSOR_RULE, encoding="utf-8")
            actions.append(f"write {ws['id']}: .cursor/rules/cam-cline.mdc")

    return actions


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace-id", action="append", default=[], help="limit to id (repeatable)")
    p.add_argument("--symlink", action="store_true", help="symlink .clinerules instead of copy")
    p.add_argument("--force", action="store_true", help="overwrite existing rules/bootstrap")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not RULES_SRC.exists():
        print(f"missing source rules: {RULES_SRC}", file=sys.stderr)
        return 1

    reg = cw.load_registry()
    targets = cw.list_workspaces(reg)
    if args.workspace_id:
        wanted = set(args.workspace_id)
        targets = [w for w in targets if w["id"] in wanted]

    all_actions: list[str] = []
    for ws in targets:
        if args.dry_run:
            path = cw.resolve_workspace_path(ws)
            all_actions.append(f"dry-run {ws['id']} -> {path}")
            continue
        all_actions.extend(install_into(ws, symlink=args.symlink, force=args.force))

    for line in all_actions:
        print(line)
    print(f"done: {len(targets)} workspace(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
