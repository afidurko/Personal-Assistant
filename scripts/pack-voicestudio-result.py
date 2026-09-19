#!/usr/bin/env python3
"""Pack VoiceStudio TTS/ASR/clone job results into mesh/voice (no raw audio).

Does not call the backend. Takes a small JSON summary from a completed job
and emits a distilled mesh document for nulltickets / vault.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_job(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("job JSON must be an object")
    return data


def distill(job: dict) -> dict:
    return {
        "kind": job.get("kind") or job.get("task") or "speech",
        "engine": job.get("engine") or job.get("model"),
        "profile_id": job.get("profile_id") or job.get("voice"),
        "language": job.get("language") or job.get("locale"),
        "duration_s": job.get("duration_s") or job.get("duration"),
        "output_path": job.get("output_path") or job.get("path"),
        "audio_id": job.get("audio_id"),
        "chars": job.get("chars") or (len(job["text"]) if isinstance(job.get("text"), str) else None),
        "ok": job.get("ok", True),
        "error": job.get("error"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", required=True, help="path to VoiceStudio job/result JSON")
    p.add_argument("--client-id", default="cam", help="X-VoiceStudio-Client-Id / agent id")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    job_path = Path(args.job)
    if not job_path.exists():
        print(f"missing job file: {job_path}", file=__import__("sys").stderr)
        return 1

    distilled = distill(load_job(job_path))
    doc = {
        "namespace": "mesh/voice",
        "source": "integrations/voicestudio",
        "sensitivity": "private",
        "client_id": args.client_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic": True,
        "job": distilled,
        "note": "raw WAV/clones not included; mark_synthetic; Aaron gate for audible play",
    }
    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
