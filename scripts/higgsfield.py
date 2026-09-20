#!/usr/bin/env python3
"""Cam → Higgsfield Speak (lip-sync clips).

Default is status / dry-run. Live jobs require credentials, HIGGSFIELD_LIVE=1,
and --live. Cline must not call --live (cost + Cam's face leaves the box).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "integrations" / "higgsfield.json"
LAST = ROOT / "data" / "higgsfield" / "last.json"


def load_cfg() -> dict:
    if not CFG.exists():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def creds(cfg: dict) -> tuple[str | None, str | None, str, str]:
    prov = cfg.get("provider") or {}
    key_id = os.environ.get(prov.get("key_id_env") or "HIGGSFIELD_API_KEY_ID")
    secret = os.environ.get(prov.get("key_secret_env") or "HIGGSFIELD_API_KEY_SECRET")
    base = (
        os.environ.get(prov.get("api_base_env") or "HIGGSFIELD_API_BASE")
        or prov.get("api_base_default")
        or "https://platform.higgsfield.ai"
    ).rstrip("/")
    speak = prov.get("speak_path") or "/v1/speak/higgsfield"
    return key_id, secret, base, speak


def live_enabled(cfg: dict) -> bool:
    prov = cfg.get("provider") or {}
    flag = os.environ.get(prov.get("live_env") or "HIGGSFIELD_LIVE", "0")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


def status_report() -> dict:
    cfg = load_cfg()
    key_id, secret, base, speak = creds(cfg)
    last = {}
    if LAST.exists():
        try:
            last = json.loads(LAST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            last = {}
    return {
        "ok": True,
        "engine": "higgsfield_speak",
        "configured": CFG.exists(),
        "credentials_present": bool(key_id and secret),
        "live_enabled": live_enabled(cfg),
        "auto_on_turn": False,
        "api_base": base,
        "speak_path": speak,
        "portrait": cfg.get("portrait") or "identity/persona/cam-face.jpg",
        "quality": (cfg.get("defaults") or {}).get("quality") or "mid",
        "duration": (cfg.get("defaults") or {}).get("duration") or 10,
        "last_clip": last.get("clip_url") or last.get("local_path"),
        "last": last or None,
        "notes": "Live Speak is Aaron-gated. /api/turn never uploads Cam's face.",
    }


def pick_duration(text: str, requested: int | None) -> int:
    if requested in {5, 10, 15}:
        return requested
    words = len((text or "").split())
    if words <= 8:
        return 5
    if words <= 24:
        return 10
    return 15


def auth_header(key_id: str, secret: str) -> str:
    return f"Key {key_id}:{secret}"


def http_json(
    method: str,
    url: str,
    key_id: str,
    secret: str,
    body: dict | None = None,
    timeout: float = 60.0,
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": auth_header(key_id, secret),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}: {detail[:400]}") from e


def save_last(payload: dict) -> None:
    LAST.parent.mkdir(parents=True, exist_ok=True)
    LAST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def speak(args: argparse.Namespace) -> dict:
    cfg = load_cfg()
    defaults = cfg.get("defaults") or {}
    key_id, secret, base, speak_path = creds(cfg)
    duration = pick_duration(args.text or "", args.duration)
    body = {
        "input_image": {"type": "image_url", "image_url": args.image_url},
        "input_audio": {"type": "audio_url", "audio_url": args.audio_url},
        "prompt": args.prompt or defaults.get("prompt"),
        "quality": args.quality or defaults.get("quality") or "mid",
        "duration": duration,
    }
    report = {
        "ok": False,
        "dry_run": bool(args.dry_run),
        "live": bool(args.live),
        "url": f"{base}{speak_path}",
        "body": {
            **body,
            "input_image": {"type": "image_url", "image_url": "(set)" if args.image_url else None},
            "input_audio": {"type": "audio_url", "audio_url": "(set)" if args.audio_url else None},
        },
        "text": args.text,
        "error": None,
    }

    if args.dry_run or not args.live:
        report["ok"] = True
        report["dry_run"] = True
        report["notes"] = "No upload. Pass --live and HIGGSFIELD_LIVE=1 to spend."
        return report

    if not live_enabled(cfg):
        report["error"] = "HIGGSFIELD_LIVE is not enabled"
        return report
    if not key_id or not secret:
        report["error"] = "missing HIGGSFIELD_API_KEY_ID / HIGGSFIELD_API_KEY_SECRET"
        return report
    if not args.image_url or not args.audio_url:
        report["error"] = "live Speak needs --image-url and --audio-url (public URLs)"
        return report

    submitted = http_json("POST", f"{base}{speak_path}", key_id, secret, body)
    request_id = submitted.get("request_id") or submitted.get("id")
    status_url = submitted.get("status_url") or (
        f"{base}/requests/{request_id}/status" if request_id else None
    )
    if not status_url:
        report["error"] = f"no status_url in submit response: {submitted}"
        return report

    deadline = time.time() + max(30.0, args.timeout)
    result = submitted
    while time.time() < deadline:
        result = http_json("GET", status_url, key_id, secret, None, timeout=30.0)
        state = str(result.get("status") or "")
        if state in {"completed", "failed", "nsfw"}:
            break
        time.sleep(2.0)

    clip = None
    video = result.get("video") or {}
    if isinstance(video, dict):
        clip = video.get("url")
    elif isinstance(result.get("videos"), list) and result["videos"]:
        first = result["videos"][0]
        clip = first.get("url") if isinstance(first, dict) else first

    local_path = None
    if clip:
        out_dir = ROOT / "data" / "higgsfield"
        out_dir.mkdir(parents=True, exist_ok=True)
        local_path = out_dir / f"cam-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.mp4"
        with urllib.request.urlopen(clip, timeout=120) as resp, local_path.open("wb") as fh:
            fh.write(resp.read())

    last = {
        "at": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "status": result.get("status"),
        "clip_url": clip,
        "local_path": str(local_path) if local_path else None,
        "public_path": f"/higgsfield-clips/{local_path.name}" if local_path else None,
        "text": args.text,
    }
    save_last(last)
    report.update({"ok": result.get("status") == "completed", "submit": submitted, "result": result, "last": last})
    if result.get("status") != "completed":
        report["error"] = f"job {result.get('status')}"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sp = sub.add_parser("speak")
    sp.add_argument("--text", default="")
    sp.add_argument("--image-url", default=os.environ.get("HIGGSFIELD_IMAGE_URL"))
    sp.add_argument("--audio-url", default=os.environ.get("HIGGSFIELD_AUDIO_URL"))
    sp.add_argument("--prompt", default=None)
    sp.add_argument("--quality", choices=["mid", "high"], default=None)
    sp.add_argument("--duration", type=int, choices=[5, 10, 15], default=None)
    sp.add_argument("--timeout", type=float, default=180.0)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--live", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.cmd == "status":
        report = status_report()
    else:
        report = speak(args)

    print(json.dumps(report, indent=2) if args.json or True else report)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
