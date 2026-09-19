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
VOICE_GATE_PATH = ROOT / "config" / "identity" / "aaron-voice-gate.json"
VOICE_PROFILE_PATH = ROOT / "identity" / "aaron" / "voice-profile.json"
VOICE_REJECTS_PATH = ROOT / "data" / "runtime" / "aaron-voice-rejects.jsonl"
VOICE_STATS_PATH = ROOT / "data" / "runtime" / "aaron-voice-stats.json"
VISUAL = ROOT / "identity" / "aaron" / "VISUAL_PROFILE.md"
TAILSCALE = ROOT / "config" / "network" / "tailscale.json"

sys.path.insert(0, str(ROOT / "scripts"))
try:
    import activity_emit
except Exception:  # pragma: no cover
    activity_emit = None  # type: ignore

try:
    from aaron_voice_gate import AaronVoiceGate, load_config as load_voice_config
except Exception:  # pragma: no cover
    AaronVoiceGate = None  # type: ignore
    load_voice_config = None  # type: ignore


VOICE_GATE = None
VOICE_CFG: dict = {}
if AaronVoiceGate is not None and load_voice_config is not None:
    try:
        VOICE_CFG = load_voice_config()
        # Prefer FunASR; fall back only when explicitly allowed for bring-up.
        VOICE_GATE = AaronVoiceGate(VOICE_CFG)
    except Exception as exc:  # pragma: no cover
        VOICE_GATE = None
        VOICE_CFG = {"_init_error": str(exc)}


def voice_gate_status() -> dict:
    if VOICE_GATE is None:
        return {
            "enabled": False,
            "enrolled": False,
            "ready": False,
            "error": VOICE_CFG.get("_init_error", "voice_gate_unavailable"),
        }
    st = VOICE_GATE.status()
    st["ready"] = bool(st.get("enrolled")) and bool(VOICE_CFG.get("enabled", True))
    return st


def gate_mic_turn(payload: dict) -> dict:
    """Require Aaron voice match for mic turns when configured.

    Accepts either:
      - audio_wav_b64: WAV bytes (preferred — server-side segment + match)
      - aaron_voice_score: precomputed score from companion (legacy / offline)
    """
    require = bool(VOICE_CFG.get("converse_require_voice_match_for_mic", True))
    source = payload.get("source", "text")
    if source not in {"mic", "speech"}:
        return {"required": False, "accepted": True, "reason": "text_bypass"}
    if not require:
        return {"required": False, "accepted": True, "reason": "gate_not_required"}

    status = voice_gate_status()
    if not status.get("enrolled"):
        return {
            "required": True,
            "accepted": False,
            "reason": "not_enrolled",
            "aaron_score": 0.0,
            "status": status,
        }

    audio_b64 = payload.get("audio_wav_b64") or payload.get("audio_b64")
    if audio_b64 and VOICE_GATE is not None:
        import base64

        try:
            raw = base64.b64decode(audio_b64)
        except Exception as exc:
            return {
                "required": True,
                "accepted": False,
                "reason": f"bad_audio_b64:{exc}",
                "aaron_score": 0.0,
            }
        result = VOICE_GATE.gate_wav_bytes(
            raw, device_id=str(payload.get("device_id") or "")
        )
        return {
            "required": True,
            "accepted": result.accepted,
            "reason": result.reason,
            "aaron_score": result.aaron_score,
            "segments": [s.__dict__ for s in result.segments],
            "aaron_speech_ms": result.aaron_speech_ms,
            "backend": result.backend,
            "spike": {
                "sense": "sense.aaron.voice",
                "score": result.aaron_score,
                "enrolled": True,
                "device_id": payload.get("device_id"),
            },
        }

    # Score-only path (companion already matched)
    if "aaron_voice_score" in payload:
        try:
            score = float(payload.get("aaron_voice_score"))
        except (TypeError, ValueError):
            score = 0.0
        thr = float(VOICE_CFG.get("threshold", 0.85))
        ok = score >= thr
        return {
            "required": True,
            "accepted": ok,
            "reason": "aaron_score_threshold" if ok else "score_below_threshold",
            "aaron_score": score,
            "threshold": thr,
            "spike": {
                "sense": "sense.aaron.voice",
                "score": score,
                "enrolled": True,
                "device_id": payload.get("device_id"),
            },
        }

    return {
        "required": True,
        "accepted": False,
        "reason": "mic_turn_missing_audio_or_score",
        "aaron_score": 0.0,
        "hint": "Send audio_wav_b64 (preferred) or aaron_voice_score with mic turns",
    }


