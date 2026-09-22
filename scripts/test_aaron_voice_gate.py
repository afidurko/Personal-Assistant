#!/usr/bin/env python3
"""Unit tests for Aaron-only voice gate (no FunASR required)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["AARON_VOICE_TEST"] = "1"
os.environ["AARON_VOICE_ALLOW_DEV_BACKEND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from aaron_voice_gate import (  # noqa: E402
    AaronVoiceGate,
    HashEmbeddingBackend,
    energy_vad_segments,
    load_config,
    pcm16_mono_wav_bytes,
    synthesize_tone,
)


class AaronVoiceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self.tmp.name)
        self.store = self.tdir / "embeddings.json"
        self.cfg = load_config()
        self.cfg = {
            **self.cfg,
            "backend": "hash_dev",
            "threshold": 0.85,
            "fail_closed": True,
            "min_segment_ms": 200,
            "min_aaron_speech_ms": 200,
            "store_path": str(self.store),
        }
        self.backend = HashEmbeddingBackend()
        self.gate = AaronVoiceGate(self.cfg, backend=self.backend)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_not_enrolled_fail_closed(self) -> None:
        audio = synthesize_tone(1.0, freq=200, seed=1)
        result = self.gate.gate_samples(audio, 16000)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "not_enrolled")

    def test_aaron_match_accepts(self) -> None:
        aaron = synthesize_tone(2.0, freq=180, seed=7)
        self.gate.enroll_samples(aaron, 16000, source="aaron-a.wav", template_id="aaron-voice-01")
        # Same seed family → high score under hash backend
        probe = synthesize_tone(2.0, freq=180, seed=7)
        result = self.gate.gate_samples(probe, 16000)
        self.assertTrue(result.accepted, result)
        self.assertGreaterEqual(result.aaron_score, self.cfg["threshold"])
        self.assertEqual(result.reason, "aaron_match")

    def test_other_speaker_rejected(self) -> None:
        aaron = synthesize_tone(2.0, freq=180, seed=7)
        self.gate.enroll_samples(aaron, 16000, source="aaron-a.wav")
        other = synthesize_tone(2.0, freq=440, seed=99)
        result = self.gate.gate_samples(other, 16000)
        self.assertFalse(result.accepted, result)
        self.assertLess(result.aaron_score, self.cfg["threshold"])

    def test_surrounding_voices_only_aaron_segments_count(self) -> None:
        aaron = synthesize_tone(1.2, freq=180, seed=7)
        other = synthesize_tone(1.2, freq=440, seed=99)
        silence = synthesize_tone(0.35, freq=1, seed=0) * 0.0
        # Surrounding talker, pause, then Aaron
        mixed = np_concat([other, silence, aaron])
        self.gate.enroll_samples(aaron, 16000, source="aaron-a.wav")
        result = self.gate.gate_samples(mixed, 16000)
        self.assertTrue(result.accepted, result.to_dict())
        self.assertTrue(any(s.is_aaron for s in result.segments))
        self.assertTrue(any(not s.is_aaron for s in result.segments))
        self.assertEqual(result.reason, "aaron_match_with_surrounding_dropped")
        extracted = self.gate.extract_aaron_audio(mixed, 16000, result)
        self.assertIsNotNone(extracted)
        assert extracted is not None
        # Extracted should be shorter than full mix
        self.assertLess(len(extracted), len(mixed))

    def test_energy_vad_finds_speech(self) -> None:
        silence = synthesize_tone(0.5, freq=1, seed=0) * 0.0
        speech = synthesize_tone(0.8, freq=220, seed=3)
        clip = np_concat([silence, speech, silence])
        segs = energy_vad_segments(clip, 16000, min_segment_ms=200)
        self.assertGreaterEqual(len(segs), 1)

    def test_wav_roundtrip_gate(self) -> None:
        aaron = synthesize_tone(1.5, freq=180, seed=7)
        wav = self.tdir / "a.wav"
        wav.write_bytes(pcm16_mono_wav_bytes(aaron, 16000))
        self.gate.enroll_file(wav, template_id="aaron-voice-01")
        result = self.gate.gate_wav_file(wav)
        self.assertTrue(result.accepted)
        status = self.gate.status()
        self.assertTrue(status["enrolled"])
        self.assertEqual(status["templates"], 1)
        # Store must not be world-readable ideally; at least exists locally
        self.assertTrue(self.store.exists())
        stored = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertIn("centroid", stored)
        self.assertTrue(stored["templates"])
        self.assertTrue(self.gate.store.verify_enroll_checksum())
        self.assertEqual(len(stored.get("enroll_checksum") or ""), 32)
        self.assertTrue(status.get("enroll_checksum_ok"))


def np_concat(parts):
    import numpy as np

    return np.concatenate(parts)


if __name__ == "__main__":
    unittest.main()
