#!/usr/bin/env python3
"""Calendar → Instinct bridge (read-only).

Reads one or more ICS sources (local .ics export or a private ICS URL) and
turns upcoming events into Instinct *prep jobs* so follow-through starts
before the event, not after. Nothing is ever written back to the calendar —
changes Cam wants to make stay drafts (scheduler role, outbox).

    export CAM_CALENDAR_ICS=/path/aaron.ics        # or https://.../private.ics
    python3 scripts/calendar-sync.py --horizon-days 14 --write
    python3 scripts/instinct.py sync               # fold the drops

Idempotent: each event carries `source_ref: ics:<UID>`; events already in
the ledger (any status) are skipped. Description / location text is stored as
data only — never interpreted as an instruction.

Only stdlib: ICS folding (RFC 5545 §3.1), DATE and DATE-TIME (Z, TZID via
zoneinfo, floating → UTC), RRULE-free. Recurring master events are surfaced
once with their first DTSTART; expanding RRULEs is out of scope for a
prep-job bridge.

Trust: URL sources are fetched only when they appear in Aaron's
CAM_CALENDAR_ICS (or with the CLI-only --trust-url). Anything else that
looks like a URL is refused, so no agent can turn this bridge into a
free-form HTTP / exfiltration channel. The MCP tool never forwards `ics`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import instinct  # noqa: E402

TEXT_LIMIT = 240
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# --- ICS parsing ------------------------------------------------------------

def unfold(text: str) -> list[str]:
    """RFC 5545 line unfolding: a line starting with space/tab continues the previous."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def unescape(value: str) -> str:
    return (value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def parse_dt(value: str, params: dict[str, str]) -> tuple[datetime, bool]:
    """Return (utc datetime, all_day). `Z` is UTC; TZID resolves through
    zoneinfo (unknown zones fall back to UTC and are flagged by the caller);
    floating times are taken as UTC."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc), True
    if value.endswith("Z"):
        return datetime.strptime(value[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc), False
    naive = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid = params.get("TZID")
    if tzid:
        try:
            return naive.replace(tzinfo=ZoneInfo(tzid)).astimezone(timezone.utc), False
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown TZID {tzid}")
    return naive.replace(tzinfo=timezone.utc), False


def parse_ics(text: str) -> list[dict]:
    events: list[dict] = []
    cur: dict | None = None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
            continue
        if line == "END:VEVENT":
            if cur is not None and cur.get("uid") and cur.get("start"):
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        head, _, value = line.partition(":")
        name, *param_parts = head.split(";")
        params = dict(p.split("=", 1) for p in param_parts if "=" in p)
        name = name.upper()
        try:
            if name == "UID":
                cur["uid"] = value.strip()
            elif name == "SUMMARY":
                cur["summary"] = clean(unescape(value))
            elif name == "DTSTART":
                cur["start"], cur["all_day"] = parse_dt(value, params)
            elif name == "DTEND":
                cur["end"], _ = parse_dt(value, params)
            elif name == "LOCATION":
                cur["location"] = clean(unescape(value))
            elif name == "DESCRIPTION":
                cur["description"] = clean(unescape(value))
            elif name == "STATUS":
                cur["status"] = value.strip().upper()
            elif name == "SEQUENCE":
                cur["sequence"] = int(value.strip() or 0)
            elif name == "RRULE":
                cur["recurring"] = True
        except ValueError:
            cur["broken"] = f"{name}: {value[:40]}"
    return events


def clean(text: str) -> str:
    text = CONTROL.sub("", text).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:TEXT_LIMIT] + ("…" if len(text) > TEXT_LIMIT else "")


# --- sources ------------------------------------------------------------------

URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def host_is_private(host: str) -> bool:
    """Loopback / link-local / RFC1918 / ULA — a trusted public ICS URL must not
    be able to redirect Cam onto its own LAN or metadata endpoints."""
    import ipaddress
    import socket
    host = (host or "").strip("[]").lower()
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError):
        return True  # unresolvable → treat as unsafe
    for a in addrs:
        try:
            ip = ipaddress.ip_address(a.split("%", 1)[0])
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return True
    return False


class PinnedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to the same host, over http(s), never to private ranges."""

    def __init__(self, host: str):
        super().__init__()
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        from urllib.parse import urlsplit
        parts = urlsplit(newurl)
        if parts.scheme not in ("http", "https"):
            raise PermissionError(f"redirect to non-http(s) URL refused")
        if (parts.hostname or "").lower() != self.host:
            raise PermissionError(f"redirect to a different host refused ({parts.hostname})")
        if host_is_private(parts.hostname or ""):
            raise PermissionError("redirect to a private / loopback address refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(src: str, host: str, timeout: int = 20) -> str:
    opener = urllib.request.build_opener(PinnedRedirects(host))
    with opener.open(src, timeout=timeout) as resp:  # noqa: S310 — Aaron-trusted ICS URL, host pinned
        return resp.read(5_000_000).decode("utf-8", errors="replace")


def read_source(src: str, trusted_urls: set[str], allow_private: bool = False) -> str:
    if URL_RE.match(src):
        from urllib.parse import urlsplit
        if not re.match(r"^https?://", src, re.IGNORECASE):
            raise PermissionError(f"only http(s) ICS URLs are supported: {src}")
        if src not in trusted_urls:
            raise PermissionError("untrusted URL source — add it to CAM_CALENDAR_ICS or pass --trust-url at the CLI")
        host = (urlsplit(src).hostname or "").lower()
        if not allow_private and host_is_private(host):
            raise PermissionError(f"ICS host {host!r} resolves to a private / loopback address "
                                  "(set CAM_CALENDAR_ALLOW_PRIVATE=1 for a LAN calendar)")
        return open_url(src, host)
    path = Path(src).expanduser()
    if path.suffix.lower() not in (".ics", ".ical", ".icalendar", ".txt"):
        raise PermissionError(f"refusing non-calendar file {path.name} (expected .ics)")
    return path.read_text(encoding="utf-8", errors="replace")


def sources_from_env() -> list[str]:
    raw = os.environ.get("CAM_CALENDAR_ICS", "")
    return [s.strip() for s in re.split(r"[,\n]", raw) if s.strip()]


# --- bridge ---------------------------------------------------------------------

def prep_lead(start: datetime, all_day: bool) -> timedelta:
    """How early the prep job falls due: the day before for all-day events,
    two hours before for timed ones."""
    return timedelta(days=1) if all_day else timedelta(hours=2)


def _calendar_blob(ev: dict) -> dict:
    return {"uid": ev["uid"], "start": instinct.iso(ev["start"]), "sequence": int(ev.get("sequence") or 0),
            "all_day": bool(ev.get("all_day")), "recurring": bool(ev.get("recurring"))}


def plan(events: list[dict], now: datetime, horizon_days: int, existing_refs, existing: dict | None = None) -> list[dict]:
    """New events become prep jobs. An event already in the ledger whose
    DTSTART moved (or SEQUENCE grew) yields an *update* event instead, so the
    prep job follows the reschedule rather than firing for the old time.
    `existing_refs` may be a set (legacy) or the dict from existing_source_refs()."""
    if existing is None and isinstance(existing_refs, dict):
        existing, existing_refs = existing_refs, set(existing_refs)
    existing = existing or {}
    horizon = now + timedelta(days=horizon_days)
    out: list[dict] = []
    for ev in sorted(events, key=lambda e: e["start"]):
        if ev.get("status") == "CANCELLED":
            continue
        end = ev.get("end") or ev["start"]
        if end < now or ev["start"] > horizon:
            continue
        ref = f"ics:{ev['uid']}"
        due = ev["start"] - prep_lead(ev["start"], bool(ev.get("all_day")))
        if due < now:
            due = now
        title = ev.get("summary") or "(untitled event)"
        where = f" @ {ev['location']}" if ev.get("location") else ""
        when = ev["start"].strftime("%Y-%m-%d" if ev.get("all_day") else "%Y-%m-%d %H:%M UTC")
        if ref in existing_refs:
            prev = existing.get(ref) or {}
            moved = prev.get("start") and prev["start"] != instinct.iso(ev["start"])
            bumped = int(ev.get("sequence") or 0) > int(prev.get("sequence") or 0)
            if prev and (moved or bumped):
                out.append({
                    "from": "sense.calendar.event",
                    "text": f"Calendar moved: {title}{where} — now {when}",
                    "update_ref": ref,
                    "update": {"title": f"Prep: {title}"[:140], "due": instinct.iso(due),
                               "calendar": _calendar_blob(ev), "reopen_if_done": ev["start"] > now},
                    "source_ref": ref,
                })
            continue
        text = f"Calendar: {title}{where} — {when}"
        if ev.get("description"):
            text += f" | note: {ev['description'][:120]}"
        out.append({
            "from": "sense.calendar.event",
            "text": text,
            "job": f"Prep: {title}"[:140],
            "due": instinct.iso(due),
            "priority": "high" if (ev["start"] - now) <= timedelta(days=2) else "normal",
            "kind": "life",
            "workspace": instinct.DEFAULT_WORKSPACE,
            "source_ref": ref,
            "calendar": _calendar_blob(ev),
        })
    return out


def existing_source_refs() -> dict[str, dict]:
    """ref → {start, sequence, status} for every calendar-sourced job and
    every not-yet-folded drop (so a re-run never double-plans)."""
    refs: dict[str, dict] = {}
    try:
        ledger = instinct.load_ledger()
    except SystemExit:
        ledger = {"jobs": []}
    for j in ledger.get("jobs") or []:
        if j.get("source_ref"):
            cal = j.get("calendar") or {}
            refs[j["source_ref"]] = {"start": cal.get("start"), "sequence": cal.get("sequence", 0),
                                     "status": j.get("status")}
    # drops not yet folded by `instinct sync`
    inbox = instinct.inbox_dir()
    if inbox.exists():
        for p in inbox.glob("*.json"):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            ref = doc.get("source_ref")
            if ref:
                cal = (doc.get("update") or {}).get("calendar") or doc.get("calendar") or {}
                refs[ref] = {"start": cal.get("start"), "sequence": cal.get("sequence", 0), "status": "pending"}
    return refs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ICS calendar → Instinct prep jobs (read-only)")
    parser.add_argument("--ics", action="append", help="ICS path or URL (repeatable; default $CAM_CALENDAR_ICS)")
    parser.add_argument("--horizon-days", type=int, default=14)
    parser.add_argument("--now", help="ISO8601 clock override")
    parser.add_argument("--write", action="store_true", help="drop events into the Instinct inbox")
    parser.add_argument("--trust-url", action="store_true",
                        help="CLI only: allow --ics URLs not listed in CAM_CALENDAR_ICS")
    parser.add_argument("--note-ignored-ics", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    env_sources = sources_from_env()
    sources = args.ics or env_sources
    trusted_urls = {s for s in env_sources if URL_RE.match(s)}
    if args.trust_url:
        trusted_urls |= {s for s in sources if URL_RE.match(s)}
    now = instinct.now_utc(args.now)
    if not sources:
        print(json.dumps({"ok": True, "sources": 0, "events": 0, "planned": 0,
                          "ignored_ics_argument": bool(args.note_ignored_ics) or None,
                          "note": "set CAM_CALENDAR_ICS (path or private ICS URL) or pass --ics"}, indent=2))
        return 0

    events: list[dict] = []
    errors: list[str] = []
    allow_private = bool(os.environ.get("CAM_CALENDAR_ALLOW_PRIVATE"))
    for src in sources:
        try:
            events.extend(parse_ics(read_source(src, trusted_urls, allow_private=allow_private)))
        except Exception as exc:  # noqa: BLE001 — report per source, keep going
            errors.append(f"{src}: {exc.__class__.__name__}: {exc}")
    broken = [f"{e['uid']}: {e['broken']}" for e in events if e.get("broken")]

    planned = plan(events, now, args.horizon_days, existing_source_refs())
    new_items = [p for p in planned if p.get("job")]
    updates = [p for p in planned if p.get("update_ref")]
    dropped = 0
    if args.write:
        for item in planned:
            if instinct.drop_event(item, now):
                dropped += 1
    print(json.dumps({
        "ok": not errors, "sources": len(sources), "events": len(events),
        "in_horizon_new": len(new_items), "rescheduled": len(updates), "dropped": dropped, "write": args.write,
        "errors": errors,
        "broken_fields": broken,
        "ignored_ics_argument": bool(args.note_ignored_ics) or None,
        "planned": [{"job": p["job"], "due": p["due"], "priority": p["priority"],
                     "source_ref": p["source_ref"]} for p in new_items],
        "updates": [{"source_ref": p["update_ref"], "due": p["update"]["due"]} for p in updates],
        "next": "python3 scripts/instinct.py sync" if dropped else None,
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
