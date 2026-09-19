#!/usr/bin/env python3
"""Cam → VoiceStudio local speech bridge (REST).

Suggestive motor.voicestudio implementation: generate a short WAV via the
OpenAI-compatible /v1/audio/speech endpoint when the backend is up.

Does not download models. Fails closed if localhost:3900 is down.
Audible playback still requires switch.presence / switch.outbound via Cam.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "integrations" / "voicestudio.json"


def load_cfg() -> dict:
    if not CFG.exists():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True, help="text to synthesize")
    parser.add_argument("--voice", default=None, help="profile id or compatibility alias")
    parser.add_argument("--out", default=None, help="output WAV path")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = load_cfg()
    backend = cfg.get("backend") or {}
    mcp = cfg.get("mcp") or {}
    base = (args.base_url or backend.get("base_url") or "http://localhost:3900").rstrip("/")
    voice = args.voice or (cfg.get("persona_voice_profile_id")) or "alloy"
    client_id = args.client_id or mcp.get("default_client_id") or "cam"
    out_path = Path(
        args.out
        or (
            ROOT
            / "data"
            / "voicestudio"
            / f"cam-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.wav"
        )
    )

    payload = {
        "model": "tts-1",
        "voice": voice,
        "input": args.text,
        "response_format": "wav",
    }
    url = f"{base}{backend.get('speech_path') or '/v1/audio/speech'}"
    report = {
        "ok": False,
        "url": url,
        "voice": voice,
        "client_id": client_id,
        "out": str(out_path),
        "chars": len(args.text),
        "synthetic": True,
        "error": None,
    }

    if args.dry_run:
        report["ok"] = True
        report["dry_run"] = True
        print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: DRY {url} → {out_path}")
        return 0

    # Preflight health
    health_url = f"{base}{backend.get('health_path') or '/health'}"
    try:
        with urllib.request.urlopen(health_url, timeout=min(5.0, args.timeout)) as resp:
            if getattr(resp, "status", 200) >= 300:
                report["error"] = f"health_http_{resp.status}"
                print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: FAIL {report['error']}")
                return 1
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"backend_down:{exc}"
        print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: FAIL {report['error']}")
        print("  hint: start VoiceStudio Electron/backend on this host first", file=sys.stderr)
        return 1

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-VoiceStudio-Client-Id": client_id,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            data = resp.read()
            # Error bodies can be JSON written to --out if we aren't careful
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype.lower() or data[:1] in (b"{", b"["):
                report["error"] = f"non_audio_response:{data[:200]!r}"
                print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: FAIL {report['error']}")
                return 1
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            report["ok"] = True
            report["bytes"] = len(data)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        report["error"] = f"http_{exc.code}:{body}"
        print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: FAIL {report['error']}")
        return 1
    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)
        print(json.dumps(report, indent=2) if args.json else f"voicestudio-speak: FAIL {report['error']}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"voicestudio-speak: OK {out_path} ({report.get('bytes')} bytes) synthetic=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
