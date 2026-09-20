#!/usr/bin/env python3
"""Unit tests for the Cam swarm runtime (scripts/cam_swarm.py). Offline, deterministic.

Run: python3 scripts/test_cam_swarm.py
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
import cam_swarm as swarm  # noqa: E402

T0 = "2026-09-20T15:00:00Z"


def run(*argv: str):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = swarm.main(list(argv))
        except SystemExit as exc:  # policy refusals surface as SystemExit(message)
            return {"ok": False, "error": str(exc), "_exit": 1}
    out = buf.getvalue()
    if out.lstrip().startswith(("{", "[")):
        parsed = json.loads(out)
        if isinstance(parsed, dict):
            parsed["_exit"] = code
        return parsed
    return {"text": out, "_exit": code}


class SwarmBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["CAM_SWARM_DIR"] = self._tmp.name
        os.environ["CAM_SWARM_MESH_OUT"] = str(Path(self._tmp.name) / "mesh.json")
        os.environ["CAM_SWARM_SERVER_LINEAGE"] = str(Path(self._tmp.name) / "swarm-lineage.json")
        os.environ.pop("CAM_SWITCH_KILL", None)

    def tearDown(self):
        for k in ("CAM_SWARM_DIR", "CAM_SWARM_MESH_OUT", "CAM_SWITCH_KILL", "CAM_SWARM_SERVER_LINEAGE"):
            os.environ.pop(k, None)
        self._tmp.cleanup()

    def spawn(self, role: str, parent: str = "chief", **kw) -> dict:
        argv = ["--now", T0, "spawn", role, "--parent", parent]
        for key, val in kw.items():
            if key == "privileges":
                for p in val:
                    argv += ["--privilege", p]
            else:
                argv += [f"--{key}", val]
        out = run(*argv)
        self.assertTrue(out.get("ok"), out)
        return out["agent"]


class SeedAndLevelsTests(SwarmBase):
    def test_seed_has_aaron_l0_and_chief_l1(self):
        agents = run("--now", T0, "agents", "--all")
        by_id = {a["id"]: a for a in agents}
        self.assertEqual(by_id["human.aaron"]["level"], 0)
        self.assertEqual(by_id["human.aaron"]["kind"], "human")
        self.assertEqual(by_id["chief"]["level"], 1)
        self.assertEqual(by_id["chief"]["parent"], "human.aaron")

    def test_child_is_parent_level_plus_one(self):
        a = self.spawn("task-executor")
        b = self.spawn("qa", parent=a["id"])
        c = self.spawn("watcher", parent=b["id"])
        self.assertEqual((a["level"], b["level"], c["level"]), (2, 3, 4))

    def test_unlimited_depth_and_count(self):
        parent = "chief"
        for _ in range(12):
            parent = self.spawn("task-executor", parent=parent)["id"]
        for _ in range(15):
            self.spawn("watcher")
        stats = run("stats")
        self.assertEqual(stats["max_level"], 13)
        self.assertEqual(stats["agents_active"], 1 + 12 + 15)
        self.assertTrue(stats["unlimited_spawn"])
        self.assertTrue(run("doctor")["ok"])


class PrivilegeTests(SwarmBase):
    def test_child_privileges_subset_of_parent(self):
        lead = self.spawn("follow-through-lead")
        child = self.spawn("negotiator", parent=lead["id"])
        self.assertTrue(set(child["privileges"]) <= set(lead["privileges"]))
        # negotiator default has no terminate_lineage / broadcast: the role default is respected
        self.assertNotIn("broadcast", child["privileges"])

    def test_role_default_clipped_by_parent(self):
        # watcher has no outbound_draft; its child errand-runner (which normally has it) must not gain it
        watcher = self.spawn("watcher")
        self.assertNotIn("outbound_draft", watcher["privileges"])
        runner = self.spawn("errand-runner", parent=watcher["id"])
        self.assertNotIn("outbound_draft", runner["privileges"])

    def test_explicit_escalation_refused(self):
        watcher = self.spawn("watcher")
        out = run("--now", T0, "spawn", "qa", "--parent", watcher["id"], "--privilege", "outbound_draft")
        self.assertEqual(out["_exit"], 1)

    def test_aaron_only_never_granted(self):
        for priv in ("kill_master", "task_giver", "cam_enhance_apply"):
            out = run("--now", T0, "spawn", "qa", "--privilege", priv)
            self.assertEqual(out["_exit"], 1, priv)
        agents = run("agents", "--all")
        for a in agents:
            if a["kind"] == "agent":
                self.assertFalse(set(a["privileges"]) & swarm.aaron_only(), a["id"])

    def test_outbound_send_not_in_any_subagent_role_default(self):
        # chief may hold outbound_send (switch.outbound decides live use); no specialist default does
        defaults = swarm.privileges_config()["role_defaults"]
        for role, entry in defaults.items():
            if role == "chief":
                continue
            self.assertNotIn("outbound_send", entry["privileges"], role)
            self.assertNotIn("careers_submit", entry["privileges"], role)

    def test_unknown_role_falls_back_to_default_subagent(self):
        child = self.spawn("some-ephemeral-mandate")
        default = set(swarm.role_default_privileges("default_subagent"))
        self.assertTrue(set(child["privileges"]) <= default)


class ActionTests(SwarmBase):
    def test_assign_resolve_notifies_parent(self):
        worker = self.spawn("task-executor")
        act = run("--now", T0, "assign", worker["id"], "run tests", "--job", "job:abc")
        self.assertEqual(act["action"]["status"], "open")
        res = run("--now", T0, "resolve", act["action"]["id"], "done", "--caller", worker["id"],
                  "--distillate", "48/48 green")
        self.assertEqual(res["action"]["status"], "done")
        ledger = swarm.load_ledger()
        notes = [m for m in ledger["commute"] if m["kind"] == "send_message" and m["to"] == "chief"]
        self.assertEqual(len(notes), 1)

    def test_stranger_cannot_resolve(self):
        worker = self.spawn("task-executor")
        other = self.spawn("qa")
        act = run("--now", T0, "assign", worker["id"], "run tests")
        out = run("--now", T0, "resolve", act["action"]["id"], "done", "--caller", other["id"])
        self.assertEqual(out["_exit"], 1)

    def test_ancestor_can_resolve(self):
        lead = self.spawn("follow-through-lead")
        worker = self.spawn("errand-runner", parent=lead["id"])
        act = run("--now", T0, "assign", worker["id"], "compare quotes", "--caller", lead["id"])
        out = run("--now", T0, "resolve", act["action"]["id"], "blocked", "--caller", lead["id"])
        self.assertEqual(out["action"]["status"], "blocked")

    def test_bad_status_rejected(self):
        worker = self.spawn("task-executor")
        act = run("--now", T0, "assign", worker["id"], "x")
        with self.assertRaises(SystemExit):
            swarm.resolve(swarm.load_ledger(), "chief", act["action"]["id"], "open", swarm.now_utc(T0))


class BroadcastTests(SwarmBase):
    def test_team_channel_fanout_excludes_sender_and_other_teams(self):
        lead = self.spawn("follow-through-lead", team="team.follow-through")
        w1 = self.spawn("watcher", parent=lead["id"], team="team.follow-through")
        self.spawn("task-executor", team="team.capability")
        out = run("--now", T0, "broadcast", "team.follow-through", "standup", "--sender", lead["id"])
        self.assertEqual(out["broadcast"]["recipients"], [w1["id"]])

    def test_unknown_channel_refused(self):
        out = run("--now", T0, "broadcast", "team.nope", "hi")
        self.assertEqual(out["_exit"], 1)

    def test_mesh_all_reaches_everyone_active(self):
        a = self.spawn("qa")
        b = self.spawn("watcher")
        out = run("--now", T0, "broadcast", "mesh.all", "hello")
        self.assertEqual(set(out["broadcast"]["recipients"]), {a["id"], b["id"]})


class TerminateAndKillTests(SwarmBase):
    def test_terminate_cascades_and_cancels_open_actions(self):
        lead = self.spawn("follow-through-lead")
        w = self.spawn("watcher", parent=lead["id"])
        act = run("--now", T0, "assign", w["id"], "watch price")
        out = run("--now", T0, "terminate", lead["id"], "--reason", "done")
        self.assertEqual(set(out["terminated"]), {lead["id"], w["id"]})
        actions = run("actions", "--all")
        self.assertEqual([a["status"] for a in actions if a["id"] == act["action"]["id"]], ["cancelled"])
        self.assertTrue(run("doctor")["ok"])

    def test_non_ancestor_cannot_terminate(self):
        a = self.spawn("qa")
        b = self.spawn("watcher")
        out = run("--now", T0, "terminate", b["id"], "--caller", a["id"])
        self.assertEqual(out["_exit"], 1)

    def test_only_aaron_terminates_chief(self):
        a = self.spawn("follow-through-lead")
        out = run("--now", T0, "terminate", "chief", "--caller", a["id"])
        self.assertEqual(out["_exit"], 1)
        out = run("--now", T0, "terminate", "chief", "--caller", "human.aaron", "--reason", "kill")
        self.assertEqual(out["_exit"], 1)  # claiming to be Aaron without --aaron is refused
        out = run("--now", T0, "--aaron", "terminate", "chief", "--caller", "human.aaron", "--reason", "kill")
        self.assertIn("chief", out["terminated"])

    def test_kill_silences_spawn_and_assign_but_keeps_records(self):
        w = self.spawn("watcher")
        run("--now", T0, "kill", "--reason", "pause")
        self.assertEqual(run("--now", T0, "spawn", "qa")["_exit"], 1)
        self.assertEqual(run("--now", T0, "assign", w["id"], "x")["_exit"], 1)
        self.assertTrue(run("stats")["kill_active"])
        self.assertEqual(len(run("agents")), 3)  # aaron + chief + watcher retained
        self.assertEqual(run("--now", T0, "resume")["_exit"], 1)  # resume needs --aaron
        run("--now", T0, "--aaron", "resume")
        self.assertTrue(run("--now", T0, "spawn", "qa")["ok"])

    def test_env_kill_honoured(self):
        os.environ["CAM_SWITCH_KILL"] = "act"
        self.assertEqual(run("--now", T0, "spawn", "qa")["_exit"], 1)


class DoctorAndDistillTests(SwarmBase):
    def test_doctor_detects_tampered_escalation(self):
        parent = self.spawn("watcher")  # no outbound_draft
        w = self.spawn("watcher", parent=parent["id"])
        ledger = swarm.load_ledger()
        ledger["agents"][w["id"]]["privileges"].append("outbound_draft")
        ledger["agents"][w["id"]]["level"] = 7
        swarm.save_ledger(ledger)
        out = run("doctor")
        self.assertFalse(out["ok"])
        self.assertTrue(any("escalates" in p for p in out["problems"]))
        self.assertTrue(any("level" in p for p in out["problems"]))

    def test_distill_is_counts_only(self):
        self.spawn("negotiator", mandate="Negotiate Aaron's Comcast bill — acct 12345")
        run("--now", T0, "assign", "chief", "call Comcast about acct 12345")
        out = run("--now", T0, "distill")
        doc = json.loads(Path(os.environ["CAM_SWARM_MESH_OUT"]).read_text())
        blob = json.dumps(doc)
        self.assertNotIn("Comcast", blob)
        self.assertNotIn("12345", blob)
        self.assertEqual(doc["stats"]["agents_active"], 2)
        self.assertTrue(out["ok"])

    def test_corrupt_lineage_is_clean_error(self):
        swarm.lineage_path().parent.mkdir(parents=True, exist_ok=True)
        swarm.lineage_path().write_text("{not json")
        with self.assertRaises(SystemExit):
            swarm.load_ledger()

    def test_server_lineage_cross_checked_read_only(self):
        srv = Path(os.environ["CAM_SWARM_SERVER_LINEAGE"])
        srv.write_text(json.dumps({
            "version": 1, "soleOperator": "Aaron", "updatedAt": T0, "events": [],
            "agents": [
                {"id": "agent.chief", "role": "chief", "level": 1, "parentId": None, "status": "active",
                 "privileges": ["spawn_subagents"], "lineage": [], "createdAt": T0, "workspaceIds": []},
                {"id": "w1", "role": "qa", "level": 2, "parentId": "agent.chief", "status": "active",
                 "privileges": ["kill_master"], "lineage": ["agent.chief"], "createdAt": T0, "workspaceIds": []},
            ]}))
        before = srv.read_text()
        out = run("doctor")
        self.assertFalse(out["ok"])
        self.assertTrue(any("server lineage" in p for p in out["problems"]))
        self.assertEqual(out["stats"]["server_runtime"]["agents_active"], 2)
        self.assertEqual(srv.read_text(), before)  # never written

    def test_tree_renders_hierarchy(self):
        a = self.spawn("follow-through-lead")
        self.spawn("watcher", parent=a["id"], job="job:zz")
        text = run("tree")["text"]
        self.assertIn("human.aaron (aaron, L0)", text)
        self.assertIn("    " + a["id"], text)
        self.assertIn("job:zz", text)


class ExploitRegressionTests(SwarmBase):
    """Each test replays an attack from the round-5 red-team pass
    (docs/SWARM_CONNECTORS_SECURITY_REVIEW.md) and asserts it now fails."""

    def test_x1_role_chief_cannot_inherit_outbound_send(self):
        out = run("--now", T0, "spawn", "chief")
        self.assertEqual(out["_exit"], 1)
        # even a legit role under chief never receives chief-only privileges
        child = self.spawn("errand-runner")
        self.assertNotIn("outbound_send", child["privileges"])
        self.assertNotIn("careers_submit", child["privileges"])
        out = run("--now", T0, "spawn", "qa", "--privilege", "outbound_send")
        self.assertEqual(out["_exit"], 1)

    def test_x2_agents_cannot_spawn_under_human_root(self):
        out = run("--now", T0, "spawn", "shadow-chief", "--parent", "human.aaron")
        self.assertEqual(out["_exit"], 1)
        self.assertIn("only Aaron", out["error"])
        ok = run("--now", T0, "--aaron", "spawn", "specialist", "--parent", "human.aaron")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["agent"]["level"], 1)
        self.assertNotIn("outbound_send", ok["agent"]["privileges"])

    def test_x3_prefix_cannot_impersonate_aaron_or_chief(self):
        w = self.spawn("watcher")
        act = run("--now", T0, "assign", w["id"], "x")["action"]["id"]
        for who in ("hum", "human", "human.aaron", "chi", "aaron"):
            out = run("--now", T0, "resolve", act, "failed", "--caller", who)
            self.assertEqual(out["_exit"], 1, who)
        out = run("--now", T0, "terminate", "chief", "--caller", "human")
        self.assertEqual(out["_exit"], 1)
        self.assertEqual(run("agents")[1]["status"], "active")  # chief untouched
        # prefix convenience still works for spawned role-hex ids
        short = w["id"][: len(w["id"]) - 3]
        self.assertTrue(run("--now", T0, "assign", short, "y")["ok"])

    def test_x5_cycle_in_tampered_ledger_terminates_and_is_reported(self):
        a = self.spawn("qa")
        b = self.spawn("qa", parent=a["id"])
        ledger = swarm.load_ledger()
        ledger["agents"][a["id"]]["parent"] = b["id"]
        swarm.save_ledger(ledger)
        out = run("--now", T0, "terminate", b["id"])  # must return, not hang
        self.assertIn("_exit", out)
        doc = run("doctor")
        self.assertFalse(doc["ok"])
        self.assertTrue(any("lineage cycle" in p for p in doc["problems"]))

    def test_x8_reserved_and_malformed_roles_refused(self):
        for role in ("chief", "aaron", "human.aaron", "Human", "a", "x" * 40, "qa;rm", "chi ef"):
            self.assertEqual(run("--now", T0, "spawn", role)["_exit"], 1, role)
        self.spawn("chie")  # legal role; must not shadow `chief` lookups
        self.assertEqual(run("--now", T0, "assign", "chie", "x")["_exit"], 1)  # no dash → no prefix match
        self.assertTrue(run("--now", T0, "assign", "chief", "x")["ok"])

    def test_doctor_flags_chief_only_privilege_on_specialist(self):
        w = self.spawn("watcher")
        ledger = swarm.load_ledger()
        ledger["agents"][w["id"]]["privileges"].append("outbound_send")
        swarm.save_ledger(ledger)
        doc = run("doctor")
        self.assertTrue(any("chief-only" in p for p in doc["problems"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
