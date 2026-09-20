#!/usr/bin/env python3
"""Cam Needs Attention triage + auto-clear across all coding workspaces.

Surveys registry connectivity, ranks attention items, emits a dispatch plan,
and can **execute** workspace-connector work (submodule init) for auto-clearable
items. Does not outbound-message, spend money, merge PRs, or apply Cam enhance
— those stay Aaron-gated.

Examples:
  python3 scripts/needs-attention.py --json
  python3 scripts/needs-attention.py --connect
  python3 scripts/needs-attention.py --dispatch-plan --limit 12
  python3 scripts/needs-attention.py --execute --write
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402

TEAM_PATH = ROOT / "config" / "teams" / "needs-attention.json"
SUGGESTIONS_PATH = ROOT / "vault" / "00-Inbox" / "home-suggestions.jsonl"
OUT_DEFAULT = ROOT / "vault" / "10-Mesh-Distillates" / "needs-attention" / "latest.json"
MESH_NS = "mesh/needs-attention"
COMPLETED_DEFAULT = (
    ROOT / "vault" / "10-Mesh-Distillates" / "needs-attention" / "completed.jsonl"
)


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

    # Aaron's Home Live suggestions surface first — they outrank plumbing
    if SUGGESTIONS_PATH.exists():
        for line in SUGGESTIONS_PATH.read_text(encoding="utf-8").splitlines():
            try:
                sug = json.loads(line)
            except Exception:
                continue
            if sug.get("status") != "queued":
                continue
            items.append(
                {
                    "id": f"suggestion-{sug.get('id')}",
                    "kind": "suggestion",
                    "severity": "high",
                    "title": f"Aaron suggestion: {str(sug.get('text', ''))[:80]}",
                    "detail": f"queued {sug.get('at')} via Cam Home Live",
                    "auto_clearable": False,
                    "aaron_gate": False,
                    "workspace_id": "personal-assistant",
                    "suggestion": "triage into a ticket; report back on the home queue",
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
                "auto_clearable": True,
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

    # Open draft/ready PRs — surface for dispatcher (never auto-merge)
    for pr in scan_open_prs():
        items.append(pr)
    return items


def scan_open_prs() -> list[dict[str, Any]]:
    """List open PRs that need attention (draft / no checks / conflicts). Never merges."""
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                "30",
                "--json",
                "number,title,url,isDraft,mergeable,headRefName,statusCheckRollup",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return [
            {
                "id": "pr-scan-unavailable",
                "kind": "wiring",
                "severity": "low",
                "title": "PR attention scan unavailable",
                "detail": str(exc),
                "auto_clearable": False,
                "aaron_gate": False,
                "workspace_id": "personal-assistant",
            }
        ]
    if proc.returncode != 0:
        return []
    try:
        prs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    items: list[dict[str, Any]] = []
    for pr in prs:
        checks = pr.get("statusCheckRollup") or []
        fails = [
            c.get("name") or c.get("context")
            for c in checks
            if (c.get("conclusion") or "") in {"FAILURE", "CANCELLED"}
        ]
        severity = "medium"
        if pr.get("mergeable") == "CONFLICTING" or fails:
            severity = "high"
        elif pr.get("isDraft"):
            severity = "low"
        items.append(
            {
                "id": f"pr-{pr['number']}",
                "kind": "pr",
                "severity": severity,
                "title": f"Open PR #{pr['number']}: {pr.get('title')}",
                "detail": (
                    f"{pr.get('url')} draft={pr.get('isDraft')} "
                    f"mergeable={pr.get('mergeable')} fails={fails or 'none'}"
                ),
                "auto_clearable": False,  # never auto-merge
                "aaron_gate": True if pr.get("mergeable") == "MERGEABLE" and not pr.get("isDraft") else False,
                "workspace_id": "personal-assistant",
                "suggestion": "Progress on branch; do not merge unless Aaron asks",
                "pr_number": pr.get("number"),
                "head_ref": pr.get("headRefName"),
            }
        )
    return items


def dispatch_plan(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in items:
        if item.get("aaron_gate") and item.get("severity") == "info":
            continue
        # Connectivity items are auto-executable via submodule init
        if item.get("kind") == "connectivity":
            item = {**item, "auto_clearable": True}
        goal = item.get("title") or item.get("id")
        ws_id = item.get("workspace_id")
        try:
            choice = cw.choose_workspace(goal=str(goal), workspace_id=ws_id)
        except KeyError:
            # Flat registry may list integrations not yet in coding_workspaces
            choice = {
                "workspace": {"id": ws_id, "path": item.get("detail")},
                "path": None,
            }
        ws = choice.get("workspace") or {}
        plan.append(
            {
                "item_id": item["id"],
                "title": item["title"],
                "severity": item["severity"],
                "kind": item.get("kind"),
                "auto_clearable": bool(item.get("auto_clearable")),
                "aaron_gate": bool(item.get("aaron_gate")),
                "target_workspace": ws.get("id") or ws_id,
                "target_path": choice.get("path") or ws.get("path"),
                "runner": "scripts/run-cline.py",
                "hint": item.get("suggestion"),
            }
        )
        if len(plan) >= limit:
            break
    return plan


def _submodule_init(rel_path: str) -> dict[str, Any]:
    """Init/update one submodule path. Never touches secrets or outbound."""
    path = ROOT / rel_path
    if path.exists() and any(p.name != ".git" for p in path.iterdir()) if path.is_dir() else False:
        return {"ok": True, "action": "already_connected", "path": rel_path}
    cmd = ["git", "submodule", "update", "--init", "--recursive", "--", rel_path]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    connected = path.exists() and (
        path.is_file()
        or (path.is_dir() and any(p.name != ".git" for p in path.iterdir()))
    )
    return {
        "ok": proc.returncode == 0 and connected,
        "action": "submodule_init",
        "path": rel_path,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-1500:],
        "stderr": (proc.stderr or "")[-1500:],
        "connected": connected,
    }


def execute_plan(plan: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Workspace-connector + attention-dispatcher: clear auto-clearable items."""
    by_id = {r["id"]: r for r in rows}
    completed: list[dict[str, Any]] = []
    for step in plan:
        if step.get("aaron_gate") and not step.get("auto_clearable"):
            completed.append({**step, "status": "escalated_aaron", "executed": False})
            continue
        if step.get("kind") != "connectivity" and not step.get("auto_clearable"):
            completed.append({**step, "status": "skipped_not_auto", "executed": False})
            continue
        ws_id = step.get("target_workspace")
        row = by_id.get(ws_id) or {}
        rel = row.get("path") or ""
        if not rel or rel in {".", ""}:
            completed.append({**step, "status": "skipped_primary", "executed": False})
            continue
        result = _submodule_init(str(rel))
        completed.append(
            {
                **step,
                "status": "cleared" if result.get("ok") else "failed",
                "executed": True,
                "result": result,
            }
        )
    return completed


