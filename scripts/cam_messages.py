#!/usr/bin/env python3
"""Cam message center — the "it never sends me messages" fix.

Cam now has a real delivery path:

- **Inbox** (always on): every proactive message lands in
  `data/runtime/cam-inbox.jsonl`; the live UI shows and (optionally)
  speaks them, and surfaces browser notifications.
- **Reminders**: parsed by the brain, stored durably, fired by the
  server's background loop, delivered as inbox messages.
- **Outbound push** (optional, off by default per `.clinerules`): when
  `switch.outbound` is flipped by Aaron via `CAM_OUTBOUND=on` *and* a
  channel is configured — `CAM_NTFY_TOPIC` (ntfy.sh push to phone) or
  `CAM_WEBHOOK_URL` (any JSON webhook) — messages also leave the box.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime"
INBOX_PATH = RUNTIME / "cam-inbox.jsonl"
REMINDERS_PATH = RUNTIME / "cam-reminders.json"
OUTBOX_PATH = RUNTIME / "cam-outbox.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def outbound_config() -> dict:
    enabled = os.environ.get("CAM_OUTBOUND", "").lower() in {"1", "on", "true", "yes"}
    ntfy = os.environ.get("CAM_NTFY_TOPIC", "").strip()
    webhook = os.environ.get("CAM_WEBHOOK_URL", "").strip()
    return {
        "enabled": enabled and bool(ntfy or webhook),
        "switch": "switch.outbound",
        "requested": enabled,
        "channels": [c for c, v in (("ntfy", ntfy), ("webhook", webhook)) if v],
    }


class MessageCenter:
    def __init__(self, inbox_path: Path = INBOX_PATH,
                 reminders_path: Path = REMINDERS_PATH) -> None:
        self.inbox_path = inbox_path
        self.reminders_path = reminders_path
        self._lock = threading.Lock()
        self.messages: list[dict] = []
        self.reminders: list[dict] = []
        self._load()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if self.inbox_path.exists():
            for line in self.inbox_path.read_text(encoding="utf-8").splitlines():
                try:
                    self.messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.messages = self.messages[-500:]
        if self.reminders_path.exists():
            try:
                self.reminders = list(
                    json.loads(self.reminders_path.read_text(encoding="utf-8")).get("reminders") or [])
            except (json.JSONDecodeError, OSError):
                self.reminders = []

    def _save_reminders(self) -> None:
        self.reminders_path.parent.mkdir(parents=True, exist_ok=True)
        self.reminders_path.write_text(
            json.dumps({"updated": utc_now(), "reminders": self.reminders},
                       indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

    # -- messages --------------------------------------------------------------

    def send(self, subject: str, body: str, *, kind: str = "info",
             priority: str = "normal", meta: dict | None = None,
             allow_outbound: bool = True) -> dict:
        msg = {
            "id": str(uuid.uuid4())[:8],
            "at": utc_now(),
            "kind": kind,
            "priority": priority,
            "subject": subject.strip()[:140],
            "body": body.strip(),
            "read": False,
            "meta": meta or {},
        }
        with self._lock:
            self.messages.append(msg)
            self.messages = self.messages[-500:]
            self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
            with self.inbox_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        if allow_outbound:
            delivered = self._push_outbound(msg)
            if delivered:
                msg["meta"]["outbound"] = delivered
        return msg

    def list(self, since: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = list(self.messages)
        if since:
            rows = [m for m in rows if m.get("at", "") > since]
        return rows[-limit:]

    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for m in self.messages if not m.get("read"))

    def mark_read(self, ids: list[str] | None = None) -> int:
        n = 0
        with self._lock:
            for m in self.messages:
                if not m.get("read") and (ids is None or m.get("id") in ids):
                    m["read"] = True
                    n += 1
        return n

    # -- reminders --------------------------------------------------------------

    def add_reminder(self, what: str, due: datetime) -> dict:
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        rem = {
            "id": str(uuid.uuid4())[:8],
            "what": what.strip(),
            "due": due.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "created": utc_now(),
            "fired": False,
        }
        with self._lock:
            self.reminders.append(rem)
            self._save_reminders()
        return rem

    def pending_reminders(self) -> list[dict]:
        with self._lock:
            return [r for r in self.reminders if not r.get("fired")]

    def fire_due(self, now: datetime | None = None) -> list[dict]:
        """Called by the server heartbeat; delivers due reminders as messages."""
        now = now or datetime.now(timezone.utc)
        now_s = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fired: list[dict] = []
        with self._lock:
            due = [r for r in self.reminders if not r.get("fired") and r.get("due", "") <= now_s]
            for r in due:
                r["fired"] = True
                r["fired_at"] = now_s
            if due:
                self._save_reminders()
        for r in due:
            self.send(
                "Reminder", f"Aaron — it's time: {r['what']}",
                kind="reminder", priority="high", meta={"reminder_id": r["id"]},
            )
            fired.append(r)
        return fired

    # -- outbound (gated) ---------------------------------------------------------

    def _push_outbound(self, msg: dict) -> list[dict]:
        cfg = outbound_config()
        if not cfg["enabled"]:
            return []
        delivered: list[dict] = []
        ntfy = os.environ.get("CAM_NTFY_TOPIC", "").strip()
        if ntfy:
            ok, err = self._post(
                f"https://ntfy.sh/{ntfy}",
                data=msg["body"].encode("utf-8"),
                headers={"Title": f"Cam · {msg['subject']}",
                         "Priority": "high" if msg["priority"] == "high" else "default"},
            )
            delivered.append({"channel": "ntfy", "ok": ok, "error": err})
        webhook = os.environ.get("CAM_WEBHOOK_URL", "").strip()
        if webhook:
            ok, err = self._post(
                webhook,
                data=json.dumps({"text": f"Cam · {msg['subject']}\n{msg['body']}"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            delivered.append({"channel": "webhook", "ok": ok, "error": err})
        try:
            OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
            with OUTBOX_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": utc_now(), "msg_id": msg["id"],
                                     "delivered": delivered}) + "\n")
        except OSError:
            pass
        return delivered

    @staticmethod
    def _post(url: str, data: bytes, headers: dict) -> tuple[bool, str | None]:
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=8) as resp:
                return 200 <= resp.status < 300, None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return False, str(exc)
