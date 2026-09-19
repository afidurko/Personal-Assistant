#!/usr/bin/env python3
"""Verify / gate a WAV against Aaron's enrolled voice templates.

Exit 0 if accepted as Aaron, 1 otherwise.

  python3 scripts/aaron-voice-verify.py path/to/clip.wav
  AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/aaron-voice-verify.py --backend hash_dev clip.wav
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aaron_voice_gate import AaronVoiceGate, HashEmbeddingBackend, load_config, select_backend  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("wav", type=Path)
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--backend", choices=["auto", "funasr", "hash_dev"], default=None)
    p.add_argument("--device-id", default="")
    p.add_argument("--json", action="store_true", help="Print full GateResult JSON")
    args = p.parse_args()

    if not args.wav.exists():
        print(f"missing: {args.wav}", file=sys.stderr)
        return 1

    cfg = load_config(args.config) if args.config else load_config()
    if args.backend:
        cfg = {**cfg, "backend": args.backend}

    backend = None
    if args.backend == "hash_dev":
        backend = HashEmbeddingBackend()
    elif args.backend:
        backend = select_backend(cfg, force=args.backend)

    gate = AaronVoiceGate(cfg, backend=backend)
    result = gate.gate_wav_file(args.wav, device_id=args.device_id)
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            json.dumps(
                {
                    "accepted": result.accepted,
                    "aaron_score": result.aaron_score,
                    "reason": result.reason,
                    "segments": len(result.segments),
                    "aaron_speech_ms": result.aaron_speech_ms,
                    "backend": result.backend,
                },
                indent=2,
            )
        )
    return 0 if result.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