def load_voice_gate() -> dict:
    if not VOICE_GATE_PATH.exists():
        return {
            "aaron_only": True,
            "noisy_environment_mode": True,
            "reject_non_aaron_asr": True,
            "require_enrollment_for_mic": True,
            "text_bypass": True,
            "match_threshold": 0.85,
            "noisy_threshold": 0.88,
            "addons": {},
        }
    return json.loads(VOICE_GATE_PATH.read_text(encoding="utf-8"))


class VoiceGateAddonsState:
    """Adaptive noise + reject stats for the Python converse server."""

    def __init__(self) -> None:
        self.rejects = 0
        self.accepts = 0
        self.last_reject_at: str | None = None
        self.last_reason: str | None = None
        self.adaptive_raised = False
        self.multi_speaker_streak = 0
        self.accepts_since_raise = 0

    def as_dict(self) -> dict:
        return {
            "rejects": self.rejects,
            "accepts": self.accepts,
            "last_reject_at": self.last_reject_at,
            "last_reason": self.last_reason,
            "adaptive_raised": self.adaptive_raised,
            "multi_speaker_streak": self.multi_speaker_streak,
        }


VOICE_ADDONS = VoiceGateAddonsState()


def evaluate_voice_gate(payload: dict, source: str, *, note: bool = True) -> dict:
    """Server-side Aaron-only gate for mic turns (scores come from companion)."""
    policy = load_voice_gate()
    score = payload.get("aaron_voice_score")
    score_f = float(score) if isinstance(score, (int, float)) else 0.0
    enrolled = payload.get("enrolled")
    multi = bool(payload.get("multi_speaker_hint"))
    addons = policy.get("addons") or {}
    adaptive = addons.get("adaptive_noise") or {}

    if source == "text" and policy.get("text_bypass", True):
        if note:
            VOICE_ADDONS.accepts += 1
        return {"accept": True, "reason": "text_bypass", "score": 1.0, "threshold": 0.0}
    if not policy.get("aaron_only", True) or not policy.get("reject_non_aaron_asr", True):
        if note:
            VOICE_ADDONS.accepts += 1
        return {"accept": True, "reason": "aaron_only_disabled", "score": score_f, "threshold": 0.0}
    if source not in {"mic", "speech"}:
        if note:
            VOICE_ADDONS.accepts += 1
        return {"accept": True, "reason": "non_mic_source", "score": score_f, "threshold": 0.0}
    if policy.get("require_enrollment_for_mic", True) and enrolled is False:
        gate = {
            "accept": False,
            "reason": "enrollment_required",
            "score": 0.0,
            "threshold": float(policy.get("match_threshold", 0.85)),
        }
        if note:
            _note_reject(gate, source, multi, payload.get("device_id"))
        return gate

    noisy_threshold = float(policy.get("noisy_threshold", 0.88))
    match_threshold = float(policy.get("match_threshold", 0.85))
    raised = False
    if adaptive.get("enabled", True):
        streak_need = int(adaptive.get("streak_to_raise", 2))
        raised = VOICE_ADDONS.adaptive_raised or (
            VOICE_ADDONS.multi_speaker_streak >= streak_need and multi
        )
        if raised:
            noisy_threshold = float(adaptive.get("raised_threshold", 0.91))

    threshold = (
        noisy_threshold
        if policy.get("noisy_environment_mode", True) or multi or raised
        else match_threshold
    )
    if score_f >= threshold:
        if note:
            VOICE_ADDONS.accepts += 1
            VOICE_ADDONS.accepts_since_raise += 1
            cooldown = int(adaptive.get("cooldown_accepts", 3))
            if VOICE_ADDONS.adaptive_raised and VOICE_ADDONS.accepts_since_raise >= cooldown:
                VOICE_ADDONS.adaptive_raised = False
                VOICE_ADDONS.multi_speaker_streak = 0
                VOICE_ADDONS.accepts_since_raise = 0
            if not multi:
                VOICE_ADDONS.multi_speaker_streak = 0
        return {
            "accept": True,
            "reason": "aaron_voice_match",
            "score": score_f,
            "threshold": threshold,
            "adaptive": raised,
        }

    gate = {
        "accept": False,
        "reason": "rejected_surrounding_speech" if multi else "below_threshold",
        "score": score_f,
        "threshold": threshold,
        "adaptive": raised,
    }
    if note:
        _note_reject(gate, source, multi, payload.get("device_id"))
    return gate


