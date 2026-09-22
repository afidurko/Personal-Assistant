#!/usr/bin/env python3
"""Minimal stdio MCP server exposing Cam mesh/vault/connectome to Cline.

Implements a small JSON-RPC MCP subset over stdin/stdout:
  initialize, tools/list, tools/call, ping

Tools:
  list_workspaces, choose_workspace, mesh_search, mesh_put,
  vault_search, memorybear_read, memorybear_write, connectome_route,
  kill_switch_status, ticket_list,
  public_apis_search, public_apis_addon, google_trends_search, google_trends_addon, inkbox_check,
  loop_check, loop_audit, loop_run,
  voicestudio_health, needs_attention,
  instinct_scan, instinct_report, instinct_brief,
  privacy_status, privacy_redact, privacy_audit

Install into Cline (example):
  cline mcp install cam -- python3 /path/to/Personal-Assistant/scripts/cam-mcp-server.py

One process serves one person (config/privacy/charter.json). For another
person Aaron enrolls them once (`cam_privacy.py --aaron principals add <id>`)
and runs a separate server: `CAM_PRINCIPAL=<id> python3 scripts/cam-mcp-server.py`
(or `--principal <id>`). That process sees only the guest tool allowlist and
only that person's own root — never Aaron's data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_privacy as privacy  # noqa: E402
import cam_workspaces as cw  # noqa: E402

SERVER_NAME = "cam-personal-assistant"
SERVER_VERSION = "1.2.0"


def principal() -> str:
    """One server process serves one person (config/privacy/charter.json).
    Set via CAM_PRINCIPAL or `--principal`; the owner is the default."""
    return privacy.current_principal()


def guest_tool_allowlist() -> set[str]:
    return set(privacy.charter()["principals"].get("guest_tools") or [])


def tool_visible(name: str) -> bool:
    return privacy.is_owner(principal()) or name in guest_tool_allowlist()


def _ok(result: Any, req_id: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def tool_defs() -> list[dict]:
    return [t for t in all_tool_defs() if tool_visible(t["name"])]


def all_tool_defs() -> list[dict]:
    return [
        {
            "name": "privacy_status",
            "description": (
                "Which principal this server serves, the privacy charter summary, seal/HMAC state "
                "and known principals (ids only). Read-only; consent grants and adding people are "
                "Aaron-only CLI actions (scripts/cam_privacy.py --aaron)."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "privacy_redact",
            "description": (
                "Redact personal information / preferences / secrets from a text with class tags "
                "([email], [phone], [address], [preference], [secret] …). Use before any text crosses "
                "a boundary (mesh note, third-party draft). Returns counts, never the removed values."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "privacy_audit",
            "description": (
                "Owner-only: scan mesh distillates, the cline cache, git tracking and ledger seals for "
                "personal classes (charter P1/P6/P9). Findings are counts and locations, never values."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_workspaces",
            "description": "List Aaron's registered Cam coding workspaces (paths, remotes, existence).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "choose_workspace",
            "description": "Pick a workspace for a coding goal using Cam registry signals.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "workspace_id": {"type": "string"},
                    "path": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
        },
        {
            "name": "mesh_search",
            "description": "Search local Cam mesh seed + cline session cache by keyword.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
        },
        {
            "name": "mesh_put",
            "description": "Append a distillate note into local mesh/cline session cache (not secrets).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "note": {"type": "string"},
                    "workspace": {"type": "string"},
                    "namespace": {"type": "string"},
                },
                "required": ["note"],
            },
        },
        {
            "name": "vault_search",
            "description": "Keyword search over Personal-Assistant vault markdown notes.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
        },
        {
            "name": "memorybear_read",
            "description": "Recall via MemoryBear cognitive memory (offline fixture or live API).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "offline": {"type": "boolean"},
                    "search_switch": {
                        "type": "string",
                        "enum": ["deep", "normal", "quick", "express", "meta"],
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "memorybear_write",
            "description": "Persist a concise cognitive memory via MemoryBear.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "offline": {"type": "boolean"},
                },
                "required": ["message"],
            },
        },
        {
            "name": "connectome_route",
            "description": "Route a sensory spike through Cam connectome to a motor plan.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sense": {"type": "string"},
                    "goal": {"type": "string"},
                    "kill": {"type": "boolean"},
                    "no_autonomy": {"type": "boolean"},
                    "hotspot": {"type": "string"},
                },
                "required": ["sense"],
            },
        },
        {
            "name": "kill_switch_status",
            "description": "Report Cam kill-switch / autonomy defaults from connectome config.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ticket_list",
            "description": "List recent Cline tickets bound by scripts/run-cline.py.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "done", "all"]},
                    "limit": {"type": "integer"},
                },
            },
        },
        {
            "name": "public_apis_search",
            "description": (
                "Search the curated free/public API catalog (afidurko/public-apis) "
                "shared by all Cam agents. Offline fixture available."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "auth": {"type": "string"},
                    "https": {"type": "boolean"},
                    "num": {"type": "integer"},
                    "offline": {"type": "boolean"},
                    "list_categories": {"type": "boolean"},
                },
            },
        },
        {
            "name": "public_apis_addon",
            "description": (
                "Call an allowlisted public-apis thin-wrapper add-on "
                "(weather, geocode, ip, cat facts, dogs, coingecko). "
                "No free-form URLs — only curated add-on ids."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "addon_id": {"type": "string"},
                    "list": {"type": "boolean"},
                    "offline": {"type": "boolean"},
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "days": {"type": "integer"},
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                    "ids": {"type": "string"},
                    "vs": {"type": "string"},
                },
            },
        },
        {
            "name": "google_trends_search",
            "description": (
                "Search Google Trends open datasets (github.com/GoogleTrends/data). "
                "Offline fixture available; live mode uses GitHub git trees API."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "year": {"type": "string"},
                    "ext": {"type": "string"},
                    "num": {"type": "integer"},
                    "offline": {"type": "boolean"},
                    "list_years": {"type": "boolean"},
                    "fetch": {"type": "string"},
                },
            },
        },
        {
            "name": "google_trends_addon",
            "description": (
                "Call an allowlisted Google Trends curated search or dataset preview "
                "(election/nba/storm searches; game_theory / same_sex_marriage previews). "
                "No free-form paths — only curated add-on ids."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "addon_id": {"type": "string"},
                    "list": {"type": "boolean"},
                    "offline": {"type": "boolean"},
                    "num": {"type": "integer"},
                    "preview_lines": {"type": "integer"},
                },
            },
        },
        {
            "name": "inkbox_check",
            "description": (
                "Confirm Inkbox wiring (connectome, registry, submodule). "
                "Does not send email/SMS or require INKBOX_API_KEY. "
                "Live outbound uses motor.inkbox under switch.outbound."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "loop_check",
            "description": (
                "Confirm Loop Engineering wiring (connectome, spine files, submodule). "
                "No network required."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "loop_audit",
            "description": (
                "Run loop-audit against Personal-Assistant and return Loop Ready output. "
                "Prefer local submodule CLI."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "suggest": {"type": "boolean"},
                    "badge": {"type": "boolean"},
                },
            },
        },
        {
            "name": "loop_run",
            "description": (
                "Run a Cam L1 loop pattern (daily-triage, qa-cycle, post-merge-cleanup, "
                "issue-triage). Week-one report-only — no auto-fix/merge."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "level": {"type": "string"},
                    "list": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                },
            },
        },
        {
            "name": "voicestudio_health",
            "description": "Probe Cam's VoiceStudio local backend /health (default http://localhost:3900).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                    "timeout": {"type": "number"},
                },
            },
        },
        {
            "name": "needs_attention",
            "description": (
                "Survey Cam Needs Attention across all coding workspaces: connectivity, "
                "attention queue, and choose-workspace dispatch plan. Does not outbound-send "
                "or apply Cam enhance."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "connect": {"type": "boolean"},
                    "dispatch_plan": {"type": "boolean"},
                    "write": {"type": "boolean"},
                    "limit": {"type": "integer"},
                },
            },
        },
        {
            "name": "instinct_scan",
            "description": (
                "Run Cam Instinct follow-through scan: unanswered Aaron asks, stale/overdue "
                "jobs, due monitor checks. write=true drafts follow-ups to data/instinct/outbox "
                "(draft-only — live send stays behind switch.outbound via motor.inkbox)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "write": {"type": "boolean"},
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_report",
            "description": (
                "Cam Instinct structured brief: open/waiting/monitor/snoozed jobs, unanswered "
                "asks, escalations, pending drafts."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_brief",
            "description": (
                "Cam Instinct markdown daily brief. write=true also saves to "
                "data/instinct/briefs/YYYY-MM-DD.md."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "write": {"type": "boolean"},
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_workspaces",
            "description": (
                "Cam Instinct per-workspace rollup across all registered coding workspaces: "
                "connectivity, open/waiting/monitor jobs, escalations, pending drafts."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "all": {"type": "boolean", "description": "include workspaces with no jobs"},
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_dispatch",
            "description": (
                "Print-only run-cline dispatch plan for Instinct coding/attention jobs. "
                "Never executes — motor.cline still fires only under switch.autonomy."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_stats",
            "description": (
                "Cam Instinct follow-through scorecard: jobs done, avg time-to-done, "
                "follow-ups drafted, ask answer rate, draft review counts. Read-only. "
                "(Outbox approve/discard stays Aaron-only via the CLI.)"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "now": {"type": "string", "description": "ISO8601 clock override"},
                },
            },
        },
        {
            "name": "instinct_delegate",
            "description": (
                "Spawn a subagent for one Instinct job (synapse.spawn + assign_task via "
                "scripts/cam_swarm.py). Role is picked by job kind/title unless given. "
                "Unlimited, no human gate; child privileges ⊆ chief — it can draft, never send."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job": {"type": "string", "description": "job id (prefix ok)"},
                    "role": {"type": "string"},
                    "parent": {"type": "string", "description": "spawning agent id (default chief)"},
                    "force": {"type": "boolean"},
                    "now": {"type": "string"},
                },
                "required": ["job"],
            },
        },
        {
            "name": "swarm_spawn",
            "description": (
                "synapse.spawn — create a subagent at parent.level + 1 with privileges ⊆ parent. "
                "Unlimited count/depth; never grants Aaron-only or chief-only (outbound_send) privileges; "
                "parent must be an agent (never human.aaron); reserved roles refused; refused while switch.kill is act."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "parent": {"type": "string", "description": "default chief"},
                    "mandate": {"type": "string"},
                    "job": {"type": "string", "description": "job:<instinct id>"},
                    "team": {"type": "string", "description": "team.* for broadcast membership"},
                    "privileges": {"type": "array", "items": {"type": "string"}},
                    "now": {"type": "string"},
                },
                "required": ["role"],
            },
        },
        {
            "name": "swarm_assign",
            "description": "synapse.assign_task — queue a task on an active agent (internal bus; not outbound).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "assignee": {"type": "string"},
                    "task": {"type": "string"},
                    "caller": {"type": "string", "description": "default chief"},
                    "parent_action": {"type": "string"},
                    "job": {"type": "string"},
                    "now": {"type": "string"},
                },
                "required": ["assignee", "task"],
            },
        },
        {
            "name": "swarm_resolve",
            "description": "synapse.resolve_task — done | failed | blocked | cancelled with an optional distillate.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "status": {"type": "string", "enum": ["done", "failed", "blocked", "cancelled"]},
                    "caller": {"type": "string", "description": "default chief"},
                    "distillate": {"type": "string"},
                    "now": {"type": "string"},
                },
                "required": ["action", "status"],
            },
        },
        {
            "name": "swarm_tree",
            "description": "Lineage tree (Aaron → chief → specialists → subagents) with open action counts.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "swarm_stats",
            "description": "Swarm counts: active/terminated agents, max level, by role/team, actions, kill state.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "connectors_list",
            "description": (
                "Every app/connector Cam can reach (config/connectors/registry.json) with mode "
                "(read/draft/act/via_brain), switch gate, connectome node, roles, and whether its "
                "credential is present (bool only). Validated by scripts/connectors-check.py."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "filter: read | draft | act | via_brain"},
                    "role": {"type": "string", "description": "only connectors this role may use"},
                },
            },
        },
        {
            "name": "calendar_sync",
            "description": (
                "Read-only ICS calendar → Instinct prep jobs (source_ref ics:<uid>, idempotent). "
                "Sources come ONLY from Aaron's $CAM_CALENDAR_ICS; an `ics` argument is ignored "
                "(no agent-supplied URLs). write=true drops events for `instinct sync`. "
                "Never writes to the calendar."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "horizon_days": {"type": "integer"},
                    "write": {"type": "boolean"},
                    "now": {"type": "string"},
                },
            },
        },
        {
            "name": "inkbox_inbound",
            "description": (
                "Fold Inkbox inbound events (email/SMS/missed call JSON in data/inkbox/inbound) into "
                "the Instinct thread as DATA ONLY — links stripped, content never executed. "
                "write=true drops + archives; no_jobs=true keeps it to thread notes."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "write": {"type": "boolean"},
                    "no_jobs": {"type": "boolean"},
                    "reply_due": {"type": "string", "description": "default +2d"},
                    "now": {"type": "string"},
                },
            },
        },
    ]


def script_cli(rel: str, argv: list[str], text_output: bool = False) -> Any:
    proc = subprocess.run([sys.executable, str(ROOT / rel), *argv], cwd=str(ROOT),
                          capture_output=True, text=True)
    if text_output:
        out = {"ok": proc.returncode == 0, "text": proc.stdout, "stderr": proc.stderr or None}
        if proc.returncode != 0 and proc.stderr:
            out["error"] = proc.stderr.strip()
        return out
    try:
        out = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "tool failed",
                "stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}
    if proc.returncode != 0 and isinstance(out, dict) and "ok" not in out:
        out["ok"] = False
    if proc.returncode != 0 and proc.stderr:
        out = {"ok": False, "error": proc.stderr.strip(), "result": out} if isinstance(out, dict) else out
    return out


def connectors_list(arguments: dict | None) -> dict:
    arguments = arguments or {}
    reg = cw.load_json(ROOT / "config" / "connectors" / "registry.json")
    rows = []
    for c in reg.get("connectors") or []:
        if arguments.get("mode") and c.get("mode") != arguments["mode"]:
            continue
        role = arguments.get("role")
        if role and c.get("roles") != "all" and role not in (c.get("roles") or []):
            continue
        rows.append({
            "id": c["id"], "label": c.get("label"), "mode": c.get("mode"), "status": c.get("status"),
            "switch": c.get("switch"), "sense": c.get("sense"), "motor": c.get("motor"),
            "roles": c.get("roles"), "mcp_tools": c.get("mcp_tools") or [],
            "credentials_present": {k: bool(os.environ.get(k)) for k in (c.get("credential_env") or [])},
            "notes": c.get("notes"),
        })
    return {"ok": True, "count": len(rows), "modes": reg.get("modes"), "connectors": rows,
            "policy": reg.get("policy")}


def mesh_search(query: str, limit: int = 20) -> dict:
    q = query.lower()
    seed = cw.load_json(ROOT / "identity" / "persistence" / "mesh-seed.json")
    cache = cw.load_json(cw.CLINE_CACHE)
    hits = []
    for ns, body in seed.items():
        blob = json.dumps(body, sort_keys=True).lower()
        if q in ns.lower() or q in blob:
            hits.append({"namespace": ns, "snippet": blob[:400]})
        if len(hits) >= limit:
            break
    if len(hits) < limit:
        blob = json.dumps(cache, sort_keys=True).lower()
        if q in blob:
            hits.append({"namespace": "mesh/cline/cache", "snippet": blob[:400]})
    return {"query": query, "hits": hits[:limit]}


def mesh_put(note: str, workspace: str = ".", namespace: str = "mesh/cline") -> dict:
    from datetime import datetime, timezone

    # Charter P8: mesh notes are read by every agent, so personal classes are
    # redacted before the write; a secret makes the whole note refuse.
    clean = privacy.assert_shareable(note, "mesh_note")
    cache = cw.load_json(cw.CLINE_CACHE)
    cache.setdefault("notes", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "text": clean,
            "workspace": workspace,
            "namespace": namespace,
        }
    )
    cw.write_json(cw.CLINE_CACHE, cache)
    return {"ok": True, "notes": len(cache["notes"]), "path": str(cw.CLINE_CACHE),
            "redacted": clean != note}


def privacy_status() -> dict:
    rep = privacy.doctor()
    ch = privacy.charter()
    return {
        "ok": rep["ok"], "principal": rep["principal"], "owner": rep["owner"],
        "principals": [{"id": p["id"], "kind": p["kind"]} for p in rep["principals"]],
        "hmac_key": rep["hmac_key"], "problems": rep["problems"], "notes": rep["notes"],
        "charter": {"principle": ch["principle"], "invariants": [i["id"] + ": " + i["rule"] for i in ch["invariants"]]},
        "guest_tools": sorted(guest_tool_allowlist()),
        "aaron_only": ["principals add", "consent grant/revoke", "keygen", "outbox approve", "swarm resume"],
    }


def vault_search(query: str, limit: int = 20) -> dict:
    q = query.lower()
    vault = ROOT / "vault"
    hits = []
    if not vault.exists():
        return {"query": query, "hits": [], "error": "vault missing"}
    for path in vault.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if q in path.name.lower() or q in text.lower():
            # find a small context window
            idx = text.lower().find(q)
            start = max(0, idx - 80) if idx >= 0 else 0
            snippet = text[start : start + 240].replace("\n", " ")
            hits.append({"path": str(path.relative_to(ROOT)), "snippet": snippet})
        if len(hits) >= limit:
            break
    return {"query": query, "hits": hits}


def memorybear_read(query: str, offline: bool = True, search_switch: str = "express") -> dict:
    import subprocess

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "memorybear.py"),
        "read",
        "--query",
        query,
        "--search-switch",
        search_switch or "express",
    ]
    if offline:
        cmd.append("--offline")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "memorybear_read_failed", "stdout": proc.stdout, "stderr": proc.stderr}


def memorybear_write(message: str, offline: bool = True) -> dict:
    import subprocess

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "memorybear.py"),
        "write",
        "--message",
        message,
    ]
    if offline:
        cmd.append("--offline")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "memorybear_write_failed", "stdout": proc.stdout, "stderr": proc.stderr}


def connectome_route(args: dict) -> dict:
    import subprocess

    cmd = [sys.executable, str(ROOT / "scripts" / "connectome-route.py"), "--sense", args["sense"]]
    if args.get("goal"):
        cmd.extend(["--goal", args["goal"]])
    if args.get("kill"):
        cmd.append("--kill")
    if args.get("no_autonomy"):
        cmd.append("--no-autonomy")
    if args.get("hotspot"):
        cmd.extend(["--hotspot", args["hotspot"]])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "route_failed", "stdout": proc.stdout, "stderr": proc.stderr}


def kill_switch_status() -> dict:
    switches = cw.load_json(ROOT / "config" / "connectome" / "switches.json")
    by_id = {s["id"]: s for s in switches.get("switches", [])}
    return {
        "sole_operator": switches.get("sole_operator"),
        "kill": by_id.get("switch.kill"),
        "autonomy": by_id.get("switch.autonomy"),
        "tasking": by_id.get("switch.tasking"),
    }


def ticket_list(status: str = "all", limit: int = 20) -> dict:
    paths: list[Path] = []
    if status in {"pending", "all"}:
        paths.extend(sorted((cw.TICKETS_DIR / "pending").glob("*.json")))
    if status in {"done", "all"}:
        paths.extend(sorted((cw.TICKETS_DIR / "done").glob("*.json")))
    items = []
    for path in paths[-limit:]:
        try:
            doc = cw.load_json(path)
            items.append(
                {
                    "id": doc.get("id"),
                    "status": doc.get("status"),
                    "workspace_id": doc.get("workspace_id"),
                    "path": str(path),
                    "updated_at": doc.get("updated_at"),
                }
            )
        except Exception:
            continue
    return {"tickets": items}


def public_apis_search(arguments: dict) -> Any:
    cmd = [sys.executable, str(ROOT / "scripts/public-apis-search.py")]
    if arguments.get("list_categories"):
        cmd.append("--list-categories")
    if arguments.get("query"):
        cmd.extend(["--query", str(arguments["query"])])
    if arguments.get("category"):
        cmd.extend(["--category", str(arguments["category"])])
    if arguments.get("auth"):
        cmd.extend(["--auth", str(arguments["auth"])])
    if arguments.get("https"):
        cmd.append("--https")
    if arguments.get("num") is not None:
        cmd.extend(["--num", str(int(arguments["num"]))])
    if arguments.get("offline") is True:
        cmd.append("--offline")
    out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
    return json.loads(out)


def public_apis_addon(arguments: dict) -> Any:
    cmd = [sys.executable, str(ROOT / "scripts/public-apis-addon.py")]
    if arguments.get("list"):
        cmd.append("list")
        out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
        return json.loads(out)
    addon_id = arguments.get("addon_id")
    if not addon_id:
        raise ValueError("addon_id required unless list=true")
    cmd.extend(["call", str(addon_id)])
    for flag, key in (
        ("--latitude", "latitude"),
        ("--longitude", "longitude"),
        ("--days", "days"),
        ("--name", "name"),
        ("--count", "count"),
        ("--ids", "ids"),
        ("--vs", "vs"),
    ):
        if arguments.get(key) is not None:
            cmd.extend([flag, str(arguments[key])])
    if arguments.get("offline") is True:
        cmd.append("--offline")
    out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
    return json.loads(out)


def google_trends_search(arguments: dict) -> Any:
    cmd = [sys.executable, str(ROOT / "scripts/google-trends-search.py")]
    if arguments.get("list_years"):
        cmd.append("--list-years")
    if arguments.get("query"):
        cmd.extend(["--query", str(arguments["query"])])
    if arguments.get("year"):
        cmd.extend(["--year", str(arguments["year"])])
    if arguments.get("ext"):
        cmd.extend(["--ext", str(arguments["ext"])])
    if arguments.get("num") is not None:
        cmd.extend(["--num", str(int(arguments["num"]))])
    if arguments.get("fetch"):
        cmd.extend(["--fetch", str(arguments["fetch"])])
    if arguments.get("offline") is True:
        cmd.append("--offline")
    out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
    return json.loads(out)


def google_trends_addon(arguments: dict) -> Any:
    cmd = [sys.executable, str(ROOT / "scripts/google-trends-addon.py")]
    if arguments.get("list"):
        cmd.append("list")
        out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
        return json.loads(out)
    addon_id = arguments.get("addon_id")
    if not addon_id:
        raise ValueError("addon_id required unless list=true")
    cmd.extend(["call", str(addon_id)])
    if arguments.get("num") is not None:
        cmd.extend(["--num", str(int(arguments["num"]))])
    if arguments.get("preview_lines") is not None:
        cmd.extend(["--preview-lines", str(int(arguments["preview_lines"]))])
    if arguments.get("offline") is True:
        cmd.append("--offline")
    out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
    return json.loads(out)


def inkbox_check(_arguments: dict | None = None) -> Any:
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/inkbox-check.py")],
        text=True,
        cwd=str(ROOT),
    )
    return json.loads(out)


def loop_check(_arguments: dict | None = None) -> Any:
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/loop-check.py")],
        text=True,
        cwd=str(ROOT),
    )
    return json.loads(out)


def loop_audit(arguments: dict | None = None) -> Any:
    arguments = arguments or {}
    cmd = [sys.executable, str(ROOT / "scripts/loop-audit.py"), "--json"]
    if arguments.get("suggest"):
        cmd.append("--suggest")
    if arguments.get("badge"):
        cmd.append("--badge")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }


def loop_run(arguments: dict | None = None) -> Any:
    arguments = arguments or {}
    cmd = [sys.executable, str(ROOT / "scripts/loop-run.py")]
    if arguments.get("list"):
        cmd.append("--list")
    else:
        pattern = arguments.get("pattern") or "daily-triage"
        cmd.extend(["--pattern", str(pattern)])
        if arguments.get("level"):
            cmd.extend(["--level", str(arguments["level"])])
        if arguments.get("dry_run"):
            cmd.append("--dry-run")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }


def instinct_cli(arguments: dict | None, command: str,
                 write_flag: bool = False, text_output: bool = False,
                 extra: list[str] | None = None) -> Any:
    arguments = arguments or {}
    cmd = [sys.executable, str(ROOT / "scripts/instinct.py")]
    if arguments.get("now"):
        cmd.extend(["--now", str(arguments["now"])])
    cmd.append(command)
    if write_flag and arguments.get("write"):
        cmd.append("--write")
    if extra:
        cmd.extend(extra)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if text_output:
        return {"ok": proc.returncode == 0, "brief": proc.stdout, "stderr": proc.stderr or None}
    try:
        out = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    if proc.returncode != 0 and not proc.stdout.strip():
        # a refusal (privacy seal, guest scope, kill) exits before printing JSON
        return {"ok": False, "error": (proc.stderr or "").strip(), "exit_code": proc.returncode}
    return out


def voicestudio_health(base_url: str | None = None, timeout: float = 5.0) -> dict:
    cmd = [sys.executable, str(ROOT / "scripts" / "voicestudio-health.py"), "--json"]
    if base_url:
        cmd.extend(["--base-url", base_url])
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "health_probe_failed",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }


def needs_attention(arguments: dict | None = None) -> Any:
    args = arguments or {}
    cmd = [sys.executable, str(ROOT / "scripts" / "needs-attention.py"), "--json"]
    if args.get("connect"):
        cmd.append("--connect")
    if args.get("dispatch_plan", True):
        cmd.append("--dispatch-plan")
    if args.get("execute"):
        cmd.append("--execute")
    if args.get("write"):
        cmd.append("--write")
    if args.get("limit") is not None:
        cmd.extend(["--limit", str(int(args["limit"]))])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "needs_attention_failed",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }


def call_tool(name: str, arguments: dict) -> Any:
    if not tool_visible(name):
        # Charter P3: a guest process cannot reach tools that touch the owner's
        # data or configuration — not even by name.
        return {"ok": False, "error": f"tool {name!r} is not available to principal {principal()!r} "
                                      "(owner-only; see privacy_status.guest_tools)"}
    if name in ("instinct_scan", "instinct_brief") and arguments.get("write") and arguments.get("now"):
        # drafts / briefs are records; agents do not backdate them
        arguments = {k: v for k, v in arguments.items() if k != "now"}
    if name == "privacy_status":
        return privacy_status()
    if name == "privacy_redact":
        text, counts = privacy.redact(str(arguments.get("text") or ""))
        return {"ok": True, "text": text, "redacted": counts}
    if name == "privacy_audit":
        return privacy.audit()
    if name == "list_workspaces":
        return cw.mesh_projects_doc()
    if name == "choose_workspace":
        return cw.choose_workspace(
            goal=arguments.get("goal", ""),
            workspace_id=arguments.get("workspace_id"),
            explicit_path=arguments.get("path"),
            role=arguments.get("role"),
        )
    if name == "mesh_search":
        return mesh_search(arguments.get("query", ""), int(arguments.get("limit") or 20))
    if name == "mesh_put":
        return mesh_put(
            arguments.get("note", ""),
            workspace=arguments.get("workspace", "."),
            namespace=arguments.get("namespace", "mesh/cline"),
        )
    if name == "vault_search":
        return vault_search(arguments.get("query", ""), int(arguments.get("limit") or 20))
    if name == "memorybear_read":
        return memorybear_read(
            arguments.get("query", ""),
            offline=bool(arguments.get("offline", True)),
            search_switch=arguments.get("search_switch") or "express",
        )
    if name == "memorybear_write":
        return memorybear_write(
            arguments.get("message", ""),
            offline=bool(arguments.get("offline", True)),
        )
    if name == "connectome_route":
        return connectome_route(arguments)
    if name == "kill_switch_status":
        return kill_switch_status()
    if name == "ticket_list":
        return ticket_list(arguments.get("status", "all"), int(arguments.get("limit") or 20))
    if name == "public_apis_search":
        return public_apis_search(arguments)
    if name == "public_apis_addon":
        return public_apis_addon(arguments)
    if name == "google_trends_search":
        return google_trends_search(arguments)
    if name == "google_trends_addon":
        return google_trends_addon(arguments)
    if name == "inkbox_check":
        return inkbox_check(arguments)
    if name == "loop_check":
        return loop_check(arguments)
    if name == "loop_audit":
        return loop_audit(arguments)
    if name == "loop_run":
        return loop_run(arguments)
    if name == "voicestudio_health":
        return voicestudio_health(
            base_url=arguments.get("base_url"),
            timeout=float(arguments.get("timeout") or 5.0),
        )
    if name == "needs_attention":
        return needs_attention(arguments)
    if name == "instinct_scan":
        return instinct_cli(arguments, "scan", write_flag=True)
    if name == "instinct_report":
        return instinct_cli(arguments, "report")
    if name == "instinct_brief":
        return instinct_cli(arguments, "brief", write_flag=True, text_output=True)
    if name == "instinct_stats":
        return instinct_cli(arguments, "stats")
    if name == "instinct_workspaces":
        return instinct_cli(arguments, "workspaces", extra=["--all"] if arguments.get("all") else None)
    if name == "instinct_dispatch":
        limit = arguments.get("limit")
        return instinct_cli(arguments, "dispatch", extra=["--limit", str(int(limit))] if limit else None)
    if name in ("instinct_delegate", "swarm_spawn", "swarm_assign", "swarm_resolve"):
        # Agent bus guards: nobody on MCP is Aaron, nobody backdates the ledger.
        for key in ("caller", "parent", "sender"):
            val = str(arguments.get(key) or "")
            if val and (val == "human.aaron" or val.startswith("human") or val == "aaron"):
                return {"ok": False, "error": f"{key}={val!r} refused: agents never act as Aaron over MCP "
                                              "(Aaron uses the CLI with --aaron)"}
        if arguments.get("now"):
            arguments = {k: v for k, v in arguments.items() if k != "now"}
    if name == "instinct_delegate":
        extra = [str(arguments["job"])]
        if arguments.get("role"):
            extra += ["--role", str(arguments["role"])]
        if arguments.get("parent"):
            extra += ["--parent", str(arguments["parent"])]
        if arguments.get("force"):
            extra.append("--force")
        return instinct_cli(arguments, "delegate", extra=extra)
    if name.startswith("swarm_"):
        argv: list[str] = []
        if arguments.get("now"):
            argv += ["--now", str(arguments["now"])]
        sub = name.split("_", 1)[1]
        if sub == "spawn":
            argv += ["spawn", str(arguments["role"])]
            for key, flag in (("parent", "--parent"), ("mandate", "--mandate"), ("job", "--job"), ("team", "--team")):
                if arguments.get(key):
                    argv += [flag, str(arguments[key])]
            for priv in arguments.get("privileges") or []:
                argv += ["--privilege", str(priv)]
        elif sub == "assign":
            argv += ["assign", str(arguments["assignee"]), str(arguments["task"])]
            for key, flag in (("caller", "--caller"), ("parent_action", "--parent-action"), ("job", "--job")):
                if arguments.get(key):
                    argv += [flag, str(arguments[key])]
        elif sub == "resolve":
            argv += ["resolve", str(arguments["action"]), str(arguments["status"])]
            for key, flag in (("caller", "--caller"), ("distillate", "--distillate")):
                if arguments.get(key):
                    argv += [flag, str(arguments[key])]
        elif sub in ("tree", "stats"):
            argv += [sub]
        else:
            raise ValueError(f"unknown tool: {name}")
        return script_cli("scripts/cam_swarm.py", argv, text_output=(sub == "tree"))
    if name == "connectors_list":
        return connectors_list(arguments)
    if name == "calendar_sync":
        argv = []
        if arguments.get("now"):
            argv += ["--now", str(arguments["now"])]
        if arguments.get("ics"):
            # Sources are Aaron's ($CAM_CALENDAR_ICS). Agent-supplied URLs would be a
            # free-form HTTP / exfiltration channel, so they are ignored, not fetched.
            arguments = {k: v for k, v in arguments.items() if k != "ics"}
            argv += ["--note-ignored-ics"]
        if arguments.get("horizon_days"):
            argv += ["--horizon-days", str(int(arguments["horizon_days"]))]
        if arguments.get("write"):
            argv.append("--write")
        return script_cli("scripts/calendar-sync.py", argv)
    if name == "inkbox_inbound":
        argv = []
        if arguments.get("now"):
            argv += ["--now", str(arguments["now"])]
        if arguments.get("write"):
            argv.append("--write")
        if arguments.get("no_jobs"):
            argv.append("--no-jobs")
        if arguments.get("reply_due"):
            argv += ["--reply-due", str(arguments["reply_due"])]
        return script_cli("scripts/inkbox-inbound.py", argv)
    raise ValueError(f"unknown tool: {name}")


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) — ignore
    if req_id is None and method:
        return None

    if method == "initialize":
        pid = principal()
        name = SERVER_NAME if privacy.is_owner(pid) else f"{SERVER_NAME}-{pid}"
        return _ok(
            {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": name, "version": SERVER_VERSION, "principal": pid},
            },
            req_id,
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _ok({}, req_id)
    if method == "tools/list":
        return _ok({"tools": tool_defs()}, req_id)
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = call_tool(name, arguments)
            return _ok(
                {
                    "content": [
                        {"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}
                    ]
                },
                req_id,
            )
        except privacy.PrivacyViolation as exc:
            # Charter refusals are answers, not crashes: the write did not
            # happen and the session stays up for the next request. Killing
            # the server here would hand any agent a one-line denial of service.
            return _ok(
                {
                    "isError": True,
                    "content": [{"type": "text", "text": json.dumps(
                        {"ok": False, "refused": "privacy", "error": str(exc)}, indent=2, sort_keys=True)}],
                },
                req_id,
            )
        except SystemExit as exc:  # a tool's own argparse/usage exit
            return _ok(
                {
                    "isError": True,
                    "content": [{"type": "text", "text": json.dumps(
                        {"ok": False, "error": str(exc) or "tool exited"}, indent=2, sort_keys=True)}],
                },
                req_id,
            )
        except Exception as exc:  # noqa: BLE001
            return _ok(
                {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
                req_id,
            )
    return _err(req_id, -32601, f"method not found: {method}")


def main() -> int:
    argv = sys.argv[1:]
    if "--principal" in argv:
        idx = argv.index("--principal")
        if idx + 1 >= len(argv):
            sys.stderr.write("--principal needs an id\n")
            return 2
        os.environ[privacy.PRINCIPAL_ENV] = argv[idx + 1]
    try:
        pid = principal()  # fail fast on an invalid id
    except SystemExit as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if not privacy.is_owner(pid):
        root = privacy.guest_root(pid)
        if not (root / "profile.json").exists():
            sys.stderr.write(f"principal {pid!r} is not enrolled — Aaron runs: "
                             f"python3 scripts/cam_privacy.py --aaron principals add {pid}\n")
            return 2
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
