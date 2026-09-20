#!/usr/bin/env python3
"""Tests for the Cam Live stack: brain, messages, teams, vision, live server."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cam_brain
import cam_messages
import cam_teams
import cam_vision


class TestSafeMath(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(cam_brain.safe_math("2 + 2 * 10"), 22.0)
        self.assertEqual(cam_brain.safe_math("(17 * 4) + 12 / 3"), 72.0)
        self.assertEqual(cam_brain.safe_math("sqrt(144)"), 12.0)

    def test_rejects_code(self) -> None:
        self.assertIsNone(cam_brain.safe_math("__import__('os').system('id')"))
        self.assertIsNone(cam_brain.safe_math("open('/etc/passwd')"))
        self.assertIsNone(cam_brain.safe_math("hello world"))


class TestParseDue(unittest.TestCase):
    def test_relative(self) -> None:
        now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        due = cam_brain.parse_due("remind me to stretch in 20 minutes", now)
        self.assertEqual(due, now + timedelta(minutes=20))

    def test_at_pm(self) -> None:
        now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        due = cam_brain.parse_due("remind me to call mom at 5pm", now)
        self.assertEqual((due.hour, due.minute), (17, 0))

    def test_tomorrow(self) -> None:
        now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        due = cam_brain.parse_due("remind me tomorrow at 9am to file taxes", now)
        self.assertEqual((due.day, due.hour), (21, 9))


class TestMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = cam_brain.Memory(Path(self.tmp.name) / "mem.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_remember_recall_forget_persist(self) -> None:
        self.mem.remember("my dentist appointment is Tuesday at 3pm")
        self.mem.remember("the garage code is 4471")
        hits = self.mem.recall("when is my dentist appointment?")
        self.assertTrue(hits and "dentist" in hits[0]["text"])
        # persistence across instances
        mem2 = cam_brain.Memory(self.mem.path)
        self.assertEqual(len(mem2.facts), 2)
        removed = mem2.forget("garage code")
        self.assertEqual(removed, 1)


class TestBrain(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = cam_brain.Memory(Path(self.tmp.name) / "mem.json")
        self.reminders: list = []
        self.tasks: list = []
        self.vision_snap: dict | None = None
        self.brain = cam_brain.CamBrain(
            memory=self.mem,
            task_dispatch=lambda g: (self.tasks.append(g) or
                                     {"id": "t1", "team": "team.research",
                                      "team_name": "Research Team", "subtask_count": 4}),
            reminder_create=lambda what, due: (self.reminders.append((what, due)) or
                                               {"id": "r1", "due": due.isoformat()}),
            vision_latest=lambda: self.vision_snap,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_remember_and_recall_turns(self) -> None:
        t1 = self.brain.respond("remember that my parking spot is level 3 row F")
        self.assertIn("remember", t1["cam"].lower())
        t2 = self.brain.respond("do you remember my parking spot?")
        self.assertIn("level 3 row F", t2["cam"])

    def test_math_turn(self) -> None:
        t = self.brain.respond("what is 17 * 4 + 12?")
        self.assertIn("80", t["cam"])

    def test_reminder_turn(self) -> None:
        t = self.brain.respond("remind me to take out the trash in 2 hours")
        self.assertIn("Reminder set", t["cam"])
        self.assertEqual(len(self.reminders), 1)
        self.assertIn("take out the trash", self.reminders[0][0])

    def test_task_dispatch_turn(self) -> None:
        t = self.brain.respond("task: research small language models for the home lab")
        self.assertTrue(self.tasks)
        self.assertIn("subagents", t["cam"])

    def test_vision_query(self) -> None:
        t = self.brain.respond("what do you see?")
        self.assertIn("Camera", t["cam"])
        self.vision_snap = {"source": "cocossd", "objects": [
            {"label": "cup", "score": 0.9}, {"label": "laptop", "score": 0.8}]}
        t2 = self.brain.respond("what do you see?")
        self.assertIn("cup", t2["cam"])
        self.assertIn("laptop", t2["cam"])

    def test_never_empty_reply(self) -> None:
        for text in ("", "hello", "what's the meaning of my week",
                     "status", "what time is it"):
            t = self.brain.respond(text)
            self.assertTrue(t["cam"] and len(t["cam"]) > 4, text)


class TestMessages(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.mc = cam_messages.MessageCenter(
            inbox_path=base / "inbox.jsonl", reminders_path=base / "rem.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_send_list_read(self) -> None:
        self.mc.send("Test", "hello Aaron")
        self.assertEqual(self.mc.unread_count(), 1)
        self.assertEqual(self.mc.mark_read(), 1)
        self.assertEqual(self.mc.unread_count(), 0)

    def test_reminder_fires_as_message(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(seconds=5)
        self.mc.add_reminder("drink water", past)
        fired = self.mc.fire_due()
        self.assertEqual(len(fired), 1)
        msgs = self.mc.list()
        self.assertTrue(any(m["kind"] == "reminder" and "drink water" in m["body"] for m in msgs))
        # does not double-fire
        self.assertEqual(self.mc.fire_due(), [])

    def test_outbound_disabled_by_default(self) -> None:
        cfg = cam_messages.outbound_config()
        self.assertFalse(cfg["enabled"])


class TestTeams(unittest.TestCase):
    def test_pick_team(self) -> None:
        t = cam_teams.pick_team("research new agent papers")
        self.assertEqual(t["id"], "team.research")
        t = cam_teams.pick_team("draft a summary message")
        self.assertEqual(t["id"], "team.comms")

    def test_dispatch_runs_subagents_in_parallel(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        mem = cam_brain.Memory(Path(tmp.name) / "mem.json")
        mem.remember("Aaron likes espresso in the morning")
        notes: list = []
        orch = cam_teams.TeamOrchestrator(memory=mem, notify=notes.append)
        task = orch.dispatch("research what notes exist about espresso", wait=True)
        self.assertEqual(task["status"], "done")
        self.assertGreaterEqual(len(task["subtasks"]), 2)
        self.assertTrue(all(s["status"] in {"done", "failed"} for s in task["subtasks"]))
        # memory scout found the fact
        mem_sub = next(s for s in task["subtasks"] if s["agent"] == "memory-scout")
        self.assertIn("espresso", " ".join(mem_sub["findings"]))
        self.assertTrue(task["result"])
        self.assertEqual(len(notes), 1)
        self.assertIn("Task done", notes[0]["subject"])
        tmp.cleanup()


class TestVision(unittest.TestCase):
    @staticmethod
    def synthetic_frame(w: int = 80, h: int = 60) -> bytes:
        """Gray background with a red square and a blue tall bar."""
        import numpy as np
        arr = np.full((h, w, 4), 128, dtype=np.uint8)
        arr[:, :, 3] = 255
        arr[10:30, 10:30, 0] = 220; arr[10:30, 10:30, 1] = 30; arr[10:30, 10:30, 2] = 30
        arr[15:55, 55:65, 0] = 30; arr[15:55, 55:65, 1] = 60; arr[15:55, 55:65, 2] = 220
        return arr.tobytes()

    def test_identifies_colored_objects(self) -> None:
        raw = self.synthetic_frame()
        out = cam_vision.analyze_rgba(raw, 80, 60)
        self.assertTrue(out["ok"], out)
        labels = " ".join(o["label"] for o in out["objects"])
        self.assertIn("red", labels)
        self.assertIn("blue", labels)
        self.assertGreaterEqual(len(out["objects"]), 2)

    def test_b64_roundtrip_and_state(self) -> None:
        raw = self.synthetic_frame()
        out = cam_vision.analyze_rgba_b64(base64.b64encode(raw).decode(), 80, 60)
        self.assertTrue(out["ok"])
        vs = cam_vision.VisionState()
        vs.ingest_frame_analysis(out)
        self.assertTrue(vs.latest()["objects"])
        vs.ingest_detections([{"label": "cup", "score": 0.91}])
        self.assertEqual(vs.latest()["objects"][0]["label"], "cup")

    def test_bad_input(self) -> None:
        self.assertFalse(cam_vision.analyze_rgba(b"xx", 10, 10)["ok"])
        self.assertFalse(cam_vision.analyze_rgba_b64("!!!", 10, 10)["ok"])


class TestLiveServerHTTP(unittest.TestCase):
    """Boot the real server on an ephemeral port and drive the API."""

    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "scripts" / "cam-live-server.py"
        spec = importlib.util.spec_from_file_location("cam_live_server", path)
        assert spec and spec.loader
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        from http.server import ThreadingHTTPServer
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), cls.mod.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
            return json.loads(r.read().decode())

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    def test_state_and_ui(self) -> None:
        st = self._get("/api/state")
        self.assertTrue(st["ok"])
        self.assertIn("brain", st)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10) as r:
            html = r.read().decode()
        self.assertIn("Cam · Live Assistant", html)

    def test_chat_mic_accepted_without_enrollment(self) -> None:
        turn = self._post("/api/chat", {"text": "hello cam", "source": "mic"})
        self.assertTrue(turn["accepted"])
        self.assertEqual(turn["gate"]["mode"], "open_mic")
        self.assertTrue(turn["cam"])

    def test_chat_memory_flow(self) -> None:
        self._post("/api/chat", {"text": "remember that my wifi password is sunset42"})
        turn = self._post("/api/chat", {"text": "do you remember my wifi password?"})
        self.assertIn("sunset42", turn["cam"])

    def test_task_via_api_completes(self) -> None:
        doc = self._post("/api/tasks", {"goal": "audit runtime stores"})
        task_id = doc["task"]["id"]
        for _ in range(60):
            time.sleep(0.5)
            t = self._get(f"/api/tasks/{task_id}")["task"]
            if t["status"] in {"done", "failed"}:
                break
        self.assertEqual(t["status"], "done")
        self.assertTrue(t["result"])

    def test_vision_frame_endpoint(self) -> None:
        raw = TestVision.synthetic_frame()
        out = self._post("/api/vision/frame", {
            "rgba_b64": base64.b64encode(raw).decode(), "width": 80, "height": 60})
        self.assertTrue(out["ok"])
        latest = self._get("/api/vision/latest")["latest"]
        self.assertTrue(latest["objects"])
        turn = self._post("/api/chat", {"text": "what do you see?"})
        self.assertIn("object", turn["cam"])

    def test_reminder_end_to_end(self) -> None:
        turn = self._post("/api/chat", {"text": "remind me to check the oven in 1 second"})
        self.assertIn("Reminder set", turn["cam"])
        self.mod.APP.messages.fire_due()  # heartbeat would do this
        time.sleep(1.2)
        self.mod.APP.messages.fire_due()
        msgs = self._get("/api/messages")["messages"]
        self.assertTrue(any(m["kind"] == "reminder" and "oven" in m["body"] for m in msgs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
