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
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
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
        os.environ["CAM_SWARM_DIR"] = str(Path(self._tmp.name) / "swarm")

    def tearDown(self):
        os.environ.pop("INSTINCT_DATA_DIR", None)
        os.environ.pop("CAM_SWARM_DIR", None)
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


class RegressionTests(InstinctBase):
    def test_naive_timestamps_are_utc_regardless_of_host_tz(self):
        import time
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/New_York"
        time.tzset()
        try:
            dt = instinct.parse_ts("2026-09-18T00:00:00")
            self.assertEqual((dt.hour, dt.utcoffset().total_seconds()), (0, 0))
        finally:
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

    def test_sync_bad_reply_to_does_not_leak_job(self):
        inbox = self.data() / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "bad.json").write_text(json.dumps({
            "from": "sense.x", "text": "hi",
            "job": "Leaky job", "reply_to": "nonexistent",
        }))
        out = run("--now", T0, "sync")
        self.assertEqual(len(out["skipped"]), 1)
        self.assertEqual(run("job", "list"), [])

    def test_overdue_draft_respects_cooldown_but_stays_in_findings(self):
        run("--now", T0, "job", "add", "Overdue thing", "--due", "2026-09-14T10:00:00Z")
        first = run("--now", "2026-09-14T11:00:00Z", "scan", "--write")
        self.assertEqual(len(first["drafts"]), 1)
        soon = run("--now", "2026-09-14T12:00:00Z", "scan", "--write")
        self.assertEqual(soon["drafts"], [])  # cooldown: no second nudge 1h later
        self.assertEqual(soon["findings"][0]["kind"], "overdue")  # still reported
        later = run("--now", "2026-09-16T09:00:00Z", "scan", "--write")
        self.assertEqual(len(later["drafts"]), 1)

    def test_snoozed_job_not_double_counted_as_open(self):
        add = run("--now", T0, "job", "add", "Snoozed thing")
        run("--now", T0, "job", "snooze", add["job"], "--until", "2026-09-20T00:00:00Z")
        rep = run("--now", "2026-09-15T09:00:00Z", "report")
        self.assertEqual(rep["open"], [])
        self.assertEqual(rep["jobs"]["snoozed"], 1)
        self.assertEqual(rep["snoozed"][0]["until"], "2026-09-20T00:00:00Z")

    def test_job_note_and_wait_require_text(self):
        add = run("--now", T0, "job", "add", "Some job")
        for action in ("note", "wait"):
            with self.assertRaises(SystemExit) as ctx:
                run("--now", T0, "job", action, add["job"])
            self.assertNotEqual(ctx.exception.code, 0)


class ValidationAndRobustnessTests(InstinctBase):
    def test_bad_due_rejected_at_creation(self):
        with self.assertRaises(SystemExit):
            run("--now", T0, "job", "add", "Poisoned", "--due", "next tuesday")
        self.assertEqual(run("job", "list"), [])

    def test_bad_due_in_sync_event_skipped_cleanly(self):
        inbox = self.data() / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "bad-due.json").write_text(json.dumps({
            "from": "sense.x", "text": "hi", "job": "Poisoned", "due": "whenever",
        }))
        out = run("--now", T0, "sync")
        self.assertEqual(len(out["skipped"]), 1)
        self.assertEqual(run("job", "list"), [])

    def test_corrupt_ledger_fails_with_clear_message(self):
        (self.data()).mkdir(parents=True, exist_ok=True)
        (self.data() / "ledger.json").write_text("{broken")
        with self.assertRaises(SystemExit) as ctx:
            run("report")
        self.assertIn("ledger corrupt", str(ctx.exception))

    def test_ambiguous_reply_to_rejected(self):
        # Force two messages whose ids share a prefix, then reply with that prefix
        run("--now", T0, "ingest", "--text", "first")
        run("--now", T0, "ingest", "--text", "second")
        ledger = json.loads((self.data() / "ledger.json").read_text())
        ledger["thread"][0]["id"] = "aaaa1111"
        ledger["thread"][1]["id"] = "aaaa2222"
        (self.data() / "ledger.json").write_text(json.dumps(ledger))
        with self.assertRaises(SystemExit) as ctx:
            run("--now", T0, "ingest", "--from", "cam", "--text", "reply", "--reply-to", "aaaa")
        self.assertIn("ambiguous", str(ctx.exception))

    def test_atomic_save_leaves_no_temp_file(self):
        run("--now", T0, "job", "add", "Anything")
        self.assertFalse(list(self.data().glob("*.tmp")))
        self.assertTrue((self.data() / "ledger.json").exists())


