#!/usr/bin/env python3
"""Unit tests for google-trends catalog search/pack."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "scripts" / "google-trends-search.py"
PACK = ROOT / "scripts" / "pack-google-trends-result.py"


class GoogleTrendsSearchTests(unittest.TestCase):
    def test_offline_election_search(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--query", "election", "--offline", "--num", "5"],
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("offline"))
        self.assertGreaterEqual(payload.get("returned", 0), 1)
        blob = " ".join(
            f"{r.get('topic','')} {r.get('name','')} {r.get('path','')}"
            for r in payload["results"]
        ).lower()
        self.assertTrue("election" in blob or "primary" in blob or "iowa" in blob)

    def test_list_years_offline(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--list-years", "--offline"],
            text=True,
        )
        payload = json.loads(out)
        self.assertGreaterEqual(payload.get("count", 0), 1)
        self.assertTrue(any(str(y).startswith("20") for y in payload.get("years") or []))

    def test_doctor(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--doctor"],
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))

    def test_offline_fetch_does_not_download(self) -> None:
        out = subprocess.check_output(
            [
                sys.executable,
                str(SEARCH),
                "--fetch",
                "20150626_SameSexMarriage.csv",
                "--offline",
            ],
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))
        self.assertFalse(payload.get("fetched"))
        self.assertEqual(payload.get("entry", {}).get("name"), "20150626_SameSexMarriage.csv")

    def test_pack(self) -> None:
        search = subprocess.check_output(
            [sys.executable, str(SEARCH), "--query", "nba", "--offline", "--num", "2"],
            text=True,
        )
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "results.json"
            dst = Path(td) / "mesh.json"
            src.write_text(search, encoding="utf-8")
            subprocess.check_call(
                [sys.executable, str(PACK), "--results", str(src), "--out", str(dst)]
            )
            doc = json.loads(dst.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("namespace"), "mesh/research")
            self.assertEqual(doc.get("kind"), "google_trends_catalog_hit")
            self.assertGreaterEqual(len(doc.get("datasets") or []), 1)


if __name__ == "__main__":
    unittest.main()
