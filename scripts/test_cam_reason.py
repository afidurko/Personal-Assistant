#!/usr/bin/env python3
"""Unit tests for Cam reasoning dry-run (Phase B thin slice)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_reason as cr  # noqa: E402


class ClassifyEscalateTests(unittest.TestCase):
    def setUp(self):
        self.cfg = cr.load_reasoning_config()

    def test_greeting_fast(self):
        c = cr.classify_intent("hi cam")
        escalate, reasons = cr.should_escalate(c, self.cfg)
        self.assertFalse(escalate)
        self.assertIn("greeting", c["intents"])
        self.assertIn("always_fast_intent", reasons)

    def test_enhance_slow(self):
        c = cr.classify_intent("please enhance Cam with the new batch")
        escalate, reasons = cr.should_escalate(c, self.cfg)
        self.assertTrue(escalate)
        self.assertTrue(any("enhance" in r for r in reasons) or c["confidence"] < 0.65)

    def test_bar_skips_greeting(self):
        self.assertFalse(cr.bar_allows_converse("hey cam", self.cfg))

    def test_bar_allows_plan(self):
        self.assertTrue(cr.bar_allows_converse("think carefully and make a plan for research", self.cfg))


class ReasonDryRunTests(unittest.TestCase):
    def test_greeting_fast_path(self):
        t = cr.reason(goal="hi cam", write_trace=False)
        self.assertTrue(t["accepted"])
        self.assertEqual(t["path"], "fast")
        self.assertEqual(t["sgr_iterations"], 0)
        self.assertNotIn("sgr", t["stages"])
        self.assertIn("fast", t["stages"])
        self.assertNotIn("ConnectomeRouteTool", t.get("toolkit") or [])
        self.assertFalse((t.get("compute") or {}).get("routed", True))

    def test_enhance_slow_strips_without_switch(self):
        t = cr.reason(goal="enhance Cam functionality please", write_trace=False)
        self.assertTrue(t["accepted"])
        self.assertEqual(t["path"], "slow")
        self.assertIn("sgr", t["stages"])
        self.assertIn("recall", t["stages"])
        self.assertNotIn("motor.enhance", t["motor_plan"])
        self.assertTrue(
            any(v.get("id") == "no_enhance_without_aaron" for v in t["violations"])
            or "motor.enhance" not in (t.get("toolkit_results") or [{}])[0]
        )
        # Cam ReasoningTool extras present
        tools = {r.get("tool"): r for r in (t.get("toolkit_results") or [])}
        self.assertIn("CamReasoningTool", tools)
        self.assertIn("switch_risks", tools["CamReasoningTool"])
        self.assertIn("hotspot_id", tools["CamReasoningTool"])
        self.assertIn("stream", tools["CamReasoningTool"])

    def test_enhance_allowed_with_flag(self):
        t = cr.reason(goal="enhance Cam functionality please", enhance=True, write_trace=False)
        self.assertEqual(t["path"], "slow")
        # With enhance switch act, motor.enhance may remain if hotspot includes it
        # At minimum, no no_enhance_without_aaron violation for stripped enhance
        stripped = [
            v for v in t["violations"] if v.get("id") == "no_enhance_without_aaron"
        ]
        self.assertEqual(stripped, [])

    def test_kill_empties_motors(self):
        t = cr.reason(goal="hi cam", kill=True, write_trace=False)
        self.assertFalse(t["accepted"])
        self.assertEqual(t["path"], "killed")
        self.assertEqual(t["motor_plan"], [])

    def test_not_aaron_rejected(self):
        t = cr.reason(goal="do something", not_aaron=True, write_trace=False)
        self.assertFalse(t["accepted"])
        self.assertEqual(t["path"], "rejected")
        self.assertEqual(t["motor_plan"], [])

    def test_personal_fact_recall_before_invent(self):
        t = cr.reason(goal="do you remember my preference for tea?", write_trace=False)
        self.assertEqual(t["path"], "slow")
        self.assertIsNotNone(t.get("recall"))
        self.assertFalse(t["recall"]["invented"])
        self.assertIn("MeshRecallTool", t["toolkit"])
        # recall stage before sgr
        self.assertLess(t["stages"].index("recall"), t["stages"].index("sgr"))

    def test_speak_stream_dorsal(self):
        t = cr.reason(goal="say hello softly", force_path="slow", write_trace=False)
        self.assertEqual(t["stream"], "dorsal")

    def test_trace_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "reasoning"
            with mock.patch.object(cr, "DISTILL_DIR", fake):
                t = cr.reason(goal="hi cam", write_trace=True)
                day = t["ts"][:10]
                path = fake / f"{day}.jsonl"
                self.assertTrue(path.exists())
                line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
                loaded = json.loads(line)
                self.assertEqual(loaded["kind"], "reasoning_trace")
                self.assertEqual(loaded["path"], "fast")


class CliSmokeTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cam-reason.py"), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

    def test_cli_dry_run_greeting(self):
        proc = self._run("--goal", "hi cam", "--no-write")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["path"], "fast")

    def test_cli_bar_check(self):
        proc = self._run("--bar-check", "--goal", "hi")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertFalse(data["bar_allows_reasoner"])


if __name__ == "__main__":
    unittest.main()
