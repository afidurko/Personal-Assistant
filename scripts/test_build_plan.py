#!/usr/bin/env python3
"""Unit tests for the Cam home build plan manifest + checker."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "system" / "build-plan.json"


class BuildPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_priority_ladder_order(self) -> None:
        priorities = self.plan["priorities"]
        self.assertEqual([p["rank"] for p in priorities], [1, 2, 3, 4])
        self.assertEqual(priorities[0]["id"], "real_world_execution")
        self.assertEqual(priorities[2]["id"], "human_ultimate_say")
        self.assertTrue(priorities[2]["hard_rules"])

    def test_avatar_tiers_and_muscle_spec(self) -> None:
        avatar = self.plan["avatar"]
        tier_ids = [t["id"] for t in avatar["tiers"]]
        self.assertEqual(
            tier_ids, ["hf_realtime", "studio_full_presence", "custom_finetune"]
        )
        hf = avatar["tiers"][0]
        self.assertEqual(hf["source"], "huggingface")
        self.assertIn("MuseTalk", hf["models"]["face_lipsync"])
        self.assertIn("LivePortrait", hf["models"]["face_expression"])
        spec = avatar["muscle_spec"]
        self.assertEqual(spec["blendshapes"], "arkit_52")
        self.assertGreaterEqual(spec["target_fps_min"], 25)
        self.assertLessEqual(spec["first_lip_latency_ms_max"], 500)
        self.assertIn("brain_rule", avatar)

    def test_auto_update_channels(self) -> None:
        channels = self.plan["auto_update"]["channels"]
        ids = {c["id"] for c in channels}
        self.assertIn("cloud_environments", ids)
        self.assertIn("workspace_persistence", ids)
        self.assertIn("schedules_loops", ids)

    def test_phases_have_exit_checks(self) -> None:
        phases = self.plan["phases"]
        self.assertGreaterEqual(len(phases), 5)
        for ph in phases:
            self.assertTrue(ph.get("exit_check"), ph.get("id"))

    def test_checker_passes(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-plan-check.py"), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["failures"], [])

    def test_checker_fails_on_bad_priorities(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_plan_check", ROOT / "scripts" / "build-plan-check.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        bad = json.loads(PLAN.read_text(encoding="utf-8"))
        bad["priorities"] = list(reversed(bad["priorities"]))
        report = mod.check(bad)
        self.assertFalse(report["ok"])
        bad2 = json.loads(PLAN.read_text(encoding="utf-8"))
        bad2["avatar"]["muscle_spec"].pop("blendshapes")
        report2 = mod.check(bad2)
        self.assertFalse(report2["ok"])


if __name__ == "__main__":
    unittest.main()
