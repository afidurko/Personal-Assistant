#!/usr/bin/env python3
"""Cam swarm runtime — file-backed lineage for the HAAS-style synapse
primitives in config/swarm/primitives.json.

This is the offline / local-first implementation of `synapse.spawn`,
`assign_task`, `resolve_task`, `send_message`, `broadcast` and
`terminate_lineage`. When the Null stack (nulltickets + mesh) is live the
same records mirror into `mesh/agent-lineage` and `mesh/agent-commute`; when
it is not, this ledger *is* the lineage.

Invariants (checked by `doctor` and by scripts/test_cam_swarm.py):

- Aaron is level 0 and the only root task-giver; `chief` is level 1.
- Every child is exactly `parent.level + 1` (spawn one level below only).
- Child privileges are a subset of the parent's — never escalate.
- No agent ever holds an Aaron-only privilege.
- Spawn count / depth are unbounded (identity/persistence/UNLIMITED_SUBAGENTS.md).
- `switch.kill` (Aaron) silences spawn / assign / broadcast; records stay.
- Only an ancestor — or Aaron — may terminate a lineage.
- Internal bus only: nothing here talks to a human channel. Outbound stays
  behind switch.outbound via motor.inkbox; drafts flow through Instinct.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_privacy as privacy  # noqa: E402

PRIVILEGES = ROOT / "config/swarm/privileges.json"
PRIMITIVES = ROOT / "config/swarm/primitives.json"

AARON_ID = "human.aaron"
CHIEF_ID = "chief"
ACTION_STATUSES = ("open", "done", "failed", "blocked", "cancelled")
RESERVED_ROLES = {"chief", "aaron", "human", "human.aaron", "default_subagent"}
ROLE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


# --- paths ------------------------------------------------------------------

def data_dir() -> Path:
    """One lineage per principal. The owner keeps data/swarm (or CAM_SWARM_DIR);
    a guest principal is confined to data/principals/<id>/swarm."""
    return privacy.scoped_dir("swarm", "CAM_SWARM_DIR", ROOT / "data/swarm")


def lineage_path() -> Path:
    return data_dir() / "lineage.json"


def kill_flag_path() -> Path:
    return data_dir() / "KILL"


def archive_dir() -> Path:
    return data_dir() / "archive"


def bus_bridge_path() -> Path:
    """Append-only SwarmBusEvent-shaped log the Node runtime can tail
    (server/core/swarm-runtime.ts) so CLI spawns are visible before the
    nightly distill."""
    return data_dir() / "bus-bridge.jsonl"


def mesh_out_path() -> Path:
    if not privacy.is_owner():
        return data_dir().parent / "distill" / "agent-lineage.json"
    override = os.environ.get("CAM_SWARM_MESH_OUT")
    return Path(override) if override else ROOT / "vault/10-Mesh-Distillates/agent-lineage/latest.json"


# --- time / ids -------------------------------------------------------------

def now_utc(override: str | None = None) -> datetime:
    if override:
        dt = datetime.fromisoformat(override.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --- config -----------------------------------------------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def privileges_config() -> dict:
    return load_json(PRIVILEGES)


def primitives_config() -> dict:
    return load_json(PRIMITIVES)


def aaron_only() -> set[str]:
    return set(privileges_config()["privilege_catalog"]["aaron_only"])


def agent_grantable() -> set[str]:
    return set(privileges_config()["privilege_catalog"]["agent_grantable"])


def non_inheritable() -> set[str]:
    """Privileges only the chief may hold; never passed down even though
    child ⊆ parent would allow it (live use is a switch decision, not a grant)."""
    return set(privileges_config()["privilege_catalog"].get("non_inheritable") or [])


def role_default_privileges(role: str) -> list[str]:
    defaults = privileges_config()["role_defaults"]
    entry = defaults.get(role) or defaults["default_subagent"]
    return list(entry["privileges"])


def broadcast_channels() -> list[str]:
    for prim in primitives_config()["primitives"]:
        if prim["id"] == "synapse.broadcast":
            return list(prim.get("channels") or [])
    return []


# --- ledger -----------------------------------------------------------------

def empty_ledger(ts: datetime) -> dict:
    """Seed Aaron (level 0, human) and chief (level 1) — the two fixed roots."""
    grantable = sorted(agent_grantable())
    return {
        "version": 1,
        "created": iso(ts),
        "agents": {
            AARON_ID: {
                "id": AARON_ID, "kind": "human", "role": "aaron", "level": 0,
                "parent": None, "status": "active", "privileges": sorted(agent_grantable() | aaron_only()),
                "created": iso(ts), "mandate": "sole operator / root task-giver / kill master",
            },
            CHIEF_ID: {
                "id": CHIEF_ID, "kind": "agent", "role": "chief", "level": 1,
                "parent": AARON_ID, "status": "active",
                "privileges": [p for p in role_default_privileges("chief") if p in grantable],
                "created": iso(ts), "mandate": "Cam chief — finishes Aaron's tasks end-to-end",
            },
        },
        "actions": [],
        "commute": [],
        "events": [],
    }


SEAL_STATE: dict[str, str] = {"lineage": "nokey"}


def load_ledger(ts: datetime | None = None) -> dict:
    path = lineage_path()
    privacy.enter(path.parent, create=False)  # refuse a directory sealed to someone else
    if not path.exists():
        return empty_ledger(ts or now_utc())
    try:
        ledger = load_json(path)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"swarm lineage is corrupt: {path} ({exc}). "
                         "Fix or move it aside; a fresh lineage is seeded on next write.")
    SEAL_STATE["lineage"] = privacy.verify_doc(ledger)
    ledger.setdefault("agents", {})
    ledger.setdefault("actions", [])
    ledger.setdefault("commute", [])
    ledger.setdefault("events", [])
    return ledger


EVENT_CAP = 2000
COMMUTE_CAP = 5000
BRIDGE_OPS = {"spawn": "synapse.spawn", "assign_task": "synapse.assign_task",
              "resolve_task": "synapse.resolve_task", "terminate_lineage": "synapse.terminate_lineage",
              "kill_master": "denied", "kill_resume": "denied"}


def save_ledger(ledger: dict) -> None:
    # Unlimited spawn is policy; unbounded logs are not. Agents/actions are
    # kept (they are the lineage); event + commute logs are ring-buffered.
    if len(ledger["events"]) > EVENT_CAP:
        ledger["events"] = ledger["events"][-EVENT_CAP:]
    if len(ledger["commute"]) > COMMUTE_CAP:
        ledger["commute"] = ledger["commute"][-COMMUTE_CAP:]
    path = lineage_path()
    privacy.enter(path.parent)
    privacy.seal_doc(ledger)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    privacy.harden_file(path)
    _flush_bridge(ledger)


def _flush_bridge(ledger: dict) -> None:
    """Mirror new lineage events into the SwarmBusEvent-shaped bridge log."""
    pending = ledger.pop("_bridge_pending", None)
    if not pending:
        return
    try:
        with bus_bridge_path().open("a", encoding="utf-8") as fh:
            for ev in pending:
                fh.write(json.dumps(ev) + "\n")
        privacy.harden_file(bus_bridge_path())
    except OSError:
        pass


def log_event(ledger: dict, ts: datetime, kind: str, **fields) -> None:
    ledger["events"].append({"ts": iso(ts), "kind": kind, **fields})
    if kind in BRIDGE_OPS:
        # counts / ids only — no task text, no mandates (bridge is readable by the server)
        ledger.setdefault("_bridge_pending", []).append({
            "id": short_id("evt"), "op": BRIDGE_OPS[kind],
            "from": str(fields.get("by") or fields.get("parent") or AARON_ID),
            "to": fields.get("agent") or fields.get("assignee") or fields.get("target"),
            "detail": f"{kind} role={fields.get('role')} level={fields.get('level')} status={fields.get('status')}",
            "at": iso(ts), "workspaceIds": [], "ok": kind not in ("kill_master",),
            "source": "scripts/cam_swarm.py",
        })


# --- kill switch ------------------------------------------------------------

def ledger_says_killed(ledger: dict | None) -> bool:
    """The KILL file is convenience; the ledger is the record. If the last
    kill_master event is newer than the last kill_resume, the swarm is killed
    even when someone deleted the flag file."""
    if not ledger:
        return False
    last_kill = last_resume = None
    for e in ledger.get("events") or []:
        if e.get("kind") == "kill_master":
            last_kill = e["ts"]
        elif e.get("kind") == "kill_resume":
            last_resume = e["ts"]
    return bool(last_kill and (not last_resume or last_resume < last_kill))


def kill_active(ledger: dict | None = None) -> bool:
    if os.environ.get("CAM_SWITCH_KILL", "").lower() == "act":
        return True
    if kill_flag_path().exists():
        return True
    return ledger_says_killed(ledger)


def require_motor(primitive: str, ledger: dict | None = None) -> None:
    if kill_active(ledger):
        raise SystemExit(f"switch.kill act — {primitive} silenced (records retained; `resume` to re-arm)")


# --- core primitives --------------------------------------------------------

def get_agent(ledger: dict, agent_id: str) -> dict:
    """Exact id first. Prefix matching is a convenience for spawned
    `<role>-<hex>` ids only — it never resolves onto the fixed roots
    (human.aaron, chief), so `--caller hum` cannot become Aaron."""
    agent = ledger["agents"].get(agent_id)
    if agent:
        return agent
    if "-" in agent_id:
        matches = [a for a in ledger["agents"].values()
                   if a["kind"] == "agent" and a["id"] not in (AARON_ID, CHIEF_ID)
                   and a["id"].startswith(agent_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SystemExit(f"ambiguous agent id prefix {agent_id!r}: {[m['id'] for m in matches]}")
    raise SystemExit(f"unknown agent: {agent_id}")


def resolve_actor(ledger: dict, actor_id: str, aaron: bool) -> dict:
    """Who is acting. Acting as human.aaron needs the explicit CLI `--aaron`
    flag; the MCP server never sets it, so agents cannot claim to be Aaron."""
    actor = get_agent(ledger, actor_id)
    if actor["kind"] == "human" and not aaron:
        raise SystemExit("acting as human.aaron requires --aaron (Aaron's CLI only; never over the agent bus)")
    return actor


def is_ancestor(ledger: dict, ancestor_id: str, agent_id: str) -> bool:
    seen: set[str] = set()
    cur = ledger["agents"].get(agent_id)
    while cur and cur.get("parent"):
        if cur["id"] in seen:  # tampered cycle — treat as no relation
            return False
        seen.add(cur["id"])
        if cur["parent"] == ancestor_id:
            return True
        cur = ledger["agents"].get(cur["parent"])
    return False


def descendants(ledger: dict, agent_id: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = {agent_id}
    frontier = [agent_id]
    while frontier:
        pid = frontier.pop()
        for a in ledger["agents"].values():
            if a.get("parent") == pid and a["id"] not in seen:
                seen.add(a["id"])
                out.append(a)
                frontier.append(a["id"])
    return out


def lineage_cycles(ledger: dict) -> list[str]:
    """Agents whose parent chain never reaches a root (tampered ledger)."""
    bad: list[str] = []
    for start in ledger["agents"]:
        seen: set[str] = set()
        cur = ledger["agents"].get(start)
        while cur and cur.get("parent"):
            if cur["id"] in seen:
                bad.append(start)
                break
            seen.add(cur["id"])
            cur = ledger["agents"].get(cur["parent"])
    return bad


def spawn(ledger: dict, parent_id: str, role: str, ts: datetime,
          privileges: list[str] | None = None, mandate: str | None = None,
          job_ref: str | None = None, team: str | None = None, aaron: bool = False) -> dict:
    """synapse.spawn — child at parent.level + 1 with privileges ⊆ parent."""
    require_motor("synapse.spawn", ledger)
    role = (role or "").strip()
    if role in RESERVED_ROLES or not ROLE_RE.match(role):
        raise SystemExit(f"invalid or reserved role {role!r} (lowercase [a-z0-9_-], 2-32 chars; "
                         f"reserved: {sorted(RESERVED_ROLES)})")
    parent = get_agent(ledger, parent_id)
    if parent["kind"] == "human" and not aaron:
        raise SystemExit("only Aaron (CLI --aaron) may spawn directly under human.aaron; agents spawn under chief or themselves")
    if parent["status"] != "active":
        raise SystemExit(f"parent {parent['id']} is {parent['status']} — cannot spawn")
    if parent["kind"] == "agent" and "spawn_subagents" not in parent["privileges"]:
        raise SystemExit(f"parent {parent['id']} lacks spawn_subagents")

    parent_grantable = set(parent["privileges"]) - aaron_only() - non_inheritable()
    requested = set(privileges) if privileges else set(role_default_privileges(role))
    forbidden = requested & aaron_only()
    if forbidden:
        raise SystemExit(f"refusing to grant Aaron-only privileges {sorted(forbidden)} to an agent")
    sticky = requested & non_inheritable()
    if privileges and sticky:
        raise SystemExit(f"{sorted(sticky)} are chief-only and never inherited (switch.outbound / "
                         "switch.careers_submit decide live use)")
    if privileges and not requested <= parent_grantable:
        raise SystemExit(f"privilege escalation: {sorted(requested - parent_grantable)} "
                         f"not held by parent {parent['id']}")
    granted = sorted(requested & parent_grantable)

    child = {
        "id": short_id(role.replace(" ", "-").lower()[:24]),
        "kind": "agent",
        "role": role,
        "level": int(parent["level"]) + 1,
        "parent": parent["id"],
        "status": "active",
        "privileges": granted,
        "created": iso(ts),
        "mandate": mandate or f"{role} subagent",
        "job_ref": job_ref,
        "team": team,
        "boundaries": ["aaron_only_tasking", "switch.kill", "no_outbound_from_agent_bus"],
    }
    ledger["agents"][child["id"]] = child
    log_event(ledger, ts, "spawn", agent=child["id"], parent=parent["id"], role=role,
              level=child["level"], job_ref=job_ref)
    return child


def assign(ledger: dict, caller_id: str, assignee_id: str, task: str, ts: datetime,
           parent_action_id: str | None = None, job_ref: str | None = None,
           aaron: bool = False) -> dict:
    """synapse.assign_task — child ticket / mesh job queued on assignee."""
    require_motor("synapse.assign_task", ledger)
    caller = resolve_actor(ledger, caller_id, aaron)
    assignee = get_agent(ledger, assignee_id)
    if caller["kind"] == "agent" and "assign_task" not in caller["privileges"]:
        raise SystemExit(f"{caller['id']} lacks assign_task")
    if assignee["status"] != "active":
        raise SystemExit(f"assignee {assignee['id']} is {assignee['status']}")
    if parent_action_id and not any(a["id"] == parent_action_id for a in ledger["actions"]):
        raise SystemExit(f"unknown parent action: {parent_action_id}")
    action = {
        "id": short_id("act"),
        "task": task.strip(),
        "from": caller["id"],
        "assignee": assignee["id"],
        "status": "open",
        "parent_action": parent_action_id,
        "job_ref": job_ref,
        "created": iso(ts),
        "updated": iso(ts),
        "distillate": None,
    }
    ledger["actions"].append(action)
    log_event(ledger, ts, "assign_task", action=action["id"], assignee=assignee["id"], by=caller["id"])
    return action


def find_action(ledger: dict, action_id: str) -> dict:
    for a in ledger["actions"]:
        if a["id"] == action_id:
            return a
    matches = [a for a in ledger["actions"] if a["id"].startswith(action_id)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(f"ambiguous action id prefix {action_id!r}")
    raise SystemExit(f"unknown action: {action_id}")


def resolve(ledger: dict, caller_id: str, action_id: str, status: str, ts: datetime,
            distillate: str | None = None, aaron: bool = False) -> dict:
    """synapse.resolve_task — close/transition; notify parent action holder."""
    if status not in ACTION_STATUSES[1:]:
        raise SystemExit(f"status must be one of {ACTION_STATUSES[1:]}")
    caller = resolve_actor(ledger, caller_id, aaron)
    action = find_action(ledger, action_id)
    if caller["kind"] == "agent" and "resolve_task" not in caller["privileges"]:
        raise SystemExit(f"{caller['id']} lacks resolve_task")
    if caller["kind"] == "agent" and caller["id"] not in (action["assignee"], action["from"]) \
            and not is_ancestor(ledger, caller["id"], action["assignee"]):
        raise SystemExit(f"{caller['id']} is neither party nor ancestor of action {action['id']}")
    action["status"] = status
    action["updated"] = iso(ts)
    action["distillate"] = (distillate or "").strip() or None
    log_event(ledger, ts, "resolve_task", action=action["id"], status=status, by=caller["id"])
    if action["from"] != caller["id"]:
        ledger["commute"].append({
            "ts": iso(ts), "kind": "send_message", "from": caller["id"], "to": action["from"],
            "action": action["id"], "message": f"resolved {status}: {action['task'][:80]}",
        })
    return action


def send_message(ledger: dict, sender_id: str, to_id: str, message: str, ts: datetime,
                 action_id: str | None = None, aaron: bool = False) -> dict:
    """synapse.send_message — internal agent bus only (never motor.text)."""
    require_motor("synapse.send_message", ledger)
    sender = resolve_actor(ledger, sender_id, aaron)
    target = get_agent(ledger, to_id)
    if sender["kind"] == "agent" and "send_message" not in sender["privileges"]:
        raise SystemExit(f"{sender['id']} lacks send_message")
    entry = {"ts": iso(ts), "kind": "send_message", "from": sender["id"], "to": target["id"],
             "action": action_id, "message": message.strip()}
    ledger["commute"].append(entry)
    return entry


def broadcast(ledger: dict, sender_id: str, channel: str, message: str, ts: datetime,
              aaron: bool = False) -> dict:
    """synapse.broadcast — fan-out to a team channel; sender excluded."""
    require_motor("synapse.broadcast", ledger)
    sender = resolve_actor(ledger, sender_id, aaron)
    if sender["kind"] == "agent" and "broadcast" not in sender["privileges"]:
        raise SystemExit(f"{sender['id']} lacks broadcast")
    channels = broadcast_channels()
    if channel not in channels:
        raise SystemExit(f"unknown broadcast channel {channel!r}; known: {channels}")
    team = channel.split(".", 1)[1] if channel.startswith("team.") else None
    recipients = [
        a["id"] for a in ledger["agents"].values()
        if a["kind"] == "agent" and a["status"] == "active" and a["id"] != sender["id"]
        and (channel == "mesh.all" or a.get("team") == f"team.{team}")
    ]
    entry = {"ts": iso(ts), "kind": "broadcast", "from": sender["id"], "channel": channel,
             "recipients": recipients, "message": message.strip()}
    ledger["commute"].append(entry)
    return entry


def terminate(ledger: dict, caller_id: str, target_id: str, reason: str, ts: datetime,
              aaron: bool = False) -> list[str]:
    """synapse.terminate_lineage — ancestor or Aaron cancels a descendant tree."""
    caller = resolve_actor(ledger, caller_id, aaron)
    target = get_agent(ledger, target_id)
    if target["id"] in (AARON_ID, CHIEF_ID) and caller["id"] != AARON_ID:
        raise SystemExit(f"only Aaron may terminate {target['id']}")
    if caller["id"] != AARON_ID:
        if "terminate_lineage" not in caller["privileges"]:
            raise SystemExit(f"{caller['id']} lacks terminate_lineage")
        if not is_ancestor(ledger, caller["id"], target["id"]):
            raise SystemExit(f"{caller['id']} is not an ancestor of {target['id']}")
    victims = [target] + descendants(ledger, target["id"])
    ids = []
    for v in victims:
        if v["id"] == AARON_ID:
            continue
        v["status"] = "terminated"
        v["terminated"] = {"ts": iso(ts), "by": caller["id"], "reason": reason}
        ids.append(v["id"])
        for a in ledger["actions"]:
            if a["assignee"] == v["id"] and a["status"] == "open":
                a["status"] = "cancelled"
                a["updated"] = iso(ts)
                a["distillate"] = f"lineage terminated: {reason}"
    log_event(ledger, ts, "terminate_lineage", target=target["id"], by=caller["id"],
              reason=reason, cancelled=ids)
    return ids


# --- introspection ----------------------------------------------------------

def doctor(ledger: dict) -> list[str]:
    problems: list[str] = []
    forbidden = aaron_only()
    agents = ledger["agents"]
    if agents.get(AARON_ID, {}).get("level") != 0:
        problems.append("human.aaron must be level 0")
    chief = agents.get(CHIEF_ID)
    if not chief or chief.get("level") != 1 or chief.get("parent") != AARON_ID:
        problems.append("chief must be level 1 under human.aaron")
    for cyc in lineage_cycles(ledger):
        problems.append(f"lineage cycle: {cyc} never reaches a root (tampered ledger)")
    sticky = non_inheritable()
    for a in agents.values():
        if a["kind"] != "agent":
            continue
        if set(a["privileges"]) & forbidden:
            problems.append(f"{a['id']} holds Aaron-only privileges {sorted(set(a['privileges']) & forbidden)}")
        if a["id"] != CHIEF_ID and set(a["privileges"]) & sticky:
            problems.append(f"{a['id']} holds chief-only privileges {sorted(set(a['privileges']) & sticky)}")
        if a["role"] in RESERVED_ROLES and a["id"] != CHIEF_ID:
            problems.append(f"{a['id']} uses reserved role {a['role']!r}")
        parent = agents.get(a.get("parent") or "")
        if not parent:
            problems.append(f"{a['id']} has no parent")
            continue
        if a["level"] != parent["level"] + 1:
            problems.append(f"{a['id']} level {a['level']} != parent level {parent['level']} + 1")
        if not set(a["privileges"]) <= (set(parent["privileges"]) - forbidden):
            problems.append(f"{a['id']} escalates beyond parent {parent['id']}")
        if parent["status"] == "terminated" and a["status"] == "active":
            problems.append(f"{a['id']} active under terminated parent {parent['id']}")
    for act in ledger["actions"]:
        if act["status"] not in ACTION_STATUSES:
            problems.append(f"action {act['id']} has bad status {act['status']}")
        if act["assignee"] not in agents:
            problems.append(f"action {act['id']} assignee {act['assignee']} unknown")
    server = server_lineage_summary()
    if server and server.get("aaron_only_leaks"):
        problems.append(f"server lineage grants Aaron-only privileges: {server['aaron_only_leaks']}")
    if server and server.get("error"):
        problems.append(f"server lineage unreadable: {server['path']}")
    if SEAL_STATE.get("lineage") == "mismatch":
        problems.append("lineage HMAC seal mismatch — ledger edited outside cam_swarm (or key rotated)")
    if ledger_says_killed(ledger) and not kill_flag_path().exists() \
            and os.environ.get("CAM_SWITCH_KILL", "").lower() != "act":
        problems.append("KILL flag removed without `resume --aaron` — ledger still says killed; spawn stays silenced")
    seal = privacy.read_seal(data_dir())
    if seal and seal.get("principal") != privacy.current_principal():
        problems.append(f"lineage dir sealed to {seal.get('principal')!r}, process is {privacy.current_principal()!r}")
    return problems


def tree_lines(ledger: dict) -> list[str]:
    lines: list[str] = []
    agents = ledger["agents"]
    open_by_agent: dict[str, int] = {}
    for act in ledger["actions"]:
        if act["status"] == "open":
            open_by_agent[act["assignee"]] = open_by_agent.get(act["assignee"], 0) + 1

    def walk(agent_id: str, depth: int) -> None:
        a = agents[agent_id]
        mark = "" if a["status"] == "active" else f" [{a['status']}]"
        opens = open_by_agent.get(agent_id, 0)
        extra = f" · {opens} open" if opens else ""
        job = f" · {a['job_ref']}" if a.get("job_ref") else ""
        lines.append(f"{'  ' * depth}{a['id']} ({a['role']}, L{a['level']}){mark}{extra}{job}")
        for child in sorted((c for c in agents.values() if c.get("parent") == agent_id),
                            key=lambda c: c["created"]):
            walk(child["id"], depth + 1)

    if AARON_ID in agents:
        walk(AARON_ID, 0)
    return lines


def server_lineage_path() -> Path:
    """The neural-mesh server (server/core/swarm-runtime.ts) keeps its own
    lineage with a different schema; we read it, never write it."""
    override = os.environ.get("CAM_SWARM_SERVER_LINEAGE")
    return Path(override) if override else ROOT / "data/swarm-lineage.json"


def server_lineage_summary() -> dict | None:
    path = server_lineage_path()
    if not path.exists():
        return None
    try:
        state = load_json(path)
    except json.JSONDecodeError:
        return {"path": str(path), "error": "corrupt"}
    agents = state.get("agents") or []
    forbidden = aaron_only()
    escalations = [a["id"] for a in agents if set(a.get("privileges") or []) & forbidden]
    active = [a for a in agents if a.get("status") == "active"]
    return {
        "path": str(path),
        "updated": state.get("updatedAt"),
        "agents_active": len(active),
        "agents_terminated": len([a for a in agents if a.get("status") == "terminated"]),
        "max_level": max((int(a.get("level") or 0) for a in agents), default=0),
        "events": len(state.get("events") or []),
        "aaron_only_leaks": escalations,
    }


def stats(ledger: dict) -> dict:
    agents = [a for a in ledger["agents"].values() if a["kind"] == "agent"]
    active = [a for a in agents if a["status"] == "active"]
    by_role: dict[str, int] = {}
    by_team: dict[str, int] = {}
    for a in active:
        by_role[a["role"]] = by_role.get(a["role"], 0) + 1
        if a.get("team"):
            by_team[a["team"]] = by_team.get(a["team"], 0) + 1
    actions = ledger["actions"]
    return {
        "agents_total": len(agents),
        "agents_active": len(active),
        "agents_terminated": len([a for a in agents if a["status"] == "terminated"]),
        "max_level": max((a["level"] for a in agents), default=0),
        "by_role": dict(sorted(by_role.items())),
        "by_team": dict(sorted(by_team.items())),
        "actions": {s: len([a for a in actions if a["status"] == s]) for s in ACTION_STATUSES},
        "commute_messages": len(ledger["commute"]),
        "kill_active": kill_active(ledger),
        "unlimited_spawn": True,
        "principal": privacy.current_principal(),
        "seal": SEAL_STATE.get("lineage"),
        "server_runtime": server_lineage_summary(),
    }


def distill(ledger: dict, ts: datetime) -> dict:
    """Counts-only mesh distillate — no task text, no mandates, no messages.
    The privacy kernel re-checks that claim before anything is written: a
    distillate carrying any personal class or secret is refused (charter P1).
    Guest principals distill into their own root, never the owner's vault."""
    doc = {
        "kind": "agent-lineage",
        "generated": iso(ts),
        "source": "scripts/cam_swarm.py",
        "sole_operator": "Aaron",
        "principal": privacy.current_principal(),
        "stats": stats(ledger),
        "doctor": doctor(ledger),
        "recent_events": [
            {k: v for k, v in e.items() if k in ("ts", "kind", "role", "level", "status")}
            for e in ledger["events"][-20:]
        ],
    }
    if privacy.is_owner():
        doc = privacy.assert_shareable(doc, "mesh_distillate")
    else:
        doc = privacy.assert_operational(doc, "guest agent-lineage distillate")
    out = mesh_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def gc(ledger: dict, ts: datetime, older_than: timedelta) -> dict:
    """Archive lineages terminated before `ts - older_than` (plus their
    actions / commute) to data/swarm/archive/, mirroring the server's
    lineage-guardian cap on ephemeral workers. Nothing is deleted — the
    archive file keeps the records; the live ledger just stops growing."""
    cutoff = iso(ts - older_than)
    agents = ledger["agents"]
    old = {a["id"] for a in agents.values()
           if a["kind"] == "agent" and a["id"] != CHIEF_ID and a["status"] == "terminated"
           and (a.get("terminated") or {}).get("ts", "9999") < cutoff}
    # only lineages whose whole subtree is archivable go — never orphan a child
    removable: set[str] = set()
    for aid in old:
        subtree = {d["id"] for d in descendants(ledger, aid)}
        if subtree <= old:
            removable.add(aid)
    if not removable:
        return {"archived_agents": 0, "archived_actions": 0, "archived_commute": 0, "cutoff": cutoff}
    arch_agents = {aid: agents.pop(aid) for aid in removable}
    arch_actions = [a for a in ledger["actions"] if a["assignee"] in removable and a["status"] != "open"]
    ledger["actions"] = [a for a in ledger["actions"] if not (a["assignee"] in removable and a["status"] != "open")]
    arch_commute = [c for c in ledger["commute"] if c.get("from") in removable or c.get("to") in removable]
    ledger["commute"] = [c for c in ledger["commute"] if not (c.get("from") in removable or c.get("to") in removable)]
    archive_dir().mkdir(parents=True, exist_ok=True)
    privacy.harden_dir(archive_dir())
    out = archive_dir() / f"lineage-{ts.strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps({"archived": iso(ts), "cutoff": cutoff, "agents": arch_agents,
                               "actions": arch_actions, "commute": arch_commute}, indent=2) + "\n", encoding="utf-8")
    privacy.harden_file(out)
    log_event(ledger, ts, "gc", archived=len(arch_agents), archive=out.name)
    return {"archived_agents": len(arch_agents), "archived_actions": len(arch_actions),
            "archived_commute": len(arch_commute), "cutoff": cutoff, "archive": str(out)}


