#!/usr/bin/env python3
"""Minimal stdio MCP server exposing Cam mesh/vault/connectome to Cline.

Implements a small JSON-RPC MCP subset over stdin/stdout:
  initialize, tools/list, tools/call, ping

Tools:
  list_workspaces, choose_workspace, mesh_search, mesh_put,
  vault_search, connectome_route, kill_switch_status, ticket_list,
  public_apis_search, public_apis_addon

Install into Cline (example):
  cline mcp install cam -- python3 /path/to/Personal-Assistant/scripts/cam-mcp-server.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402

SERVER_NAME = "cam-personal-assistant"
SERVER_VERSION = "1.1.0"


def _ok(result: Any, req_id: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def tool_defs() -> list[dict]:
    return [
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
    ]


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

    cache = cw.load_json(cw.CLINE_CACHE)
    cache.setdefault("notes", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "text": note,
            "workspace": workspace,
            "namespace": namespace,
        }
    )
    cw.write_json(cw.CLINE_CACHE, cache)
    return {"ok": True, "notes": len(cache["notes"]), "path": str(cw.CLINE_CACHE)}


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


def call_tool(name: str, arguments: dict) -> Any:
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
    raise ValueError(f"unknown tool: {name}")


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) — ignore
    if req_id is None and method:
        return None

    if method == "initialize":
        return _ok(
            {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
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
