#!/usr/bin/env python3
"""Unit tests for ILLA desktop Cam wiring + packaging contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "integrations" / "illa-desktop"
sys.path.insert(0, str(ROOT / "scripts"))


class IllaDesktopTests(unittest.TestCase):
    def test_package_pin_and_author(self):
        pkg = json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["devDependencies"]["electron-builder"], "26.16.1")
        self.assertEqual(pkg["build"]["appId"], "com.afidurko.illa-builder")
        self.assertIn("@", pkg["author"]["email"])
        self.assertIn("@", pkg["build"]["linux"]["maintainer"])

    def test_required_files(self):
        for rel in (
            "src/main.js",
            "src/preload.js",
            "src/url-contract.js",
            "scripts/assert-builder-pin.mjs",
            "scripts/contract-selftest.js",
            "build/icon.png",
            "build/icon.ico",
        ):
            self.assertTrue((DESKTOP / rel).is_file(), rel)

    def test_node_contract_selftest(self):
        proc = subprocess.run(
            ["node", str(DESKTOP / "scripts/contract-selftest.js")],
            cwd=str(DESKTOP),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_assert_builder_pin(self):
        proc = subprocess.run(
            ["node", str(DESKTOP / "scripts/assert-builder-pin.mjs")],
            cwd=str(DESKTOP),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_illa_electron_check(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/illa-electron-check.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["pin"], "26.16.1")

    def test_registry_workspaces(self):
        reg = json.loads((ROOT / "config/workspaces/registry.json").read_text(encoding="utf-8"))
        ids = {w["id"] for w in reg["workspaces"]}
        for need in ("illa-builder", "illa-desktop", "electron-builder"):
            self.assertIn(need, ids)

    def test_promote_script_pin_constant(self):
        body = (ROOT / "scripts/promote-illa-desktop.py").read_text(encoding="utf-8")
        self.assertIn('PIN = "26.16.1"', body)

    def test_url_contract_xss_escape_in_source(self):
        body = (DESKTOP / "src/url-contract.js").read_text(encoding="utf-8")
        self.assertIn("&amp;", body)
        self.assertIn("escapeHtml", body)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
