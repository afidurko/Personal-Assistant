#!/usr/bin/env python3
"""Smoke tests for MemoryBear Cam wiring (offline, no network)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MemoryBearWiringTests(unittest.TestCase):
    def test_offline_doctor(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(ROOT / "scripts/memorybear.py"), "--doctor", "--offline"],
            text=True,
        )
        doc = json.loads(out)
        self.assertTrue(doc.get("ok"))
        self.assertEqual(doc.get("sense"), "sense.memorybear.hit")
        self.assertEqual(doc.get("motor"), "motor.memorybear")

    def test_offline_read_write(self) -> None:
        read = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/memorybear.py"),
                    "read",
                    "--query",
                    "Aaron preferences",
                    "--offline",
                    "--no-save-vault",
                ],
                text=True,
            )
        )
        self.assertTrue(read.get("ok", True))
        self.assertIn("Aaron", read.get("answer") or "")

        write = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/memorybear.py"),
                    "write",
                    "--message",
                    "Aaron prefers soft airy Cam voice",
                    "--offline",
                    "--no-save-vault",
                ],
                text=True,
            )
        )
        self.assertTrue(write.get("ok", True))
        self.assertTrue(write.get("msg_id"))

    def test_pack_result(self) -> None:
        sample = ROOT / "scripts/testdata/sample-memorybear-read.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "mesh.json"
            subprocess.check_call(
                [
                    sys.executable,
                    str(ROOT / "scripts/pack-memorybear-result.py"),
                    "--results",
                    str(sample),
                    "--out",
                    str(out),
                ]
            )
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["namespace"], "mesh/memorybear")
            self.assertGreaterEqual(doc["count"], 1)

    def test_connectome_route(self) -> None:
        route = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.memorybear.hit",
                    "--goal",
                    "memorybear recall",
                ],
                text=True,
            )
        )
        self.assertEqual(route.get("hotspot_id"), "hotspot.memorybear_recall")
        self.assertIn("motor.memorybear", route.get("motor_plan") or [])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
