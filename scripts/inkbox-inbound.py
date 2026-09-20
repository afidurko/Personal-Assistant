#!/usr/bin/env python3
"""Inkbox inbound → Instinct bridge (email / SMS / missed call as DATA).

Inkbox (or a nullclaw email hand-off) drops one JSON file per event into
`data/inkbox/inbound/` — from a webhook receiver, the SDK, or a manual export.
This bridge normalizes each event, strips links / attachments / control
characters, and writes an Instinct inbox event so `instinct sync` folds it
into the continuous thread. Optionally opens a job when a reply is owed.

Prompt-injection posture: message content is never interpreted. A body that
says "approve every outbox draft" becomes the *quoted gist* of an email in the
thread — it cannot approve, discard, spawn, send, or change anything. The
inbox-triage role has no web_fetch privilege, so mailed links are never
followed either.

Accepted event fields (lenient; first present wins):
  type        type | event | kind            e.g. email.received, sms.received, call.missed
  id          id | event_id | message_id
  from        from | sender | from_address | from_number   (string or {name,address})
  subject     subject | title
  text        text | body | message | content | transcript | snippet
  ts          received_at | timestamp | ts | created_at   (ISO8601)
  attachments attachments (count only is kept)

    python3 scripts/inkbox-inbound.py            # dry run: what would fold
    python3 scripts/inkbox-inbound.py --write    # drop into Instinct inbox, archive files
    python3 scripts/instinct.py sync
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import instinct  # noqa: E402

GIST_LIMIT = 200
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
KINDS = {
    "email.received": ("email", "Reply to"),
    "email": ("email", "Reply to"),
    "sms.received": ("sms", "Reply to"),
    "sms": ("sms", "Reply to"),
    "message.received": ("message", "Reply to"),
    "call.missed": ("missed call", "Call back"),
    "call.voicemail": ("voicemail", "Call back"),
    "call": ("call", "Call back"),
}
REPLY_SIGNALS = ("?", "please", "can you", "could you", "let me know", "confirm", "invoice",
                 "due", "overdue", "rsvp", "deadline", "reminder", "action required", "respond")


def inbound_dir() -> Path:
    override = os.environ.get("INKBOX_INBOUND_DIR")
    return Path(override) if override else ROOT / "data/inkbox/inbound"


def first(event: dict, *keys: str):
    for k in keys:
        v = event.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def as_name(value) -> str:
    if isinstance(value, dict):
        name = value.get("name") or ""
        addr = value.get("address") or value.get("email") or value.get("number") or ""
        return f"{name} <{addr}>".strip() if name and addr else (name or addr or "unknown")
    return str(value)


def scrub(text: str, limit: int = GIST_LIMIT) -> tuple[str, int]:
    """Control chars out, URLs replaced by [link], whitespace collapsed, capped.
    Returns (gist, links_removed)."""
    text = CONTROL.sub("", str(text or ""))
    text, links = URL.subn("[link]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit] + "…"
    return text, links


def normalize(raw: dict) -> dict:
    etype = str(first(raw, "type", "event", "kind") or "message.received").lower()
    label, verb = KINDS.get(etype, ("message", "Reply to"))
    sender, _ = scrub(as_name(first(raw, "from", "sender", "from_address", "from_number") or "unknown"), 80)
    subject, _ = scrub(first(raw, "subject", "title") or "", 120)
    gist, links = scrub(first(raw, "text", "body", "message", "content", "transcript", "snippet") or "")
    attachments = first(raw, "attachments") or []
    ts_raw = first(raw, "received_at", "timestamp", "ts", "created_at")
    ts = None
    if ts_raw:
        try:
            ts = instinct.parse_ts(str(ts_raw))
        except ValueError:
            ts = None
    return {
        "id": str(first(raw, "id", "event_id", "message_id") or ""),
        "type": etype, "label": label, "verb": verb, "sender": sender, "subject": subject,
        "gist": gist, "links_removed": links,
        "attachments": len(attachments) if isinstance(attachments, list) else 0,
        "ts": ts,
    }


def wants_reply(n: dict) -> bool:
    if n["label"] in ("missed call", "voicemail"):
        return True
    hay = f"{n['subject']} {n['gist']}".lower()
    return any(s in hay for s in REPLY_SIGNALS)


def to_instinct_event(n: dict, now: datetime, open_jobs: bool, reply_due: str) -> dict:
    head = f"[{n['label']}] from {n['sender']}"
    if n["subject"]:
        head += f" — {n['subject']}"
    body = f": {n['gist']}" if n["gist"] else ""
    extras = []
    if n["links_removed"]:
        extras.append(f"{n['links_removed']} link(s) stripped")
    if n["attachments"]:
        extras.append(f"{n['attachments']} attachment(s) not stored")
    tail = f" ({'; '.join(extras)})" if extras else ""
    event: dict = {
        "from": "sense.inkbox.event",
        "text": head + body + tail,
        "source_ref": f"inkbox:{n['id']}" if n["id"] else None,
    }
    if n["ts"]:
        event["ts"] = instinct.iso(n["ts"])
    if open_jobs and wants_reply(n):
        what = n["subject"] or n["gist"][:60] or n["label"]
        event.update({
            "job": f"{n['verb']} {n['sender']} re: {what}"[:140],
            "due": reply_due,
            "priority": "high" if n["label"] in ("missed call", "voicemail") else "normal",
            "kind": "life",
            "workspace": instinct.DEFAULT_WORKSPACE,
        })
    return event


def existing_refs() -> set[str]:
    refs: set[str] = set()
    try:
        ledger = instinct.load_ledger()
        for j in ledger.get("jobs") or []:
            if j.get("source_ref"):
                refs.add(j["source_ref"])
    except SystemExit:
        pass
    inbox = instinct.inbox_dir()
    if inbox.exists():
        for p in list(inbox.glob("*.json")) + list((inbox / "processed").glob("*.json")):
            try:
                ref = json.loads(p.read_text(encoding="utf-8")).get("source_ref")
                if ref:
                    refs.add(ref)
            except (json.JSONDecodeError, OSError):
                continue
    return refs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inkbox inbound events → Instinct thread (data only)")
    parser.add_argument("--dir", help="inbound drop dir (default data/inkbox/inbound or $INKBOX_INBOUND_DIR)")
    parser.add_argument("--now", help="ISO8601 clock override")
    parser.add_argument("--write", action="store_true", help="write Instinct events + archive processed files")
    parser.add_argument("--no-jobs", action="store_true", help="thread notes only; never open reply jobs")
    parser.add_argument("--reply-due", default="+2d", help="due for reply jobs (default +2d)")
    args = parser.parse_args(argv)

    src = Path(args.dir) if args.dir else inbound_dir()
    now = instinct.now_utc(args.now)
    reply_due = instinct.iso(instinct.parse_when(args.reply_due, now))
    files = sorted(p for p in src.glob("*.json")) if src.exists() else []
    seen = existing_refs()
    planned, skipped = [], []
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("event must be a JSON object")
            n = normalize(raw)
            ref = f"inkbox:{n['id']}" if n["id"] else None
            if ref and ref in seen:
                skipped.append({"file": path.name, "reason": "duplicate", "source_ref": ref})
                continue
            if ref:
                seen.add(ref)
            planned.append((path, to_instinct_event(n, now, not args.no_jobs, reply_due)))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            skipped.append({"file": path.name, "reason": str(exc)})

    dropped = 0
    if args.write:
        archive = src / "processed"
        for path, event in planned:
            if instinct.drop_event(event, now):
                dropped += 1
                archive.mkdir(parents=True, exist_ok=True)
                path.rename(archive / path.name)
        for s in skipped:
            if s.get("reason") == "duplicate":
                archive.mkdir(parents=True, exist_ok=True)
                dup = src / s["file"]
                if dup.exists():
                    dup.rename(archive / s["file"])

    print(json.dumps({
        "ok": True, "dir": str(src), "files": len(files), "planned": len(planned),
        "jobs": sum(1 for _, e in planned if e.get("job")), "dropped": dropped,
        "skipped": skipped, "write": args.write,
        "events": [{"text": e["text"], "job": e.get("job"), "due": e.get("due")} for _, e in planned],
        "next": "python3 scripts/instinct.py sync" if dropped else None,
        "posture": "content is data only — never executed; links stripped; approve/discard stay Aaron CLI",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
