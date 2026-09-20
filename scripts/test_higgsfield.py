#!/usr/bin/env python3
"""Unit tests for Higgsfield Speak local-upload path (no paid API)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_mod():
    spec = importlib.util.spec_from_file_location("higgsfield", ROOT / "scripts" / "higgsfield.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hf = load_mod()


def write_wav(path: Path, seconds: float = 1.0, rate: int = 16000) -> Path:
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frames)
    return path


class HiggsfieldCredsTests(unittest.TestCase):
    def test_official_hf_credentials_alias(self) -> None:
        env = os.environ
        old = {k: env.get(k) for k in ("HF_CREDENTIALS", "HIGGSFIELD_API_KEY_ID", "HIGGSFIELD_API_KEY_SECRET")}
        try:
            env.pop("HIGGSFIELD_API_KEY_ID", None)
            env.pop("HIGGSFIELD_API_KEY_SECRET", None)
            env["HF_CREDENTIALS"] = "official-id:official-secret"
            creds = hf.resolve_credentials({})
            self.assertTrue(creds["present"])
            self.assertEqual(creds["source"], "HF_CREDENTIALS")
            self.assertEqual(creds["key_id"], "official-id")
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_split_hf_api_key_names(self) -> None:
        env = os.environ
        old = {k: env.get(k) for k in ("HF_API_KEY_ID", "HF_API_KEY_SECRET", "HF_CREDENTIALS")}
        try:
            env.pop("HF_CREDENTIALS", None)
            env["HF_API_KEY_ID"] = "id-from-docs"
            env["HF_API_KEY_SECRET"] = "secret-from-docs"
            creds = hf.resolve_credentials({})
            self.assertTrue(creds["present"])
            self.assertIn("HF_API_KEY_ID", creds["source"])
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v


class HiggsfieldPlanTests(unittest.TestCase):
    def test_duration_from_wav(self) -> None:
        self.assertEqual(hf.pick_duration("", None, 3.2), 5)
        self.assertEqual(hf.pick_duration("", None, 9.0), 10)
        self.assertEqual(hf.pick_duration("", None, 14.0), 15)
        self.assertEqual(hf.pick_duration("", 10, 3.0), 10)

    def test_extract_clip_url_shapes(self) -> None:
        self.assertEqual(hf.extract_clip_url({"video": {"url": "https://x/a.mp4"}}), "https://x/a.mp4")
        self.assertEqual(
            hf.extract_clip_url({"jobs": [{"results": {"raw": {"url": "https://x/b.mp4"}}}]}),
            "https://x/b.mp4",
        )

    def test_auth_header(self) -> None:
        self.assertEqual(hf.auth_header("id", "sec"), "Key id:sec")

    def test_dry_run_uses_local_portrait_not_public_urls(self) -> None:
        env = os.environ.copy()
        env.pop("HIGGSFIELD_IMAGE_URL", None)
        env.pop("HIGGSFIELD_AUDIO_URL", None)
        out = subprocess.check_output(
            [sys.executable, str(ROOT / "scripts/higgsfield.py"), "speak", "--text", "Hello Aaron", "--dry-run"],
            cwd=str(ROOT),
            env=env,
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["local_image"])
        self.assertIn("cam-face.jpg", payload["local_image"])
        self.assertIn("generate-upload-url", " ".join(payload["planned_steps"]))
        self.assertEqual(payload["body"]["input_image"]["image_url"], "(upload local portrait)")
        self.assertEqual(payload["body"]["input_audio"]["audio_url"], "(upload local WAV)")

    def test_dry_run_with_local_wav(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wav = write_wav(Path(td) / "line.wav", seconds=2.0)
            # Copy under ROOT so path check is not required for --audio (audio resolve allows abs)
            out = subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/higgsfield.py"),
                    "speak",
                    "--text",
                    "Hello Aaron",
                    "--audio",
                    str(wav),
                    "--dry-run",
                ],
                cwd=str(ROOT),
                text=True,
            )
            payload = json.loads(out)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["audio_plan"]["source"], "file")
            self.assertGreater(payload["audio_plan"]["seconds"], 1.0)

    def test_live_without_flag_fails_closed(self) -> None:
        env = os.environ.copy()
        env["HIGGSFIELD_LIVE"] = "0"
        env["HF_CREDENTIALS"] = "id:secret"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/higgsfield.py"), "speak", "--text", "Hi", "--live"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertIn("HIGGSFIELD_LIVE", payload.get("error") or "")

    def test_status_mentions_real_life_failure(self) -> None:
        payload = json.loads(
            subprocess.check_output(
                [sys.executable, str(ROOT / "scripts/higgsfield.py"), "status"],
                cwd=str(ROOT),
                text=True,
            )
        )
        self.assertTrue(payload["ok"])
        self.assertIn("generate-upload-url", payload["real_life_failure"] + payload["upload_path"])
        self.assertTrue(payload["portrait_exists"])


if __name__ == "__main__":
    unittest.main()