def append_completed(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"at": utc_now(), **row}, sort_keys=True) + "\n")


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
    p.add_argument(
        "--execute",
        action="store_true",
        help="run workspace-connector: init submodules for auto-clearable connectivity items",
    )
    p.add_argument("--limit", type=int, default=50, help="max dispatch plan rows")
    p.add_argument("--write", action="store_true", help=f"write distillate to {OUT_DEFAULT}")
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args()

    team = load_team()
    rows = survey_workspaces()
    items = build_attention_items(rows, team)
    connected = sum(1 for r in rows if r["connected"])
    queue = [i for i in items if i.get("severity") not in ("info",)]
    want_plan = args.dispatch_plan or args.json or args.write or args.execute
    plan = dispatch_plan(items, limit=args.limit) if want_plan else []

    executed: list[dict[str, Any]] = []
    if args.execute:
        executed = execute_plan(plan, rows)
        append_completed(COMPLETED_DEFAULT, executed)
        # Re-survey after connector work
        rows = survey_workspaces()
        items = build_attention_items(rows, team)
        connected = sum(1 for r in rows if r["connected"])
        queue = [i for i in items if i.get("severity") not in ("info",)]
        plan = dispatch_plan(items, limit=args.limit)

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
        "executed": executed,
        "cleared": sum(1 for e in executed if e.get("status") == "cleared"),
        "failed": sum(1 for e in executed if e.get("status") == "failed"),
        "ok": bool(team.get("id")) and connected == len(rows),
    }

    if args.write:
        write_distillate(doc, args.out)
        doc["wrote"] = str(args.out)

    if args.connect and not args.json and not args.execute:
        for r in rows:
            mark = "OK" if r["connected"] else "NEED"
            print(f"{mark:4}  {r['id']:24}  {r['path']}")
        print(f"connected {connected}/{len(rows)}")
        return 0 if connected == len(rows) else 1

    if args.dispatch_plan and not args.json and not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    if args.json or args.write or args.execute or not (args.connect or args.dispatch_plan):
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 0 if doc["ok"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
