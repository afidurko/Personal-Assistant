#!/usr/bin/env python3
"""Cam live converse server — mic/camera companion backend.

Serves companions/web (browser mic + camera) and accepts conversation turns.
On Aaron's machine: python3 scripts/cam-converse-server.py
Then open http://127.0.0.1:8787 on phone/Mac (same LAN or localhost).

Cloud Agent VMs have no mic — run this locally for real listen/speak tests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "companions" / "web"
LOG_DIR = ROOT / "vault" / "10-Mesh-Distillates" / "converse"
VOICE = json.loads((ROOT / "config" / "persona" / "voice.json").read_text(encoding="utf-8"))
VISUAL = ROOT / "identity" / "aaron" / "VISUAL_PROFILE.md"
TAILSCALE = ROOT / "config" / "network" / "tailscale.json"


def load_tailscale() -> dict:
    if not TAILSCALE.exists():
        return {"enabled": False}
    return json.loads(TAILSCALE.read_text(encoding="utf-8"))


def converse_urls(ts: dict) -> dict:
    c = ts.get("converse") or {}
    host = c.get("cam_host_tailscale_ip") or c.get("cam_host_magicdns") or "cam-host"
    port = int(c.get("port") or 8787)
    url = f"http://{host}:{port}"
    return {
        "via": c.get("via", "tailscale" if ts.get("enabled") else "local"),
        "cam_host": host,
        "port": port,
        "url": url,
        "iphone_open": url,
        "local_open": f"http://127.0.0.1:{port}",
    }

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_sense(sense: str, goal: str = "") -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "connectome-route.py"),
        "--sense",
        sense,
    ]
    if goal:
        cmd.extend(["--goal", goal])
    try:
        out = subprocess.check_output(cmd, cwd=str(ROOT), text=True, timeout=10)
        return json.loads(out)
    except Exception as e:
        return {"accepted": False, "error": str(e), "motor_plan": []}


def cam_reply(aaron_text: str, history: list[dict]) -> str:
    """Soft airy Cam reply. Prefer short, warm, fluent English."""
    t = (aaron_text or "").strip()
    low = t.lower()
    if not t:
        return "I'm here, Aaron. Whenever you're ready — I'm listening."
    if any(w in low for w in ("hello", "hi cam", "hey cam", "hi ", "hey ")):
        return (
            "Hi Aaron. Soft and clear on my side. "
            "I can hear you through the companion when the mic is on."
        )
    if "mic" in low or "microphone" in low or "hear me" in low or "working" in low:
        return (
            "If you can read this after speaking, the listen path is up. "
            "I'm Cam — soft voice, always here for you. Say what you need."
        )
    if "camera" in low or "face" in low or "see me" in low:
        return (
            "Camera is wired through the companion too. "
            "I already have your face enrollment from the photos you shared. "
            "Keep the lens on you and I'll treat that as Aaron present."
        )
    if "who are you" in low or "your name" in low:
        return (
            "I'm Cam — thirty-two, from Argentina, soft airy English. "
            "You're Aaron, my only task-giver. What should we do?"
        )
    if "thank" in low:
        return "Of course. I'm right here."
    # Default: acknowledge + invite next beat
    short = t if len(t) < 120 else t[:117] + "…"
    return (
        f"I heard you: “{short}”. "
        "Tell me the next step and I'll take it from there."
    )


class State:
    def __init__(self) -> None:
        self.session_id = str(uuid.uuid4())
        self.history: list[dict] = []
        self.started = utc_now()
        LOG_DIR.mkdir(parents=True, exist_ok=True)


STATE = State()


class Handler(BaseHTTPRequestHandler):
    server_version = "CamConverse/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[cam-converse] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, code: int, obj: dict) -> None:
        body = (json.dumps(obj, indent=2) + "\n").encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            ts = load_tailscale()
            urls = converse_urls(ts)
            self._json(
                200,
                {
                    "ok": True,
                    "assistant": "Cam",
                    "session_id": STATE.session_id,
                    "started": STATE.started,
                    "capabilities": {
                        "mic": True,
                        "camera": True,
                        "speak": True,
                        "enabled": True,
                        "enabled_by": "Aaron",
                        "ios_capture_mode": "standing_on",
                        "aaron_face_enrolled": VISUAL.exists(),
                        "host_has_local_mic": False,  # browser supplies mic
                        "tailscale": bool(ts.get("enabled")),
                    },
                    "network": {
                        "tailscale_enabled": bool(ts.get("enabled")),
                        **urls,
                    },
                    "voice": {
                        "character": VOICE["identity"]["voice_character"],
                        "tts_browser_hint": "speechSynthesis; soft rate 0.95",
                    },
                },
            )
            return
        if path == "/api/session":
            self._json(
                200,
                {
                    "session_id": STATE.session_id,
                    "history": STATE.history[-50:],
                    "turns": len(STATE.history),
                },
            )
            return

        # static companion (relative paths for iOS PWA / on-device)
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if rel in {"assets/cam-face.jpg", "face.jpg"}:
            file_path = WEB / "face.jpg"
            if not file_path.is_file():
                file_path = ROOT / "identity" / "persona" / "cam-face.jpg"
        else:
            file_path = (WEB / rel).resolve()
            if not str(file_path).startswith(str(WEB.resolve())):
                self.send_error(403)
                return
        if not file_path.is_file():
            self.send_error(404)
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self._cors()
        ctype = MIME.get(file_path.suffix, "application/octet-stream")
        if file_path.name.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_json()

        if path == "/api/spike/mic":
            route = route_sense("sense.ios.mic", goal=payload.get("purpose", "listen"))
            event = {
                "at": utc_now(),
                "type": "mic_spike",
                "duration_ms": payload.get("duration_ms"),
                "transcript_preview": (payload.get("transcript") or "")[:200],
                "route": route,
            }
            self._append_log("spikes", event)
            self._json(200, {"accepted": True, "event": event})
            return

        if path == "/api/spike/camera":
            route = route_sense("sense.ios.camera", goal=payload.get("purpose", "see"))
            event = {
                "at": utc_now(),
                "type": "camera_spike",
                "frame_bytes": payload.get("frame_bytes"),
                "aaron_face_hint": payload.get("aaron_face_hint"),
                "route": route,
            }
            self._append_log("spikes", event)
            self._json(200, {"accepted": True, "event": event})
            return

        if path == "/api/turn":
            text = (payload.get("text") or payload.get("transcript") or "").strip()
            source = payload.get("source", "text")
            sense = "sense.ios.mic" if source in {"mic", "speech"} else "sense.chat.aaron"
            route = route_sense(sense, goal=text)
            reply = cam_reply(text, STATE.history)
            turn = {
                "id": str(uuid.uuid4()),
                "at": utc_now(),
                "source": source,
                "aaron": text,
                "cam": reply,
                "route": {
                    "sense": sense,
                    "hotspot_id": route.get("hotspot_id"),
                    "motor_plan": route.get("motor_plan"),
                    "accepted": route.get("accepted", True),
                },
                "speak": {
                    "enabled": True,
                    "rate": 0.95,
                    "pitch": 1.05,
                    "lang": "en-US",
                    "style": "soft airy fluent English",
                },
            }
            STATE.history.append(turn)
            self._append_log("turns", turn)
            self._json(200, turn)
            return

        self.send_error(404)

    def _append_log(self, kind: str, obj: dict) -> None:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = LOG_DIR / f"{day}-{STATE.session_id[:8]}-{kind}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    args = p.parse_args()
    ts = load_tailscale()
    urls = converse_urls(ts)
    host = args.host or (ts.get("converse") or {}).get("bind_host") or "0.0.0.0"
    port = args.port or urls["port"]
    WEB.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(
        f"Cam converse listening on http://{host}:{port}\n"
        f"  local:     {urls['local_open']}\n"
        f"  tailscale: {urls['iphone_open']}  (set MagicDNS in config/network/tailscale.json)\n"
        f"  health:    http://127.0.0.1:{port}/api/health\n"
        f"  session: {STATE.session_id}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
