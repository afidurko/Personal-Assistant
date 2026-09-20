#!/usr/bin/env python3
"""Push a WAV file to NVIDIA Audio2Face using the LLMAvatarTalk gRPC client."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A2F = ROOT / "integrations" / "llmavatartalk"
sys.path.insert(0, str(A2F))

import numpy as np
from scipy.io.wavfile import read

from modules.audio2face_streaming_utils import push_audio_track


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: a2f-push.py <wav>", file=sys.stderr)
        return 2
    wav_path = Path(sys.argv[1])
    rate, wav = read(str(wav_path))
    audio = wav.astype(np.float32) / 32768.0
    url = os.environ.get("A2F_URL", "127.0.0.1:50051")
    instance = os.environ.get("A2F_INSTANCE", "/World/audio2face/PlayerStreaming")
    push_audio_track(url, audio, int(rate), instance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
