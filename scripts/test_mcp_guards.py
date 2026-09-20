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


if __name__ == "__main__":
    unittest.main(verbosity=1)
