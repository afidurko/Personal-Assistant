#!/usr/bin/env python3
"""Tests for Cam System-1 fast path compute layer."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_fast as cf  # noqa: E402
import cam_reason as cr  # noqa: E402


class FastPathTests(unittest.TestCase):
    def test_warmup_and_fast_turn(self):
        w = cf.warmup()
        self.assertTrue(w["warmed"])
        r = cf.run_fast(goal="hi cam")
        self.assertEqual(r["path"], "fast")
        self.assertEqual(r["tool"], "CamFastPath")
        self.assertIn("recall", r["stages_skipped"])
        self.assertIn("logic", r["stages_skipped"])
        self.assertIn("sgr", r["stages_skipped"])
        self.assertEqual(r["motor_plan"], ["motor.mesh"])
        self.assertIn("elapsed_ms", r["compute"])

    def test_escalate_hint(self):
        r = cf.run_fast(goal="think carefully and make a plan for research")
        self.assertEqual(r["path"], "escalate_to_slow")

    def test_cache_hits(self):
        cf.warmup()
        cf.classify_cached("hello there cam")
        a = cf.classify_cached("hello there cam")
        self.assertEqual(a.get("cache"), "hit")

    def test_bench_throughput(self):
        b = cf.bench(2000, "hi cam")
        self.assertGreater(b["classifies_per_sec"], 50_000)

    def test_reason_fast_uses_cam_fast(self):
        t = cr.reason(goal="hi cam", write_trace=False)
        self.assertEqual(t["path"], "fast")
        self.assertEqual(t["engine"], "system1_fast_heuristics")
        self.assertIsNotNone(t.get("compute"))
        self.assertIn("CamFastPath", t.get("toolkit") or [])
        self.assertNotIn("logic", t["stages"])
        self.assertNotIn("sgr", t["stages"])

    def test_cli(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cam-fast.py"), "--goal", "hey cam"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data.get("path"), "fast")


if __name__ == "__main__":
    unittest.main()
