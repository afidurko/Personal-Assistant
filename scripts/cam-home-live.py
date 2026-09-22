#!/usr/bin/env python3
"""Cam Home Live — zero-dependency mission control for Aaron.

One stdlib HTTP server that makes the home usable live, per build plan
phase 4 (interactivity): see what's running, what's working, what needs
help, file suggestions that become tickets, and Cam presence — plus the
converse companion and connectome viz mounted on the same port.

  python3 scripts/cam-home-live.py            # http://127.0.0.1:8790
  python3 scripts/cam-home-live.py --port 9000

Read-only by design: no outbound motors, no enhance-apply, no merges.
Suggestions append to the inbox queue (vault/00-Inbox) for ticketing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_avatar  # noqa: E402
import cam_cortex  # noqa: E402

HOME_WEB = ROOT / "companions" / "home"
CONVERSE_WEB = ROOT / "companions" / "web"
CONNECTOME_WEB = ROOT / "visualizations" / "connectome"
FACE = ROOT / "identity" / "persona" / "cam-face.jpg"
SUGGESTIONS = ROOT / "vault" / "00-Inbox" / "home-suggestions.jsonl"
LIVE_ACTIVITY = ROOT / "vault" / "10-Mesh-Distillates" / "live-activity.json"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"

STATUS_TTL_S = 60
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".glb": "model/gltf-binary",
}

_status_lock = threading.Lock()
_status_cache: dict = {"at": 0.0, "data": None, "refreshing": False}

CORTEX = cam_cortex.Cortex()
CORTEX_TICK_S = 25


def brain_state() -> dict:
    if CORTEX.tick_count == 0:
        CORTEX.tick(get_status())
    return CORTEX.state()


def cortex_loop() -> None:
    while True:
        try:
            CORTEX.tick(get_status())
        except Exception:
            pass
        time.sleep(CORTEX_TICK_S)


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_json(cmd: list[str], timeout: int = 60) -> dict:
    try:
        p = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
        )
        out = p.stdout.strip()
        data = json.loads(out) if out.startswith(("{", "[")) else {"raw": out[:2000]}
        return {"ok": p.returncode == 0, "data": data}
    except Exception as e:
        return {"ok": False, "data": {"error": str(e)[:200]}}


def read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def tail_events(n: int = 30) -> list[dict]:
    if not EVENTS.exists():
        return []
    rows = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def compute_status() -> dict:
    py = sys.executable
    return {
        "at": utc(),
        "assistant": "Cam",
        "human": "Aaron",
        "system": run_json([py, "scripts/cam-system.py", "--json", "--no-write"]),
        "build_plan": run_json([py, "scripts/build-plan-check.py", "--json"]),
        "avatar": run_json([py, "scripts/avatar-check.py", "--json"]),
        "auto_sync": run_json(
            [py, "scripts/auto-sync.py", "--json", "--fetch-timeout", "5"]
        ),
        "needs_attention": run_json(
            [py, "scripts/needs-attention.py", "--json"], timeout=120
        ),
        "live_activity": read_json(LIVE_ACTIVITY),
        "recent_events": tail_events(),
    }


def get_status(force: bool = False) -> dict:
    now = time.time()
    with _status_lock:
        fresh = _status_cache["data"] is not None and (
            now - _status_cache["at"] < STATUS_TTL_S
        )
        if fresh and not force:
            return _status_cache["data"]
    data = compute_status()
    with _status_lock:
        _status_cache["data"] = data
        _status_cache["at"] = time.time()
    return data


def list_suggestions() -> list[dict]:
    if not SUGGESTIONS.exists():
        return []
    rows = []
    for line in SUGGESTIONS.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def add_suggestion(text: str, author: str) -> dict:
    entry = {
        "id": str(uuid.uuid4())[:8],
        "at": utc(),
        "author": author or "Aaron",
        "text": text.strip()[:2000],
        "status": "queued",
        "queued_for": "nulltickets (phase 1) — until then triaged by daily loop",
    }
    SUGGESTIONS.parent.mkdir(parents=True, exist_ok=True)
    with SUGGESTIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


class Handler(BaseHTTPRequestHandler):
    server_version = "CamHomeLive/1.0"

    def log_message(self, fmt: str, *args) -> None:  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), MIME[".json"])

    def _static(self, base: Path, rel: str) -> None:
        rel = rel.lstrip("/") or "index.html"
        path = (base / rel).resolve()
        if not str(path).startswith(str(base.resolve())) or not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = MIME.get(path.suffix.lower(), "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)

    def _redirect(self, target: str) -> None:
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _brain_stream(self) -> None:
        """Server-sent events: live thought feed + state snapshots."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def emit(event: str, obj) -> None:
            payload = f"event: {event}\ndata: {json.dumps(obj)}\n\n"
            self.wfile.write(payload.encode("utf-8"))
            self.wfile.flush()

        try:
            state = brain_state()
            emit("state", state)
            seq = max((t["seq"] for t in state["thoughts"]), default=0)
            last_tick = state["tick"]
            while True:
                time.sleep(1.5)
                fresh = CORTEX.thoughts_since(seq)
                for th in fresh:
                    emit("thought", th)
                    seq = th["seq"]
                if CORTEX.tick_count != last_tick:
                    last_tick = CORTEX.tick_count
                    emit("state", CORTEX.state())
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_GET(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        if p == "/api/home/status":
            self._json(get_status())
        elif p == "/api/brain/state":
            self._json(brain_state())
        elif p == "/api/brain/stream":
            self._brain_stream()
        elif p == "/api/avatar/contract":
            self._json(cam_avatar.contract())
        elif p == "/api/home/suggestions":
            self._json({"suggestions": list_suggestions()})
        elif p == "/api/home/health":
            self._json({"ok": True, "at": utc(), "app": "cam-home-live"})
        elif p == "/face.jpg":
            self._static(FACE.parent, FACE.name)
        elif p in ("/cam", "/cam/"):
            self._redirect("/converse/")
        elif p in ("/cortex", "/cortex/"):
            self._redirect("/connectome/")
        elif p.startswith("/converse"):
            self._static(CONVERSE_WEB, p[len("/converse") :])
        elif p.startswith("/connectome"):
            self._static(CONNECTOME_WEB, p[len("/connectome") :])
        else:
            self._static(HOME_WEB, p)

    def do_POST(self) -> None:  # noqa: N802
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
        if p == "/api/avatar/speak":
            text = (body.get("text") or "").strip()
            if not text:
                self._json({"ok": False, "error": "text required"}, 400)
                return
            self._json(cam_avatar.timeline(text[:1200], body.get("emotion", "warm")))
        elif p == "/api/home/suggest":
            text = (body.get("text") or "").strip()
            if not text:
                self._json({"ok": False, "error": "text required"}, 400)
                return
            entry = add_suggestion(text, body.get("author", "Aaron"))
            self._json({"ok": True, "suggestion": entry})
        elif p == "/api/home/refresh":
            threading.Thread(
                target=get_status, kwargs={"force": True}, daemon=True
            ).start()
            self._json({"ok": True, "refreshing": True})
        else:
            self._json({"ok": False, "error": "unknown endpoint"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cam Home Live mission control")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--warm", action="store_true", help="compute status before serving")
    args = ap.parse_args()

    if args.warm:
        get_status(force=True)
    threading.Thread(target=cortex_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Cam Home Live → http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
