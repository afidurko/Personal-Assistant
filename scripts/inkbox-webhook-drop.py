#!/usr/bin/env python3
"""Inkbox webhook receiver → verified drop file.

The web-facing receiver (nullclaw hook, a tiny Flask/uvicorn shim, or a cron
that pulls the Inkbox SDK) pipes each raw webhook body through this script.
It verifies Inkbox's signature (HMAC-SHA256 over the raw body with
INKBOX_WEBHOOK_SECRET), writes ONE file per event with O_EXCL so nothing can
be overwritten or raced, and stamps `_verified.mac` so `inkbox-inbound.py`
can prove the file was produced here and not edited since.

    cat body.json | python3 scripts/inkbox-webhook-drop.py --signature "$SIG"
    python3 scripts/inkbox-webhook-drop.py --file body.json --signature sha256=<hex>

Without the secret the script refuses (CLI-only --unsigned-ok exists for
manual exports; those drops are then folded only when inkbox-inbound runs
without --require-signed).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cam_privacy as privacy  # noqa: E402

MAX_BODY = 1_000_000


def inbound_dir() -> Path:
    return privacy.scoped_dir("inkbox/inbound", "INKBOX_INBOUND_DIR", ROOT / "data/inkbox/inbound")


def canonical_event(raw: dict) -> bytes:
    body = {k: v for k, v in raw.items() if k != "_verified"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_signature(body: bytes, signature: str, secret: bytes) -> bool:
    sig = (signature or "").strip()
    if sig.lower().startswith("sha256="):
        sig = sig[7:]
    want = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return bool(sig) and hmac.compare_digest(want.lower(), sig.lower())


def write_drop(raw: dict, secret: bytes | None, now: datetime, dest: Path) -> Path:
    privacy.enter(dest)
    stamp: dict = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "receiver": "scripts/inkbox-webhook-drop.py",
                   "body_sha256": hashlib.sha256(canonical_event(raw)).hexdigest()}
    if secret:
        stamp["alg"] = "hmac-sha256"
        stamp["mac"] = hmac.new(secret, canonical_event(raw), hashlib.sha256).hexdigest()
    doc = {**{k: v for k, v in raw.items() if k != "_verified"}, "_verified": stamp}
    name = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{stamp['body_sha256'][:12]}.json"
    path = dest / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # never overwrite, never race
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=2) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="verify an Inkbox webhook body and drop it for inkbox-inbound")
    parser.add_argument("--file", help="raw body file (default stdin)")
    parser.add_argument("--signature", help="value of the Inkbox signature header (hex or sha256=hex)")
    parser.add_argument("--dir", help="inbound dir override (tests)")
    parser.add_argument("--now", help="ISO8601 clock override")
    parser.add_argument("--unsigned-ok", action="store_true",
                        help="CLI only: accept a body without verifying (manual export); drop is left unstamped")
    args = parser.parse_args(argv)

    body = Path(args.file).read_bytes() if args.file else sys.stdin.buffer.read()
    if len(body) > MAX_BODY:
        print(json.dumps({"ok": False, "error": "body too large"}))
        return 2
    secret = os.environ.get("INKBOX_WEBHOOK_SECRET", "").encode("utf-8") or None
    if not args.unsigned_ok:
        if not secret:
            print(json.dumps({"ok": False, "error": "INKBOX_WEBHOOK_SECRET not set — refusing unverified drop "
                                                    "(use --unsigned-ok for a manual export)"}))
            return 3
        if not verify_signature(body, args.signature or "", secret):
            print(json.dumps({"ok": False, "error": "signature mismatch — body discarded", "stored": False}))
            return 4
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"body is not JSON: {exc}"}))
        return 5
    if not isinstance(raw, dict):
        print(json.dumps({"ok": False, "error": "body must be a JSON object"}))
        return 5
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc) if args.now \
        else datetime.now(timezone.utc)
    dest = Path(args.dir) if args.dir else inbound_dir()
    path = write_drop(raw, None if args.unsigned_ok else secret, now, dest)
    print(json.dumps({"ok": True, "stored": str(path), "verified": not args.unsigned_ok,
                      "next": "python3 scripts/inkbox-inbound.py --write"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
