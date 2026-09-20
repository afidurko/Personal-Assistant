#!/usr/bin/env python3
"""Cam Instinct — proactive follow-through engine (motor.instinct).

An original, local-first implementation of the behavior model popularized by
Instinct (Spear Street Technology): one continuous thread, a persistent job
ledger that survives between messages, and proactive follow-ups on dropped
threads. Divergences are deliberate (see config/integrations/instinct.md):
follow-ups are ALWAYS draft-only from this engine — live send hands off to
motor.inkbox under switch.outbound; nothing leaves the workspace; no spend.

Commands
  ingest   append a message to the single continuous thread
           (Aaron asks are tracked until answered; --reply-to closes an ask)
  job      add / note / wait / snooze / done / list persistent jobs
           (priorities tighten scan windows; --monitor makes a recurring watch)
  sync     fold event drops from data/instinct/inbox/*.json into the thread —
           the sensing seam for Inkbox / calendar / any Cam sense
  scan     detect unanswered asks, stale/overdue jobs, due monitor checks;
           emit spikes; --write drafts follow-ups; escalate needs_aaron items
  outbox   review drafted nudges: list / show / approve / discard
           (approve stages for motor.inkbox under switch.outbound — never sends)
  report   structured brief: jobs, asks, monitors, drafts, escalations
  brief    human-readable markdown daily brief (--write / --vault)
  stats    follow-through scorecard: done rate, time-to-done, ask answer rate
  find     search thread, job titles, and notes
  thread   show the continuous thread tail
  doctor   ledger + config sanity (offline, no key required)

Times accept ISO8601 or relative durations (+12h, +3d, +2w) against --now.

State lives in $INSTINCT_DATA_DIR (default data/instinct/): ledger.json,
spikes.jsonl, outbox/, inbox/, briefs/, needs-attention.json.
Deterministic: pass --now ISO8601 to override the clock for tests/demos.
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
CONFIG = ROOT / "config/integrations/instinct.json"

SENSE = "sense.instinct.followup"
MOTOR = "motor.instinct"

ASK_RE = re.compile(r"\?|\b(can you|could you|please|need to|remind me|don't forget|make sure)\b", re.I)

PRIORITY_WINDOW = {"high": 0.5, "normal": 1.0, "low": 2.0}


# --- paths (env-overridable so tests never touch real state) --------------


def data_dir() -> Path:
    override = os.environ.get("INSTINCT_DATA_DIR")
    return Path(override) if override else ROOT / "data/instinct"


def ledger_path() -> Path:
    return data_dir() / "ledger.json"


def spikes_path() -> Path:
    return data_dir() / "spikes.jsonl"


def outbox_dir() -> Path:
    return data_dir() / "outbox"


def inbox_dir() -> Path:
    return data_dir() / "inbox"


def briefs_dir() -> Path:
    return data_dir() / "briefs"


def escalations_path() -> Path:
    return data_dir() / "needs-attention.json"


def vault_briefs_dir() -> Path:
    override = os.environ.get("INSTINCT_VAULT_DIR")
    return Path(override) if override else ROOT / "vault/06-Life-Ops/instinct/briefs"


def mesh_out_path() -> Path:
    override = os.environ.get("INSTINCT_MESH_OUT")
    return Path(override) if override else ROOT / "vault/10-Mesh-Distillates/instinct/latest.json"


def attention_default_path() -> Path:
    return ROOT / "vault/10-Mesh-Distillates/needs-attention/latest.json"


# --- cross-workspace: registry + chooser (shared with run-cline / needs-attention)


DEFAULT_WORKSPACE = "personal-assistant"
JOB_KINDS = ("life", "coding", "attention")


def _cw():
    """cam_workspaces (registry + chooser); None if unavailable — never fatal."""
    try:
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        import cam_workspaces as cw  # noqa: WPS433
        return cw
    except Exception:  # pragma: no cover — registry missing in a foreign checkout
        return None


def _swarm():
    """cam_swarm (spawn runtime); None if unavailable — never fatal."""
    try:
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        import cam_swarm as swarm  # noqa: WPS433
        return swarm
    except Exception:  # pragma: no cover
        return None


# role picked for a job's subagent — by kind first, then by what the title is about
ROLE_BY_KIND = {"coding": "task-executor", "attention": "attention-triage"}
LIFE_ROLE_SIGNALS = [
    ("negotiator", ("bill", "subscription", "refund", "cancel", "dispute", "negotiate", "renewal", "rate", "fee")),
    ("scheduler", ("schedule", "calendar", "appointment", "meeting", "book", "reschedule", "prep for", "prep:")),
    ("watcher", ("monitor", "watch", "restock", "track", "price", "delivery", "status", "check on")),
]


def pick_role(job: dict) -> str:
    if job.get("kind") in ROLE_BY_KIND:
        return ROLE_BY_KIND[job["kind"]]
    if job.get("recur_hours"):
        return "watcher"
    title = (job.get("title") or "").lower()
    for role, signals in LIFE_ROLE_SIGNALS:
        if any(s in title for s in signals):
            return role
    return "errand-runner"


def known_workspaces() -> list[dict]:
    cw = _cw()
    if cw is None:
        return [{"id": DEFAULT_WORKSPACE, "label": "Personal-Assistant", "primary": True}]
    try:
        reg = cw.load_registry()
        return list((reg.get("layers") or {}).get("coding_workspaces") or cw.list_workspaces(reg))
    except Exception:
        return [{"id": DEFAULT_WORKSPACE, "label": "Personal-Assistant", "primary": True}]


def workspace_connected(ws_id: str) -> bool | None:
    cw = _cw()
    if cw is None:
        return None
    try:
        return bool(cw.workspace_exists(cw.get_workspace(ws_id)))
    except Exception:
        return None


def resolve_workspace(goal: str, workspace_id: str | None = None) -> tuple[str, str]:
    """Explicit id wins (validated against the registry); otherwise the shared
    chooser routes by goal text — the same brain run-cline uses."""
    ids = {w["id"] for w in known_workspaces()}
    if workspace_id:
        if ids and workspace_id not in ids:
            raise SystemExit(f"unknown workspace '{workspace_id}' — known: {', '.join(sorted(ids))}")
        return workspace_id, "explicit"
    cw = _cw()
    if cw is None:
        return DEFAULT_WORKSPACE, "chooser_unavailable"
    try:
        choice = cw.choose_workspace(goal=goal)
        return choice["workspace"]["id"], choice.get("reason", "chooser")
    except Exception:
        return DEFAULT_WORKSPACE, "chooser_error"


# --- time / io helpers ----------------------------------------------------


def now_utc(override: str | None = None) -> datetime:
    if override:
        return parse_ts(override)
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Naive inputs (e.g. --until 2026-09-18) are UTC, never host-local time.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


REL_RE = re.compile(r"^\+(\d+(?:\.\d+)?)([hdw])$")
REL_UNITS = {"h": 1.0, "d": 24.0, "w": 168.0}


def parse_when(s: str, ref: datetime) -> datetime:
    """Absolute ISO8601 or relative to ref: +12h, +3d, +2w."""
    m = REL_RE.match(s.strip())
    if m:
        return ref + timedelta(hours=float(m.group(1)) * REL_UNITS[m.group(2)])
    try:
        return parse_ts(s)
    except ValueError:
        raise SystemExit(
            f"invalid time '{s}' — use ISO8601 (2026-09-18T09:00:00Z) or relative (+12h, +3d, +2w)"
        )


def load_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {}


def defaults() -> dict:
    d = (load_config().get("defaults") or {})
    return {
        "stale_hours": d.get("stale_hours", 24),
        "reply_hours": d.get("reply_hours", 4),
        "max_followups": d.get("max_followups", 3),
        "draft_only": True,  # non-negotiable, not configurable
    }


def load_ledger() -> dict:
    p = ledger_path()
    if p.exists():
        try:
            ledger = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"ledger corrupt at {p} ({exc}) — restore from git/backup or move the file aside"
            )
        ledger.setdefault("version", 2)
        return ledger
    return {
        "version": 2,
        "created": iso(now_utc()),
        "thread": [],
        "jobs": [],
        "last_scan": None,
    }


def save_ledger(ledger: dict) -> None:
    """Atomic write (temp file + rename) so a crash mid-write never tears the ledger."""
    data_dir().mkdir(parents=True, exist_ok=True)
    tmp = ledger_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, ledger_path())


def emit_spike(kind: str, payload: dict, ts: datetime) -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    spike = {"ts": iso(ts), "sense": SENSE, "kind": kind, **payload}
    with spikes_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(spike) + "\n")


def short_id() -> str:
    return uuid.uuid4().hex[:8]


def find_job(ledger: dict, job_id: str) -> dict:
    matches = [j for j in ledger["jobs"] if j["id"] == job_id or j["id"].startswith(job_id)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"no job matching id '{job_id}'")
    raise SystemExit(f"ambiguous job id '{job_id}' ({', '.join(j['id'] for j in matches)})")


def new_job(title: str, ts: datetime, due: str | None = None, priority: str = "normal",
            recur_hours: float | None = None, origin_msg: str | None = None,
            workspace_id: str | None = None, kind: str = "life",
            source_ref: str | None = None) -> dict:
    if priority not in PRIORITY_WINDOW:
        raise SystemExit(f"priority must be one of {sorted(PRIORITY_WINDOW)}")
    if kind not in JOB_KINDS:
        raise SystemExit(f"kind must be one of {JOB_KINDS}")
    ws_id, ws_reason = resolve_workspace(title, workspace_id)
    return {
        "id": short_id(),
        "title": title,
        "status": "open",
        "kind": kind,
        "workspace": ws_id,
        "workspace_reason": ws_reason,
        "source_ref": source_ref,
        "created": iso(ts),
        "updated": iso(ts),
        # Validate + normalize at creation so a bad due date can never poison scans.
        "due": iso(parse_when(due, ts)) if due else None,
        "waiting_on": None,
        "priority": priority,
        "snooze_until": None,
        "recur_hours": recur_hours,
        "followups": 0,
        "last_followup": None,
        "notes": [],
        "origin_msg": origin_msg,
    }


def append_message(ledger: dict, sender: str, text: str, ts: datetime,
                   job_id: str | None = None, reply_to: str | None = None) -> dict:
    msg = {"id": short_id(), "ts": iso(ts), "from": sender, "text": text}
    if job_id:
        msg["job"] = job_id
    if sender == "aaron" and ASK_RE.search(text):
        msg["ask"] = True
    if reply_to:
        matches = [m for m in ledger["thread"]
                   if m["id"] == reply_to or m["id"].startswith(reply_to)]
        if not matches:
            raise SystemExit(f"no thread message matching '{reply_to}'")
        if len(matches) > 1:
            raise SystemExit(
                f"ambiguous reply-to '{reply_to}' ({', '.join(m['id'] for m in matches)})"
            )
        matches[0]["answered_by"] = msg["id"]
        msg["reply_to"] = matches[0]["id"]
    ledger["thread"].append(msg)
    return msg


def open_asks(ledger: dict) -> list[dict]:
    """Aaron messages that expect a response and were never answered or tied off."""
    asks = []
    for m in ledger["thread"]:
        if not m.get("ask") or m.get("answered_by"):
            continue
        # An ask that opened a job is tracked through the job, not double-counted;
        # it re-surfaces here only if the job was somehow deleted.
        if m.get("job") and any(j["id"] == m["job"] for j in ledger["jobs"]):
            continue
        asks.append(m)
    return asks


# --- commands -------------------------------------------------------------


def cmd_ingest(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    job_id = None
    if args.job:
        job = new_job(args.job, ts, due=args.due, priority=args.priority or "normal",
                      workspace_id=args.workspace, kind="coding" if args.coding else "life")
        ledger["jobs"].append(job)
        job_id = job["id"]
    msg = append_message(ledger, args.sender, args.text, ts, job_id=job_id, reply_to=args.reply_to)
    if job_id:
        for j in ledger["jobs"]:
            if j["id"] == job_id:
                j["origin_msg"] = msg["id"]
    save_ledger(ledger)
    print(json.dumps({"ok": True, "message": msg["id"], "job": job_id,
                      "tracked_ask": bool(msg.get("ask"))}, indent=2))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Fold external event drops into the thread. Each *.json file in the inbox
    is one event: {"from","text"[,"ts","job","due","priority","reply_to"]}.
    Senses (Inkbox, calendar, loops) write drops; this engine never fetches."""
    ledger = load_ledger()
    ts = now_utc(args.now)
    inbox = inbox_dir()
    processed_dir = inbox / "processed"
    folded, skipped = [], []
    for path in sorted(inbox.glob("*.json")):
        jobs_checkpoint = len(ledger["jobs"])
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
            sender = str(event.get("from") or "sense")
            text = str(event["text"])
            ev_ts = parse_ts(event["ts"]) if event.get("ts") else ts
            job_id = None
            if event.get("job"):
                ws = event.get("workspace")
                if ws and ws not in {w["id"] for w in known_workspaces()}:
                    ws = None  # unregistered (e.g. ad-hoc path): let the chooser route it
                job = new_job(str(event["job"]), ev_ts, due=event.get("due"),
                              priority=event.get("priority") or "normal",
                              workspace_id=ws,
                              kind=event.get("kind") or "life",
                              source_ref=event.get("source_ref"))
                ledger["jobs"].append(job)
                job_id = job["id"]
            msg = append_message(ledger, sender, text, ev_ts, job_id=job_id,
                                 reply_to=event.get("reply_to"))
            folded.append({"file": path.name, "message": msg["id"], "job": job_id})
        except (KeyError, ValueError, SystemExit) as exc:
            # Roll back any job created before the event failed — no partial folds.
            del ledger["jobs"][jobs_checkpoint:]
            skipped.append({"file": path.name, "error": str(exc)})
            continue
        processed_dir.mkdir(parents=True, exist_ok=True)
        path.rename(processed_dir / path.name)
    save_ledger(ledger)
    print(json.dumps({"ok": True, "folded": folded, "skipped": skipped}, indent=2))
    return 0