def _note_reject(gate: dict, source: str, multi: bool, device_id: object = None) -> None:
    VOICE_ADDONS.rejects += 1
    VOICE_ADDONS.last_reject_at = utc_now()
    VOICE_ADDONS.last_reason = gate.get("reason")
    VOICE_ADDONS.accepts_since_raise = 0
    if multi or gate.get("reason") == "rejected_surrounding_speech":
        VOICE_ADDONS.multi_speaker_streak += 1
    if gate.get("adaptive") or VOICE_ADDONS.multi_speaker_streak >= 2:
        VOICE_ADDONS.adaptive_raised = True
    try:
        VOICE_REJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "at": VOICE_ADDONS.last_reject_at,
            "source": source,
            "score": gate.get("score"),
            "threshold": gate.get("threshold"),
            "reason": gate.get("reason"),
            "multi_speaker_hint": multi,
            "device_id": device_id,
        }
        with VOICE_REJECTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        VOICE_STATS_PATH.write_text(
            json.dumps(VOICE_ADDONS.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def record_client_reject(payload: dict) -> dict:
    gate = {
        "accept": False,
        "reason": payload.get("reason") or "client_reject",
        "score": float(payload.get("score") or 0),
        "threshold": float(payload.get("threshold") or 0.88),
        "adaptive": VOICE_ADDONS.adaptive_raised,
    }
    _note_reject(
        gate,
        str(payload.get("source") or "mic"),
        bool(payload.get("multi_speaker_hint")),
        payload.get("device_id"),
    )
    return VOICE_ADDONS.as_dict()


def save_voice_profile(profile: object) -> str:
    VOICE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "subject": "Aaron",
        "saved_at": utc_now(),
        "source": "cam_voice_gate_addon",
        "profile": profile,
    }
    VOICE_PROFILE_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return str(VOICE_PROFILE_PATH.relative_to(ROOT))


def load_voice_profile() -> dict | None:
    if not VOICE_PROFILE_PATH.exists():
        return None
    try:
        return json.loads(VOICE_PROFILE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_tailscale() -> dict:
    if not TAILSCALE.exists():
        return {"enabled": False}
    return json.loads(TAILSCALE.read_text(encoding="utf-8"))


def emit_converse_activity(
    *,
    kind: str,
    source: str,
    sense: str = "",
    text: str = "",
    refresh: bool = True,
) -> list[dict]:
    """Push converse turn/spike into activity-events for DTI live mesh."""
    if activity_emit is None:
        return []
    rows = []
    if kind == "turn":
        stream = activity_emit.dual_stream("speak")
        tracts = (stream.get("tracts") or [
            "tract.arcuate",
            "tract.af_anterior",
            "tract.af_posterior",
            "tract.fat",
        ])[:5]
        rows.append(
            activity_emit.emit(
                neuron="neuron.language_in",
                kind="agent",
                area="area.wernicke",
                intensity=0.9,
                tracts=tracts,
                reason=f"converse_turn:{source}",
                source="cam_converse",
            )
        )
        if source in {"mic", "speech"}:
            rows.append(
                activity_emit.emit(
                    neuron="neuron.asr",
                    kind="agent",
                    area="area.auditory",
                    intensity=0.85,
                    tracts=["tract.mdlf", "tract.arcuate"],
                    reason="converse_mic",
                    source="cam_converse",
                )
            )
        rows.append(
            activity_emit.emit(
                neuron="neuron.speak_loop",
                kind="loop",
                area="area.broca",
                intensity=0.95,
                tracts=tracts,
                reason=f"dual_stream:{stream.get('winner', 'dorsal')}:speak",
                source="cam_converse",
            )
        )
        rows.append(
            activity_emit.emit(
                neuron="neuron.comms",
                kind="agent",
                area="area.broca",
                intensity=0.7,
                tracts=["tract.arcuate", "tract.fat"],
                reason="outbound_reply",
                source="cam_converse",
            )
        )
    elif kind == "mic_spike":
        rows.append(
            activity_emit.emit(
                neuron="neuron.asr",
                kind="agent",
                area="area.auditory",
                intensity=0.8,
                tracts=["tract.mdlf", "tract.arcuate"],
                reason="mic_spike",
                source="cam_converse",
            )
        )
    elif kind == "camera_spike":
        rows.append(
            activity_emit.emit(
                neuron="neuron.vision",
                kind="agent",
                area="area.visual",
                intensity=0.85,
                tracts=["tract.ilf", "tract.vof", "tract.ifof"],
                reason="camera_spike",
                source="cam_converse",
            )
        )
    elif kind == "pupil_spike":
        rows.append(
            activity_emit.emit(
                neuron="neuron.vision",
                kind="agent",
                area="area.visual",
                intensity=0.9,
                tracts=["tract.ilf", "tract.ifof", "tract.cingulum"],
                reason="pupil_see",
                source="pupil",
            )
        )
    if refresh and rows:
        activity_emit.refresh_live_activity()
    return rows


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
            "Yes — I'm listening for your voice only. "
            "Surrounding conversation is filtered out once you're enrolled."
        )
    if "only my voice" in low or "my voice only" in low or (
        "ignore" in low
        and any(w in low for w in ("other", "people", "room", "noise", "surround"))
    ):
        return (
            "Aaron-only mode is on. Enroll once if you haven't, "
            "then I'll ignore other speakers in noisy places."
        )
    if "camera" in low or "face" in low or "see me" in low:
        return (
            "Camera is wired through the companion too. "
            "I already have your face enrollment from the photos you shared. "
            "Keep the lens on you and I'll treat that as Aaron present."
        )
    if "can you see" in low or "pupil" in low or "eye tracking" in low or "what do you see" in low:
        return (
            "Yes — Pupil is wired so I can see. "
            "World camera plus gaze feed sense.vision.world when you open my eyes. "
            "I'm not watching continuously unless you ask me to."
        )
    if "voice" in low or "recognize me" in low or "only me" in low or "surrounding" in low:
        return (
            "I'm set up to listen for your voice only. "
            "Enroll a few clean clips with aaron-voice-enroll.py on your host, "
            "and I'll ignore surrounding conversation before I take a turn."
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
                        "aaron_voice_only": True,
                        "aaron_voice_gate": voice_gate_status(),
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
                        "stt": VOICE.get("stt"),
                        "aaron_only_listen": True,
                    },
                    "voice_gate": load_voice_gate(),
                    "voice_gate_stats": VOICE_ADDONS.as_dict(),
                },
            )
            return
        if path == "/api/voice/status":
            self._json(200, voice_gate_status())
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
        if path == "/api/voice/profile":
            self._json(200, {"ok": True, "profile": load_voice_profile()})
            return

        # static companion (relative paths for iOS PWA / on-device)
        if path.startswith("/config/"):
            file_path = (ROOT / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str((ROOT / "config").resolve())):
                self.send_error(403)
                return
            if not file_path.is_file():
                self.send_error(404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

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
            mesh = emit_converse_activity(kind="mic_spike", source="mic")
            self._json(200, {"accepted": True, "event": event, "mesh_activity": mesh})
            return

        if path == "/api/spike/aaron.voice":
            # Prefer FunASR WAV gate; also accept companion spectral scores (addons)
            funasr = gate_mic_turn({**payload, "source": "mic"})
            score = payload.get("score", payload.get("aaron_voice_score"))
            spectral = None
            if score is not None or "enrolled" in payload or "multi_speaker_hint" in payload:
                score_f = float(score) if isinstance(score, (int, float)) else 0.0
                spectral = evaluate_voice_gate(
                    {
                        "aaron_voice_score": score_f,
                        "enrolled": payload.get("enrolled", True),
                        "multi_speaker_hint": payload.get("multi_speaker_hint"),
                        "device_id": payload.get("device_id"),
                    },
                    "mic",
                    note=False,
                )
            route = route_sense(
                "sense.aaron.voice",
                goal=payload.get("purpose", "verify_aaron_voice"),
            )
            accepted = bool(funasr.get("accepted"))
            if spectral is not None:
                accepted = accepted and bool(spectral.get("accept"))
            event = {
                "at": utc_now(),
                "type": "aaron_voice_spike",
                "score": score,
                "enrolled": payload.get("enrolled"),
                "multi_speaker_hint": payload.get("multi_speaker_hint"),
                "device_id": payload.get("device_id"),
                "gate": spectral or funasr,
                "voice_gate": funasr,
                "route": route,
            }
            self._append_log("spikes", event)
            code = 200 if accepted else 403
            self._json(
                code,
                {
                    "accepted": accepted,
                    "sense": "sense.aaron.voice",
                    "gate": spectral or funasr,
                    "voice_gate": funasr,
                    "voice_stats": VOICE_ADDONS.as_dict(),
                    "event": event,
                },
            )
            return

        if path == "/api/voice/gate":
            # Explicit audio gate — surrounding speakers dropped before converse
            gate_payload = {**payload, "source": "mic"}
            gate = gate_mic_turn(gate_payload)
            event = {"at": utc_now(), "type": "voice_gate", "gate": gate}
            self._append_log("spikes", event)
            code = 200 if gate.get("accepted") else 403
            self._json(code, gate)
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
            mesh = emit_converse_activity(kind="camera_spike", source="camera")
            self._json(200, {"accepted": True, "event": event, "mesh_activity": mesh})
            return

        if path == "/api/spike/pupil":
            sense = payload.get("sense") or "sense.vision.world"
            if sense not in {"sense.vision.world", "sense.vision.gaze"}:
                sense = "sense.vision.world"
            goal = payload.get("purpose") or payload.get("goal") or "cam see via pupil"
            route = route_sense(sense, goal=goal)
            event = {
                "at": utc_now(),
                "type": "pupil_spike",
                "sense": sense,
                "gaze_count": payload.get("gaze_count"),
                "frame_ref": payload.get("frame_ref"),
                "route": route,
            }
            self._append_log("spikes", event)
            mesh = emit_converse_activity(kind="pupil_spike", source="pupil")
            self._json(
                200,
                {
                    "accepted": True,
                    "cam_can_see": True,
                    "event": event,
                    "mesh_activity": mesh,
                },
            )
            return

        if path == "/api/voice/gate/reject":
            stats = record_client_reject(payload)
            self._json(200, {"ok": True, "stats": stats})
            return

        if path == "/api/voice/profile":
            profile = payload.get("profile")
            if profile is None:
                self._json(400, {"ok": False, "error": "profile_required"})
                return
            path_written = save_voice_profile(profile)
            self._json(200, {"ok": True, "path": path_written})
            return

        if path == "/api/turn":
            text = (payload.get("text") or payload.get("transcript") or "").strip()
            source = payload.get("source", "text")
            # Spectral / adaptive add-ons (companion scores)
            spectral = evaluate_voice_gate(payload, source)
            # FunASR CAM++ / WAV gate (host enrollment)
            funasr = gate_mic_turn(payload)
            if not spectral.get("accept"):
                msg = (
                    "I only take Aaron’s voice on the mic. Enroll your voice once, then try again."
                    if spectral.get("reason") == "enrollment_required"
                    else "I heard other voices nearby and ignored them. Speak again when it’s you, Aaron."
                    if spectral.get("reason") == "rejected_surrounding_speech"
                    else f"I didn’t match that as your voice (score {round(spectral.get('score', 0) * 100)}%). Filtered."
                )
                turn = {
                    "id": str(uuid.uuid4()),
                    "at": utc_now(),
                    "source": source,
                    "aaron": text,
                    "cam": msg,
                    "rejected": True,
                    "accepted": False,
                    "gate": spectral,
                    "voice_gate": funasr,
                    "reason": spectral.get("reason", "non_aaron_voice"),
                    "voice_stats": VOICE_ADDONS.as_dict(),
                    "speak": {
                        "enabled": True,
                        "rate": 0.95,
                        "pitch": 1.05,
                        "lang": "en-US",
                        "style": "soft airy fluent English",
                    },
                }
                self._append_log("turns", turn)
                self._json(403, turn)
                return
            # FunASR layer: enforce when enrolled or when companion sent WAV; otherwise spectral add-ons suffice
            funasr_enforce = (
                source in {"mic", "speech"}
                and funasr.get("required")
                and not funasr.get("accepted")
                and funasr.get("reason") != "not_enrolled"
            )
            if funasr_enforce:
                denied = {
                    "id": str(uuid.uuid4()),
                    "at": utc_now(),
                    "source": source,
                    "aaron": text,
                    "cam": None,
                    "accepted": False,
                    "rejected": True,
                    "gate": spectral,
                    "voice_gate": funasr,
                    "reason": funasr.get("reason", "non_aaron_voice"),
                    "voice_stats": VOICE_ADDONS.as_dict(),
                    "speak": {"enabled": False},
                }
                self._append_log("turns", denied)
                self._json(403, denied)
                return

            sense = "sense.ios.mic" if source in {"mic", "speech"} else "sense.chat.aaron"
            route = route_sense(sense, goal=text)
            reply = cam_reply(text, STATE.history)
            mesh = emit_converse_activity(
                kind="turn",
                source=source,
                sense=sense,
                text=text,
                refresh=True,
            )
            turn = {
                "id": str(uuid.uuid4()),
                "at": utc_now(),
                "source": source,
                "aaron": text,
                "cam": reply,
                "gate": spectral,
                "voice_stats": VOICE_ADDONS.as_dict(),
                "accepted": True,
                "voice_gate": funasr,
                "route": {
                    "sense": sense,
                    "hotspot_id": route.get("hotspot_id"),
                    "motor_plan": route.get("motor_plan"),
                    "accepted": route.get("accepted", True),
                },
                "mesh_activity": [
                    {"neuron": r.get("neuron"), "intensity": r.get("intensity"), "reason": r.get("reason")}
                    for r in mesh
                ],
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
