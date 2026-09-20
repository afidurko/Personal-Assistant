#!/usr/bin/env python3
"""Cam Needs Attention triage across all coding workspaces.

Surveys registry connectivity, ranks attention items, and emits a dispatch plan
(choose-workspace targets). Does not outbound-message, spend money, or apply
Cam enhance — those stay Aaron-gated.

Examples:
  python3 scripts/needs-attention.py --json
  python3 scripts/needs-attention.py --connect
  python3 scripts/needs-attention.py --dispatch-plan --limit 12
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402

TEAM_PATH = ROOT / "config" / "teams" / "needs-attention.json"
OUT_DEFAULT = ROOT / "vault" / "10-Mesh-Distillates" / "needs-attention" / "latest.json"
MESH_NS = "mesh/needs-attention"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_team() -> dict[str, Any]:
    if not TEAM_PATH.exists():
        return {}
    return json.loads(TEAM_PATH.read_text(encoding="utf-8"))


def survey_workspaces() -> list[dict[str, Any]]:
    """Prefer the flat registry workspaces list (complete), else coding_workspaces."""
    raw = cw.load_json(cw.REGISTRY_PATH)
    full = raw.get("workspaces") or cw.list_workspaces()
    rows: list[dict[str, Any]] = []
    for ws in full:
        exists = cw.workspace_exists(ws)
        path = str(cw.resolve_workspace_path(ws))
        rows.append(
            {
                "id": ws["id"],
                "label": ws.get("label") or ws["id"],
                "path": ws.get("path"),
                "abs_path": path,
                "remote": ws.get("remote"),
                "connected": exists,
                "primary": bool(ws.get("primary")),
                "roles_allowed": ws.get("roles_allowed") or [],
                "attention": (
                    "ok"
                    if exists
                    else ("empty_or_missing" if Path(path).exists() else "missing_path")
                ),
            }
        )
    return rows


def build_attention_items(rows: list[dict[str, Any]], team: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not team.get("id"):
        items.append(
            {
                "id": "team-missing",
                "kind": "wiring",
                "severity": "critical",
                "title": "Needs Attention team missing",
                "detail": str(TEAM_PATH),
                "auto_clearable": False,
                "aaron_gate": True,
                "workspace_id": "personal-assistant",
            }
        )

    for row in rows:
        if row["connected"]:
            continue
        items.append(
            {
                "id": f"ws-{row['id']}",
                "kind": "connectivity",
                "severity": "high" if row.get("primary") else "medium",
                "title": f"Connect coding workspace: {row['id']}",
                "detail": f"{row['label']} @ {row['path']} ({row['attention']})",
                "auto_clearable": False,
                "aaron_gate": False,
                "workspace_id": row["id"],
                "remote": row.get("remote"),
                "suggestion": (
                    f"git submodule update --init --recursive {row['path']}"
                    if row.get("path") not in (None, ".")
                    else "Restore primary Personal-Assistant checkout"
                ),
            }
        )

    # Standing Aaron-gated reminders (never auto-clear)
    items.append(
        {
            "id": "gate-enhance",
            "kind": "policy",
            "severity": "info",
            "title": "Cam enhance remains Aaron-gated",
            "detail": "switch.cam_enhance — attention agents may propose, not apply.",
            "auto_clearable": False,
            "aaron_gate": True,
            "workspace_id": "personal-assistant",
        }
    )
    items.append(
        {
            "id": "gate-outbound",
            "kind": "policy",
            "severity": "info",
            "title": "Outbound Inkbox remains gated",
            "detail": "switch.outbound — never free-send from Cline attention sweeps.",
            "auto_clearable": False,
            "aaron_gate": True,
            "workspace_id": "inkbox",
        }
    )
    return items


def dispatch_plan(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in items:
        if item.get("aaron_gate") and item.get("severity") == "info":
            continue
        goal = item.get("title") or item.get("id")
        choice = cw.choose_workspace(goal=str(goal), workspace_id=item.get("workspace_id"))
        plan.append(
            {
                "item_id": item["id"],
                "title": item["title"],
                "severity": item["severity"],
                "auto_clearable": bool(item.get("auto_clearable")),
                "aaron_gate": bool(item.get("aaron_gate")),
                "target_workspace": choice.get("workspace_id") or item.get("workspace_id"),
                "target_path": choice.get("path"),
                "runner": "scripts/run-cline.py",
                "hint": item.get("suggestion"),
            }
        )
        if len(plan) >= limit:
            break
    return plan


def write_distillate(doc: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Mirror into cline session cache mesh namespace lightly
    cache = cw.load_json(cw.CLINE_CACHE)
    notes = cache.setdefault("mesh_notes", [])
    if not isinstance(notes, list):
        notes = []
        cache["mesh_notes"] = notes
    notes.append(
        {
            "at": utc_now(),
            "namespace": MESH_NS,
            "note": (
                f"needs-attention: connected={doc.get('connected')}/"
                f"{doc.get('coding_workspace_count')} "
                f"queue={doc.get('queue_depth')}"
            ),
        }
    )
    # keep last 40
    cache["mesh_notes"] = notes[-40:]
    cw.write_json(cw.CLINE_CACHE, cache)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="print full JSON report")
    p.add_argument("--connect", action="store_true", help="list connectivity for all coding workspaces")
    p.add_argument("--dispatch-plan", action="store_true", help="emit choose-workspace dispatch plan")
    p.add_argument("--limit", type=int, default=12, help="max dispatch plan rows")
    p.add_argument("--write", action="store_true", help=f"write distillate to {OUT_DEFAULT}")
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args()

    team = load_team()
    rows = survey_workspaces()
    items = build_attention_items(rows, team)
    connected = sum(1 for r in rows if r["connected"])
    queue = [i for i in items if i.get("severity") not in ("info",)]
    plan = dispatch_plan(items, limit=args.limit) if args.dispatch_plan or args.json or args.write else []

    doc: dict[str, Any] = {
        "at": utc_now(),
        "team": team.get("id"),
        "cross_workspace": bool(team.get("cross_workspace")),
        "coding_workspace_count": len(rows),
        "connected": connected,
        "disconnected": len(rows) - connected,
        "queue_depth": len(queue),
        "workspaces": rows,
        "attention_items": items,
        "dispatch_plan": plan,
        "ok": bool(team.get("id")) and connected == len(rows),
    }

    if args.write:
        write_distillate(doc, args.out)
        doc["wrote"] = str(args.out)

    if args.connect and not args.json:
        for r in rows:
            mark = "OK" if r["connected"] else "NEED"
            print(f"{mark:4}  {r['id']:24}  {r['path']}")
        print(f"connected {connected}/{len(rows)}")
        return 0 if connected == len(rows) else 1

    if args.dispatch_plan and not args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    if args.json or args.write or not (args.connect or args.dispatch_plan):
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 0 if doc["ok"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
