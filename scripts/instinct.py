#!/usr/bin/env python3
"""Cam Instinct — proactive follow-through engine (motor.instinct).

An original, local-first implementation of the behavior model popularized by
Instinct (Spear Street Technology): one continuous thread, a persistent job
ledger that survives between messages, and proactive follow-ups on dropped
threads. Differences are deliberate (see config/integrations/instinct.md):
follow-ups are ALWAYS draft-only from this engine — live send hands off to
motor.inkbox under switch.outbound; no data leaves the workspace; no spend.

Commands
  ingest   append a message to the single continuous thread (optionally open a job)
  job      add / note / wait / done / list persistent jobs
  scan     find dropped threads + stale/overdue jobs; emit spikes; write draft follow-ups
  report   one-thread brief: open jobs, waiting-on, pending drafts, escalations
  thread   show the continuous thread tail
  doctor   ledger + config sanity (offline, no key required)

All state lives in data/instinct/ (ledger.json, spikes.jsonl, outbox/).
Deterministic: pass --now ISO8601 to override the clock for tests/demos.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/instinct"
LEDGER = DATA_DIR / "ledger.json"
SPIKES = DATA_DIR / "spikes.jsonl"
OUTBOX = DATA_DIR / "outbox"
CONFIG = ROOT / "config/integrations/instinct.json"

SENSE = "sense.instinct.followup"
MOTOR = "motor.instinct"


def now_utc(override: str | None = None) -> datetime:
    if override:
        return datetime.fromisoformat(override.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


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
        "draft_only": d.get("draft_only", True),
    }


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "created": iso(now_utc()),
        "thread": [],
        "jobs": [],
        "last_scan": None,
    }


def save_ledger(ledger: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def emit_spike(kind: str, payload: dict, ts: datetime) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    spike = {"ts": iso(ts), "sense": SENSE, "kind": kind, **payload}
    with SPIKES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(spike) + "\n")


def short_id() -> str:
    return uuid.uuid4().hex[:8]


def find_job(ledger: dict, job_id: str) -> dict:
    for job in ledger["jobs"]:
        if job["id"] == job_id or job["id"].startswith(job_id):
            return job
    raise SystemExit(f"no job matching id '{job_id}'")


# --- commands -----------------------------------------------------------


def cmd_ingest(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    msg = {
        "id": short_id(),
        "ts": iso(ts),
        "from": args.sender,
        "text": args.text,
    }
    if args.job:
        job = {
            "id": short_id(),
            "title": args.job,
            "status": "open",
            "created": iso(ts),
            "updated": iso(ts),
            "due": args.due,
            "waiting_on": None,
            "followups": 0,
            "last_followup": None,
            "notes": [],
        }
        ledger["jobs"].append(job)
        msg["job"] = job["id"]
    ledger["thread"].append(msg)
    save_ledger(ledger)
    out = {"ok": True, "message": msg["id"], "job": msg.get("job")}
    print(json.dumps(out, indent=2))
    return 0


def cmd_job(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    if args.action == "add":
        job = {
            "id": short_id(),
            "title": args.title,
            "status": "open",
            "created": iso(ts),
            "updated": iso(ts),
            "due": args.due,
            "waiting_on": None,
            "followups": 0,
            "last_followup": None,
            "notes": [],
        }
        ledger["jobs"].append(job)
        save_ledger(ledger)
        print(json.dumps({"ok": True, "job": job["id"], "title": job["title"]}, indent=2))
        return 0
    if args.action == "list":
        rows = [
            {k: j.get(k) for k in ("id", "title", "status", "due", "waiting_on", "updated", "followups")}
            for j in ledger["jobs"]
            if args.all or j["status"] != "done"
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
    elif args.action == "done":
        job["status"] = "done"
        job["updated"] = iso(ts)
    save_ledger(ledger)
    print(json.dumps({"ok": True, "job": job["id"], "status": job["status"]}, indent=2))
    return 0


def draft_followup(job: dict, reason: str, ts: datetime) -> Path:
    """Write a draft-only follow-up to the outbox. Never sends anything."""
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    path = OUTBOX / f"{stamp}-{job['id']}.md"
    waiting = f"\n- waiting on: {job['waiting_on']}" if job.get("waiting_on") else ""
    body = (
        f"---\n"
        f"kind: instinct-followup-draft\n"
        f"job: {job['id']}\n"
        f"reason: {reason}\n"
        f"drafted: {iso(ts)}\n"
        f"send_via: motor.inkbox\n"
        f"requires: switch.outbound=act\n"
        f"---\n\n"
        f"# Follow-up draft: {job['title']}\n\n"
        f"- status: {job['status']}{waiting}\n"
        f"- last activity: {job['updated']}\n"
        f"- follow-ups so far: {job['followups']}\n\n"
        f"Suggested nudge (Aaron reviews before any send):\n\n"
        f"> Checking in on \u201c{job['title']}\u201d \u2014 {reason}. "
        f"Want me to keep pushing, park it, or close it out?\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def cmd_scan(args: argparse.Namespace) -> int:
    cfg = defaults()
    ledger = load_ledger()
    ts = now_utc(args.now)
    stale_cutoff = ts - timedelta(hours=cfg["stale_hours"])
    reply_cutoff = ts - timedelta(hours=cfg["reply_hours"])

    findings: list[dict] = []
    drafts: list[str] = []

    for job in ledger["jobs"]:
        if job["status"] == "done":
            continue
        updated = parse_ts(job["updated"])
        overdue = bool(job.get("due")) and parse_ts(job["due"]) < ts
        stale = updated < stale_cutoff
        if not (overdue or stale):
            continue
        if job["followups"] >= cfg["max_followups"]:
            findings.append({"job": job["id"], "title": job["title"], "kind": "needs_aaron",
                             "detail": f"{job['followups']} follow-ups without resolution"})
            emit_spike("needs_aaron", {"job": job["id"], "title": job["title"]}, ts)
            continue
        reason = "past its due date" if overdue else f"no activity for {cfg['stale_hours']}h+"
        kind = "overdue" if overdue else "stale"
        findings.append({"job": job["id"], "title": job["title"], "kind": kind, "detail": reason})
        emit_spike(kind, {"job": job["id"], "title": job["title"]}, ts)
        if args.write:
            path = draft_followup(job, reason, ts)
            drafts.append(str(path.relative_to(ROOT)))
            job["followups"] += 1
            job["last_followup"] = iso(ts)

    # Dropped thread: the last message is from Aaron, looks like it expects a
    # response (question or open ask), and has sat unanswered past reply_hours.
    thread = ledger["thread"]
    if thread:
        last = thread[-1]
        last_ts = parse_ts(last["ts"])
        expects_reply = bool(re.search(r"\?|can you|please|need to|remind", last["text"], re.I))
        if last["from"] == "aaron" and expects_reply and last_ts < reply_cutoff:
            findings.append({"kind": "dropped_thread", "message": last["id"],
                             "detail": f"Aaron's last message unanswered since {last['ts']}"})
            emit_spike("dropped_thread", {"message": last["id"], "text": last["text"][:120]}, ts)

    ledger["last_scan"] = iso(ts)
    save_ledger(ledger)

    print(json.dumps({
        "ok": True,
        "scanned_at": iso(ts),
        "findings": findings,
        "drafts": drafts,
        "draft_only": True,
        "send_path": "motor.inkbox under switch.outbound (never from this engine)",
    }, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    ts = now_utc(args.now)
    open_jobs = [j for j in ledger["jobs"] if j["status"] == "open"]
    waiting = [j for j in ledger["jobs"] if j["status"] == "waiting"]
    done = [j for j in ledger["jobs"] if j["status"] == "done"]
    pending_drafts = sorted(p.name for p in OUTBOX.glob("*.md")) if OUTBOX.exists() else []
    print(json.dumps({
        "ok": True,
        "as_of": iso(ts),
        "thread_messages": len(ledger["thread"]),
        "jobs": {"open": len(open_jobs), "waiting": len(waiting), "done": len(done)},
        "open": [{"id": j["id"], "title": j["title"], "due": j.get("due")} for j in open_jobs],
        "waiting": [{"id": j["id"], "title": j["title"], "waiting_on": j.get("waiting_on")} for j in waiting],
        "pending_drafts": pending_drafts,
        "last_scan": ledger.get("last_scan"),
    }, indent=2))
    return 0


def cmd_thread(args: argparse.Namespace) -> int:
    ledger = load_ledger()
    tail = ledger["thread"][-args.tail:]
    print(json.dumps(tail, indent=2))
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
    report = {
        "ok": not problems,
        "problems": problems,
        "ledger": str(LEDGER.relative_to(ROOT)),
        "jobs": len(ledger["jobs"]),
        "thread_messages": len(ledger["thread"]),
        "defaults": defaults(),
        "motor": MOTOR,
        "sense": SENSE,
    }
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Cam Instinct — proactive follow-through engine")
    parser.add_argument("--now", help="override clock (ISO8601) for deterministic runs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="append a message to the continuous thread")
    p.add_argument("--from", dest="sender", default="aaron")
    p.add_argument("--text", required=True)
    p.add_argument("--job", help="open a persistent job from this message")
    p.add_argument("--due", help="job due date ISO8601")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("job", help="manage persistent jobs")
    p.add_argument("action", choices=["add", "note", "wait", "done", "list"])
    p.add_argument("id", nargs="?", help="job id (for note/wait/done)")
    p.add_argument("title", nargs="?", help="title (add) / note text (note) / waiting-on (wait)")
    p.add_argument("--due")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_job)

    p = sub.add_parser("scan", help="find dropped threads and stale/overdue jobs")
    p.add_argument("--write", action="store_true", help="write draft follow-ups to the outbox")
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("report", help="one-thread brief")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("thread", help="show thread tail")
    p.add_argument("--tail", type=int, default=10)
    p.set_defaults(fn=cmd_thread)

    p = sub.add_parser("doctor", help="ledger + config sanity")
    p.set_defaults(fn=cmd_doctor)

    args = parser.parse_args()
    # `job add TITLE` arrives with the title in the id slot
    if args.cmd == "job" and args.action == "add" and args.title is None:
        args.title = args.id
        args.id = None
    if args.cmd == "job" and args.action == "add" and not args.title:
        parser.error("job add requires a title")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
