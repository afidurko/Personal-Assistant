#!/usr/bin/env python3
"""Cam Live — the day-to-day assistant server (brain + teams + messages + vision).

One process, stdlib only, works offline and gets smarter when a model or
network is available:

    python3 scripts/cam-live-server.py            # → http://127.0.0.1:8899

Wired pieces:
- CamBrain        real reasoning core (LLM if configured, local cortex always)
- TeamOrchestrator Cam-as-head-agent; team leads run subagents in parallel
- MessageCenter   inbox + reminders + gated outbound push
- VisionState     object identification (browser coco-ssd and/or numpy cortex)

Voice: mic turns are ACCEPTED by default ("open mic"). If Aaron has
enrolled his voice profile, the gate verifies scores like before — but a
missing enrollment no longer makes Cam deaf.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cam_brain import CamBrain, LLMBackend, Memory  # noqa: E402
from cam_messages import MessageCenter, outbound_config  # noqa: E402
from cam_teams import TeamOrchestrator  # noqa: E402
from cam_vision import VisionState, analyze_rgba_b64  # noqa: E402

WEB = ROOT / "companions" / "live"
VOICE_GATE_CFG = ROOT / "config" / "identity" / "aaron-voice-gate.json"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webmanifest": "application/manifest+json",
}

SPEAK = {"enabled": True, "rate": 0.95, "pitch": 1.05, "lang": "en-US",
         "style": "soft airy fluent English"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Voice gate with open-mic fallback (the "it's not listening" fix)
# ---------------------------------------------------------------------------

def load_gate_policy() -> dict:
    policy = {"open_mic_when_not_enrolled": True, "match_threshold": 0.85}
    if VOICE_GATE_CFG.exists():
        try:
            policy.update(json.loads(VOICE_GATE_CFG.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    policy.setdefault("open_mic_when_not_enrolled", True)
    return policy


def gate_turn(payload: dict) -> dict:
    source = payload.get("source", "text")
    if source not in {"mic", "speech"}:
        return {"accepted": True, "mode": "text"}
    policy = load_gate_policy()
    enrolled = bool(payload.get("enrolled"))
    score = payload.get("aaron_voice_score")
    if enrolled and isinstance(score, (int, float)):
        thr = float(policy.get("match_threshold", 0.85))
        ok = float(score) >= thr
        return {"accepted": ok, "mode": "verified" if ok else "rejected",
                "score": float(score), "threshold": thr,
                "reason": None if ok else "score_below_threshold"}
    if policy.get("open_mic_when_not_enrolled", True):
        return {"accepted": True, "mode": "open_mic",
                "note": "voice not enrolled — accepting Aaron's mic openly"}
    return {"accepted": False, "mode": "rejected", "reason": "enrollment_required"}


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

class App:
    def __init__(self) -> None:
        self.started = utc_now()
        self.memory = Memory()
        self.llm = LLMBackend()
        self.messages = MessageCenter()
        self.vision = VisionState()
        self.teams = TeamOrchestrator(
            memory=self.memory,
            llm=self.llm if self.llm.resolve() else None,
            notify=lambda m: self.messages.send(
                m["subject"], m["body"], kind=m.get("kind", "info"), meta=m.get("meta")),
        )
        self.brain = CamBrain(
            memory=self.memory,
            llm=self.llm,
            task_dispatch=lambda goal: self.teams.dispatch(goal),
            reminder_create=lambda what, due: self.messages.add_reminder(what, due),
            vision_latest=self.vision.latest,
            status_provider=lambda: {
                "tasks_running": self.teams.running_count(),
                "unread_messages": self.messages.unread_count(),
            },
        )
        self._stop = threading.Event()
        self._heartbeat = threading.Thread(target=self._beat, daemon=True, name="cam-heartbeat")

    def start_background(self) -> None:
        self._heartbeat.start()
        st = self.brain.status()
        engine = st.get("backend") or "local cortex"
        self.messages.send(
            "Cam is online",
            f"Hi Aaron — I'm up. Reasoning engine: {engine}. "
            f"I know {st['memory_facts']} facts, "
            f"{len(self.messages.pending_reminders())} reminders pending. "
            "Talk to me, give a team a task, or open my camera.",
            kind="system", allow_outbound=False)

    def _beat(self) -> None:
        while not self._stop.is_set():
            try:
                self.messages.fire_due()
            except Exception:
                pass
            self._stop.wait(3.0)

    def state(self) -> dict:
        return {
            "ok": True,
            "assistant": "Cam",
            "started": self.started,
            "at": utc_now(),
            "brain": self.brain.status(),
            "voice_gate": {**load_gate_policy(), "listening": True},
            "outbound": outbound_config(),
            "messages": {"unread": self.messages.unread_count(),
                         "total": len(self.messages.messages)},
            "reminders_pending": len(self.messages.pending_reminders()),
            "tasks": {"running": self.teams.running_count(),
                      "total": len(self.teams.tasks),
                      "teams": [{"id": t["id"], "name": t["name"]} for t in self.teams.teams]},
            "vision": {"latest": self.vision.latest()},
        }


APP = App()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "CamLive/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[cam-live] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, code: int, obj: dict) -> None:
        body = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 32 * 1024 * 1024:
            return {}
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    # -- GET ------------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/state":
            self._json(200, APP.state())
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "assistant": "Cam", "started": APP.started})
            return
        if path == "/api/messages":
            since = (qs.get("since") or [None])[0]
            self._json(200, {"messages": APP.messages.list(since=since),
                             "unread": APP.messages.unread_count()})
            return
        if path == "/api/reminders":
            self._json(200, {"reminders": APP.messages.pending_reminders()})
            return
        if path == "/api/tasks":
            self._json(200, {"tasks": APP.teams.list_tasks(),
                             "running": APP.teams.running_count()})
            return
        if path.startswith("/api/tasks/"):
            task = APP.teams.get(path.rsplit("/", 1)[-1])
            self._json(200 if task else 404, {"task": task})
            return
        if path == "/api/vision/latest":
            self._json(200, {"latest": APP.vision.latest(),
                             "history": APP.vision.history(10)})
            return
        if path == "/api/history":
            self._json(200, {"history": APP.brain.history[-50:]})
            return

        # static UI
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if rel == "face.jpg":
            fp = ROOT / "identity" / "persona" / "cam-face.jpg"
        else:
            fp = (WEB / rel).resolve()
            if not str(fp).startswith(str(WEB.resolve())):
                self.send_error(403)
                return
        if not fp.is_file():
            self.send_error(404)
            return
        data = fp.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", MIME.get(fp.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # -- POST -----------------------------------------------------------------

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_json()

        if path == "/api/chat":
            gate = gate_turn(payload)
            text = (payload.get("text") or payload.get("transcript") or "").strip()
            if not gate["accepted"]:
                self._json(403, {
                    "accepted": False, "gate": gate,
                    "cam": "I couldn't verify that was your voice, Aaron — try again or type it.",
                    "speak": SPEAK,
                })
                return
            turn = APP.brain.respond(text, source=payload.get("source", "text"))
            turn["accepted"] = True
            turn["gate"] = gate
            turn["speak"] = SPEAK
            self._json(200, turn)
            return

        if path == "/api/tasks":
            goal = (payload.get("goal") or "").strip()
            if not goal:
                self._json(400, {"error": "goal_required"})
                return
            task = APP.teams.dispatch(goal)
            self._json(200, {"task": task})
            return

        if path == "/api/reminders":
            what = (payload.get("what") or "").strip()
            due_raw = payload.get("due")
            if not what or not due_raw:
                self._json(400, {"error": "what_and_due_required"})
                return
            try:
                due = datetime.fromisoformat(str(due_raw).replace("Z", "+00:00"))
            except ValueError:
                self._json(400, {"error": "bad_due_iso"})
                return
            rem = APP.messages.add_reminder(what, due)
            self._json(200, {"reminder": rem})
            return

        if path == "/api/messages/read":
            n = APP.messages.mark_read(payload.get("ids"))
            self._json(200, {"marked": n, "unread": APP.messages.unread_count()})
            return

        if path == "/api/messages/send":
            # Cam-to-Aaron note (e.g. from UI test button or other tools)
            msg = APP.messages.send(
                payload.get("subject") or "Note",
                payload.get("body") or "",
                kind=payload.get("kind") or "note")
            self._json(200, {"message": msg})
            return

        if path == "/api/vision/frame":
            b64 = payload.get("rgba_b64") or ""
            w = int(payload.get("width") or 0)
            h = int(payload.get("height") or 0)
            analysis = analyze_rgba_b64(b64, w, h)
            if analysis.get("ok"):
                APP.vision.ingest_frame_analysis(analysis)
            self._json(200 if analysis.get("ok") else 400, analysis)
            return

        if path == "/api/vision/detections":
            objs = payload.get("objects") or []
            snap = APP.vision.ingest_detections(objs, source=payload.get("source") or "cocossd")
            self._json(200, {"ok": True, "latest": snap})
            return

        self.send_error(404)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args()
    APP.start_background()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    st = APP.brain.status()
    print(
        f"Cam Live listening on http://{args.host}:{args.port}\n"
        f"  open:   http://127.0.0.1:{args.port}\n"
        f"  brain:  {st.get('engine')} (live_llm={st.get('live_llm')})\n"
        f"  state:  http://127.0.0.1:{args.port}/api/state",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
