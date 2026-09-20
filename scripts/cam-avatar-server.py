#!/usr/bin/env python3
"""Cam avatar service — AvatarFrame timelines over HTTP (build-plan planned path).

  python3 scripts/cam-avatar-server.py            # http://127.0.0.1:8791

Endpoints:
  GET  /avatar/health    — liveness
  GET  /avatar/contract  — AvatarFrame contract + muscle spec + keys
  POST /avatar/speak     — {"text": "...", "emotion": "warm"} → timeline

Tier 0 is procedural (no weights). When hf_realtime weights are cached
(scripts/avatar-fetch-models.py), the same endpoints upgrade in place.
Presence output stays gated by switch.presence; this service renders only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_avatar  # noqa: E402


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Handler(BaseHTTPRequestHandler):
    server_version = "CamAvatar/1.0"

    def log_message(self, fmt: str, *args) -> None:
        pass

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        if p == "/avatar/health":
            self._json({"ok": True, "at": utc(), "app": "cam-avatar", "tier": "procedural_tier0"})
        elif p == "/avatar/contract":
            self._json(cam_avatar.contract())
        else:
            self._json({"ok": False, "error": "unknown endpoint"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            body = {}
        if p == "/avatar/speak":
            text = (body.get("text") or "").strip()
            if not text:
                self._json({"ok": False, "error": "text required"}, 400)
                return
            self._json(cam_avatar.timeline(text[:1200], body.get("emotion", "neutral")))
        else:
            self._json({"ok": False, "error": "unknown endpoint"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cam avatar AvatarFrame service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8791)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Cam avatar → http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
