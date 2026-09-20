#!/usr/bin/env python3
"""Cam loop runner — L1 report automations from loop-engineering patterns.

Default week-one mode: report-only (no auto-fix / no auto-merge).
Updates STATE.md + loop-run-log.md and mirrors to mesh/loops.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ROOT / "config/loops/patterns.json"
STATE = ROOT / "STATE.md"
RUN_LOG = ROOT / "loop-run-log.md"
MESH_OUT = ROOT / "identity/persistence/loop-mesh-latest.json"
VAULT_OUT = ROOT / "vault/10-Mesh-Distillates/loop-runs/latest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def state_paused() -> bool:
    if not STATE.exists():
        return False
    text = STATE.read_text(encoding="utf-8")
    return bool(re.search(r"(?im)^\s*-\s*paused:\s*true\b", text))


def run_py(script: str, args: list[str] | None = None) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / script), *(args or [])]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    payload: dict[str, Any] = {
        "script": script,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-1000:],
    }
    try:
        payload["json"] = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        payload["json"] = None
    return payload


def loop_audit_score() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/loop-audit.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    try:
        doc = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        doc = {"ok": False, "output": (proc.stdout or "")[:2000]}
    doc["exit_code"] = proc.returncode
    score = None
    m = re.search(r"(?i)(?:score|readiness)[^\d]{0,20}(\d{1,3})", doc.get("output") or "")
    if m:
        score = int(m.group(1))
    doc["parsed_score"] = score
    return doc


def update_state(pattern: str, level: str, status: str, score: Any, notes: str) -> None:
    now = utc_now()
    body = STATE.read_text(encoding="utf-8") if STATE.exists() else "# STATE.md\n"

    def set_bullet(text: str, key: str, value: str) -> str:
        pat = re.compile(rf"(?im)^(\s*-\s*{re.escape(key)}:\s*).*$")
        if pat.search(text):
            return pat.sub(rf"\g<1>{value}", text, count=1)
        return text

    body = set_bullet(body, "last_run", now)
    body = set_bullet(body, "last_pattern", pattern)
    body = set_bullet(body, "last_score", str(score if score is not None else "—"))
    done_line = f"- {now} · `{pattern}` @ {level} → {status}" + (f" — {notes}" if notes else "")
    if "## Done recently" in body:
        body = body.replace(
            "## Done recently\n",
            f"## Done recently\n\n{done_line}\n",
            1,
        )
    STATE.write_text(body, encoding="utf-8")


def append_run_log(pattern: str, level: str, status: str, score: Any, notes: str) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not RUN_LOG.exists():
        RUN_LOG.write_text(
            "# loop-run-log.md\n\n| When (UTC) | Pattern | Level | Status | Score | Notes |\n|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    score_s = "—" if score is None else str(score)
    notes_s = (notes or "").replace("|", "/").replace("\n", " ")
    line = f"| {utc_now()} | `{pattern}` | {level} | {status} | {score_s} | {notes_s} |\n"
    text = RUN_LOG.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    RUN_LOG.write_text(text + line, encoding="utf-8")


def pack_mesh(record: dict) -> Path:
    MESH_OUT.parent.mkdir(parents=True, exist_ok=True)
    VAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "namespace": "mesh/loops",
        "kind": "loop_run",
        "at": utc_now(),
        "source": "scripts/loop-run.py",
        **record,
    }
    MESH_OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    VAULT_OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return MESH_OUT


def action_connectome_check() -> dict:
    return run_py("scripts/connectome-check.py", ["--json"])


def action_system_health() -> dict:
    return run_py("scripts/system-health-scan.py", ["--json"])


def action_bridge_qa_status() -> dict:
    mesh = ROOT / "identity/persistence/qa-mesh-latest.json"
    if mesh.exists():
        try:
            return {"ok": True, "qa_mesh": json.loads(mesh.read_text(encoding="utf-8"))}
        except json.JSONDecodeError:
            return {"ok": False, "error": "qa-mesh-latest.json parse error"}
    return {"ok": True, "qa_mesh": None, "notes": "no qa mesh yet"}


def action_scan_findings() -> dict:
    base = ROOT / "vault/10-Mesh-Distillates/qa-cycles"
    suggestions = sorted(base.glob("*/suggestions.md")) if base.exists() else []
    latest = suggestions[-1] if suggestions else None
    preview = ""
    if latest:
        preview = "\n".join(latest.read_text(encoding="utf-8").splitlines()[:40])
    return {
        "ok": True,
        "latest_suggestions": str(latest.relative_to(ROOT)) if latest else None,
        "preview": preview,
    }


def action_scan_recent_merges() -> dict:
    proc = subprocess.run(
        ["git", "log", "--oneline", "-15", "origin/main"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "ok": proc.returncode == 0,
        "recent_commits": (proc.stdout or "").strip().splitlines(),
        "stderr": (proc.stderr or "")[:500],
    }


def action_instinct_sync() -> dict:
    """Fold inbox event drops (run-cline, senses) + the Needs Attention queue
    from all coding workspaces into the follow-through ledger."""
    return {
        "inbox": run_py("scripts/instinct.py", ["sync"]),
        "attention": run_py("scripts/instinct.py", ["attention-sync"]),
    }


def action_instinct_scan() -> dict:
    """Draft-only follow-through scan (motor.instinct); never sends."""
    return run_py("scripts/instinct.py", ["scan", "--write"])


def action_instinct_distill() -> dict:
    """Sanitized per-workspace mesh distillate (counts only)."""
    return run_py("scripts/instinct.py", ["distill"])


def action_list_open_prs_report() -> dict:
    proc = subprocess.run(
        ["gh", "pr", "list", "--limit", "10", "--json", "number,title,url,isDraft"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {
            "ok": True,
            "prs": [],
            "soft": True,
            "notes": (proc.stderr or proc.stdout or "gh unavailable")[:400],
        }
    try:
        prs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        prs = []
    return {"ok": True, "prs": prs}


def run_pattern(pattern: dict, level: str, dry_run: bool) -> dict:
    pid = pattern["id"]
    actions = pattern.get("actions") or []
    results: dict[str, Any] = {}
    score = None

    if dry_run:
        return {
            "pattern": pid,
            "level": level,
            "status": "dry_run",
            "actions": actions,
            "score": None,
        }

    for act in actions:
        if act == "connectome_check":
            results[act] = action_connectome_check()
        elif act == "system_health":
            results[act] = action_system_health()
        elif act == "loop_audit":
            results[act] = loop_audit_score()
            score = results[act].get("parsed_score")
        elif act == "bridge_qa_status":
            results[act] = action_bridge_qa_status()
        elif act in {"scan_findings", "propose_only", "suggest_cleanup"}:
            results[act] = action_scan_findings()
        elif act == "scan_recent_merges":
            results[act] = action_scan_recent_merges()
        elif act == "list_open_prs_report":
            results[act] = action_list_open_prs_report()
        elif act == "instinct_sync":
            results[act] = action_instinct_sync()
        elif act == "instinct_scan":
            results[act] = action_instinct_scan()
        elif act == "instinct_distill":
            results[act] = action_instinct_distill()
        elif act in {"update_state", "append_run_log", "pack_mesh"}:
            continue
        else:
            results[act] = {"ok": False, "error": f"unknown action {act}"}

    status = "ok"
    notes = f"actions={len(results)}"

    if "update_state" in actions:
        update_state(pid, level, status, score, notes)
    if "append_run_log" in actions:
        append_run_log(pid, level, status, score, notes)

    record = {
        "pattern": pid,
        "level": level,
        "status": status,
        "score": score,
        "notes": notes,
        "results": results,
        "human_gates": pattern.get("human_gates") or [],
        "auto_fix": False,
        "auto_merge": False,
    }
    if "pack_mesh" in actions:
        pack_mesh(record)
        record["mesh"] = str(MESH_OUT.relative_to(ROOT))
    return record


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pattern", help="pattern id from config/loops/patterns.json")
    p.add_argument("--level", default="", help="override level (default pattern/week-one)")
    p.add_argument("--list", action="store_true", help="list patterns")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true", help="print JSON result (always on)")
    args = p.parse_args()

    if state_paused() and not args.list:
        doc = {"ok": True, "status": "paused", "reason": "STATE.md paused: true"}
        print(json.dumps(doc, indent=2))
        return 0

    catalog = load_json(PATTERNS)
    patterns = catalog.get("patterns") or []
    if args.list:
        rows = [
            {
                "id": x.get("id"),
                "enabled": x.get("enabled"),
                "level": x.get("level"),
                "cadence": x.get("cadence"),
            }
            for x in patterns
        ]
        print(json.dumps({"patterns": rows}, indent=2))
        return 0

    if not args.pattern:
        p.error("--pattern is required (or use --list)")

    match = next((x for x in patterns if x.get("id") == args.pattern), None)
    if not match:
        print(f"unknown pattern: {args.pattern}", file=sys.stderr)
        return 2
    if not match.get("enabled", True) and not args.dry_run:
        print(
            json.dumps(
                {"ok": False, "error": "pattern disabled", "pattern": args.pattern},
                indent=2,
            )
        )
        return 1

    level = args.level or match.get("level") or catalog.get("week_one_mode") or "L1"
    if level.upper() not in {"L1", "L0"} and not args.dry_run:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "loop-run.py week-one gate: only L0/L1 without Aaron raise",
                    "requested_level": level,
                },
                indent=2,
            )
        )
        return 1

    record = run_pattern(match, level.upper(), args.dry_run)
    record["ok"] = record.get("status") in {"ok", "dry_run"}
    print(json.dumps(record, indent=2))
    return 0 if record.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
