#!/usr/bin/env python3
"""Enroll Aaron voice samples into Cam's local voice gate store.

Examples:
  # Production (FunASR CAM++ required):
  python3 scripts/aaron-voice-enroll.py identity/aaron/local/voice/samples/*.wav

  # Dry-run / tests only:
  AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/aaron-voice-enroll.py --backend hash_dev clip.wav

Embeddings are written under identity/aaron/local/ (gitignored).
Raw samples stay local; enroll-index.json only gets refs (no vectors).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aaron_voice_gate import (  # noqa: E402
    AaronVoiceGate,
    HashEmbeddingBackend,
    load_config,
    pcm16_mono_wav_bytes,
    select_backend,
    synthesize_tone,
    update_enroll_index,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "wavs",
        nargs="*",
        type=Path,
        help="Aaron-only WAV clips (mono preferred; resampled to 16 kHz)",
    )
    p.add_argument("--config", type=Path, default=None)
    p.add_argument(
        "--backend",
        choices=["auto", "funasr", "hash_dev"],
        default=None,
        help="Override config backend",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help="Clear existing templates and enroll only these clips",
    )
    p.add_argument(
        "--synth-demo",
        action="store_true",
        help="Write a synthetic demo clip and enroll it (dev only)",
    )
    p.add_argument("--status", action="store_true", help="Print gate status and exit")
    args = p.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    if args.backend:
        cfg = {**cfg, "backend": args.backend}

    backend = None
    if args.backend == "hash_dev" or args.synth_demo:
        backend = HashEmbeddingBackend()
    elif args.backend:
        backend = select_backend(cfg, force=args.backend)

    gate = AaronVoiceGate(cfg, backend=backend)

    if args.status:
        print(json.dumps(gate.status(), indent=2))
        return 0

    wavs = list(args.wavs)
    if args.synth_demo:
        samples_dir = Path(cfg.get("samples_dir", "identity/aaron/local/voice/samples"))
        if not samples_dir.is_absolute():
            samples_dir = ROOT / samples_dir
        samples_dir.mkdir(parents=True, exist_ok=True)
        demo = samples_dir / "aaron-demo-synth.wav"
        tone = synthesize_tone(2.5, freq=180.0, seed=7)
        demo.write_bytes(pcm16_mono_wav_bytes(tone, 16000))
        wavs.append(demo)
        print(f"wrote demo clip {demo}", flush=True)

    if not wavs:
        p.error("Provide at least one WAV, or use --synth-demo / --status")

    if args.replace:
        gate.store.templates = []
        gate.store.centroid = []

    results = []
    for i, wav in enumerate(wavs, start=1):
        if not wav.exists():
            print(f"missing: {wav}", file=sys.stderr)
            return 1
        tid = f"aaron-voice-{i:02d}" if args.replace else None
        results.append(gate.enroll_file(wav, template_id=tid, replace=False))

    update_enroll_index(gate.store.templates)
    out = {
        "ok": True,
        "enrolled": gate.store.enrolled,
        "templates": len(gate.store.templates),
        "backend": gate.store.backend,
        "store_path": str(gate.store.path),
        "results": results,
        "status": gate.status(),
    }
    print(json.dumps(out, indent=2))
    if gate.store.backend == "hash_dev":
        print(
            "\nWARNING: hash_dev backend enrolled — replace with FunASR CAM++ "
            "enrollments before relying on Aaron-only listen in the wild.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
