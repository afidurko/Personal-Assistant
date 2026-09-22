#!/usr/bin/env python3
"""Unit tests for Cam Home Live (zero-dependency mission control)."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "cam_home_live", ROOT / "scripts" / "cam-home-live.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Keep unit-test suggestions out of the real inbox queue.
mod.SUGGESTIONS = Path(tempfile.mkdtemp()) / "home-suggestions.jsonl"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class CamHomeLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()

    def _get(self, path: str):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}{path}", timeout=180
        ) as r:
            return r.status, r.read()

    def _post(self, path: str, obj: dict):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(obj).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())

    def test_health(self) -> None:
        status, body = self._get("/api/home/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_home_page_and_assets(self) -> None:
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"mission control", body)
        for asset in ("/styles.css", "/app.js", "/face.jpg"):
            status, _ = self._get(asset)
            self.assertEqual(status, 200, asset)

    def test_mounted_companions(self) -> None:
        status, body = self._get("/converse/")
        self.assertEqual(status, 200)
        self.assertIn(b"Cam", body)
        status, body = self._get("/connectome/")
        self.assertEqual(status, 200)

    def test_status_aggregates_real_checks(self) -> None:
        status, body = self._get("/api/home/status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["assistant"], "Cam")
        self.assertTrue(data["system"]["ok"], data["system"])
        self.assertTrue(data["build_plan"]["ok"], data["build_plan"])
        self.assertTrue(data["avatar"]["ok"], data["avatar"])
        self.assertGreaterEqual(
            len(data["system"]["data"].get("pieces") or []), 10
        )

    def test_suggestion_round_trip(self) -> None:
        marker = f"unit-test suggestion {time.time()}"
        status, out = self._post("/api/home/suggest", {"text": marker})
        self.assertEqual(status, 200)
        self.assertTrue(out["ok"])
        self.assertEqual(out["suggestion"]["status"], "queued")
        status, body = self._get("/api/home/suggestions")
        texts = [s["text"] for s in json.loads(body)["suggestions"]]
        self.assertIn(marker, texts)

    def test_avatar_speak_endpoint(self) -> None:
        status, out = self._post(
            "/api/avatar/speak", {"text": "Hello Aaron", "emotion": "warm"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(out["contract"], "AvatarFrame")
        self.assertGreaterEqual(out["fps"], 25)
        self.assertTrue(out["frames"])
        status, body = self._get("/api/avatar/contract")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["blendshape_keys"]), 52)

    def test_brain_state_endpoint(self) -> None:
        status, body = self._get("/api/brain/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertGreaterEqual(state["tick"], 1)
        self.assertIn("health", state["metrics"])
        self.assertTrue(state["thoughts"])
        self.assertTrue(state["predictions"])
        self.assertTrue(state["actions"])
        self.assertIn("priority", state["focus"])

    def test_brain_viz_embedded_on_homepage(self) -> None:
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="brainFrame"', body)
        self.assertIn(b"/connectome/index.html?embed=1", body)

    def test_connectome_vendored_three(self) -> None:
        status, body = self._get("/connectome/index.html")
        self.assertEqual(status, 200)
        self.assertIn(b"./vendor/three/three.module.js", body)
        self.assertNotIn(b"unpkg.com", body)
        self.assertNotIn(b"fonts.googleapis.com", body)
        for asset in (
            "/connectome/vendor/three/three.module.js",
            "/connectome/vendor/three/addons/controls/OrbitControls.js",
            "/connectome/vendor/three/addons/loaders/GLTFLoader.js",
            "/connectome/assets/cam-cortex.glb",
        ):
            status, _ = self._get(asset)
            self.assertEqual(status, 200, asset)

    def test_viz_data_mounts(self) -> None:
        status, body = self._get("/config/connectome/neurons.json")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body))
        status, _ = self._get("/identity/persona/cam-face.jpg")
        self.assertEqual(status, 200)

    def test_live_activity_is_her_thinking(self) -> None:
        # Make her speak, then confirm the brain feed fires Broca with the line.
        self._post("/api/avatar/speak", {"text": "brain feed check"})
        status, body = self._get("/vault/10-Mesh-Distillates/live-activity.json")
        self.assertEqual(status, 200)
        feed = json.loads(body)
        self.assertEqual(feed["source"], "cam_cortex")
        self.assertGreater(feed["firing_count"], 0)
        self.assertIn("area.broca", feed["active_areas"])
        reasons = " ".join(f["reason"] for f in feed["firing"])
        self.assertIn("brain feed check", reasons)

    def test_quick_access_redirects(self) -> None:
        for path, target in (("/cam", "/converse/"), ("/cortex", "/connectome/")):
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
            opener = urllib.request.build_opener(NoRedirect)
            try:
                opener.open(req, timeout=10)
                self.fail("expected redirect")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 302)
                self.assertEqual(e.headers["Location"], target)

    def test_traversal_blocked(self) -> None:
        try:
            status, _ = self._get("/../package.json")
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertNotEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
