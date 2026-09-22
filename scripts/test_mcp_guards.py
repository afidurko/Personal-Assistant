#!/usr/bin/env python3
"""Guard tests for scripts/cam-mcp-server.py — the agent bus boundary.

Every agent (Cline, subagents, other Cam roles) reaches the swarm and the
connectors through this server, so this is where "nobody on the bus is
Aaron" has to hold. Each test drives the real server over stdio.

Run: python3 scripts/test_mcp_guards.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts/cam-mcp-server.py"
T0 = "2026-09-20T15:00:00Z"


class McpBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.env = {
            **os.environ,
            "CAM_SWARM_DIR": str(tmp / "swarm"),
            "INSTINCT_DATA_DIR": str(tmp / "instinct"),
            "INKBOX_INBOUND_DIR": str(tmp / "inbound"),
            "CAM_SWARM_SERVER_LINEAGE": str(tmp / "none.json"),
            "CAM_CALENDAR_ICS": "",
        }
        self.env.pop("CAM_SWITCH_KILL", None)

    def tearDown(self):
        self._tmp.cleanup()

    def call(self, name: str, arguments: dict | None = None):
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments or {}}}
        proc = subprocess.run([sys.executable, str(SERVER)], input=json.dumps(req) + "\n",
                              capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        msg = json.loads(proc.stdout.splitlines()[0])
        res = msg.get("result") or msg.get("error")
        if isinstance(res, dict) and "content" in res:
            text = res["content"][0]["text"]
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
        return res

    def tools(self) -> dict:
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        proc = subprocess.run([sys.executable, str(SERVER)], input=json.dumps(req) + "\n",
                              capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        return {t["name"]: t for t in json.loads(proc.stdout.splitlines()[0])["result"]["tools"]}


class SwarmBusGuards(McpBase):
    def test_x1_role_chief_refused(self):
        out = self.call("swarm_spawn", {"role": "chief"})
        self.assertFalse(out.get("ok"))

    def test_x1_no_child_gets_outbound_send(self):
        out = self.call("swarm_spawn", {"role": "errand-runner"})
        self.assertTrue(out["ok"])
        self.assertNotIn("outbound_send", out["agent"]["privileges"])
        out = self.call("swarm_spawn", {"role": "qa", "privileges": ["outbound_send"]})
        self.assertFalse(out.get("ok"))

    def test_x2_parent_human_aaron_refused(self):
        for parent in ("human.aaron", "human", "hum", "aaron"):
            out = self.call("swarm_spawn", {"role": "shadow", "parent": parent})
            self.assertFalse(out.get("ok"), parent)
        self.assertEqual(len(self.call("swarm_stats")["by_role"]), 1)  # only chief

    def test_x3_caller_human_aaron_refused(self):
        w = self.call("swarm_spawn", {"role": "watcher"})["agent"]["id"]
        act = self.call("swarm_assign", {"assignee": w, "task": "x"})["action"]["id"]
        for who in ("human.aaron", "human", "hum"):
            out = self.call("swarm_resolve", {"action": act, "status": "cancelled", "caller": who})
            self.assertFalse(out.get("ok"), who)
        out = self.call("swarm_assign", {"assignee": w, "task": "y", "caller": "human.aaron"})
        self.assertFalse(out.get("ok"))

    def test_x10_now_is_ignored_on_write_ops(self):
        out = self.call("swarm_spawn", {"role": "qa", "now": "2001-01-01T00:00:00Z"})
        self.assertTrue(out["ok"])
        self.assertTrue(out["agent"]["created"].startswith("20") and not out["agent"]["created"].startswith("2001"))

    def test_kill_env_blocks_spawn_over_mcp(self):
        self.env["CAM_SWITCH_KILL"] = "act"
        out = self.call("swarm_spawn", {"role": "qa"})
        self.assertFalse(out.get("ok"))

    def test_no_resume_or_kill_or_terminate_tool_exposed(self):
        names = set(self.tools())
        for banned in ("swarm_resume", "swarm_kill", "swarm_terminate", "instinct_outbox_approve"):
            self.assertNotIn(banned, names)


class ConnectorGuards(McpBase):
    def test_x4_calendar_sync_ignores_agent_urls(self):
        out = self.call("calendar_sync", {"ics": ["http://127.0.0.1:9/exfil?x=1"]})
        self.assertTrue(out["ok"])
        self.assertEqual(out["sources"], 0)
        self.assertTrue(out.get("ignored_ics_argument"))
        self.assertNotIn("ics", self.tools()["calendar_sync"]["inputSchema"]["properties"])

    def test_instinct_delegate_parent_human_refused(self):
        subprocess.run([sys.executable, "scripts/instinct.py", "--now", T0, "job", "add", "x"],
                       capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        job = json.loads(subprocess.run([sys.executable, "scripts/instinct.py", "job", "list"],
                                        capture_output=True, text=True, env=self.env, cwd=str(ROOT)).stdout)[0]["id"]
        out = self.call("instinct_delegate", {"job": job, "parent": "human.aaron"})
        self.assertFalse(out.get("ok"))
        out = self.call("instinct_delegate", {"job": job})
        self.assertTrue(out["ok"])
        self.assertEqual(out["level"], 2)


class PrincipalGuards(McpBase):
    """Charter P3 / P8 / P10 at the bus: one server process, one person."""

    def setUp(self):
        super().setUp()
        tmp = Path(self._tmp.name)
        self.env["CAM_PRINCIPALS_ROOT"] = str(tmp / "principals")
        self.env["INSTINCT_NO_CACHE_MIRROR"] = "1"
        self.env.pop("CAM_PRINCIPAL", None)

    def enroll(self, pid: str = "dana"):
        proc = subprocess.run([sys.executable, "scripts/cam_privacy.py", "--aaron", "principals", "add", pid,
                               "--label", "Dana"], capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.env["CAM_PRINCIPAL"] = pid
        for k in ("CAM_SWARM_DIR", "INSTINCT_DATA_DIR", "INKBOX_INBOUND_DIR"):
            self.env.pop(k, None)

    def test_owner_sees_everything_and_privacy_tools(self):
        names = set(self.tools())
        for t in ("privacy_status", "privacy_redact", "privacy_audit", "vault_search", "memorybear_read"):
            self.assertIn(t, names)
        out = self.call("privacy_status")
        self.assertEqual(out["principal"], "aaron")
        self.assertIn("P1: No personal class in any mesh distillate", out["charter"]["invariants"])

    def test_guest_tool_list_is_the_allowlist(self):
        self.enroll()
        names = set(self.tools())
        for hidden in ("vault_search", "mesh_search", "mesh_put", "memorybear_read", "memorybear_write",
                       "list_workspaces", "choose_workspace", "ticket_list", "needs_attention", "calendar_sync",
                       "connectors_list", "privacy_audit", "instinct_workspaces", "instinct_dispatch", "loop_run"):
            self.assertNotIn(hidden, names, hidden)
        for shown in ("privacy_status", "privacy_redact", "instinct_scan", "instinct_report", "swarm_spawn",
                      "inkbox_inbound", "public_apis_search"):
            self.assertIn(shown, names, shown)

    def test_guest_call_to_hidden_tool_refused_by_name(self):
        self.enroll()
        for name in ("vault_search", "memorybear_read", "mesh_put", "list_workspaces", "calendar_sync", "privacy_audit"):
            out = self.call(name, {"query": "aaron", "note": "x", "message": "x"})
            self.assertFalse(out.get("ok"), name)
            self.assertIn("not available to principal 'dana'", out["error"])

    def test_guest_instinct_and_swarm_stay_in_guest_root(self):
        # owner state first
        subprocess.run([sys.executable, "scripts/instinct.py", "--now", T0, "job", "add", "Aaron private job"],
                       capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        self.assertEqual(self.call("swarm_spawn", {"role": "watcher"})["agent"]["level"], 2)
        self.enroll()
        rep = self.call("instinct_report")
        self.assertEqual(rep["jobs"]["open"], 0)
        self.assertNotIn("Aaron private job", json.dumps(rep))
        self.assertEqual(self.call("swarm_spawn", {"role": "watcher"})["agent"]["level"], 2)
        stats = self.call("swarm_stats")
        self.assertEqual(stats["principal"], "dana")
        self.assertEqual(stats["agents_total"], 2)  # this guest's chief + watcher; not the owner's
        root = Path(self.env["CAM_PRINCIPALS_ROOT"]) / "dana"
        self.assertTrue((root / "swarm" / "lineage.json").exists())
        owner = json.loads((Path(self._tmp.name) / "swarm" / "lineage.json").read_text())
        self.assertEqual(len(owner["agents"]), 3)  # aaron + chief + the owner's one watcher — untouched
        self.assertEqual(self.call("privacy_status")["principal"], "dana")

    def test_guest_env_override_onto_owner_dir_refused(self):
        self.enroll()
        self.env["INSTINCT_DATA_DIR"] = str(Path(self._tmp.name) / "instinct")  # the owner's dir
        out = self.call("instinct_report")
        self.assertFalse(out.get("ok"))
        self.assertIn("outside principal", json.dumps(out))

    def test_unenrolled_guest_server_refuses_to_start(self):
        self.env["CAM_PRINCIPAL"] = "nobody"
        proc = subprocess.run([sys.executable, str(SERVER)], input="", capture_output=True, text=True,
                              env=self.env, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not enrolled", proc.stderr)

    def test_mesh_put_redacts_and_refuses_secrets(self):
        # write to a scratch copy of the cache so the tracked file is untouched
        import shutil
        scratch = Path(self._tmp.name) / "cache.json"
        shutil.copy(ROOT / "identity/persistence/cline-session-cache.json", scratch)
        code = ("import sys, json; sys.argv=['x']; sys.path.insert(0, 'scripts'); "
                "import cam_workspaces as cw; from pathlib import Path; cw.CLINE_CACHE = Path(%r); "
                "import importlib.util; spec = importlib.util.spec_from_file_location('srv', 'scripts/cam-mcp-server.py'); "
                "srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv); srv.cw.CLINE_CACHE = Path(%r); "
                "print(json.dumps(srv.call_tool('mesh_put', {'note': 'call 512-555-0134 re dana@example.com'}))); "
                "print(json.dumps(srv.call_tool('mesh_put', {'note': 'token sk_live_abcdefghijklmnopqrstuv'})))"
                ) % (str(scratch), str(scratch))
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        lines = [l for l in proc.stdout.splitlines() if l.startswith("{")]
        self.assertEqual(len(lines), 1, proc.stdout + proc.stderr)  # second call raised (secret refused)
        first = json.loads(lines[0])
        self.assertTrue(first["ok"] and first["redacted"])
        notes = json.loads(scratch.read_text())["notes"]
        self.assertEqual(notes[-1]["text"], "call [phone] re [email]")
        self.assertIn("deny", proc.stderr)

    def test_privacy_refusal_does_not_kill_the_session(self):
        # A charter refusal must come back as an isError result and the
        # server must keep answering — otherwise any agent could end the
        # whole MCP session with one secret-bearing note.
        import shutil
        scratch = Path(self._tmp.name) / "cache.json"
        shutil.copy(ROOT / "identity/persistence/cline-session-cache.json", scratch)
        code = ("import sys, json, io; sys.argv=['x']; sys.path.insert(0, 'scripts'); "
                "import cam_workspaces as cw; from pathlib import Path; cw.CLINE_CACHE = Path(%r); "
                "import importlib.util; spec = importlib.util.spec_from_file_location('srv', 'scripts/cam-mcp-server.py'); "
                "srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv); srv.cw.CLINE_CACHE = Path(%r); "
                "sys.stdin = io.StringIO(json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'mesh_put','arguments':{'note':'token sk_live_abcdefghijklmnopqrstuv'}}}) + '\\n' "
                "+ json.dumps({'jsonrpc':'2.0','id':2,'method':'ping','params':{}}) + '\\n'); "
                "raise SystemExit(srv.main())") % (str(scratch), str(scratch))
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [json.loads(l) for l in proc.stdout.splitlines() if l.startswith("{")]
        self.assertEqual([m["id"] for m in lines], [1, 2])
        first = lines[0]["result"]
        self.assertTrue(first["isError"])
        body = json.loads(first["content"][0]["text"])
        self.assertEqual(body["refused"], "privacy")
        self.assertIn("deny", body["error"])
        notes = json.loads(scratch.read_text())["notes"]
        self.assertFalse(any("sk_live" in (n.get("text") or "") for n in notes))
        self.assertEqual(lines[1]["result"], {})

    def test_instinct_scan_write_ignores_now(self):
        subprocess.run([sys.executable, "scripts/instinct.py", "--now", "2026-01-01T00:00:00Z", "job", "add", "old"],
                       capture_output=True, text=True, env=self.env, cwd=str(ROOT))
        out = self.call("instinct_scan", {"write": True, "now": "2001-01-01T00:00:00Z"})
        self.assertTrue(out["ok"])
        for d in out.get("drafts") or []:
            self.assertFalse(Path(d).name.startswith("2001"))
        # read-only scan may still take a clock override
        out = self.call("instinct_scan", {"now": "2001-01-01T00:00:00Z"})
        self.assertEqual(out["scanned_at"][:4], "2001")


if __name__ == "__main__":
    unittest.main(verbosity=1)