# --- CLI --------------------------------------------------------------------

def _dump(obj) -> int:
    print(json.dumps(obj, indent=2))
    return 0


def cmd_spawn(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    child = spawn(ledger, args.parent, args.role, ts, privileges=args.privilege or None,
                  mandate=args.mandate, job_ref=args.job, team=args.team, aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "agent": child})


def cmd_assign(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    action = assign(ledger, args.caller, args.assignee, args.task, ts,
                    parent_action_id=args.parent_action, job_ref=args.job, aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "action": action})


def cmd_resolve(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    action = resolve(ledger, args.caller, args.action, args.status, ts, distillate=args.distillate,
                     aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "action": action})


def cmd_send(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    entry = send_message(ledger, args.sender, args.to, args.message, ts, action_id=args.action,
                         aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "message": entry})


def cmd_broadcast(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    entry = broadcast(ledger, args.sender, args.channel, args.message, ts, aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "broadcast": entry})


def cmd_terminate(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    ids = terminate(ledger, args.caller, args.target, args.reason, ts, aaron=args.aaron)
    save_ledger(ledger)
    return _dump({"ok": True, "terminated": ids})


def cmd_kill(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    kill_flag_path().parent.mkdir(parents=True, exist_ok=True)
    kill_flag_path().write_text(f"{iso(ts)} {args.reason}\n", encoding="utf-8")
    log_event(ledger, ts, "kill_master", by=AARON_ID, reason=args.reason)
    save_ledger(ledger)
    return _dump({"ok": True, "switch.kill": "act", "note": "spawn/assign/broadcast silenced; records retained"})


def cmd_resume(args: argparse.Namespace) -> int:
    if not args.aaron:
        raise SystemExit("resume is Aaron's call: re-run with --aaron (kill stays fail-safe for anyone)")
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    if kill_flag_path().exists():
        kill_flag_path().unlink()
    log_event(ledger, ts, "kill_resume", by=AARON_ID)
    save_ledger(ledger)
    return _dump({"ok": True, "switch.kill": "armed_allow_motor"})


def cmd_tree(args: argparse.Namespace) -> int:
    ledger = load_ledger(now_utc(args.now))
    print("\n".join(tree_lines(ledger)) or "(empty)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    return _dump(stats(load_ledger(now_utc(args.now))))


def cmd_agents(args: argparse.Namespace) -> int:
    ledger = load_ledger(now_utc(args.now))
    rows = [a for a in ledger["agents"].values() if args.all or a["status"] == "active"]
    return _dump(rows)


def cmd_actions(args: argparse.Namespace) -> int:
    ledger = load_ledger(now_utc(args.now))
    rows = [a for a in ledger["actions"] if args.all or a["status"] == "open"]
    return _dump(rows)


def cmd_doctor(args: argparse.Namespace) -> int:
    ledger = load_ledger(now_utc(args.now))
    problems = doctor(ledger)
    _dump({"ok": not problems, "problems": problems, "stats": stats(ledger)})
    return 0 if not problems else 1


def cmd_distill(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    doc = distill(load_ledger(ts), ts)
    return _dump({"ok": True, "out": str(mesh_out_path()), "stats": doc["stats"]})


DURATION_RE = re.compile(r"^(\d+)([hdw])$")


def parse_duration(s: str) -> timedelta:
    m = DURATION_RE.match((s or "").strip())
    if not m:
        raise SystemExit("duration must look like 30d, 12h or 2w")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(hours=n) if unit == "h" else timedelta(days=n * (7 if unit == "w" else 1))


def cmd_gc(args: argparse.Namespace) -> int:
    ts = now_utc(args.now)
    ledger = load_ledger(ts)
    result = gc(ledger, ts, parse_duration(args.older_than))
    if result["archived_agents"]:
        save_ledger(ledger)
    return _dump({"ok": True, **result})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cam swarm runtime — spawn / assign / resolve / terminate")
    parser.add_argument("--now", help="override clock (ISO8601)")
    parser.add_argument("--aaron", action="store_true",
                        help="I am Aaron at the CLI: allows acting as / spawning under human.aaron and `resume`")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("spawn", help="synapse.spawn — child at parent.level + 1")
    p.add_argument("role")
    p.add_argument("--parent", default=CHIEF_ID)
    p.add_argument("--privilege", action="append", help="explicit privilege (repeatable, ⊆ parent)")
    p.add_argument("--mandate")
    p.add_argument("--job", help="Instinct job ref (job:<id>)")
    p.add_argument("--team", help="team id for broadcast membership")
    p.set_defaults(fn=cmd_spawn)

    p = sub.add_parser("assign", help="synapse.assign_task")
    p.add_argument("assignee")
    p.add_argument("task")
    p.add_argument("--caller", default=CHIEF_ID)
    p.add_argument("--parent-action")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_assign)

    p = sub.add_parser("resolve", help="synapse.resolve_task")
    p.add_argument("action")
    p.add_argument("status", choices=ACTION_STATUSES[1:])
    p.add_argument("--caller", default=CHIEF_ID)
    p.add_argument("--distillate")
    p.set_defaults(fn=cmd_resolve)

    p = sub.add_parser("send", help="synapse.send_message (internal bus)")
    p.add_argument("to")
    p.add_argument("message")
    p.add_argument("--sender", default=CHIEF_ID)
    p.add_argument("--action")
    p.set_defaults(fn=cmd_send)

    p = sub.add_parser("broadcast", help="synapse.broadcast to a team channel")
    p.add_argument("channel")
    p.add_argument("message")
    p.add_argument("--sender", default=CHIEF_ID)
    p.set_defaults(fn=cmd_broadcast)

    p = sub.add_parser("terminate", help="synapse.terminate_lineage")
    p.add_argument("target")
    p.add_argument("--caller", default=CHIEF_ID)
    p.add_argument("--reason", default="done")
    p.set_defaults(fn=cmd_terminate)

    p = sub.add_parser("kill", help="Aaron master kill — silence spawn/assign/broadcast")
    p.add_argument("--reason", default="aaron kill")
    p.set_defaults(fn=cmd_kill)
    p = sub.add_parser("resume", help="Aaron re-arms the swarm")
    p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("tree", help="lineage tree")
    p.set_defaults(fn=cmd_tree)
    p = sub.add_parser("stats", help="counts")
    p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("agents", help="list agents")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_agents)
    p = sub.add_parser("actions", help="list actions")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_actions)
    p = sub.add_parser("doctor", help="lineage invariants")
    p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("distill", help="counts-only mesh distillate")
    p.set_defaults(fn=cmd_distill)
    p = sub.add_parser("gc", help="archive lineages terminated longer ago than --older-than")
    p.add_argument("--older-than", default="30d", help="30d | 12h | 2w (default 30d)")
    p.set_defaults(fn=cmd_gc)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
