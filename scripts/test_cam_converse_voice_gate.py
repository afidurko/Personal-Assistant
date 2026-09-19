#!/usr/bin/env python3
"""HTTP-level smoke for Aaron voice gate on cam-converse-server helpers."""

from __future__ import annotations

import base64
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["AARON_VOICE_TEST"] = "1"
os.environ["AARON_VOICE_ALLOW_DEV_BACKEND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import aaron_voice_gate as avg  # noqa: E402


def load_converse():
    path = ROOT / "scripts" / "cam-converse-server.py"
    spec = importlib.util.spec_from_file_location("cam_converse_server", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ccs = load_converse()


class ConverseVoiceGateSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self.tmp.name)
        store = self.tdir / "embeddings.json"
        cfg = avg.load_config()
        cfg = {
            **cfg,
            "backend": "hash_dev",
            "store_path": str(store),
            "converse_require_voice_match_for_mic": True,
            "fail_closed": True,
            "min_segment_ms": 200,
            "min_aaron_speech_ms": 200,
        }
        backend = avg.HashEmbeddingBackend()
        self.gate = avg.AaronVoiceGate(cfg, backend=backend)
        aaron = avg.synthesize_tone(1.5, freq=180, seed=7)
        self.gate.enroll_samples(aaron, 16000, source="aaron.wav", template_id="aaron-voice-01")
        ccs.VOICE_GATE = self.gate
        ccs.VOICE_CFG = cfg
        self.aaron_wav = avg.pcm16_mono_wav_bytes(aaron, 16000)
        other = avg.synthesize_tone(1.5, freq=440, seed=99)
        self.other_wav = avg.pcm16_mono_wav_bytes(other, 16000)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_text_bypasses(self) -> None:
        g = ccs.gate_mic_turn({"source": "text", "text": "hello"})
        self.assertTrue(g["accepted"])
        self.assertEqual(g["reason"], "text_bypass")

    def test_mic_aaron_accepted(self) -> None:
        b64 = base64.b64encode(self.aaron_wav).decode("ascii")
        g = ccs.gate_mic_turn(
            {"source": "mic", "audio_wav_b64": b64, "transcript": "hello cam"}
        )
        self.assertTrue(g["accepted"], g)
        self.assertGreaterEqual(g["aaron_score"], 0.85)

    def test_mic_other_rejected(self) -> None:
        b64 = base64.b64encode(self.other_wav).decode("ascii")
        g = ccs.gate_mic_turn(
            {"source": "mic", "audio_wav_b64": b64, "transcript": "hey there"}
        )
        self.assertFalse(g["accepted"], g)

    def test_mic_missing_audio_rejected(self) -> None:
        g = ccs.gate_mic_turn({"source": "mic", "transcript": "hello"})
        self.assertFalse(g["accepted"])
        self.assertEqual(g["reason"], "mic_turn_missing_audio_or_score")

    def test_status_enrolled(self) -> None:
        st = ccs.voice_gate_status()
        self.assertTrue(st["enrolled"])
        self.assertTrue(st["ready"])


if __name__ == "__main__":
    unittest.main()
