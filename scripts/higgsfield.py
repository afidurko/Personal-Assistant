#!/usr/bin/env python3
"""Cam → Higgsfield Speak (lip-sync clips).

Default is status / dry-run. Live jobs require credentials, HIGGSFIELD_LIVE=1,
and --live. Cline must not call --live (cost + Cam's face leaves the box).

Real Speak path (what the first wiring missed):
  1. Resolve Cam's local portrait + a local WAV (file or TTS from --text)
  2. Upload both via POST /files/generate-upload-url + PUT (not public URLs)
  3. POST /v1/speak/higgsfield and poll status_url
  4. Download the MP4 into data/higgsfield/
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "integrations" / "higgsfield.json"
LAST = ROOT / "data" / "higgsfield" / "last.json"
PORTRAIT = ROOT / "identity" / "persona" / "cam-face.jpg"
UA = "higgsfield-server-python/2.0"

COMBINED_CRED_ENVS = (
    "HIGGSFIELD_CREDENTIALS",
    "HF_CREDENTIALS",
    "HF_KEY",
)
SPLIT_CRED_ENVS = (
    ("HIGGSFIELD_API_KEY_ID", "HIGGSFIELD_API_KEY_SECRET"),
    ("HF_API_KEY_ID", "HF_API_KEY_SECRET"),
    ("HF_API_KEY", "HF_SECRET"),
    ("HF_KEY_ID", "HF_KEY_SECRET"),
)


def load_cfg() -> dict:
    if not CFG.exists():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def live_enabled(cfg: dict) -> bool:
    prov = cfg.get("provider") or {}
    flag = os.environ.get(prov.get("live_env") or "HIGGSFIELD_LIVE", "0")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


def resolve_credentials(cfg: dict | None = None) -> dict[str, Any]:
    """Accept official Higgsfield names and Cam's HIGGSFIELD_* aliases."""
    cfg = cfg if cfg is not None else load_cfg()
    prov = cfg.get("provider") or {}
    for name in COMBINED_CRED_ENVS:
        raw = (os.environ.get(name) or "").strip()
        if ":" in raw:
            key_id, secret = raw.split(":", 1)
            if key_id and secret:
                return {
                    "key_id": key_id,
                    "secret": secret,
                    "source": name,
                    "present": True,
                }
    pairs = list(SPLIT_CRED_ENVS)
    configured = (
        prov.get("key_id_env") or "HIGGSFIELD_API_KEY_ID",
        prov.get("key_secret_env") or "HIGGSFIELD_API_KEY_SECRET",
    )
    if configured not in pairs:
        pairs = [configured, *pairs]
    for id_env, secret_env in pairs:
        key_id = (os.environ.get(id_env) or "").strip()
        secret = (os.environ.get(secret_env) or "").strip()
        if key_id and secret:
            return {
                "key_id": key_id,
                "secret": secret,
                "source": f"{id_env}+{secret_env}",
                "present": True,
            }
    return {"key_id": None, "secret": None, "source": None, "present": False}


def api_bases(cfg: dict) -> tuple[str, str]:
    prov = cfg.get("provider") or {}
    speak = (
        os.environ.get(prov.get("api_base_env") or "HIGGSFIELD_API_BASE")
        or prov.get("api_base_default")
        or "https://platform.higgsfield.ai"
    ).rstrip("/")
    files = (
        os.environ.get(prov.get("files_base_env") or "HIGGSFIELD_FILES_BASE")
        or prov.get("files_base_default")
        or "https://api.higgsfield.ai"
    ).rstrip("/")
    return speak, files


def auth_header(key_id: str, secret: str) -> str:
    return f"Key {key_id}:{secret}"


def http_json(
    method: str,
    url: str,
    key_id: str | None = None,
    secret: str | None = None,
    body: dict | None = None,
    timeout: float = 60.0,
    extra_headers: dict[str, str] | None = None,
    raw: bytes | None = None,
) -> dict:
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {
        "Accept": "application/json",
        "User-Agent": UA,
    }
    if raw is None:
        headers["Content-Type"] = "application/json"
    if key_id and secret:
        headers["Authorization"] = auth_header(key_id, secret)
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {detail[:800]}") from e
    except URLError as e:
        raise RuntimeError(f"network {url}: {e.reason}") from e


