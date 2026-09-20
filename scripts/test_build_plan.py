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

    def test_auto_sync_is_a_must_and_safe(self) -> None:
        auto_sync = self.plan["auto_sync"]
        self.assertEqual(auto_sync["requirement"], "must")
        self.assertTrue(auto_sync["policy"]["never_auto_merge"])
        self.assertTrue(auto_sync["policy"]["report_first"])
        self.assertEqual(auto_sync["motor"], "scripts/auto-sync.py")
        self.assertGreaterEqual(len(auto_sync["sources"]), 4)
        ids = {c["id"] for c in auto_sync["channels"]}
        self.assertIn("repo_drift_sync", ids)
        self.assertIn("workspace_connectivity", ids)
        self.assertIn("session_distillates", ids)

    def test_auto_sync_motor_reports_offline(self) -> None:
        p = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/auto-sync.py"),
                "--json",
                "--fetch-timeout",
                "8",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mode"], "report")
        self.assertTrue(report["policy"]["never_auto_merge"])
        self.assertGreaterEqual(report["registry"]["integrations_registered"], 20)
        self.assertGreaterEqual(len(report["submodules"]), 10)
        self.assertEqual(report["registry"]["missing_paths"], [])

    def test_avatar_scripts_run_offline(self) -> None:
        for script, expect_key in (
            ("scripts/avatar-check.py", "tier_ids"),
            ("scripts/avatar-fetch-models.py", "models"),
        ):
            p = subprocess.run(
                [sys.executable, str(ROOT / script), "--json"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(p.returncode, 0, f"{script}: {p.stdout + p.stderr}")
            report = json.loads(p.stdout)
            self.assertTrue(report["ok"], report)
            self.assertIn(expect_key, report)

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
