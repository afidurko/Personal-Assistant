#!/usr/bin/env python3
"""Tests for scripts/coding-effector-smoke.py."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodingEffectorSmokeTests(unittest.TestCase):
    def test_smoke_ok(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/coding-effector-smoke.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["motor"], "motor.cline")
        self.assertTrue(data["wiring"]["motor_cline"])
        self.assertTrue(data["local_build"]["ok"])
        self.assertEqual(data["local_build"]["artifact"]["sum"], 55)
        self.assertTrue(data["run_cline_dry"]["ok"])
        self.assertEqual(data["errors"], [])


if __name__ == "__main__":
    unittest.main()