class AddOnTests(InstinctBase):
    def test_relative_due_and_snooze(self):
        add = run("--now", T0, "job", "add", "Relative due", "--due", "+3d")
        jobs = run("job", "list")
        self.assertEqual(jobs[0]["due"], "2026-09-17T09:00:00Z")
        run("--now", T0, "job", "snooze", add["job"], "--until", "+12h")
        jobs = run("job", "list")
        self.assertEqual(jobs[0]["snooze_until"], "2026-09-14T21:00:00Z")

    def test_outbox_review_lifecycle(self):
        run("--now", T0, "job", "add", "Job A")
        run("--now", T0, "job", "add", "Job B")
        run("--now", "2026-09-16T09:00:00Z", "scan", "--write")
        listing = run("outbox", "list")
        self.assertEqual(len(listing["pending"]), 2)
        a, b = listing["pending"]
        approved = run("--now", "2026-09-16T10:00:00Z", "outbox", "approve", a)
        self.assertIn("approved", approved["moved_to"])
        self.assertIn("nothing was sent", approved["note"])
        run("--now", "2026-09-16T10:01:00Z", "outbox", "discard", b)
        listing = run("outbox", "list")
        self.assertEqual(listing["pending"], [])
        self.assertEqual(len(listing["approved"]), 1)
        self.assertEqual(len(listing["discarded"]), 1)
        # approved draft carries the review stamp
        text = (self.data() / "outbox/approved" / a).read_text()
        self.assertIn("approved: 2026-09-16T10:00:00Z", text)

    def test_outbox_requires_name_and_rejects_unknown(self):
        with self.assertRaises(SystemExit):
            run("outbox", "approve")
        with self.assertRaises(SystemExit):
            run("outbox", "approve", "nope.md")

    def test_stats_scorecard(self):
        msg = run("--now", T0, "ingest", "--text", "Can you fix the sink?", "--job", "Fix sink")
        run("--now", "2026-09-15T09:00:00Z", "job", "done", msg["job"])
        run("--now", T0, "ingest", "--text", "Can you also book flights?")
        stats = run("--now", "2026-09-16T09:00:00Z", "stats")
        self.assertEqual(stats["jobs"]["done"], 1)
        self.assertEqual(stats["jobs"]["avg_hours_to_done"], 24.0)
        self.assertEqual(stats["asks"], {"tracked": 2, "answered": 1, "answer_rate": 0.5})

    def test_find_searches_thread_jobs_and_notes(self):
        run("--now", T0, "ingest", "--text", "The sink is leaking again")
        add = run("--now", T0, "job", "add", "Call plumber")
        run("--now", T0, "job", "note", add["job"], "plumber quoted 200 for the sink")
        out = run("find", "sink")
        self.assertEqual(len(out["messages"]), 1)
        self.assertEqual(len(out["jobs"]), 1)
        self.assertIn("plumber quoted 200 for the sink", out["jobs"][0]["matched_notes"])

    def test_brief_vault_distillation(self):
        vault = Path(self._tmp.name) / "vault-briefs"
        os.environ["INSTINCT_VAULT_DIR"] = str(vault)
        try:
            run("--now", T0, "job", "add", "Fix the sink")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                instinct.main(["--now", "2026-09-15T09:00:00Z", "brief", "--vault"])
            self.assertTrue((vault / "2026-09-15.md").exists())
        finally:
            os.environ.pop("INSTINCT_VAULT_DIR", None)


