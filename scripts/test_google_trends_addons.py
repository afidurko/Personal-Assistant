#!/usr/bin/env python3
"""Unit tests for google-trends curated add-ons."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "scripts" / "google-trends-addon.py"


class GoogleTrendsAddonTests(unittest.TestCase):
    def _run(self, *args: str) -> dict:
        out = subprocess.check_output(
            [sys.executable, str(ADDON), *args],
            text=True,
            cwd=str(ROOT),
        )
        return json.loads(out)

    def test_doctor(self) -> None:
        report = self._run("doctor")
        self.assertTrue(report.get("ok"))
        self.assertGreaterEqual(report.get("addon_count", 0), 4)

    def test_list(self) -> None:
        payload = self._run("list")
        ids = {a["id"] for a in payload.get("addons") or []}
        self.assertIn("trends.search_election", ids)
        self.assertIn("trends.dataset_game_theory", ids)

    def test_call_election_offline(self) -> None:
        payload = self._run("call", "trends.search_election", "--offline")
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("offline"))
        result = payload.get("result") or {}
        self.assertGreaterEqual(len(result.get("results") or []), 1)

    def test_call_dataset_offline(self) -> None:
        payload = self._run("call", "trends.dataset_game_theory", "--offline")
        self.assertTrue(payload.get("ok"))
        result = payload.get("result") or {}
        self.assertIn("GameTheory", result.get("path") or "")
        self.assertTrue(result.get("preview"))

    def test_call_unknown_rejected(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ADDON), "call", "not.a.real.addon", "--offline"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown addon", (proc.stderr + proc.stdout).lower())

    def test_free_form_path_not_in_cli(self) -> None:
        help_out = subprocess.check_output(
            [sys.executable, str(ADDON), "call", "-h"],
            text=True,
            cwd=str(ROOT),
        )
        self.assertNotIn("--path", help_out)
        self.assertNotIn("--url", help_out)


if __name__ == "__main__":
    unittest.main()
