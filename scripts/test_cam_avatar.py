#!/usr/bin/env python3
"""Unit tests for the Cam avatar engine (AvatarFrame contract, tier 0)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_avatar  # noqa: E402

PLAN = json.loads((ROOT / "config/system/build-plan.json").read_text(encoding="utf-8"))
SPEC = PLAN["avatar"]["muscle_spec"]


class AvatarEngineTests(unittest.TestCase):
    def test_contract_matches_build_plan(self) -> None:
        c = cam_avatar.contract()
        self.assertEqual(c["muscle_spec"], SPEC)
        self.assertEqual(len(c["blendshape_keys"]), 52)
        self.assertGreaterEqual(len(c["visemes"]), SPEC["visemes_min"])
        self.assertEqual(
            c["tiers"], ["hf_realtime", "studio_full_presence", "custom_finetune"]
        )

    def test_timeline_meets_muscle_spec(self) -> None:
        tl = cam_avatar.timeline("Hello Aaron, the home is live.", seed=7)
        self.assertEqual(tl["contract"], "AvatarFrame")
        self.assertGreaterEqual(tl["fps"], SPEC["target_fps_min"])
        self.assertGreater(tl["frame_count"], 10)
        # First lip movement within the latency budget.
        first_lip = next(
            f["t"]
            for f in tl["frames"]
            if any(k.startswith(("jaw", "mouth")) for k in f["blendshapes"])
        )
        self.assertLessEqual(first_lip * 1000, SPEC["first_lip_latency_ms_max"])

    def test_blendshapes_are_valid_arkit_keys(self) -> None:
        tl = cam_avatar.timeline("Testing all the muscles of speech!", seed=3)
        valid = set(cam_avatar.ARKIT_52)
        for f in tl["frames"]:
            for k, v in f["blendshapes"].items():
                self.assertIn(k, valid)
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
            self.assertIn(f["viseme"], cam_avatar.VISEMES)

    def test_blink_cadence_within_spec(self) -> None:
        long_text = "The quick brown fox jumps over the lazy dog. " * 30
        tl = cam_avatar.timeline(long_text, seed=11)
        self.assertGreater(tl["duration_s"], 30)
        lo, hi = SPEC["blink_per_min"]
        self.assertGreaterEqual(tl["blink_per_min"], lo * 0.8)
        self.assertLessEqual(tl["blink_per_min"], hi * 1.2)

    def test_coarticulation_smoothness(self) -> None:
        """jawOpen must never jump by more than 0.5 between adjacent frames."""
        tl = cam_avatar.timeline("Open wide ah ah ah, now purse ooh ooh.", seed=5)
        prev = 0.0
        for f in tl["frames"]:
            cur = f["blendshapes"].get("jawOpen", 0.0)
            self.assertLessEqual(abs(cur - prev), 0.5, f"jaw jump at t={f['t']}")
            prev = cur

    def test_emotion_baseline(self) -> None:
        warm = cam_avatar.timeline("hi", emotion="warm", seed=1)
        smiles = [
            f["blendshapes"].get("mouthSmileLeft", 0.0) for f in warm["frames"]
        ]
        self.assertGreaterEqual(max(smiles), 0.25)

    def test_deterministic_with_seed(self) -> None:
        a = cam_avatar.timeline("repeatable", seed=42)
        b = cam_avatar.timeline("repeatable", seed=42)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
