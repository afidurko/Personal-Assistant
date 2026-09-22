"""Sentinel — sole permission authority at Cam's motor boundary.

Borrowed from Meta Muse: the agent proposes, a separate authority decides
allow / deny / ask, approvals are scoped capabilities (once / session / task /
until / perpetual), and a plan that read untrusted data loses auto-allow for
egress ("tainted egress"). Switches still strip first; Sentinel judges what
survives and journals the intent before any effect runs.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cam_journal as cj

ROOT = Path(__file__).resolve().parents[1]
POL_PATH = ROOT / "config" / "connectome" / "sentinel-policy.json"

_POLICY: dict | None = None
_GRANTS_CACHE: tuple[float, list[dict]] | None = None


def load_policy() -> dict:
    global _POLICY
    if _POLICY is None:
        _POLICY = json.loads(POL_PATH.read_text(encoding="utf-8"))
    return _POLICY


def enforced(policy: dict | None = None) -> bool:
    return bool((policy or load_policy()).get("enforce", True))


def class_of(motor: str, policy: dict | None = None) -> str | None:
    for name, spec in (policy or load_policy()).get("classes", {}).items():
        if motor in (spec.get("motors") or []):
            return name
    return None


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- taint --------------------------------------------------------------------

def taint_for(
    sense: str,
    pathway: list[str] | tuple[str, ...],
    motor_plan: list[str],
    policy: dict | None = None,
) -> dict:
    pol = policy or load_policy()
    cfg = pol.get("taint") or {}
    untrusted = set(cfg.get("untrusted_senses") or [])
    taint_motors = set(cfg.get("taint_on_motors") or [])
    sources = []
    for node in [sense, *pathway]:
        if node in untrusted and node not in sources:
            sources.append(node)
    for m in motor_plan:
        if m in taint_motors and m not in sources:
            sources.append(m)
    return {"tainted": bool(sources), "sources": sources}


# --- grants -------------------------------------------------------------------

def grants_path(policy: dict | None = None) -> Path:
    return ROOT / (policy or load_policy()).get("grants_file", "data/runtime/sentinel-grants.json")


def load_grants(policy: dict | None = None) -> list[dict]:
    global _GRANTS_CACHE
    p = grants_path(policy)
    if not p.exists():
        return []
    mtime = p.stat().st_mtime
    if _GRANTS_CACHE and _GRANTS_CACHE[0] == mtime:
        return _GRANTS_CACHE[1]
    try:
        grants = json.loads(p.read_text(encoding="utf-8")).get("grants") or []
    except (json.JSONDecodeError, AttributeError):
        grants = []
    _GRANTS_CACHE = (mtime, grants)
    return grants


def save_grants(grants: list[dict], policy: dict | None = None) -> None:
    global _GRANTS_CACHE
    p = grants_path(policy)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"updated_at": cj.utc(), "grants": grants}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _GRANTS_CACHE = None


def session_path(policy: dict | None = None) -> Path:
    return ROOT / (policy or load_policy()).get("session_file", "data/runtime/sentinel-session.json")


def current_session_id(policy: dict | None = None) -> str:
    p = session_path(policy)
    if p.exists():
        try:
            sid = json.loads(p.read_text(encoding="utf-8")).get("session_id")
            if sid:
                return str(sid)
        except json.JSONDecodeError:
            pass
    return new_session(policy)


def new_session(policy: dict | None = None) -> str:
    """Rotate the session — session-scoped grants stop matching."""
    p = session_path(policy)
    p.parent.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex[:12]
    p.write_text(json.dumps({"session_id": sid, "started_at": cj.utc()}) + "\n", encoding="utf-8")
    return sid


def grant(
    motor: str,
    scope: str,
    *,
    by: str,
    task: str | None = None,
    until: str | None = None,
    covers_tainted: bool = False,
    reason: str = "",
    policy: dict | None = None,
    persist: bool = True,
) -> dict:
    pol = policy or load_policy()
    if by != pol.get("sole_operator", "Aaron"):
        raise PermissionError(f"only {pol.get('sole_operator')} may grant (got {by!r})")
    if scope not in (pol.get("grant_scopes") or []):
        raise ValueError(f"unknown grant scope: {scope}")
    if scope == "task" and not task:
        raise ValueError("task scope needs --task")
    if scope == "until" and not _parse_ts(until):
        raise ValueError("until scope needs an ISO-8601 --until")
    g = {
        "id": uuid.uuid4().hex[:12],
        "motor": motor,
        "scope": scope,
        "granted_by": by,
        "granted_at": cj.utc(),
        "covers_tainted": bool(covers_tainted),
        "reason": reason,
    }
    if scope == "task":
        g["task"] = task
    if scope == "until":
        g["until"] = until
    if scope == "session":
        g["session_id"] = current_session_id(pol)
    if persist:
        grants = list(load_grants(pol))
        grants.append(g)
        save_grants(grants, pol)
    return g


def revoke(grant_id: str | None = None, *, all_grants: bool = False, policy: dict | None = None) -> int:
    grants = list(load_grants(policy))
    keep = [] if all_grants else [g for g in grants if g.get("id") != grant_id]
    removed = len(grants) - len(keep)
    save_grants(keep, policy)
    return removed


def consume_once(grant_id: str, policy: dict | None = None) -> None:
    grants = [g for g in load_grants(policy) if g.get("id") != grant_id]
    save_grants(grants, policy)


def _grant_matches(
    g: dict,
    motor: str,
    *,
    task: str,
    now: datetime,
    session_id: str | None,
    tainted: bool,
) -> bool:
    if g.get("motor") not in (motor, "*"):
        return False
    if tainted and not g.get("covers_tainted"):
        return False
    scope = g.get("scope")
    if scope in ("once", "perpetual"):
        return True
    if scope == "task":
        return bool(task) and g.get("task") == task
    if scope == "until":
        exp = _parse_ts(g.get("until"))
        return bool(exp) and now < exp
    if scope == "session":
        return bool(session_id) and g.get("session_id") == session_id
    return False


def active_grant(
    motor: str,
    *,
    task: str = "",
    now: datetime | None = None,
    session_id: str | None = None,
    tainted: bool = False,
    grants: list[dict] | None = None,
    switch_state: dict[str, str] | None = None,
    policy: dict | None = None,
) -> dict | None:
    """Runtime grants (Aaron, scoped) first, then standing grants bound to an act switch."""
    pol = policy or load_policy()
    ts = _now(now)
    for g in grants if grants is not None else load_grants(pol):
        if _grant_matches(g, motor, task=task, now=ts, session_id=session_id, tainted=tainted):
            return g
    for sg in pol.get("standing_grants") or []:
        if motor not in (sg.get("covers") or []):
            continue
        if tainted and not sg.get("covers_tainted"):
            continue
        if (switch_state or {}).get(sg.get("switch"), "act") != "act":
            continue
        return sg
    return None


# --- decision -----------------------------------------------------------------

def _guardrail_hit(paths: list[str] | tuple[str, ...], policy: dict) -> str | None:
    rails = policy.get("guardrail_paths") or []
    root = str(ROOT).replace("\\", "/").rstrip("/") + "/"
    for raw in paths:
        rel = str(raw).replace("\\", "/")
        if rel.startswith(root):
            rel = rel[len(root):]
        while rel.startswith("./"):
            rel = rel[2:]
        for rail in rails:
            if rel == rail or (rail.endswith("/") and rel.startswith(rail)) or rel.endswith("/" + rail):
                return rel
    return None


def _private_hit(paths: list[str] | tuple[str, ...], policy: dict) -> str | None:
    """First plan path inside private memory, or None (docs/PRIVACY_SAFEGUARDS.md)."""
    cfg = policy.get("private_memory") or {}
    globs = cfg.get("paths") or []
    if not globs or not paths:
        return None
    root = str(ROOT).replace("\\", "/").rstrip("/") + "/"
    for raw in paths:
        rel = str(raw).replace("\\", "/")
        if rel.startswith(root):
            rel = rel[len(root):]
        while rel.startswith("./"):
            rel = rel[2:]
        rel = rel.lstrip("/")
        for g in globs:
            body = g.rstrip("/")
            if body.startswith("**/"):
                if ("/" + body[3:] + "/") in ("/" + rel + "/"):
                    return rel
            elif rel == body or rel.startswith(body + "/"):
                return rel
    return None


def _private_denies(motor: str, cls: str | None, policy: dict) -> bool:
    cfg = policy.get("private_memory") or {}
    return motor in (cfg.get("deny_motors") or []) or (cls in (cfg.get("deny_classes") or []))


def evaluate(
    motor_plan: list[str],
    *,
    sense: str = "",
    pathway: list[str] | tuple[str, ...] = (),
    switch_state: dict[str, str] | None = None,
    task: str = "",
    paths: list[str] | tuple[str, ...] = (),
    now: datetime | None = None,
    session_id: str | None = None,
    grants: list[dict] | None = None,
    policy: dict | None = None,
) -> dict:
    """Decide allow / deny / ask for every motor in a plan. Pure — no journal writes."""
    pol = policy or load_policy()
    state = switch_state or {}
    taint = taint_for(sense, pathway, motor_plan, pol)
    lose = set((pol.get("taint") or {}).get("classes_lose_auto_allow") or [])
    rail = _guardrail_hit(paths, pol)
    private_path = _private_hit(paths, pol)
    decisions: dict[str, dict] = {}
    allowed: list[str] = []
    pending: list[str] = []
    denied: list[str] = []
    kill = state.get("switch.kill") == "act"

    for motor in motor_plan:
        cls = class_of(motor, pol)
        row: dict = {"class": cls}
        if kill:
            row.update(decision="deny", reason="switch.kill act")
        elif private_path and _private_denies(motor, cls, pol):
            row.update(
                decision="deny",
                reason=f"private memory path {private_path} — personal information never leaves the host",
                private_path=private_path,
            )
        elif cls is None:
            row.update(
                decision=pol.get("unknown_motor_decision", "ask"),
                reason="unknown motor — fail closed",
                grant_options=["once"],
            )
        elif rail and cls in ("write_local", "self_modify"):
            row.update(
                decision="ask",
                reason=f"guardrail path {rail} — no standing grant possible",
                grant_options=list(pol.get("guardrail_grant_scopes") or ["once"]),
            )
        elif (pol["classes"][cls].get("default") or "allow") == "allow":
            row.update(decision="allow", reason=f"class {cls} default allow", authorizer="policy")
        else:
            tainted = taint["tainted"] and cls in lose
            g = active_grant(
                motor,
                task=task,
                now=now,
                session_id=session_id,
                tainted=tainted,
                grants=grants,
                switch_state=state,
                policy=pol,
            )
            if g:
                row.update(
                    decision="allow",
                    reason=f"grant:{g.get('scope')}:{g.get('granted_by')}",
                    authorizer=f"grant:{g.get('scope')}:{g.get('granted_by')}",
                    grant_id=g.get("id"),
                    grant_scope=g.get("scope"),
                )
            else:
                row.update(
                    decision="ask",
                    reason=(
                        f"tainted egress — plan read {', '.join(taint['sources'])}"
                        if tainted
                        else f"class {cls} requires Aaron grant"
                    ),
                    grant_options=list(
                        pol.get("tainted_grant_scopes" if tainted else "grant_scopes") or []
                    ),
                )
            row["tainted"] = tainted
        decisions[motor] = row
        {"allow": allowed, "ask": pending, "deny": denied}[row["decision"]].append(motor)

    return {
        "authority": "sentinel",
        "enforced": enforced(pol),
        "taint": taint,
        "private_path": private_path,
        "decisions": decisions,
        "allowed": allowed,
        "pending": pending,
        "denied": denied,
    }


# --- journal binding ----------------------------------------------------------

def record(
    evaluation: dict,
    *,
    sense: str = "",
    goal: str = "",
    session_id: str = "cli",
    day: str | None = None,
) -> dict:
    """Journal a decided plan: intents for allows, requests for asks, denies for denies."""
    motors = list(evaluation.get("decisions") or {})
    proposed = cj.append(
        "proposed",
        {"sense": sense, "goal": goal[:240], "motor_plan": motors, "taint": evaluation.get("taint")},
        session_id=session_id,
        day=day,
    )
    intents, requests, denies = [], [], []
    for motor, row in (evaluation.get("decisions") or {}).items():
        if row["decision"] == "allow":
            intents.append(
                cj.append(
                    "side_effect_intent",
                    {
                        "motor": motor,
                        "policy_decision": f"allow:{row.get('authorizer', 'policy')}",
                        "idempotency_key": cj.idempotency_key(motor, sense, goal, str(proposed["sequence"])),
                        "tainted": bool(row.get("tainted")),
                    },
                    session_id=session_id,
                    day=day,
                )
            )
            if row.get("grant_scope") == "once" and row.get("grant_id"):
                consume_once(row["grant_id"])
        elif row["decision"] == "ask":
            requests.append(
                cj.append(
                    "approval.requested",
                    {
                        "pending_id": uuid.uuid4().hex[:12],
                        "motor": motor,
                        "class": row.get("class"),
                        "purpose": goal[:240] or sense,
                        "reason": row.get("reason"),
                        "tainted": bool(row.get("tainted")),
                        "grant_options": row.get("grant_options") or [],
                        "sense": sense,
                    },
                    session_id=session_id,
                    day=day,
                )
            )
        else:
            denies.append(
                cj.append(
                    "decision_applied",
                    {
                        "pending_id": None,
                        "motor": motor,
                        "decision": "denied",
                        "decision_source": {"kind": "policy", "reason": row.get("reason")},
                    },
                    session_id=session_id,
                    day=day,
                )
            )
    return {
        "proposed_sequence": proposed["sequence"],
        "intents": [i["payload"]["idempotency_key"] for i in intents],
        "pending": [r["payload"]["pending_id"] for r in requests],
        "denied": [d["payload"]["motor"] for d in denies],
    }


def pending(day: str | None = None) -> list[dict]:
    rows = cj.read(day)
    decided = {
        (r.get("payload") or {}).get("pending_id")
        for r in rows
        if r.get("kind") == "decision_applied"
    }
    return [
        {"sequence": r.get("sequence"), "recorded_at": r.get("recorded_at"), **(r.get("payload") or {})}
        for r in rows
        if r.get("kind") == "approval.requested"
        and (r.get("payload") or {}).get("pending_id") not in decided
    ]


def _find_pending(pending_id: str, day: str | None) -> dict:
    for req in pending(day):
        if req.get("pending_id") == pending_id:
            return req
    raise KeyError(f"no open approval {pending_id}")


def approve(
    pending_id: str,
    *,
    scope: str,
    by: str,
    task: str | None = None,
    until: str | None = None,
    day: str | None = None,
    policy: dict | None = None,
) -> dict:
    """Aaron answers an approval.requested: decision_applied → grant → side_effect_intent."""
    pol = policy or load_policy()
    req = _find_pending(pending_id, day)
    options = req.get("grant_options") or []
    if scope not in options:
        raise ValueError(f"scope {scope!r} not offered for {pending_id}; options={options}")
    g = grant(
        req["motor"],
        scope,
        by=by,
        task=task or (req.get("purpose") if scope == "task" else None),
        until=until,
        covers_tainted=bool(req.get("tainted")),
        reason=f"approval {pending_id}",
        policy=pol,
        persist=scope != "once",
    )
    decision = cj.append(
        "decision_applied",
        {
            "pending_id": pending_id,
            "motor": req["motor"],
            "decision": "approved",
            "decision_source": {"kind": "aaron", "by": by, "scope": scope, "grant_id": g["id"]},
        },
        session_id=req.get("session_id", "cli"),
        day=day,
    )
    intent = cj.append(
        "side_effect_intent",
        {
            "motor": req["motor"],
            "policy_decision": f"allow:aaron:{scope}",
            "idempotency_key": cj.idempotency_key(req["motor"], pending_id),
            "tainted": bool(req.get("tainted")),
            "pending_id": pending_id,
        },
        day=day,
    )
    return {"decision": decision, "grant": g, "intent": intent}


def deny(pending_id: str, *, by: str, day: str | None = None, policy: dict | None = None) -> dict:
    pol = policy or load_policy()
    if by != pol.get("sole_operator", "Aaron"):
        raise PermissionError(f"only {pol.get('sole_operator')} may deny (got {by!r})")
    req = _find_pending(pending_id, day)
    return cj.append(
        "decision_applied",
        {
            "pending_id": pending_id,
            "motor": req["motor"],
            "decision": "denied",
            "decision_source": {"kind": "aaron", "by": by},
        },
        day=day,
    )
