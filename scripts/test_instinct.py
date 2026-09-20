#!/usr/bin/env python3
"""Unit tests for Cam Instinct (scripts/instinct.py). Offline, deterministic.

Run: python3 -m unittest scripts.test_instinct  (or python3 scripts/test_instinct.py)
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import instinct  # noqa: E402

T0 = "2026-09-14T09:00:00Z"


def run(*argv: str) -> dict | list:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = instinct.main(list(argv))
    out = buf.getvalue()
    parsed = json.loads(out) if out.lstrip().startswith(("{", "[")) else out
    if isinstance(parsed, dict):
        parsed["_exit"] = code
    return parsed


class InstinctBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["INSTINCT_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("INSTINCT_DATA_DIR", None)
        self._tmp.cleanup()

    def data(self) -> Path:
        return Path(self._tmp.name)


class ThreadAndAsksTests(InstinctBase):
    def test_ingest_tracks_aaron_ask(self):
        out = run("--now", T0, "ingest", "--text", "Can you book the dentist?")
        self.assertTrue(out["ok"])
        self.assertTrue(out["tracked_ask"])

    def test_plain_statement_not_tracked(self):
        out = run("--now", T0, "ingest", "--text", "Landed safely in Austin.")
        self.assertFalse(out["tracked_ask"])

    def test_reply_to_closes_ask(self):
        ask = run("--now", T0, "ingest", "--text", "Can you book the dentist?")
        run("--now", "2026-09-14T10:00:00Z", "ingest", "--from", "cam",
            "--text", "Booked for Thursday 3pm.", "--reply-to", ask["message"])
        scan = run("--now", "2026-09-15T09:00:00Z", "scan")
        kinds = [f["kind"] for f in scan["findings"]]
        self.assertNotIn("dropped_ask", kinds)

    def test_all_unanswered_asks_surface_not_just_last(self):
        run("--now", T0, "ingest", "--text", "Can you renew the car registration?")
        run("--now", "2026-09-14T10:00:00Z", "ingest", "--text", "Please cancel the gym trial?")
        run("--now", "2026-09-14T11:00:00Z", "ingest", "--text", "Landed safely.")
        scan = run("--now", "2026-09-15T09:00:00Z", "scan")
        dropped = [f for f in scan["findings"] if f["kind"] == "dropped_ask"]
        self.assertEqual(len(dropped), 2)

    def test_ask_within_reply_window_not_dropped(self):
        run("--now", T0, "ingest", "--text", "Can you book the dentist?")
        scan = run("--now", "2026-09-14T10:00:00Z", "scan")  # 1h later < 4h window
        self.assertEqual([f for f in scan["findings"] if f["kind"] == "dropped_ask"], [])


class JobLifecycleTests(InstinctBase):
    def test_stale_job_drafts_followup(self):
        run("--now", T0, "job", "add", "Lower the internet bill")
        scan = run("--now", "2026-09-16T09:00:00Z", "scan", "--write")
        self.assertEqual(scan["findings"][0]["kind"], "stale")
        self.assertEqual(len(scan["drafts"]), 1)
        draft = (self.data() / "outbox").glob("*.md")
        text = next(draft).read_text()
        self.assertIn("send_via: motor.inkbox", text)
        self.assertIn("requires: switch.outbound=act", text)

    def test_overdue_before_stale_window(self):
        run("--now", T0, "job", "add", "File the insurance claim", "--due", "2026-09-14T12:00:00Z")
        scan = run("--now", "2026-09-14T13:00:00Z", "scan")
        self.assertEqual(scan["findings"][0]["kind"], "overdue")

    def test_high_priority_halves_window(self):
        run("--now", T0, "job", "add", "Confirm flight change", "--priority", "high")
        scan = run("--now", "2026-09-14T22:00:00Z", "scan")  # 13h > 12h high window
        self.assertEqual(scan["findings"][0]["kind"], "stale")

    def test_low_priority_doubles_window(self):
        run("--now", T0, "job", "add", "Research standing desk", "--priority", "low")
        scan = run("--now", "2026-09-15T15:00:00Z", "scan")  # 30h < 48h low window
        self.assertEqual(scan["findings"], [])

    def test_snooze_suppresses_then_expires(self):
        add = run("--now", T0, "job", "add", "Chase the plumber quote")
        run("--now", T0, "job", "snooze", add["job"], "--until", "2026-09-18T00:00:00Z")
        quiet = run("--now", "2026-09-16T09:00:00Z", "scan")
        self.assertEqual(quiet["findings"], [])
        awake = run("--now", "2026-09-19T09:00:00Z", "scan")
        self.assertEqual(awake["findings"][0]["kind"], "stale")

    def test_done_job_never_scanned_and_closes_origin_ask(self):
        msg = run("--now", T0, "ingest", "--text", "Can you fix the sink?",
                  "--job", "Fix the sink")
        run("--now", "2026-09-14T10:00:00Z", "job", "done", msg["job"])
        scan = run("--now", "2026-09-20T09:00:00Z", "scan")
        self.assertEqual(scan["findings"], [])

    def test_followup_cadence_uses_last_followup(self):
        run("--now", T0, "job", "add", "Lower the internet bill")
        first = run("--now", "2026-09-16T09:00:00Z", "scan", "--write")
        self.assertEqual(len(first["drafts"]), 1)
        soon = run("--now", "2026-09-16T15:00:00Z", "scan", "--write")
        self.assertEqual(soon["drafts"], [])  # inside the window since last nudge
        later = run("--now", "2026-09-17T10:00:00Z", "scan", "--write")
        self.assertEqual(len(later["drafts"]), 1)


class MonitorAndEscalationTests(InstinctBase):
    def test_monitor_nudges_on_interval_and_never_escalates(self):
        run("--now", T0, "job", "add", "Watch for concert ticket restock", "--monitor", "12")
        for i, day_hour in enumerate([("14", "22"), ("15", "11"), ("16", "00"),
                                      ("16", "13"), ("17", "02")]):
            day, hour = day_hour
            scan = run("--now", f"2026-09-{day}T{hour}:00:00Z", "scan", "--write")
            self.assertEqual(scan["findings"][0]["kind"], "monitor_check", f"iteration {i}")
        # 5 nudges > max_followups(3) yet still monitor_check, never needs_aaron
        final = run("--now", "2026-09-17T15:00:00Z", "scan")
        self.assertEqual(final["findings"][0]["kind"], "monitor_check")

    def test_escalation_after_max_followups_and_handoff_file(self):
        run("--now", T0, "job", "add", "Lower the internet bill")
        for day in ("16", "18", "20"):
            run("--now", f"2026-09-{day}T09:00:00Z", "scan", "--write")
        scan = run("--now", "2026-09-22T09:00:00Z", "scan")
        self.assertEqual(scan["findings"][0]["kind"], "needs_aaron")
        handoff = json.loads((self.data() / "needs-attention.json").read_text())
        self.assertEqual(len(handoff["items"]), 1)
        self.assertEqual(handoff["source"], "motor.instinct")


class SyncTests(InstinctBase):
    def test_sync_folds_event_drop_and_opens_job(self):
        inbox = self.data() / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "evt1.json").write_text(json.dumps({
            "from": "sense.inkbox.event",
            "text": "Email from landlord: lease renewal due Oct 1",
            "ts": "2026-09-14T08:00:00Z",
            "job": "Handle lease renewal",
            "due": "2026-10-01T00:00:00Z",
            "priority": "high",
        }))
        out = run("--now", T0, "sync")
        self.assertEqual(len(out["folded"]), 1)
        self.assertTrue((inbox / "processed" / "evt1.json").exists())
        jobs = run("job", "list")
        self.assertEqual(jobs[0]["title"], "Handle lease renewal")
        self.assertEqual(jobs[0]["priority"], "high")

    def test_sync_skips_malformed_drop(self):
        inbox = self.data() / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "bad.json").write_text("{\"from\": \"x\"}")
        out = run("--now", T0, "sync")
        self.assertEqual(out["folded"], [])
        self.assertEqual(len(out["skipped"]), 1)
        self.assertTrue((inbox / "bad.json").exists())  # left for inspection


class ReportBriefDoctorTests(InstinctBase):
    def test_report_counts_and_sections(self):
        run("--now", T0, "ingest", "--text", "Can you book the dentist?")
        run("--now", T0, "job", "add", "Fix the sink")
        add = run("--now", T0, "job", "add", "Chase quote")
        run("--now", T0, "job", "wait", add["job"], "handyman reply")
        run("--now", T0, "job", "add", "Watch restock", "--monitor", "24")
        rep = run("--now", "2026-09-15T09:00:00Z", "report")
        self.assertEqual(rep["jobs"]["open"], 1)
        self.assertEqual(rep["jobs"]["waiting"], 1)
        self.assertEqual(rep["jobs"]["monitors"], 1)
        self.assertEqual(len(rep["unanswered_asks"]), 1)

    def test_brief_writes_markdown(self):
        run("--now", T0, "job", "add", "Fix the sink")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            instinct.main(["--now", "2026-09-15T09:00:00Z", "brief", "--write"])
        text = buf.getvalue()
        self.assertIn("# Instinct brief — 2026-09-15", text)
        self.assertIn("Fix the sink", text)
        self.assertTrue((self.data() / "briefs" / "2026-09-15.md").exists())

    def test_doctor_green_on_fresh_ledger(self):
        run("--now", T0, "ingest", "--text", "hello")
        doc = run("doctor")
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["_exit"], 0)

    def test_draft_only_is_not_configurable(self):
        self.assertTrue(instinct.defaults()["draft_only"])


if __name__ == "__main__":
    unittest.main()