def http_put_file(url: str, path: Path, headers: dict[str, str], timeout: float = 120.0) -> None:
    # Presigned storage must not receive Higgsfield API credentials.
    put_headers = {"User-Agent": UA, **headers}
    req = Request(url, data=path.read_bytes(), method="PUT", headers=put_headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read()
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} upload {path.name}: {detail[:400]}") from e


def content_type_for(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".wav": "audio/wav",
        ".mp4": "video/mp4",
    }.get(path.suffix.lower(), "application/octet-stream")


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate() or 1
        return wf.getnframes() / float(rate)


def pick_duration(text: str, requested: int | None, audio_sec: float | None = None) -> int:
    if requested in {5, 10, 15}:
        return requested
    if audio_sec is not None:
        if audio_sec <= 5.5:
            return 5
        if audio_sec <= 10.5:
            return 10
        return 15
    words = len((text or "").split())
    if words <= 8:
        return 5
    if words <= 24:
        return 10
    return 15


def detect_tts_engine() -> dict[str, Any]:
    """Prefer VoiceStudio, then local TTS binaries. Never calls a paid API."""
    vs_health = "http://127.0.0.1:3900/health"
    try:
        with urlopen(vs_health, timeout=0.6) as resp:
            if getattr(resp, "status", 200) < 300:
                return {"id": "voicestudio", "cmd": "scripts/voicestudio-speak.py", "ready": True}
    except Exception:
        pass
    for binary, args in (
        ("espeak-ng", ["-v", "en-us", "-s", "145", "-w"]),
        ("espeak", ["-v", "en-us", "-s", "145", "-w"]),
        ("pico2wave", ["-l", "en-US", "-w"]),
    ):
        path = shutil.which(binary)
        if path:
            return {"id": binary, "cmd": path, "ready": True}
    if shutil.which("say"):
        return {"id": "say", "cmd": "say", "ready": True}
    return {"id": None, "cmd": None, "ready": False}


def synthesize_wav(text: str, out_path: Path, engine: dict[str, Any] | None = None) -> dict[str, Any]:
    engine = engine or detect_tts_engine()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    spoken = (text or "").strip() or "Hello Aaron."
    if not engine.get("ready"):
        raise RuntimeError(
            "no local WAV: pass --audio path.wav, start VoiceStudio on :3900, or install espeak-ng"
        )
    ident = engine["id"]
    if ident == "voicestudio":
        script = ROOT / "scripts" / "voicestudio-speak.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--text", spoken, "--out", str(out_path), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"voicestudio TTS failed: {(proc.stderr or proc.stdout)[:400]}")
    elif ident in {"espeak-ng", "espeak"}:
        proc = subprocess.run(
            [engine["cmd"], "-v", "en-us", "-s", "145", "-w", str(out_path), spoken],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"{ident} failed: {(proc.stderr or proc.stdout)[:400]}")
    elif ident == "pico2wave":
        proc = subprocess.run(
            [engine["cmd"], "-l", "en-US", "-w", str(out_path), spoken],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"pico2wave failed: {(proc.stderr or proc.stdout)[:400]}")
    elif ident == "say":
        aiff = out_path.with_suffix(".aiff")
        proc = subprocess.run(
            ["say", "-v", "Samantha", "-o", str(aiff), spoken],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not aiff.exists():
            raise RuntimeError(f"say failed: {(proc.stderr or proc.stdout)[:400]}")
        if shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(aiff), "-acodec", "pcm_s16le", "-ac", "1", str(out_path)],
                capture_output=True,
                check=True,
            )
            aiff.unlink(missing_ok=True)
        else:
            raise RuntimeError("mac say produced AIFF; install ffmpeg to convert to WAV")
    else:
        raise RuntimeError(f"unknown TTS engine {ident}")
    return {"engine": ident, "path": str(out_path), "seconds": round(wav_seconds(out_path), 3)}