class CrossWorkspaceTests(InstinctBase):
    def setUp(self):
        super().setUp()
        os.environ["INSTINCT_NO_CACHE_MIRROR"] = "1"

    def tearDown(self):
        os.environ.pop("INSTINCT_NO_CACHE_MIRROR", None)
        os.environ.pop("INSTINCT_MESH_OUT", None)
        super().tearDown()

    def test_chooser_routes_coding_job_by_goal(self):
        out = run("--now", T0, "job", "add", "Fix inkbox sdk identity email auth", "--coding")
        self.assertEqual(out["workspace"], "inkbox")
        self.assertEqual(out["kind"], "coding")

    def test_life_job_defaults_to_personal_assistant(self):
        out = run("--now", T0, "job", "add", "Book dentist appointment")
        self.assertEqual(out["workspace"], "personal-assistant")

    def test_explicit_workspace_validated(self):
        out = run("--now", T0, "job", "add", "anything", "--workspace", "voicestudio")
        self.assertEqual((out["workspace"], out["workspace_reason"]), ("voicestudio", "explicit"))
        with self.assertRaises(SystemExit):
            run("--now", T0, "job", "add", "anything", "--workspace", "not-a-workspace")

    def test_job_list_filters_by_workspace(self):
        run("--now", T0, "job", "add", "A", "--workspace", "pupil")
        run("--now", T0, "job", "add", "B", "--workspace", "jarvis")
        rows = run("job", "list", "--workspace", "pupil")
        self.assertEqual([r["title"] for r in rows], ["A"])

    def test_workspaces_rollup_and_brief_section(self):
        run("--now", T0, "job", "add", "A", "--workspace", "pupil", "--coding")
        run("--now", T0, "job", "add", "B", "--workspace", "pupil")
        run("--now", T0, "job", "add", "C", "--workspace", "jarvis")
        out = run("--now", T0, "workspaces")
        by = {r["workspace"]: r for r in out["workspaces"]}
        self.assertEqual((by["pupil"]["live"], by["pupil"]["coding"]), (2, 1))
        self.assertEqual(by["jarvis"]["live"], 1)
        self.assertGreaterEqual(out["registered"], 10)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            instinct.main(["--now", T0, "brief"])
        self.assertIn("## By workspace", buf.getvalue())
        self.assertIn("`pupil`", buf.getvalue())

    def test_dispatch_plan_is_print_only_and_prioritized(self):
        run("--now", T0, "job", "add", "low thing", "--coding", "--workspace", "cline", "--priority", "low")
        run("--now", T0, "job", "add", "urgent thing", "--coding", "--workspace", "inkbox", "--priority", "high")
        run("--now", T0, "job", "add", "life thing")  # not dispatchable
        out = run("--now", T0, "dispatch")
        self.assertFalse(out["executes"])
        self.assertEqual([r["title"] for r in out["plan"]], ["urgent thing", "low thing"])
        self.assertIn("--workspace-id inkbox", out["plan"][0]["command"])
        self.assertFalse((self.data() / "dispatch-plan.json").exists())
        run("--now", T0, "dispatch", "--write")
        self.assertTrue((self.data() / "dispatch-plan.json").exists())

    def test_track_cline_run_failure_opens_coding_job_via_sync(self):
        ts = instinct.parse_ts(T0)
        path = instinct.track_cline_run("voicestudio", "refactor tts pipeline", "failed", 1, "t-1", ts)
        self.assertIsNotNone(path)
        instinct.track_cline_run("inkbox", "add sdk docs", "completed", 0, "t-2", ts)
        out = run("--now", T0, "sync")
        self.assertEqual(len(out["folded"]), 2)
        jobs = run("job", "list")
        self.assertEqual(len(jobs), 1)  # only the failure opened a job
        self.assertEqual((jobs[0]["workspace"], jobs[0]["kind"], jobs[0]["priority"]),
                         ("voicestudio", "coding", "high"))
        thread = run("thread")
        self.assertTrue(all(m["from"] == "motor.cline" for m in thread))

    def test_track_cline_run_unregistered_workspace_still_folds(self):
        ts = instinct.parse_ts(T0)
        instinct.track_cline_run("ad-hoc", "something odd", "failed", 2, None, ts)
        out = run("--now", T0, "sync")
        self.assertEqual(len(out["folded"]), 1)
        self.assertEqual(out["skipped"], [])

    def test_attention_sync_imports_dedupes_and_closes_upstream(self):
        distillate = self.data() / "na.json"
        items = [
            {"id": "ws-inkbox", "kind": "connectivity", "severity": "high",
             "title": "Connect coding workspace: inkbox", "detail": "submodule empty",
             "workspace_id": "inkbox", "suggestion": "git submodule update --init"},
            {"id": "gate-outbound", "kind": "policy", "severity": "info", "title": "gated"},
            {"id": "instinct-abc", "kind": "followup", "severity": "medium",
             "title": "Instinct escalation: x", "workspace_id": "personal-assistant"},
        ]
        distillate.write_text(json.dumps({"attention_items": items}))
        out = run("--now", T0, "attention-sync", "--file", str(distillate))
        self.assertEqual(len(out["added"]), 1)
        self.assertEqual(out["added"][0]["workspace"], "inkbox")
        # idempotent
        again = run("--now", "2026-09-14T10:00:00Z", "attention-sync", "--file", str(distillate))
        self.assertEqual(again["added"], [])
        jobs = run("job", "list")
        self.assertEqual((jobs[0]["kind"], jobs[0]["priority"]), ("attention", "high"))
        # item cleared upstream -> job auto-closes
        distillate.write_text(json.dumps({"attention_items": []}))
        cleared = run("--now", "2026-09-15T09:00:00Z", "attention-sync", "--file", str(distillate))
        self.assertEqual(len(cleared["closed_upstream"]), 1)
        self.assertEqual(run("job", "list"), [])

    def test_attention_sync_missing_file_reports_cleanly(self):
        out = run("attention-sync", "--file", str(self.data() / "nope.json"))
        self.assertFalse(out["ok"])
        self.assertEqual(out["_exit"], 1)

    def test_distill_is_sanitized_counts_only(self):
        mesh_out = self.data() / "mesh" / "latest.json"
        os.environ["INSTINCT_MESH_OUT"] = str(mesh_out)
        run("--now", T0, "ingest", "--text", "Can you call Dr. Secret about the private thing?",
            "--job", "Private job title", "--workspace", "pupil")
        out = run("--now", T0, "distill")
        self.assertTrue(out["ok"])
        text = mesh_out.read_text()
        self.assertNotIn("Secret", text)
        self.assertNotIn("Private job title", text)
        doc = json.loads(text)
        self.assertEqual(doc["by_workspace"][0]["workspace"], "pupil")
        self.assertTrue(doc["draft_only"])

    def test_escalation_carries_workspace(self):
        run("--now", T0, "job", "add", "Stuck thing", "--workspace", "jarvis")
        for day in ("16", "18", "20"):
            run("--now", f"2026-09-{day}T09:00:00Z", "scan", "--write")
        run("--now", "2026-09-22T09:00:00Z", "scan")
        handoff = json.loads((self.data() / "needs-attention.json").read_text())
        self.assertEqual(handoff["items"][0]["workspace"], "jarvis")


