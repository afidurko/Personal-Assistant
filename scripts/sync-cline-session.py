#!/usr/bin/env python3
"""Bridge Cline session distillates ↔ mesh/cline (cross-workspace coding memory)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "identity" / "persistence" / "cline-session-cache.json"
MESH_KEY = "mesh/cline"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _scrub(data: dict) -> dict:
    """Distillates are tracked in git — strip personal information before they land."""
    try:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        import privacy

        return privacy.scrub_obj(data)
    except Exception:  # noqa: BLE001
        return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_scrub(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_payload(state: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    try:
        import cam_workspaces as cw

        registry_ws = cw.mesh_cline_workspaces_doc().get("workspaces") or []
    except Exception:  # noqa: BLE001
        registry_ws = state.get("workspaces", [])
    return {
        MESH_KEY: {
            "effector": "cline",
            "submodule": "integrations/cline",
            "source": "https://github.com/afidurko/cline",
            "rules": ".clinerules",
            "available_to": "all_roles_and_subagents",
            "cross_workspace": True,
            "last_export_at": now,
            "workspaces": registry_ws or state.get("workspaces", []),
            "last_session": state.get("last_session"),
            "schedules": state.get("schedules", []),
            "notes": state.get("notes", []),
            "registry": "config/workspaces/registry.json",
            "runner": "scripts/run-cline.py",
        }
    }


def cmd_export(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state) if args.state else DEFAULT_STATE)
    payload = export_payload(state)
    if args.out:
        out = Path(args.out)
        write_json(out, payload)
        print(f"wrote {out}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    src = Path(args.from_path)
    incoming = load_json(src)
    block = incoming.get(MESH_KEY, incoming)
    state_path = Path(args.state) if args.state else DEFAULT_STATE
    current = load_json(state_path)

    merged = {
        "workspaces": _uniq_list(
            current.get("workspaces", []) + block.get("workspaces", [])
        ),
        "schedules": _uniq_list(
            current.get("schedules", []) + block.get("schedules", [])
        ),
        "notes": _uniq_list(current.get("notes", []) + block.get("notes", [])),
        "last_session": block.get("last_session") or current.get("last_session"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.dry_run:
        print(json.dumps({MESH_KEY: merged}, indent=2, sort_keys=True))
        print("dry-run: no files written")
        return 0

    write_json(state_path, merged)
    print(f"updated {state_path}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    state_path = Path(args.state) if args.state else DEFAULT_STATE
    state = load_json(state_path)
    workspaces = state.setdefault("workspaces", [])
    if args.workspace and args.workspace not in workspaces:
        workspaces.append(args.workspace)
    state["last_session"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "workspace": args.workspace,
        "mode": args.mode,
        "summary": args.summary,
    }
    if args.note:
        state.setdefault("notes", []).append(
            {
                "at": state["last_session"]["at"],
                "text": args.note,
                "workspace": args.workspace,
            }
        )
    write_json(state_path, state)
    print(f"recorded session → {state_path}")
    return 0


def _uniq_list(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        help="local Cline session cache path (default: identity/persistence/cline-session-cache.json)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_export = sub.add_parser("export", help="print or write mesh/cline document")
    p_export.add_argument("--out", help="write JSON to path instead of stdout")
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser("import", help="merge a mesh/cline dump into local cache")
    p_import.add_argument("--from", dest="from_path", required=True)
    p_import.add_argument("--dry-run", action="store_true")
    p_import.set_defaults(func=cmd_import)

    p_record = sub.add_parser("record", help="append a local session distillate")
    p_record.add_argument("--workspace", required=True, help="absolute or repo-relative path")
    p_record.add_argument("--mode", default="act", choices=["plan", "act", "headless", "team"])
    p_record.add_argument("--summary", default="", help="short distillate")
    p_record.add_argument("--note", default="", help="optional mesh note")
    p_record.set_defaults(func=cmd_record)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