def resolve_image(path_or_none: str | None, cfg: dict) -> Path:
    rel = path_or_none or cfg.get("portrait") or "identity/persona/cam-face.jpg"
    image = Path(rel)
    if not image.is_absolute():
        image = ROOT / image
    image = image.resolve()
    if ROOT not in image.parents and image != ROOT:
        raise RuntimeError(f"image path escapes workspace: {image}")
    if not image.exists():
        raise RuntimeError(f"missing portrait: {image}")
    return image


def resolve_audio(
    audio_path: str | None,
    text: str,
    *,
    synthesize: bool,
) -> tuple[Path | None, dict[str, Any]]:
    if audio_path:
        audio = Path(audio_path)
        if not audio.is_absolute():
            audio = ROOT / audio
        audio = audio.resolve()
        if not audio.exists():
            raise RuntimeError(f"missing audio: {audio}")
        if audio.suffix.lower() != ".wav":
            raise RuntimeError("Speak v2 accepts WAV only; pass a .wav file")
        return audio, {"source": "file", "seconds": round(wav_seconds(audio), 3)}
    engine = detect_tts_engine()
    planned = ROOT / "data" / "higgsfield" / "line.wav"
    meta = {"source": "tts", "engine": engine, "text": text, "planned": str(planned)}
    if not synthesize:
        return None, meta
    if not (text or "").strip():
        raise RuntimeError("live Speak needs --audio or --text to synthesize a WAV")
    return Path(synthesize_wav(text, planned, engine)["path"]), meta


def upload_local(path: Path, key_id: str, secret: str, files_base: str, speak_base: str) -> str:
    ctype = content_type_for(path)
    body = {"content_type": ctype, "filename": path.name}
    last_error = None
    ticket = None
    for base in (files_base, speak_base):
        for suffix in ("/files/generate-upload-url", "/v1/files/generate-upload-url"):
            try:
                ticket = http_json("POST", f"{base}{suffix}", key_id, secret, body)
                break
            except RuntimeError as exc:
                last_error = exc
                continue
        if ticket:
            break
    if not ticket:
        raise RuntimeError(f"upload ticket failed: {last_error}")
    public_url = ticket.get("public_url") or ticket.get("url")
    upload_url = ticket.get("upload_url") or ticket.get("put_url")
    if not public_url or not upload_url:
        raise RuntimeError(f"upload ticket missing urls: {ticket}")
    headers = dict(ticket.get("upload_headers") or {})
    headers.setdefault("Content-Type", ticket.get("content_type") or ctype)
    http_put_file(upload_url, path, headers)
    return str(public_url)


def extract_clip_url(result: dict) -> str | None:
    video = result.get("video")
    if isinstance(video, dict) and video.get("url"):
        return str(video["url"])
    if isinstance(video, str) and video.startswith("http"):
        return video
    videos = result.get("videos")
    if isinstance(videos, list) and videos:
        first = videos[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])
        if isinstance(first, str):
            return first
    jobs = result.get("jobs")
    if isinstance(jobs, list) and jobs:
        raw = ((jobs[0] or {}).get("results") or {}).get("raw") or {}
        if isinstance(raw, dict) and raw.get("url"):
            return str(raw["url"])
    for key in ("video_url", "output_url", "url"):
        val = result.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    return None