def cmd_job(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    if args.action == "add":
        job = new_job(args.title, ts, due=args.due, priority=args.priority or "normal",
                      recur_hours=args.monitor, workspace_id=args.workspace,
                      kind="coding" if args.coding else "life")
        ledger["jobs"].append(job)
        save_ledger(ledger)
        print(json.dumps({"ok": True, "job": job["id"], "title": job["title"],
                          "monitor": bool(args.monitor), "kind": job["kind"],
                          "workspace": job["workspace"],
                          "workspace_reason": job["workspace_reason"]}, indent=2))
        return 0
    if args.action == "list":
        rows = [
            {k: j.get(k) for k in ("id", "title", "status", "kind", "workspace", "priority", "due",
                                    "waiting_on", "snooze_until", "recur_hours", "updated", "followups")}
            for j in ledger["jobs"]
            if (args.all or j["status"] != "done")
            and (not args.workspace or j.get("workspace") == args.workspace)
        ]
        print(json.dumps(rows, indent=2))
        return 0

    job = find_job(ledger, args.id)
    if args.action == "note":
        job["notes"].append({"ts": iso(ts), "text": args.title})
        job["updated"] = iso(ts)
    elif args.action == "wait":
        job["status"] = "waiting"
        job["waiting_on"] = args.title
        job["updated"] = iso(ts)
    elif args.action == "snooze":
        if not args.until:
            raise SystemExit("job snooze requires --until (ISO8601 or +12h/+3d/+2w)")
        job["snooze_until"] = iso(parse_when(args.until, ts))
        job["updated"] = iso(ts)
    elif args.action == "done":
        job["status"] = "done"
        job["updated"] = iso(ts)
        origin = job.get("origin_msg")
        if origin:
            for m in ledger["thread"]:
                if m["id"] == origin and not m.get("answered_by"):
                    m["answered_by"] = f"job:{job['id']}"
        resolved = resolve_delegation(job, ts, "done")
        if resolved:
            job["notes"].append({"ts": iso(ts), "text": f"lineage resolved: {resolved}"})
    save_ledger(ledger)
    print(json.dumps({"ok": True, "job": job["id"], "status": job["status"],
                      "snooze_until": job.get("snooze_until")}, indent=2))
    return 0


def resolve_delegation(job: dict, ts: datetime, status: str) -> str | None:
    """Close the swarm action + retire the subagent behind a delegated job.
    Best-effort: a swarm bookkeeping problem never blocks closing a job."""
    delegation = job.get("delegation")
    swarm = _swarm()
    if not delegation or swarm is None:
        return None
    try:
        lineage = swarm.load_ledger(ts)
        action = swarm.find_action(lineage, delegation["action"])
        if action["status"] == "open":
            swarm.resolve(lineage, swarm.CHIEF_ID, action["id"], status, ts,
                          distillate=f"instinct job {job['id']} {status}")
        agent = lineage["agents"].get(delegation["agent"])
        if agent and agent["status"] == "active":
            swarm.terminate(lineage, swarm.CHIEF_ID, agent["id"], f"job {job['id']} {status}", ts)
        swarm.save_ledger(lineage)
        return f"{action['id']} {status}"
    except SystemExit as exc:
        return f"unresolved ({exc})"


def cmd_delegate(args: argparse.Namespace) -> int:
    """Spawn a subagent for a job (synapse.spawn + assign_task) and pin the
    lineage onto the job. Unlimited, no human gate — but the child inherits
    only the chief's privileges, so it can draft and never send."""
    ledger = load_ledger()
    ts = now_utc(args.now)
    job = find_job(ledger, args.id)
    if job["status"] == "done":
        raise SystemExit(f"job {job['id']} is done — nothing to delegate")
    if job.get("delegation") and not args.force:
        raise SystemExit(f"job {job['id']} already delegated to {job['delegation']['agent']} "
                         "(use --force to spawn another)")
    swarm = _swarm()
    if swarm is None:
        raise SystemExit("cam_swarm runtime unavailable")
    role = args.role or pick_role(job)
    team = "team.follow-through" if job.get("kind") == "life" else (
        "team.needs-attention" if job.get("kind") == "attention" else "team.capability")
    lineage = swarm.load_ledger(ts)
    mandate = f"Instinct job {job['id']}: {job['title'][:120]}"
    child = swarm.spawn(lineage, args.parent, role, ts, mandate=mandate,
                        job_ref=f"job:{job['id']}", team=team)
    task = job["title"]
    if job.get("workspace") and job.get("kind") in ("coding", "attention"):
        task += f" [workspace {job['workspace']}]"
    action = swarm.assign(lineage, args.parent, child["id"], task, ts, job_ref=f"job:{job['id']}")
    swarm.save_ledger(lineage)

    job["delegation"] = {"agent": child["id"], "role": role, "action": action["id"],
                         "team": team, "level": child["level"], "ts": iso(ts)}
    job["updated"] = iso(ts)
    job["notes"].append({"ts": iso(ts), "text": f"delegated to {role} {child['id']} (action {action['id']})"})
    if job["status"] == "open" and not job.get("recur_hours"):
        job["status"] = "waiting"
        job["waiting_on"] = f"subagent {child['id']} ({role})"
    save_ledger(ledger)
    print(json.dumps({"ok": True, "job": job["id"], "role": role, "agent": child["id"],
                      "level": child["level"], "action": action["id"], "team": team,
                      "privileges": child["privileges"],
                      "run_hint": (f"python3 scripts/run-cline.py --workspace {job['workspace']} "
                                   f"--goal {json.dumps(job['title'])} \"...\""
                                   if job.get("kind") == "coding" and job.get("workspace") else None)},
                     indent=2))
    return 0


def job_context(ledger: dict, job: dict, limit: int = 2) -> list[str]:
    lines = [f"note {n['ts']}: {n['text']}" for n in (job.get("notes") or [])[-limit:]]
    for m in ledger["thread"]:
        if m.get("job") == job["id"]:
            lines.append(f"thread {m['ts']} ({m['from']}): {m['text']}")
    return lines[-3:]


def draft_followup(ledger: dict, job: dict, reason: str, ts: datetime) -> Path:
    """Write a draft-only follow-up to the outbox. Never sends anything."""
    outbox_dir().mkdir(parents=True, exist_ok=True)
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    path = outbox_dir() / f"{stamp}-{job['id']}.md"
    waiting = f"\n- waiting on: {job['waiting_on']}" if job.get("waiting_on") else ""
    context = job_context(ledger, job)
    context_block = ("\nContext:\n" + "\n".join(f"- {c}" for c in context) + "\n") if context else ""
    if job.get("recur_hours"):
        nudge = (f"Monitor check for \u201c{job['title']}\u201d \u2014 {reason}. "
                 f"Anything changed since last look?")
    else:
        nudge = (f"Checking in on \u201c{job['title']}\u201d \u2014 {reason}. "
                 f"Want me to keep pushing, park it, or close it out?")
    body = (
        f"---\n"
        f"kind: instinct-followup-draft\n"
        f"job: {job['id']}\n"
        f"workspace: {job.get('workspace', DEFAULT_WORKSPACE)}\n"
        f"job_kind: {job.get('kind', 'life')}\n"
        f"priority: {job.get('priority', 'normal')}\n"
        f"reason: {reason}\n"
        f"drafted: {iso(ts)}\n"
        f"send_via: motor.inkbox\n"
        f"requires: switch.outbound=act\n"
        f"---\n\n"
        f"# Follow-up draft: {job['title']}\n\n"
        f"- status: {job['status']}{waiting}\n"
        f"- last activity: {job['updated']}\n"
        f"- follow-ups so far: {job['followups']}\n"
        f"{context_block}\n"
        f"Suggested nudge (Aaron reviews before any send):\n\n"
        f"> {nudge}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def scan_findings(ledger: dict, ts: datetime, write: bool) -> tuple[list[dict], list[str]]:
    cfg = defaults()
    findings: list[dict] = []
    drafts: list[str] = []
    escalations: list[dict] = []

    for job in ledger["jobs"]:
        if job["status"] == "done":
            continue
        snooze = job.get("snooze_until")
        if snooze and parse_ts(snooze) > ts:
            continue
        updated = parse_ts(job["updated"])
        last_touch = max(updated, parse_ts(job["last_followup"])) if job.get("last_followup") else updated

        if job.get("recur_hours"):
            # Monitor job: recurring watch, nudges on its own interval, never escalates.
            if ts - last_touch >= timedelta(hours=float(job["recur_hours"])):
                reason = f"recurring check every {job['recur_hours']}h"
                findings.append({"job": job["id"], "title": job["title"],
                                 "kind": "monitor_check", "detail": reason})
                emit_spike("monitor_check", {"job": job["id"], "title": job["title"]}, ts)
                if write:
                    path = draft_followup(ledger, job, reason, ts)
                    drafts.append(str(path))
                    job["followups"] += 1
                    job["last_followup"] = iso(ts)
            continue

        window = timedelta(hours=cfg["stale_hours"] * PRIORITY_WINDOW.get(job.get("priority", "normal"), 1.0))
        overdue = bool(job.get("due")) and parse_ts(job["due"]) < ts
        stale = ts - last_touch >= window
        if not (overdue or stale):
            continue
        if job["followups"] >= cfg["max_followups"]:
            detail = f"{job['followups']} follow-ups without resolution"
            findings.append({"job": job["id"], "title": job["title"],
                             "kind": "needs_aaron", "detail": detail})
            escalations.append({"job": job["id"], "title": job["title"],
                                "workspace": job.get("workspace", DEFAULT_WORKSPACE),
                                "kind": job.get("kind", "life"),
                                "followups": job["followups"], "detail": detail})
            emit_spike("needs_aaron", {"job": job["id"], "title": job["title"]}, ts)
            continue
        reason = "past its due date" if overdue else f"no activity in its {window.total_seconds() / 3600:.0f}h window"
        kind = "overdue" if overdue else "stale"
        findings.append({"job": job["id"], "title": job["title"], "kind": kind, "detail": reason})
        emit_spike(kind, {"job": job["id"], "title": job["title"]}, ts)
        # Nudge cooldown: overdue jobs stay in findings every scan, but a new
        # draft is written only once per window — no nightly nagging spiral.
        cooled_down = (job.get("last_followup") is None
                       or ts - parse_ts(job["last_followup"]) >= window)
        if write and cooled_down:
            path = draft_followup(ledger, job, reason, ts)
            drafts.append(str(path))
            job["followups"] += 1
            job["last_followup"] = iso(ts)

    # Every unanswered Aaron ask past the reply window — not just the last message.
    reply_cutoff = ts - timedelta(hours=cfg["reply_hours"])
    for msg in open_asks(ledger):
        if parse_ts(msg["ts"]) < reply_cutoff:
            findings.append({"kind": "dropped_ask", "message": msg["id"],
                             "detail": f"Aaron's ask unanswered since {msg['ts']}",
                             "text": msg["text"][:120]})
            emit_spike("dropped_ask", {"message": msg["id"], "text": msg["text"][:120]}, ts)

    # Escalation handoff for Needs Attention sweeps (read-only surface, no send).
    if escalations or escalations_path().exists():
        data_dir().mkdir(parents=True, exist_ok=True)
        escalations_path().write_text(json.dumps({
            "generated": iso(ts),
            "source": MOTOR,
            "items": escalations,
        }, indent=2) + "\n", encoding="utf-8")

    return findings, drafts


def cmd_scan(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    findings, drafts = scan_findings(ledger, ts, write=args.write)
    ledger["last_scan"] = iso(ts)
    save_ledger(ledger)
    rel_drafts = []
    for d in drafts:
        p = Path(d)
        rel_drafts.append(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p))
    print(json.dumps({
        "ok": True,
        "scanned_at": iso(ts),
        "findings": findings,
        "drafts": rel_drafts,
        "draft_only": True,
        "send_path": "motor.inkbox under switch.outbound (never from this engine)",
    }, indent=2))
    return 0


def report_doc(ledger: dict, ts: datetime) -> dict:
    def is_snoozed(j: dict) -> bool:
        return bool(j.get("snooze_until")) and parse_ts(j["snooze_until"]) > ts

    live = [j for j in ledger["jobs"] if j["status"] != "done"]
    snoozed = [j for j in live if is_snoozed(j)]
    monitors = [j for j in live if j.get("recur_hours") and not is_snoozed(j)]
    open_jobs = [j for j in live
                 if j["status"] == "open" and not j.get("recur_hours") and not is_snoozed(j)]
    waiting = [j for j in live if j["status"] == "waiting" and not is_snoozed(j)]
    done = [j for j in ledger["jobs"] if j["status"] == "done"]
    pending_drafts = sorted(p.name for p in outbox_dir().glob("*.md")) if outbox_dir().exists() else []
    escalations = []
    if escalations_path().exists():
        escalations = (json.loads(escalations_path().read_text(encoding="utf-8")).get("items") or [])
    asks = [{"id": m["id"], "ts": m["ts"], "text": m["text"]} for m in open_asks(ledger)]
    return {
        "ok": True,
        "as_of": iso(ts),
        "thread_messages": len(ledger["thread"]),
        "jobs": {"open": len(open_jobs), "waiting": len(waiting),
                 "monitors": len(monitors), "snoozed": len(snoozed), "done": len(done),
                 "delegated": sum(1 for j in live if j.get("delegation"))},
        "open": [{"id": j["id"], "title": j["title"], "priority": j.get("priority"),
                  "due": j.get("due")} for j in open_jobs],
        "waiting": [{"id": j["id"], "title": j["title"], "waiting_on": j.get("waiting_on")}
                    for j in waiting],
        "monitors": [{"id": j["id"], "title": j["title"], "every_hours": j.get("recur_hours")}
                     for j in monitors],
        "snoozed": [{"id": j["id"], "title": j["title"], "until": j.get("snooze_until")}
                    for j in snoozed],
        "unanswered_asks": asks,
        "escalations": escalations,
        "pending_drafts": pending_drafts,
        "last_scan": ledger.get("last_scan"),
    }


def cmd_report(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    print(json.dumps(report_doc(ledger, now_utc(args.now)), indent=2))
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    doc = report_doc(ledger, ts)
    lines = [f"# Instinct brief — {ts.strftime('%Y-%m-%d')} ({iso(ts)})", ""]
    if doc["escalations"]:
        lines.append("## Needs Aaron")
        for e in doc["escalations"]:
            lines.append(f"- **{e['title']}** (`{e['job']}`) — {e['detail']}")
        lines.append("")
    if doc["unanswered_asks"]:
        lines.append("## Dropped asks")
        for a in doc["unanswered_asks"]:
            lines.append(f"- {a['ts']} — \u201c{a['text']}\u201d (`{a['id']}`)")
        lines.append("")
    lines.append("## Jobs")
    counts = doc["jobs"]
    lines.append(f"- open {counts['open']} · waiting {counts['waiting']} · monitors "
                 f"{counts['monitors']} · snoozed {counts['snoozed']} · done {counts['done']}")
    for j in doc["open"]:
        due = f" (due {j['due']})" if j.get("due") else ""
        lines.append(f"- open: {j['title']} [{j.get('priority')}]{due}")
    for j in doc["waiting"]:
        lines.append(f"- waiting: {j['title']} — on {j.get('waiting_on')}")
    for j in doc["monitors"]:
        lines.append(f"- monitor: {j['title']} (every {j.get('every_hours')}h)")
    for j in doc["snoozed"]:
        lines.append(f"- snoozed: {j['title']} (until {j.get('until')})")
    lines.append("")
    rollup = [r for r in workspace_rollup(ledger, ts) if r["live"]]
    if rollup:
        lines.append("## By workspace")
        for r in rollup:
            conn = "" if r["connected"] in (None, True) else " · NOT CONNECTED"
            lines.append(f"- `{r['workspace']}` — open {r['open']} · waiting {r['waiting']} · "
                         f"monitors {r['monitors']} · escalations {r['escalations']} · "
                         f"drafts {r['pending_drafts']}{conn}")
        lines.append("")
    if doc["pending_drafts"]:
        lines.append("## Pending follow-up drafts (review before any send)")
        for d in doc["pending_drafts"]:
            lines.append(f"- data/instinct/outbox/{d}")
        lines.append("")
    lines.append(f"_Draft-only engine; sends require switch.outbound via motor.inkbox. "
                 f"Last scan: {doc['last_scan']}_")
    text = "\n".join(lines) + "\n"
    if args.write:
        briefs_dir().mkdir(parents=True, exist_ok=True)
        out = briefs_dir() / f"{ts.strftime('%Y-%m-%d')}.md"
        out.write_text(text, encoding="utf-8")
    if args.vault:
        # Durable distillate for Aaron's vault (config vault_dir) — review before commit.
        vault_briefs_dir().mkdir(parents=True, exist_ok=True)
        out = vault_briefs_dir() / f"{ts.strftime('%Y-%m-%d')}.md"
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_thread(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    print(json.dumps(ledger["thread"][-args.tail:], indent=2))
    return 0


def outbox_match(name: str) -> Path:
    drafts = sorted(outbox_dir().glob("*.md")) if outbox_dir().exists() else []
    matches = [p for p in drafts if p.name == name or p.name.startswith(name) or name in p.name]
    if not matches:
        raise SystemExit(f"no pending draft matching '{name}'")
    if len(matches) > 1:
        raise SystemExit(f"ambiguous draft '{name}' ({', '.join(p.name for p in matches)})")
    return matches[0]


def cmd_outbox(args: argparse.Namespace) -> int:
    """Aaron's review lane for drafted nudges. approve moves a draft to
    outbox/approved/ for the gated comms pathway (motor.inkbox under
    switch.outbound) to pick up — approving still does NOT send anything."""
    ts = now_utc(args.now)
    if args.action == "list":
        pending = sorted(p.name for p in outbox_dir().glob("*.md")) if outbox_dir().exists() else []
        approved_d = outbox_dir() / "approved"
        discarded_d = outbox_dir() / "discarded"
        print(json.dumps({
            "ok": True,
            "pending": pending,
            "approved": sorted(p.name for p in approved_d.glob("*.md")) if approved_d.exists() else [],
            "discarded": sorted(p.name for p in discarded_d.glob("*.md")) if discarded_d.exists() else [],
            "send_path": "approved drafts await motor.inkbox under switch.outbound (never sent from here)",
        }, indent=2))
        return 0
    draft = outbox_match(args.name)
    if args.action == "show":
        print(draft.read_text(encoding="utf-8"))
        return 0
    dest_dir = outbox_dir() / ("approved" if args.action == "approve" else "discarded")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / draft.name
    text = draft.read_text(encoding="utf-8")
    stamp = f"{args.action}d: {iso(ts)}\n"
    text = text.replace("---\n\n# Follow-up draft:", f"{stamp}---\n\n# Follow-up draft:", 1)
    dest.write_text(text, encoding="utf-8")
    draft.unlink()
    emit_spike(f"draft_{args.action}d", {"draft": draft.name}, ts)
    print(json.dumps({
        "ok": True,
        "draft": draft.name,
        "moved_to": str(dest.relative_to(data_dir())),
        "note": ("approved drafts are handed to motor.inkbox under switch.outbound — "
                 "nothing was sent" if args.action == "approve" else "draft discarded"),
    }, indent=2))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Follow-through statistics from the ledger — the assistant's scorecard."""
    ledger = load_ledger()
    ts = now_utc(args.now)
    jobs = ledger["jobs"]
    done = [j for j in jobs if j["status"] == "done"]
    hours_to_done = [
        (parse_ts(j["updated"]) - parse_ts(j["created"])).total_seconds() / 3600
        for j in done
    ]
    asks = [m for m in ledger["thread"] if m.get("ask")]
    answered = [m for m in asks if m.get("answered_by")
                or (m.get("job") and any(j["id"] == m["job"] and j["status"] == "done"
                                         for j in jobs))]
    approved_d = outbox_dir() / "approved"
    discarded_d = outbox_dir() / "discarded"
    print(json.dumps({
        "ok": True,
        "as_of": iso(ts),
        "jobs": {
            "total": len(jobs),
            "done": len(done),
            "open": sum(1 for j in jobs if j["status"] == "open" and not j.get("recur_hours")),
            "waiting": sum(1 for j in jobs if j["status"] == "waiting"),
            "monitors": sum(1 for j in jobs if j.get("recur_hours") and j["status"] != "done"),
            "delegated": sum(1 for j in jobs if j.get("delegation") and j["status"] != "done"),
            "avg_hours_to_done": round(sum(hours_to_done) / len(hours_to_done), 1) if hours_to_done else None,
        },
        "followups_drafted": sum(j.get("followups", 0) for j in jobs),
        "asks": {
            "tracked": len(asks),
            "answered": len(answered),
            "answer_rate": round(len(answered) / len(asks), 2) if asks else None,
        },
        "drafts": {
            "pending": len(list(outbox_dir().glob("*.md"))) if outbox_dir().exists() else 0,
            "approved": len(list(approved_d.glob("*.md"))) if approved_d.exists() else 0,
            "discarded": len(list(discarded_d.glob("*.md"))) if discarded_d.exists() else 0,
        },
        "thread_messages": len(ledger["thread"]),
    }, indent=2))
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    """Case-insensitive search across the thread, job titles, and notes."""
    ledger = load_ledger()
    needle = args.query.lower()
    messages = [
        {"id": m["id"], "ts": m["ts"], "from": m["from"], "text": m["text"]}
        for m in ledger["thread"] if needle in m["text"].lower()
    ]
    jobs = []
    for j in ledger["jobs"]:
        hit_notes = [n for n in (j.get("notes") or []) if needle in (n.get("text") or "").lower()]
        if needle in j["title"].lower() or hit_notes:
            jobs.append({"id": j["id"], "title": j["title"], "status": j["status"],
                         "matched_notes": [n["text"] for n in hit_notes]})
    print(json.dumps({"ok": True, "query": args.query,
                      "messages": messages, "jobs": jobs}, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    problems: list[str] = []
    cfg = load_config()
    if not cfg:
        problems.append("missing config/integrations/instinct.json")
    ledger = load_ledger()
    ids = [j["id"] for j in ledger["jobs"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate job ids in ledger")
    for job in ledger["jobs"]:
        if job["status"] not in ("open", "waiting", "done"):
            problems.append(f"job {job['id']} has unknown status {job['status']}")
        if job.get("priority") not in PRIORITY_WINDOW:
            problems.append(f"job {job['id']} has unknown priority {job.get('priority')}")
    msg_ids = {m["id"] for m in ledger["thread"]}
    for m in ledger["thread"]:
        answered = m.get("answered_by")
        if answered and not answered.startswith("job:") and answered not in msg_ids:
            problems.append(f"message {m['id']} answered_by unknown message {answered}")
    report = {
        "ok": not problems,
        "problems": problems,
        "data_dir": str(data_dir()),
        "jobs": len(ledger["jobs"]),
        "thread_messages": len(ledger["thread"]),
        "open_asks": len(open_asks(ledger)),
        "defaults": defaults(),
        "motor": MOTOR,
        "sense": SENSE,
    }
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


# --- cross-workspace commands ----------------------------------------------


def workspace_rollup(ledger: dict, ts: datetime) -> list[dict]:
    """Per-workspace follow-through counts across every registered coding workspace."""
    def is_snoozed(j: dict) -> bool:
        return bool(j.get("snooze_until")) and parse_ts(j["snooze_until"]) > ts

    escalated = set()
    if escalations_path().exists():
        try:
            doc = json.loads(escalations_path().read_text(encoding="utf-8"))
            escalated = {e.get("job") for e in doc.get("items") or []}
        except json.JSONDecodeError:
            escalated = set()
    drafts_by_job: dict[str, int] = {}
    if outbox_dir().exists():
        for p in outbox_dir().glob("*.md"):
            job_id = p.stem.split("-", 1)[-1]
            drafts_by_job[job_id] = drafts_by_job.get(job_id, 0) + 1

    ids = [w["id"] for w in known_workspaces()]
    for j in ledger["jobs"]:
        if j.get("workspace", DEFAULT_WORKSPACE) not in ids:
            ids.append(j.get("workspace", DEFAULT_WORKSPACE))
    rows = []
    for ws_id in ids:
        jobs = [j for j in ledger["jobs"] if j.get("workspace", DEFAULT_WORKSPACE) == ws_id]
        live = [j for j in jobs if j["status"] != "done"]
        rows.append({
            "workspace": ws_id,
            "connected": workspace_connected(ws_id),
            "live": len(live),
            "open": sum(1 for j in live if j["status"] == "open"
                        and not j.get("recur_hours") and not is_snoozed(j)),
            "waiting": sum(1 for j in live if j["status"] == "waiting" and not is_snoozed(j)),
            "monitors": sum(1 for j in live if j.get("recur_hours")),
            "snoozed": sum(1 for j in live if is_snoozed(j)),
            "done": sum(1 for j in jobs if j["status"] == "done"),
            "coding": sum(1 for j in live if j.get("kind") == "coding"),
            "attention": sum(1 for j in live if j.get("kind") == "attention"),
            "escalations": sum(1 for j in live if j["id"] in escalated),
            "pending_drafts": sum(drafts_by_job.get(j["id"], 0) for j in live),
        })
    rows.sort(key=lambda r: (-r["live"], r["workspace"]))
    return rows


def cmd_workspaces(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    rows = workspace_rollup(ledger, ts)
    if not args.all:
        rows = [r for r in rows if r["live"] or r["done"]]
    print(json.dumps({"ok": True, "as_of": iso(ts), "workspaces": rows,
                      "registered": len(known_workspaces())}, indent=2))
    return 0


def dispatch_plan(ledger: dict, ts: datetime, limit: int) -> list[dict]:
    """Print-only plan mapping coding/attention jobs to run-cline commands.
    Nothing here executes; motor.cline still fires only under switch.autonomy
    with the pattern's human gates."""
    order = {"high": 0, "normal": 1, "low": 2}
    rows = []
    for j in ledger["jobs"]:
        if j["status"] == "done" or j.get("kind") not in ("coding", "attention"):
            continue
        if j.get("snooze_until") and parse_ts(j["snooze_until"]) > ts:
            continue
        ws = j.get("workspace", DEFAULT_WORKSPACE)
        goal = j["title"].replace('"', "'")
        rows.append({
            "job": j["id"],
            "workspace": ws,
            "connected": workspace_connected(ws),
            "kind": j.get("kind"),
            "priority": j.get("priority", "normal"),
            "title": j["title"],
            "command": (f'python3 scripts/run-cline.py --workspace-id {ws} '
                        f'--goal "{goal}" "{goal}"'),
            "gate": "switch.autonomy act + pattern human gates; never auto-run from this plan",
        })
    rows.sort(key=lambda r: (order.get(r["priority"], 1), r["title"]))
    return rows[:limit]


def cmd_dispatch(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    plan = dispatch_plan(ledger, ts, args.limit)
    doc = {"ok": True, "as_of": iso(ts), "plan": plan, "executes": False,
           "note": "print-only — run-cline is Aaron/loop dispatched, not fired from Instinct"}
    if args.write:
        data_dir().mkdir(parents=True, exist_ok=True)
        (data_dir() / "dispatch-plan.json").write_text(json.dumps(doc, indent=2) + "\n",
                                                       encoding="utf-8")
        doc["wrote"] = str((data_dir() / "dispatch-plan.json"))
    print(json.dumps(doc, indent=2))
    return 0


SEVERITY_PRIORITY = {"critical": "high", "high": "high", "medium": "normal", "low": "low"}


def cmd_attention_sync(args: argparse.Namespace) -> int:
    """Pull the Needs Attention queue (all coding workspaces) into the ledger as
    attention jobs, idempotently by item id; auto-close jobs whose item cleared."""
    ledger = load_ledger()
    ts = now_utc(args.now)
    path = Path(args.file) if args.file else attention_default_path()
    if not path.exists():
        print(json.dumps({"ok": False, "error": f"no needs-attention distillate at {path} — "
                          "run scripts/needs-attention.py --write first"}, indent=2))
        return 1
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"needs-attention distillate unreadable: {exc}")
    items = [i for i in doc.get("attention_items") or []
             if i.get("severity") in ("critical", "high", "medium")
             and i.get("kind") != "policy"
             and not str(i.get("id", "")).startswith("instinct-")]  # never re-import our own escalations
    current_refs = {f"na:{i['id']}" for i in items}
    existing = {j.get("source_ref"): j for j in ledger["jobs"] if j.get("source_ref")}

    added, closed = [], []
    for item in items:
        ref = f"na:{item['id']}"
        if ref in existing:
            continue
        ws = item.get("workspace_id") or DEFAULT_WORKSPACE
        known = {w["id"] for w in known_workspaces()}
        job = new_job(str(item.get("title") or item["id"]), ts,
                      priority=SEVERITY_PRIORITY.get(item.get("severity"), "normal"),
                      workspace_id=ws if ws in known else None, kind="attention", source_ref=ref)
        detail = item.get("detail")
        if detail:
            job["notes"].append({"ts": iso(ts), "text": str(detail)})
        if item.get("suggestion"):
            job["notes"].append({"ts": iso(ts), "text": f"suggestion: {item['suggestion']}"})
        ledger["jobs"].append(job)
        added.append({"job": job["id"], "title": job["title"], "workspace": job["workspace"]})
    for ref, job in existing.items():
        if ref.startswith("na:") and job["status"] != "done" and ref not in current_refs:
            job["status"] = "done"
            job["updated"] = iso(ts)
            job["notes"].append({"ts": iso(ts), "text": "cleared upstream in Needs Attention sweep"})
            closed.append({"job": job["id"], "title": job["title"]})
    save_ledger(ledger)
    print(json.dumps({"ok": True, "source": str(path), "items_seen": len(items),
                      "added": added, "closed_upstream": closed}, indent=2))
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    """Sanitized mesh distillate (counts only — no message text, no PII) for
    cross-workspace visibility, mirrored as a mesh note like needs-attention."""
    ledger = load_ledger()
    ts = now_utc(args.now)
    report = report_doc(ledger, ts)
    rollup = workspace_rollup(ledger, ts)
    doc = {
        "at": iso(ts),
        "source": MOTOR,
        "namespace": (load_config().get("mesh_namespace") or "mesh/projects"),
        "jobs": report["jobs"],
        "unanswered_asks": len(report["unanswered_asks"]),
        "escalations": len(report["escalations"]),
        "pending_drafts": len(report["pending_drafts"]),
        "by_workspace": [r for r in rollup if r["live"] or r["done"]],
        "last_scan": report["last_scan"],
        "draft_only": True,
    }
    out = mesh_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mirrored = False
    cw = _cw()
    if cw is not None and not os.environ.get("INSTINCT_NO_CACHE_MIRROR") and cw.CLINE_CACHE.exists():
        try:
            cache = cw.load_json(cw.CLINE_CACHE)
            notes = cache.setdefault("mesh_notes", [])
            if not isinstance(notes, list):
                notes = []
                cache["mesh_notes"] = notes
            live = sum(r["live"] for r in rollup)
            notes.append({"at": iso(ts), "namespace": doc["namespace"],
                          "note": (f"instinct: live={live} escalations={doc['escalations']} "
                                   f"drafts={doc['pending_drafts']} asks={doc['unanswered_asks']}")})
            cache["mesh_notes"] = notes[-40:]
            cw.write_json(cw.CLINE_CACHE, cache)
            mirrored = True
        except Exception:
            mirrored = False
    print(json.dumps({"ok": True, "wrote": str(out), "mesh_note_mirrored": mirrored,
                      "by_workspace": doc["by_workspace"]}, indent=2))
    return 0


# --- event-drop helpers for other workspace tooling (run-cline, senses) -------


def drop_event(payload: dict, ts: datetime | None = None) -> Path | None:
    """Write one inbox event for `sync` to fold in. Never raises — a follow-
    through bookkeeping failure must never break a Cline run or a sense."""
    try:
        ts = ts or now_utc()
        inbox_dir().mkdir(parents=True, exist_ok=True)
        payload = {"ts": iso(ts), **payload}
        path = inbox_dir() / f"{ts.strftime('%Y%m%dT%H%M%S%fZ')}-{short_id()}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def track_cline_run(workspace_id: str, prompt: str, status: str, exit_code: int | None = None,
                    ticket_id: str | None = None, ts: datetime | None = None) -> Path | None:
    """Hook for run-cline.py: every Cline run in any workspace lands in the
    thread; failures/timeouts open a high-priority coding job to follow through."""
    summary = (prompt or "doctor").strip().replace("\n", " ")
    short = summary[:100] + ("…" if len(summary) > 100 else "")
    event: dict = {
        "from": "motor.cline",
        "text": f"Cline run {status} in {workspace_id} (exit={exit_code}): {short}",
        "workspace": workspace_id,
        "source_ref": f"ticket:{ticket_id}" if ticket_id else None,
    }
    if status in ("failed", "timeout"):
        event.update({
            "job": f"Cline run {status} in {workspace_id}: {short[:70]}",
            "kind": "coding",
            "priority": "high",
        })
    return drop_event(event, ts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cam Instinct — proactive follow-through engine")
    parser.add_argument("--now", help="override clock (ISO8601) for deterministic runs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="append a message to the continuous thread")
    p.add_argument("--from", dest="sender", default="aaron")
    p.add_argument("--text", required=True)
    p.add_argument("--job", help="open a persistent job from this message")
    p.add_argument("--due", help="job due date ISO8601")
    p.add_argument("--priority", choices=sorted(PRIORITY_WINDOW))
    p.add_argument("--reply-to", help="mark an earlier message answered by this one")
    p.add_argument("--workspace", help="registry workspace id for the opened job (default: chooser)")
    p.add_argument("--coding", action="store_true", help="opened job is coding work (dispatchable)")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("sync", help="fold event drops from the inbox into the thread")
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("job", help="manage persistent jobs")
    p.add_argument("action", choices=["add", "note", "wait", "snooze", "done", "list"])
    p.add_argument("id", nargs="?", help="job id (for note/wait/snooze/done)")
    p.add_argument("title", nargs="?", help="title (add) / note text (note) / waiting-on (wait)")
    p.add_argument("--due")
    p.add_argument("--priority", choices=sorted(PRIORITY_WINDOW))
    p.add_argument("--monitor", type=float, metavar="HOURS",
                   help="recurring watch: nudge every HOURS, never escalates")
    p.add_argument("--until", help="snooze until ISO8601 or +12h/+3d/+2w")
    p.add_argument("--all", action="store_true")
    p.add_argument("--workspace", help="registry workspace id (add: assign; list: filter)")
    p.add_argument("--coding", action="store_true", help="job is coding work (dispatchable)")
    p.set_defaults(fn=cmd_job)

    p = sub.add_parser("scan", help="find dropped asks and stale/overdue/monitor jobs")
    p.add_argument("--write", action="store_true", help="write draft follow-ups to the outbox")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("report", help="structured brief")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("brief", help="markdown daily brief")
    p.add_argument("--write", action="store_true", help="also write to data/instinct/briefs/")
    p.add_argument("--vault", action="store_true",
                   help="also distill to the vault (vault/06-Life-Ops/instinct/briefs/)")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("outbox", help="review drafted nudges: list / show / approve / discard")
    p.add_argument("action", choices=["list", "show", "approve", "discard"])
    p.add_argument("name", nargs="?", help="draft filename (or unique prefix/substring)")
    p.set_defaults(fn=cmd_outbox)

    p = sub.add_parser("stats", help="follow-through scorecard from the ledger")
    p.set_defaults(fn=cmd_stats)

    p = sub.add_parser("find", help="search thread, job titles, and notes")
    p.add_argument("query")
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("workspaces", help="per-workspace follow-through rollup")
    p.add_argument("--all", action="store_true", help="include workspaces with no jobs")
    p.set_defaults(fn=cmd_workspaces)

    p = sub.add_parser("dispatch", help="print-only run-cline plan for coding/attention jobs")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--write", action="store_true", help="also write data/instinct/dispatch-plan.json")
    p.set_defaults(fn=cmd_dispatch)

    p = sub.add_parser("delegate", help="spawn a subagent for a job (synapse.spawn + assign_task)")
    p.add_argument("id", help="job id (prefix ok)")
    p.add_argument("--role", help="override role (default: by kind/title)")
    p.add_argument("--parent", default="chief", help="spawning agent (default chief)")
    p.add_argument("--force", action="store_true", help="spawn another even if already delegated")
    p.set_defaults(fn=cmd_delegate)

    p = sub.add_parser("attention-sync",
                       help="import Needs Attention queue (all coding workspaces) as attention jobs")
    p.add_argument("--file", help="needs-attention distillate (default vault/.../needs-attention/latest.json)")
    p.set_defaults(fn=cmd_attention_sync)

    p = sub.add_parser("distill", help="write sanitized mesh distillate + mesh note")
    p.set_defaults(fn=cmd_distill)

    p = sub.add_parser("thread", help="show thread tail")
    p.add_argument("--tail", type=int, default=10)
    p.set_defaults(fn=cmd_thread)

    p = sub.add_parser("doctor", help="ledger + config sanity")
    p.set_defaults(fn=cmd_doctor)

    args = parser.parse_args(argv)
    # `job add TITLE` arrives with the title in the id slot
    if args.cmd == "job" and args.action == "add" and args.title is None:
        args.title = args.id
        args.id = None
    if args.cmd == "job" and args.action == "add" and not args.title:
        parser.error("job add requires a title")
    if args.cmd == "job" and args.action in ("note", "wait", "snooze", "done") and not args.id:
        parser.error(f"job {args.action} requires a job id")
    if args.cmd == "job" and args.action == "note" and not args.title:
        parser.error("job note requires the note text")
    if args.cmd == "job" and args.action == "wait" and not args.title:
        parser.error("job wait requires what the job is waiting on")
    if args.cmd == "outbox" and args.action in ("show", "approve", "discard") and not args.name:
        parser.error(f"outbox {args.action} requires a draft name")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
