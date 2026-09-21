#!/usr/bin/env python3
"""Unit tests for Cam Sentinel + intent journal (Muse pattern)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_inproc  # noqa: E402
import cam_journal as cj  # noqa: E402
import cam_sentinel as cs  # noqa: E402


class IsolatedRuntime(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._root, self._journal = cs.ROOT, cj.JOURNAL_DIR
        cs.ROOT = Path(self.tmp.name)
        cj.JOURNAL_DIR = Path(self.tmp.name) / "journal"
        cs._GRANTS_CACHE = None

    def tearDown(self) -> None:
        cs.ROOT, cj.JOURNAL_DIR = self._root, self._journal
        cs._GRANTS_CACHE = None
        self.tmp.cleanup()


class SentinelDecisionTests(IsolatedRuntime):
    def test_route_marks_email_egress_pending(self) -> None:
        doc = cam_inproc.route(sense="sense.email.thread", goal="reply")
        self.assertIn("motor.text", doc["motor_pending"])
        self.assertIn("motor.inkbox", doc["motor_pending"])
        self.assertNotIn("motor.text", doc["motor_plan"])
        self.assertIn("motor.mesh", doc["motor_plan"])
        self.assertTrue(doc["sentinel"]["taint"]["tainted"])

    def test_clean_chat_unchanged(self) -> None:
        doc = cam_inproc.route(sense="sense.chat.aaron", goal="system smoke")
        self.assertEqual(doc["motor_pending"], [])
        self.assertFalse(doc["sentinel"]["taint"]["tainted"])

    def test_presence_speak_allowed_by_standing_grant(self) -> None:
        doc = cam_inproc.route(sense="sense.audio.transcript", goal="hello")
        self.assertIn("motor.speak", doc["motor_plan"])
        self.assertEqual(doc["sentinel"]["decisions"]["motor.speak"]["authorizer"], "grant:perpetual:Aaron")

    def test_web_fetch_taints_plan_but_reads_still_allow(self) -> None:
        doc = cam_inproc.route(sense="sense.web.scholar", goal="scholar search")
        self.assertIn("motor.web_fetch", doc["motor_plan"])
        self.assertIn("motor.web_fetch", doc["sentinel"]["taint"]["sources"])
        self.assertEqual(doc["motor_pending"], [])

    def test_kill_denies_all(self) -> None:
        v = cs.evaluate(["motor.mesh", "motor.text"], switch_state={"switch.kill": "act"})
        self.assertEqual(v["allowed"], [])
        self.assertEqual(v["denied"], ["motor.mesh", "motor.text"])

    def test_unknown_motor_fails_closed(self) -> None:
        v = cs.evaluate(["motor.mystery"], switch_state={})
        self.assertEqual(v["decisions"]["motor.mystery"]["decision"], "ask")

    def test_standing_grant_needs_switch_act(self) -> None:
        v = cs.evaluate(["motor.text"], switch_state={"switch.outbound": "hold"})
        self.assertEqual(v["decisions"]["motor.text"]["decision"], "ask")

    def test_guardrail_write_offers_once_only(self) -> None:
        v = cs.evaluate(["motor.docs"], switch_state={}, paths=[str(ROOT / "AGENTS.md")])
        row = v["decisions"]["motor.docs"]
        self.assertEqual(row["decision"], "ask")
        self.assertEqual(row["grant_options"], ["once"])
        v2 = cs.evaluate(["motor.docs"], switch_state={}, paths=["docs/PERSONA.md"])
        self.assertEqual(v2["decisions"]["motor.docs"]["decision"], "allow")


class GrantTests(IsolatedRuntime):
    PLAN = ["motor.inkbox"]
    KW = dict(sense="sense.inkbox.event", pathway=["sense.inkbox.event"], switch_state={"switch.outbound": "act"})

    def test_only_aaron_grants(self) -> None:
        with self.assertRaises(PermissionError):
            cs.grant("motor.inkbox", "perpetual", by="Cline")
        with self.assertRaises(ValueError):
            cs.grant("motor.inkbox", "forever", by="Aaron")
        with self.assertRaises(ValueError):
            cs.grant("motor.inkbox", "task", by="Aaron")

    def test_session_grant_dies_with_session(self) -> None:
        sid = cs.current_session_id()
        cs.grant("motor.inkbox", "session", by="Aaron", covers_tainted=True)
        v = cs.evaluate(self.PLAN, task="x", session_id=sid, **self.KW)
        self.assertEqual(v["allowed"], ["motor.inkbox"])
        cs.new_session()
        v2 = cs.evaluate(self.PLAN, task="x", session_id=cs.current_session_id(), **self.KW)
        self.assertEqual(v2["pending"], ["motor.inkbox"])

    def test_once_grant_consumed_on_record(self) -> None:
        cs.grant("motor.inkbox", "once", by="Aaron", covers_tainted=True)
        v = cs.evaluate(self.PLAN, task="x", **self.KW)
        self.assertEqual(v["allowed"], ["motor.inkbox"])
        cs.record(v, sense="sense.inkbox.event", goal="x", day="2026-01-01")
        self.assertEqual(cs.load_grants(), [])
        self.assertEqual(cs.evaluate(self.PLAN, task="x", **self.KW)["pending"], ["motor.inkbox"])

    def test_revoke(self) -> None:
        g = cs.grant("motor.inkbox", "perpetual", by="Aaron", covers_tainted=True)
        self.assertEqual(cs.revoke(g["id"]), 1)
        self.assertEqual(cs.load_grants(), [])


class JournalTests(IsolatedRuntime):
    def test_sequence_monotonic_and_redacted(self) -> None:
        a = cj.append("proposed", {"note": "token=supersecretvalue"}, day="2026-01-02")
        b = cj.append("proposed", {"note": "Authorization: Bearer abcdefghijklmnopqrst"}, day="2026-01-02")
        c = cj.append("proposed", {"token": "shhh-very-secret", "nested": {"api_key": "k123456"}}, day="2026-01-02")
        self.assertEqual((a["sequence"], b["sequence"], c["sequence"]), (1, 2, 3))
        raw = cj.path_for("2026-01-02").read_text()
        self.assertNotIn("supersecretvalue", raw)
        self.assertNotIn("abcdefghijklmnopqrst", raw)
        self.assertNotIn("shhh-very-secret", raw)
        self.assertNotIn("k123456", raw)
        with self.assertRaises(ValueError):
            cj.append("bogus", {}, day="2026-01-02")

    def test_approval_chain_and_resume(self) -> None:
        v = cs.evaluate(["motor.text", "motor.mesh"], sense="sense.email.thread", pathway=["sense.email.thread"], switch_state={"switch.outbound": "act"}, task="reply")
        rec = cs.record(v, sense="sense.email.thread", goal="reply", day="2026-01-03")
        pid = rec["pending"][0]
        self.assertEqual([p["pending_id"] for p in cs.pending("2026-01-03")], [pid])
        res = cs.approve(pid, scope="task", by="Aaron", day="2026-01-03")
        self.assertEqual(res["grant"]["task"], "reply")
        self.assertTrue(res["grant"]["covers_tainted"])
        self.assertEqual(cs.pending("2026-01-03"), [])
        rows = cj.read("2026-01-03")
        kinds = [r["kind"] for r in rows]
        self.assertLess(kinds.index("decision_applied"), len(kinds) - 1 - kinds[::-1].index("side_effect_intent"))
        exp = cj.export("2026-01-03")
        self.assertEqual(exp["open_approvals"], [])
        self.assertEqual(len(exp["unconfirmed_intents"]), 2)
        cj.append("effect.terminal", {"motor": "motor.mesh", "idempotency_key": exp["unconfirmed_intents"][0], "outcome": "ok"}, day="2026-01-03")
        self.assertEqual(len(cj.export("2026-01-03")["unconfirmed_intents"]), 1)
        with self.assertRaises(KeyError):
            cs.deny(pid, by="Aaron", day="2026-01-03")

    def test_deny_closes_request(self) -> None:
        v = cs.evaluate(["motor.jobs"], sense="sense.careers.listing", pathway=["sense.careers.listing"], switch_state={"switch.careers_submit": "act"}, task="apply")
        rec = cs.record(v, sense="sense.careers.listing", goal="apply", day="2026-01-04")
        with self.assertRaises(PermissionError):
            cs.deny(rec["pending"][0], by="Cline", day="2026-01-04")
        cs.deny(rec["pending"][0], by="Aaron", day="2026-01-04")
        self.assertEqual(cs.pending("2026-01-04"), [])
        self.assertTrue(any("DENIED" in line for line in cj.ledger_lines(cj.read("2026-01-04"))))


class CliTests(unittest.TestCase):
    def test_cli_decide_json(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/cam-sentinel.py"), "decide", "--sense", "sense.careers.listing", "--goal", "watch roles", "--json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        doc = json.loads(p.stdout)
        self.assertIn("motor.jobs", doc["motor_pending"])

    def test_cli_rejects_non_aaron_grant(self) -> None:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/cam-sentinel.py"), "grant", "--motor", "motor.text", "--scope", "perpetual", "--by", "Cline"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(p.returncode, 2)
        self.assertIn("only Aaron", p.stderr)


if __name__ == "__main__":
    unittest.main()