def save_last(payload: dict) -> None:
    LAST.parent.mkdir(parents=True, exist_ok=True)
    LAST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_last() -> dict:
    if not LAST.exists():
        return {}
    try:
        return json.loads(LAST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def status_report() -> dict:
    cfg = load_cfg()
    creds = resolve_credentials(cfg)
    speak_base, files_base = api_bases(cfg)
    last = load_last()
    tts = detect_tts_engine()
    portrait = cfg.get("portrait") or "identity/persona/cam-face.jpg"
    return {
        "ok": True,
        "engine": "higgsfield_speak",
        "configured": CFG.exists(),
        "credentials_present": bool(creds["present"]),
        "credential_source": creds["source"],
        "live_enabled": live_enabled(cfg),
        "auto_on_turn": False,
        "api_base": speak_base,
        "files_base": files_base,
        "speak_path": (cfg.get("provider") or {}).get("speak_path") or "/v1/speak/higgsfield",
        "upload_path": "/files/generate-upload-url",
        "portrait": portrait,
        "portrait_exists": (ROOT / portrait).exists() if not Path(portrait).is_absolute() else Path(portrait).exists(),
        "tts": tts,
        "quality": (cfg.get("defaults") or {}).get("quality") or "mid",
        "duration": (cfg.get("defaults") or {}).get("duration") or 10,
        "last_clip": last.get("public_path") or last.get("clip_url") or last.get("local_path"),
        "public_path": last.get("public_path"),
        "last_error": last.get("error"),
        "last": last or None,
        "real_life_failure": (
            "First wiring required public --image-url/--audio-url, ignored official HF_* keys, "
            "never synthesized WAV, and never uploaded via /files/generate-upload-url."
        ),
        "notes": "Live Speak is Aaron-gated. /api/turn never uploads Cam's face.",
    }


def speak(args: argparse.Namespace) -> dict:
    cfg = load_cfg()
    defaults = cfg.get("defaults") or {}
    creds = resolve_credentials(cfg)
    speak_base, files_base = api_bases(cfg)
    speak_path = (cfg.get("provider") or {}).get("speak_path") or "/v1/speak/higgsfield"

    image_path = None
    audio_path = None
    audio_meta: dict[str, Any] = {}
    image_error = None
    audio_error = None
    try:
        image_path = resolve_image(getattr(args, "image", None), cfg)
    except RuntimeError as exc:
        image_error = str(exc)
    try:
        audio_path, audio_meta = resolve_audio(
            getattr(args, "audio", None),
            args.text or "",
            synthesize=False,
        )
    except RuntimeError as exc:
        audio_error = str(exc)

    audio_sec = None
    if audio_path:
        audio_sec = wav_seconds(audio_path)
    elif audio_meta.get("seconds"):
        audio_sec = float(audio_meta["seconds"])
    duration = pick_duration(args.text or "", args.duration, audio_sec)

    image_url = args.image_url
    audio_url = args.audio_url
    body = {
        "input_image": {"type": "image_url", "image_url": image_url},
        "input_audio": {"type": "audio_url", "audio_url": audio_url},
        "prompt": args.prompt or defaults.get("prompt"),
        "quality": args.quality or defaults.get("quality") or "mid",
        "duration": duration,
    }
    report: dict[str, Any] = {
        "ok": False,
        "dry_run": bool(args.dry_run) or not args.live,
        "live": bool(args.live),
        "url": f"{speak_base}{speak_path}",
        "files_base": files_base,
        "upload_path": "/files/generate-upload-url",
        "local_image": str(image_path) if image_path else None,
        "local_audio": str(audio_path) if audio_path else None,
        "audio_plan": audio_meta,
        "tts": detect_tts_engine(),
        "credential_source": creds["source"],
        "credentials_present": creds["present"],
        "live_enabled": live_enabled(cfg),
        "body": {
            **body,
            "input_image": {"type": "image_url", "image_url": "(set)" if image_url else "(upload local portrait)"},
            "input_audio": {"type": "audio_url", "audio_url": "(set)" if audio_url else "(upload local WAV)"},
        },
        "text": args.text,
        "planned_steps": [
            "resolve identity/persona/cam-face.jpg",
            "resolve WAV (--audio or local TTS from --text)",
            "POST /files/generate-upload-url for image + audio",
            "PUT bytes to the presigned upload_url (no API key on storage)",
            f"POST {speak_path} with the returned public_url values",
            "poll status_url until completed / failed / nsfw",
            "download MP4 to data/higgsfield/",
        ],
        "error": None,
    }
    if image_error:
        report["error"] = image_error
    if audio_error and not report["error"]:
        report["error"] = audio_error

    if args.dry_run or not args.live:
        report["ok"] = report["error"] is None and image_path is not None
        report["dry_run"] = True
        report["notes"] = (
            "No upload. Live Speak now uses the local portrait + a local WAV "
            "(no public --image-url/--audio-url required). "
            "Pass --live and HIGGSFIELD_LIVE=1 to spend."
        )
        return report

    if not live_enabled(cfg):
        report["error"] = "HIGGSFIELD_LIVE is not enabled"
        return report
    if not creds["present"]:
        report["error"] = (
            "missing credentials — set HF_API_KEY_ID + HF_API_KEY_SECRET "
            "(or HF_CREDENTIALS / HIGGSFIELD_API_KEY_ID + HIGGSFIELD_API_KEY_SECRET)"
        )
        return report
    if report["error"]:
        return report
    if image_path is None:
        report["error"] = "missing local portrait"
        return report

    key_id, secret = creds["key_id"], creds["secret"]
    try:
        if not audio_url and audio_path is None:
            audio_path, audio_meta = resolve_audio(None, args.text or "", synthesize=True)
            report["local_audio"] = str(audio_path) if audio_path else None
            report["audio_plan"] = audio_meta
        if not image_url:
            image_url = upload_local(image_path, key_id, secret, files_base, speak_base)
        if not audio_url:
            if audio_path is None:
                raise RuntimeError("WAV synthesis produced no file")
            audio_url = upload_local(audio_path, key_id, secret, files_base, speak_base)
        body["input_image"] = {"type": "image_url", "image_url": image_url}
        body["input_audio"] = {"type": "audio_url", "audio_url": audio_url}
        submitted = http_json("POST", f"{speak_base}{speak_path}", key_id, secret, body)
        request_id = submitted.get("request_id") or submitted.get("id")
        status_url = submitted.get("status_url") or (
            f"{speak_base}/requests/{request_id}/status" if request_id else None
        )
        if not status_url:
            raise RuntimeError(f"no status_url in submit response: {submitted}")

        deadline = time.time() + max(30.0, args.timeout)
        result = submitted
        delay = 2.0
        while time.time() < deadline:
            result = http_json("GET", status_url, key_id, secret, None, timeout=30.0)
            state = str(result.get("status") or "")
            if state in {"completed", "failed", "nsfw"}:
                break
            time.sleep(delay)
            delay = min(8.0, delay * 1.4)

        clip = extract_clip_url(result)
        local_path = None
        if clip:
            out_dir = ROOT / "data" / "higgsfield"
            out_dir.mkdir(parents=True, exist_ok=True)
            local_path = out_dir / f"cam-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.mp4"
            with urlopen(clip, timeout=120) as resp, local_path.open("wb") as fh:
                fh.write(resp.read())

        last = {
            "at": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "status": result.get("status"),
            "clip_url": clip,
            "local_path": str(local_path) if local_path else None,
            "public_path": f"/higgsfield-clips/{local_path.name}" if local_path else None,
            "text": args.text,
            "error": None if result.get("status") == "completed" else f"job {result.get('status')}",
        }
        save_last(last)
        report.update(
            {
                "ok": result.get("status") == "completed" and bool(clip),
                "submit": {k: submitted.get(k) for k in ("request_id", "status", "status_url") if k in submitted},
                "result_status": result.get("status"),
                "last": last,
            }
        )
        if not report["ok"]:
            report["error"] = last["error"] or "speak did not return a video url"
        return report
    except Exception as exc:  # noqa: BLE001
        last = {
            "at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "text": args.text,
            "error": str(exc),
        }
        save_last(last)
        report["error"] = str(exc)
        report["last"] = last
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sp = sub.add_parser("speak")
    sp.add_argument("--text", default="")
    sp.add_argument("--image", default=None, help="local portrait (default identity/persona/cam-face.jpg)")
    sp.add_argument("--audio", default=None, help="local WAV (synthesized from --text if omitted)")
    sp.add_argument("--image-url", default=os.environ.get("HIGGSFIELD_IMAGE_URL"), help="optional public override")
    sp.add_argument("--audio-url", default=os.environ.get("HIGGSFIELD_AUDIO_URL"), help="optional public override")
    sp.add_argument("--prompt", default=None)
    sp.add_argument("--quality", choices=["mid", "high"], default=None)
    sp.add_argument("--duration", type=int, choices=[5, 10, 15], default=None)
    sp.add_argument("--timeout", type=float, default=240.0)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--live", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.cmd == "status":
        report = status_report()
    else:
        report = speak(args)

    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
