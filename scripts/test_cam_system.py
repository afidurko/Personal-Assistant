#!/usr/bin/env python3
"""Unit tests for cam-system inventory + hard paths."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CamSystemTests(unittest.TestCase):
    def test_pieces_inventory_loads(self) -> None:
        cfg = json.loads((ROOT / "config/system/pieces.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("assistant"), "Cam")
        pieces = cfg.get("pieces") or []
        self.assertGreaterEqual(len(pieces), 10)
        ids = {p["id"] for p in pieces}
        self.assertIn("piece.system_bridge", ids)
        self.assertIn("piece.connectome", ids)
        self.assertIn("piece.converse", ids)
        boot = cfg.get("boot_order") or []
        self.assertIn("piece.system_bridge", boot)

    def test_cam_system_script_passes(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/cam-system.py"), "--json", "--no-write"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["piece_count"], 10)
        self.assertEqual(report.get("hard_missing"), [])

    def test_system_bridge_file_present(self) -> None:
        self.assertTrue((ROOT / "server/core/system-bridge.ts").exists())
        self.assertTrue((ROOT / "docs/SYSTEM_INTEGRATION.md").exists())


if __name__ == "__main__":
    unittest.main()
