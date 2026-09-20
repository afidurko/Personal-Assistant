#!/usr/bin/env python3
"""Unit tests for Cam ↔ InfiniteMind adapter (Phase C thin slice)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_infinitemind as ci  # noqa: E402
import cam_reason as cr  # noqa: E402


class InfiniteMindAdapterTests(unittest.TestCase):
    def test_submodule_present(self):
        self.assertTrue(ci.available(), "integrations/infinitemind missing")

    def test_enrich_plan_slow(self):
        r = ci.enrich(
            goal="think carefully and make a plan for research",
            intents=["explicit_plan", "research_cite"],
            confidence=0.5,
            escalate=True,
            escalate_reasons=["always_slow_intent"],
            recall={
                "hits": {"primary": [{"ns": "mesh/persona", "note": "Aaron sole operator"}]},
                "invented": False,
            },
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["tool"], "InfiniteMindEnrich")
        self.assertEqual(r["strategy"], "systematic")
        self.assertIn("tasking_ok", r["logic"]["derived"])
        self.assertIn("no_invent_aaron_facts", r["logic"]["derived"])
        self.assertEqual(r["recommendation"]["path_hint"], "slow")
        self.assertTrue(r["epistemic"]["accepted"])

    def test_kill_silences(self):
        r = ci.enrich(goal="hi", intents=["greeting"], confidence=0.9, escalate=False, kill=True)
        self.assertTrue(r["logic"]["motors_silenced"])
        self.assertEqual(r["recommendation"]["path_hint"], "killed")

    def test_non_aaron_rejects(self):
        r = ci.enrich(
            goal="do something",
            intents=["general"],
            confidence=0.7,
            escalate=True,
            not_aaron=True,
        )
        self.assertTrue(r["logic"]["reject_task"])
        self.assertEqual(r["recommendation"]["path_hint"], "reject")

    def test_enhance_needs_switch_flag(self):
        r = ci.enrich(
            goal="enhance Cam",
            intents=["enhance"],
            confidence=0.4,
            escalate=True,
            enhance_intent=True,
        )
        self.assertTrue(r["logic"]["needs_enhance_switch"])
        self.assertEqual(r["strategy"], "analytical")

    def test_strategy_map(self):
        self.assertEqual(ci.pick_strategy(["personal_fact"]), "analogical")
        self.assertEqual(ci.pick_strategy(["greeting"]), "systematic")

    def test_cli(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cam-infinitemind.py"), "--goal", "plan research"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data.get("ok"))


class ReasonIntegrationTests(unittest.TestCase):
    def test_slow_path_includes_logic_stage(self):
        t = cr.reason(goal="think carefully and make a plan", write_trace=False)
        self.assertEqual(t["path"], "slow")
        self.assertIn("logic", t["stages"])
        tools = {r.get("tool"): r for r in (t.get("toolkit_results") or [])}
        self.assertIn("InfiniteMindEnrich", tools)
        self.assertTrue(tools["InfiniteMindEnrich"].get("ok"))
        self.assertIn("infinitemind", t.get("engine", ""))

    def test_fast_path_skips_logic(self):
        t = cr.reason(goal="hi cam", write_trace=False)
        self.assertEqual(t["path"], "fast")
        self.assertNotIn("logic", t["stages"])
        tools = [r.get("tool") for r in (t.get("toolkit_results") or [])]
        self.assertNotIn("InfiniteMindEnrich", tools)


if __name__ == "__main__":
    unittest.main()
