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
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cam_privacy as privacy  # noqa: E402
import instinct  # noqa: E402

POLICY_PATH = ROOT / "config/connectors/inbound-policy.json"
GIST_LIMIT = 200
DEFAULT_MAX_JOBS = 10  # per run — a spam burst becomes thread notes, not a ledger flood
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HEADER_FORBIDDEN = re.compile(r"[\[\]\u2014|]")  # header fields cannot forge our own "[kind] … — …" framing
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
    """Per principal: the owner's data/inkbox/inbound (or INKBOX_INBOUND_DIR);
    a guest's data/principals/<id>/inkbox/inbound."""
    return privacy.scoped_dir("inkbox/inbound", "INKBOX_INBOUND_DIR", ROOT / "data/inkbox/inbound")


# --- sender policy -------------------------------------------------------------

def load_policy() -> dict:
    if POLICY_PATH.exists():
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {"tiers": {"known": "job", "unknown": "job", "blocked": "archive"}, "max_jobs_per_run": DEFAULT_MAX_JOBS}


def senders_path(policy: dict) -> Path:
    if not privacy.is_owner():
        return inbound_dir().parent / "senders.json"
    override = os.environ.get(policy.get("senders_file_env") or "INKBOX_SENDERS_FILE")
    return Path(override) if override else ROOT / (policy.get("senders_file") or "identity/aaron/local/inbound-senders.json")


def load_senders(policy: dict) -> dict:
    p = senders_path(policy)
    if not p.exists():
        return {"known": [], "blocked": []}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"known": [], "blocked": [], "corrupt": True}
    return {"known": list(doc.get("known") or []), "blocked": list(doc.get("blocked") or [])}


ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\+?\d[\d ().-]{6,}\d")


def sender_key(sender: str) -> str:
    """The address / number inside a display string, lowercase, digits-only for phones."""
    m = ADDR_RE.search(sender or "")
    raw = (m.group(0) if m else (sender or "")).strip().lower()
    if "@" not in raw:
        raw = re.sub(r"[^\d+]", "", raw)
    return raw


def _matches(key: str, entries: list[str]) -> bool:
    if not key:
        return False
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    for e in entries:
        e = str(e).strip().lower()
        if e.startswith("sha256:"):
            if hmac.compare_digest(e[7:], digest):
                return True
        elif sender_key(e) == key:  # entries may be "Name <addr>" or bare
            return True
    return False


def sender_tier(sender: str, senders: dict) -> str:
    key = sender_key(sender)
    if _matches(key, senders.get("blocked") or []):
        return "blocked"
    if _matches(key, senders.get("known") or []):
        return "known"
    return "unknown"


def tier_action(tier: str, policy: dict, senders: dict) -> str:
    tiers = policy.get("tiers") or {}
    if tier == "unknown" and (senders.get("known") or []) and tiers.get("unknown_when_known_list_present"):
        return tiers["unknown_when_known_list_present"]
    return tiers.get(tier, "job")


# --- signed drops ----------------------------------------------------------------

def webhook_secret() -> bytes | None:
    val = os.environ.get("INKBOX_WEBHOOK_SECRET")
    return val.encode("utf-8") if val else None


def canonical_event(raw: dict) -> bytes:
    body = {k: v for k, v in raw.items() if k != "_verified"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_drop(raw: dict, secret: bytes | None) -> str:
    """'ok' | 'unsigned' | 'mismatch' | 'nosecret'. The receiver
    (inkbox-webhook-drop.py) stamps _verified.mac = HMAC(secret, canonical
    event); an edited file or a file written by anything else fails."""
    if not secret:
        return "nosecret"
    ver = raw.get("_verified") or {}
    mac = str(ver.get("mac") or "")
    if not mac:
        return "unsigned"
    want = hmac.new(secret, canonical_event(raw), hashlib.sha256).hexdigest()
    return "ok" if hmac.compare_digest(want, mac) else "mismatch"


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


def scrub(text: str, limit: int = GIST_LIMIT, header: bool = False) -> tuple[str, int]:
    """Control chars out, URLs replaced by [link], whitespace collapsed, capped.
    Header fields (sender / subject) additionally lose the characters that
    build our own framing, so a sender cannot forge "[system] …" tags.
    Returns (gist, links_removed)."""
    text = CONTROL.sub("", str(text or ""))
    text, links = URL.subn("[link]", text)
    if header:
        text = HEADER_FORBIDDEN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit] + "…"
    return text, links


