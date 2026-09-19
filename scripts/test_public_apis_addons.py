#!/usr/bin/env python3
"""Unit tests for public-apis thin-wrapper add-ons."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "scripts" / "public-apis-addon.py"


class PublicApisAddonTests(unittest.TestCase):
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
        self.assertIn("weather.open_meteo", ids)
        self.assertIn("geo.open_meteo", ids)
        self.assertIn("facts.catfact", ids)

    def test_call_weather_offline(self) -> None:
        payload = self._run(
            "call",
            "weather.open_meteo",
            "--latitude",
            "40.7",
            "--longitude",
            "-74.0",
            "--offline",
        )
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("offline"))
        self.assertIn("current", payload.get("result") or {})

    def test_call_geo_offline(self) -> None:
        payload = self._run("call", "geo.open_meteo", "--name", "New York", "--offline")
        self.assertTrue(payload.get("ok"))
        results = (payload.get("result") or {}).get("results") or []
        self.assertGreaterEqual(len(results), 1)

    def test_call_unknown_rejected(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ADDON), "call", "not.a.real.addon", "--offline"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown addon", (proc.stderr + proc.stdout).lower())

    def test_free_form_url_not_in_cli(self) -> None:
        # Guardrail: argparse has no --url; allowlist only.
        help_out = subprocess.check_output(
            [sys.executable, str(ADDON), "call", "-h"],
            text=True,
            cwd=str(ROOT),
        )
        self.assertNotIn("--url", help_out)


if __name__ == "__main__":
    unittest.main()