class DelegationTests(InstinctBase):
    """`instinct delegate` — one subagent per job via the swarm runtime."""

    def swarm(self):
        import cam_swarm
        return cam_swarm

    def test_delegate_picks_role_by_kind_and_title(self):
        cases = [
            (("job", "add", "Negotiate Comcast bill before renewal"), "negotiator"),
            (("job", "add", "Reschedule dentist appointment"), "scheduler"),
            (("job", "add", "Find a plumber for the kitchen leak"), "errand-runner"),
            (("job", "add", "Watch Steam Deck restock", "--monitor", "24"), "watcher"),
            (("job", "add", "Fix flaky voice test", "--coding", "--workspace", "voicestudio"), "task-executor"),
        ]
        for argv, expected in cases:
            job = run("--now", T0, *argv)["job"]
            out = run("--now", T0, "delegate", job)
            self.assertEqual(out["role"], expected, argv)

    def test_delegate_pins_lineage_and_child_cannot_send(self):
        job = run("--now", T0, "job", "add", "Cancel gym membership")["job"]
        out = run("--now", T0, "delegate", job)
        self.assertTrue(out["ok"])
        self.assertEqual(out["level"], 2)
        self.assertEqual(out["team"], "team.follow-through")
        self.assertNotIn("outbound_send", out["privileges"])
        self.assertIn("outbound_draft", out["privileges"])
        ledger = instinct.load_ledger()
        j = ledger["jobs"][0]
        self.assertEqual(j["delegation"]["agent"], out["agent"])
        self.assertEqual(j["status"], "waiting")
        self.assertIn(out["agent"], j["waiting_on"])
        lineage = self.swarm().load_ledger()
        self.assertEqual(lineage["agents"][out["agent"]]["job_ref"], f"job:{job}")
        self.assertEqual([a["status"] for a in lineage["actions"]], ["open"])

    def test_monitor_stays_open_when_delegated(self):
        job = run("--now", T0, "job", "add", "Watch price", "--monitor", "12")["job"]
        run("--now", T0, "delegate", job)
        self.assertEqual(instinct.load_ledger()["jobs"][0]["status"], "open")

    def test_done_resolves_action_and_retires_agent(self):
        job = run("--now", T0, "job", "add", "Cancel gym membership")["job"]
        out = run("--now", T0, "delegate", job)
        run("--now", T0, "job", "done", job)
        lineage = self.swarm().load_ledger()
        self.assertEqual(lineage["actions"][0]["status"], "done")
        self.assertEqual(lineage["agents"][out["agent"]]["status"], "terminated")
        notes = instinct.load_ledger()["jobs"][0]["notes"]
        self.assertTrue(any("lineage resolved" in n["text"] for n in notes))

    def test_double_delegate_needs_force(self):
        job = run("--now", T0, "job", "add", "Cancel gym membership")["job"]
        run("--now", T0, "delegate", job)
        with self.assertRaises(SystemExit):
            run("--now", T0, "delegate", job)
        out = run("--now", T0, "delegate", job, "--force", "--role", "qa")
        self.assertEqual(out["role"], "qa")

    def test_delegate_done_job_refused(self):
        job = run("--now", T0, "job", "add", "x")["job"]
        run("--now", T0, "job", "done", job)
        with self.assertRaises(SystemExit):
            run("--now", T0, "delegate", job)

    def test_kill_switch_blocks_delegate(self):
        job = run("--now", T0, "job", "add", "x")["job"]
        os.environ["CAM_SWITCH_KILL"] = "act"
        try:
            with self.assertRaises(SystemExit):
                run("--now", T0, "delegate", job)
        finally:
            os.environ.pop("CAM_SWITCH_KILL", None)
        self.assertNotIn("delegation", instinct.load_ledger()["jobs"][0])

    def test_report_and_stats_count_delegated(self):
        a = run("--now", T0, "job", "add", "a")["job"]
        run("--now", T0, "job", "add", "b")
        run("--now", T0, "delegate", a)
        self.assertEqual(run("--now", T0, "report")["jobs"]["delegated"], 1)
        self.assertEqual(run("--now", T0, "stats")["jobs"]["delegated"], 1)


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