def normalize(raw: dict) -> dict:
    etype = str(first(raw, "type", "event", "kind") or "message.received").lower()
    label, verb = KINDS.get(etype, ("message", "Reply to"))
    sender, _ = scrub(as_name(first(raw, "from", "sender", "from_address", "from_number") or "unknown"), 80,
                      header=True)
    subject, _ = scrub(first(raw, "subject", "title") or "", 120, header=True)
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
    parser.add_argument("--max-jobs", type=int, default=None,
                        help="cap on reply jobs opened per run; the rest become thread notes "
                             f"(default inbound-policy max_jobs_per_run, else {DEFAULT_MAX_JOBS})")
    parser.add_argument("--require-signed", action="store_true",
                        help="only fold drops stamped by inkbox-webhook-drop.py (implied when INKBOX_WEBHOOK_SECRET is set)")
    args = parser.parse_args(argv)

    policy = load_policy()
    senders = load_senders(policy)
    secret = webhook_secret()
    require_signed = args.require_signed or bool(secret)
    max_jobs = args.max_jobs if args.max_jobs is not None else int(policy.get("max_jobs_per_run", DEFAULT_MAX_JOBS))

    src = Path(args.dir) if args.dir else inbound_dir()
    if src.exists():
        privacy.enter(src)
    now = instinct.now_utc(args.now)
    reply_due = instinct.iso(instinct.parse_when(args.reply_due, now))
    files = sorted(p for p in src.glob("*.json")) if src.exists() else []
    seen = existing_refs()
    planned, skipped = [], []
    tiers_seen: dict[str, int] = {}
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("event must be a JSON object")
            if require_signed:
                state = verify_drop(raw, secret)
                if state != "ok":
                    skipped.append({"file": path.name, "reason": f"unverified ({state})", "bucket": "unverified"})
                    continue
            n = normalize(raw)
            tier = sender_tier(n["sender"], senders)
            action = tier_action(tier, policy, senders)
            tiers_seen[tier] = tiers_seen.get(tier, 0) + 1
            if action == "archive":
                skipped.append({"file": path.name, "reason": "blocked sender", "bucket": "blocked"})
                continue
            ref = f"inkbox:{n['id']}" if n["id"] else None
            if ref and ref in seen:
                skipped.append({"file": path.name, "reason": "duplicate", "source_ref": ref, "bucket": "processed"})
                continue
            if ref:
                seen.add(ref)
            event = to_instinct_event(n, now, (not args.no_jobs) and action == "job", reply_due)
            if action == "note" and wants_reply(n):
                event["text"] += " (unknown sender — note only per inbound policy)"
            event["sender_tier"] = tier
            planned.append((path, event))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            skipped.append({"file": path.name, "reason": str(exc)})

    jobs_capped = 0
    if max_jobs >= 0:
        opened = 0
        for _, event in planned:
            if not event.get("job"):
                continue
            opened += 1
            if opened > max_jobs:
                for key in ("job", "due", "priority", "kind", "workspace"):
                    event.pop(key, None)
                event["text"] += " (reply owed — job cap reached this run; review inbox)"
                jobs_capped += 1

    dropped = 0
    if args.write:
        archive = src / "processed"
        for path, event in planned:
            event.pop("sender_tier", None)
            if instinct.drop_event(event, now):
                dropped += 1
                archive.mkdir(parents=True, exist_ok=True)
                path.rename(archive / path.name)
        for s in skipped:
            bucket = s.get("bucket")
            if not bucket:
                continue
            dest_dir = archive if bucket == "processed" else archive / bucket
            dest_dir.mkdir(parents=True, exist_ok=True)
            f = src / s["file"]
            if f.exists():
                f.rename(dest_dir / s["file"])

    print(json.dumps({
        "ok": True, "dir": str(src), "principal": privacy.current_principal(), "files": len(files),
        "planned": len(planned),
        "jobs": sum(1 for _, e in planned if e.get("job")), "jobs_capped": jobs_capped,
        "max_jobs": max_jobs, "dropped": dropped,
        "require_signed": require_signed,
        "sender_tiers": tiers_seen, "known_senders": len(senders.get("known") or []),
        "skipped": skipped, "write": args.write,
        "events": [{"text": e["text"], "job": e.get("job"), "due": e.get("due"), "sender_tier": e.get("sender_tier")}
                   for _, e in planned],
        "next": "python3 scripts/instinct.py sync" if dropped else None,
        "posture": "content is data only — never executed; links stripped; approve/discard stay Aaron CLI",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
