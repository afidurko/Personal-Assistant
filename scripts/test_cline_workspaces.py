#!/usr/bin/env python3
"""Unit tests for Cam↔Cline workspace runtime (no live cline binary required)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402


class WorkspaceRegistryTests(unittest.TestCase):
    def test_registry_loads(self):
        reg = cw.load_registry()
        self.assertTrue(reg["workspaces"])
        self.assertEqual(reg["default_workspace_id"], "personal-assistant")

    def test_choose_personal_assistant(self):
        c = cw.choose_workspace(goal="update connectome vault mesh notes")
        self.assertEqual(c["workspace"]["id"], "personal-assistant")

    def test_choose_cline(self):
        c = cw.choose_workspace(goal="refactor cline cli auth provider")
        self.assertEqual(c["workspace"]["id"], "cline")

    def test_choose_paddledetection(self):
        c = cw.choose_workspace(goal="paddledetection model export")
        self.assertEqual(c["workspace"]["id"], "paddledetection")

    def test_choose_inkbox(self):
        c = cw.choose_workspace(goal="inkbox sdk identity email")
        self.assertEqual(c["workspace"]["id"], "inkbox")

    def test_choose_loop_engineering(self):
        c = cw.choose_workspace(goal="loop-engineering loop-audit daily triage")
        self.assertEqual(c["workspace"]["id"], "loop-engineering")

    def test_choose_voicestudio(self):
        c = cw.choose_workspace(goal="voicestudio voice cloning local tts")
        self.assertEqual(c["workspace"]["id"], "voicestudio")

    def test_choose_pupil(self):
        c = cw.choose_workspace(goal="pupil eye tracking gaze capture")
        self.assertEqual(c["workspace"]["id"], "pupil")

    def test_explicit_id_wins(self):
        c = cw.choose_workspace(goal="cline sdk", workspace_id="jarvis")
        self.assertEqual(c["workspace"]["id"], "jarvis")
        self.assertEqual(c["reason"], "explicit_workspace_id")

    def test_explicit_path_ad_hoc(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = cw.choose_workspace(explicit_path=tmp)
            self.assertEqual(c["workspace"]["id"], "ad-hoc")
            self.assertEqual(c["path"], str(Path(tmp).resolve()))

    def test_mesh_projects_doc(self):
        doc = cw.mesh_projects_doc()
        self.assertEqual(doc["namespace"], "mesh/projects")
        ids = {p["id"] for p in doc["projects"]}
        self.assertIn("personal-assistant", ids)
        self.assertIn("cline", ids)


class ScriptSmokeTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

    def test_choose_workspace_cli(self):
        proc = self._run("scripts/choose-workspace.py", "--goal", "jarvis plugin weather")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["workspace"]["id"], "jarvis")

    def test_run_cline_dry_run(self):
        proc = self._run(
            "scripts/run-cline.py",
            "--workspace-id",
            "personal-assistant",
            "--dry-run",
            "hello",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["accepted"])
        self.assertIn("--cwd", data["argv"])
        self.assertTrue(data["dry_run"])

    def test_run_cline_kill(self):
        proc = self._run("scripts/run-cline.py", "--kill", "x")
        self.assertEqual(proc.returncode, 2)
        data = json.loads(proc.stdout)
        self.assertFalse(data["accepted"])

    def test_connectome_route_coding(self):
        proc = self._run(
            "scripts/connectome-route.py",
            "--sense",
            "sense.chat.aaron",
            "--goal",
            "implement coding refactor with cline",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["hotspot_id"], "hotspot.coding")
        self.assertIn("motor.cline", data["motor_plan"])
        self.assertIn("workspace", data)

    def test_pupil_see_route(self):
        proc = self._run(
            "scripts/connectome-route.py",
            "--sense",
            "sense.vision.world",
            "--goal",
            "cam see via pupil",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["hotspot_id"], "hotspot.pupil_see")
        self.assertIn("motor.pupil", data["motor_plan"])

    def test_pupil_see_dry_run(self):
        proc = self._run("scripts/pupil-see.py", "--dry-run", "--no-route")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc2 = self._run("scripts/pupil-see.py", "--dry-run")
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        data = json.loads(proc2.stdout)
        self.assertTrue(data["cam_can_see"])
        self.assertEqual(data["motor"], "motor.pupil")
        self.assertIn("motor.pupil", (data.get("route") or {}).get("motor_plan") or [])

    def test_connectome_check(self):
        proc = self._run("scripts/connectome-check.py", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])

    def test_mcp_tools_list(self):
        payload = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"},
                    },
                }
            )
            + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            + "\n"
        )
        proc = subprocess.run(
            [sys.executable, "scripts/cam-mcp-server.py"],
            cwd=str(ROOT),
            input=payload,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [json.loads(l) for l in proc.stdout.strip().splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 2)
        tools = {t["name"] for t in lines[1]["result"]["tools"]}
        self.assertIn("choose_workspace", tools)
        self.assertIn("mesh_search", tools)
        self.assertIn("connectome_route", tools)
        self.assertIn("inkbox_check", tools)
        self.assertIn("loop_check", tools)
        self.assertIn("loop_run", tools)
        self.assertIn("voicestudio_health", tools)
        self.assertIn("higgsfield_check", tools)
        self.assertIn("presence_check", tools)

    def test_voicestudio_speak_dry_run(self):
        proc = self._run(
            "scripts/voicestudio-speak.py",
            "--text",
            "hello",
            "--dry-run",
            "--json",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertTrue(data.get("dry_run"))

    def test_pack_voicestudio_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job.json"
            job.write_text(
                json.dumps(
                    {
                        "kind": "tts",
                        "profile_id": "cam-soft",
                        "output_path": "/tmp/x.wav",
                        "duration_s": 1.2,
                        "ok": True,
                    }
                ),
                encoding="utf-8",
            )
            proc = self._run(
                "scripts/pack-voicestudio-result.py",
                "--job",
                str(job),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["namespace"], "mesh/voice")
            self.assertTrue(data["synthetic"])

    def test_sync_schedules(self):
        proc = self._run("scripts/sync-cline-schedules.py", "--apply-cache")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        export = ROOT / "identity" / "persistence" / "cline-schedules.export.json"
        self.assertTrue(export.exists())
        doc = json.loads(export.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(doc.get("schedules") or []), 1)

    def test_install_rules_skips_empty(self):
        proc = self._run("scripts/install-cline-rules.py")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("personal-assistant", proc.stdout)


class SimIntegrityTests(unittest.TestCase):
    def test_build_tables_clean(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "sim", ROOT / "scripts" / "connectome-simulate.py"
        )
        sim = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(sim)
        _sense, _by, _known, _motors, _edges, hard, soft = sim.build_tables()
        self.assertEqual(hard, [])
        missing = [
            e
            for e in soft
            if e.startswith("missing_edge:") or e.startswith("missing_feedback_edge:")
        ]
        self.assertEqual(missing, [])


class AnatomyCortexTests(unittest.TestCase):
    def test_anatomy_check_script(self):
        proc = subprocess.run(
            [sys.executable, "scripts/connectome-anatomy-check.py", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"], data.get("errors"))
        self.assertGreaterEqual(data["mapped_areas"], data["areas"])
        self.assertGreater(data["glb_bytes"], 100_000)

    def test_region_map_covers_areas(self):
        areas = json.loads(
            (ROOT / "config/connectome/areas.json").read_text(encoding="utf-8")
        )
        region_map = json.loads(
            (ROOT / "config/connectome/anatomy-region-map.json").read_text(
                encoding="utf-8"
            )
        )
        area_ids = {a["id"] for a in areas["areas"]}
        mapped = {
            e["name"]
            for e in region_map
            if e.get("name", "").startswith("area.")
            and not e["name"].endswith(".hippocampus")
        }
        self.assertEqual(area_ids - mapped, set())

    def test_glass_modules_present(self):
        viz = ROOT / "visualizations" / "connectome"
        self.assertTrue((viz / "cortex-anatomy.js").is_file())
        self.assertTrue((viz / "cortex3d.js").is_file())
        body = (viz / "cortex-anatomy.js").read_text(encoding="utf-8")
        self.assertIn("MeshPhysicalMaterial", body)
        self.assertIn("setTranslucency", body)
        self.assertIn("installGlassEnvironment", body)


    def test_merge_prep_script_exists(self):
        p = ROOT / "scripts" / "merge-prep-billion.sh"
        self.assertTrue(p.is_file())
        body = p.read_text(encoding="utf-8")
        self.assertIn("1000000000", body)
        self.assertIn("connectome-anatomy-check", body)

    def test_merge_prep_trillion_script_exists(self):
        p = ROOT / "scripts" / "merge-prep-trillion.sh"
        self.assertTrue(p.is_file())
        body = p.read_text(encoding="utf-8")
        self.assertIn("three-trillion-campaign", body)
        self.assertTrue((ROOT / "scripts" / "three-trillion-campaign.py").is_file())
        self.assertTrue((ROOT / "scripts" / "trillion_scale.py").is_file())
        self.assertTrue((ROOT / "scripts" / "presence-check.py").is_file())
        campaign = (ROOT / "scripts" / "three-trillion-campaign.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("test_cloud_agent_install.py", campaign)
        self.assertIn("_maybe_install_embodiment_deps", campaign)
        self.assertIn("embodiment_lite", campaign)
        self.assertIn("test_embodiment_lite.py", campaign)
        self.assertIn("ci-static-gate.py", campaign)
        self.assertIn("aaron-voice-billion-fuzz.py", campaign)
        self.assertIn("public-apis-billion-fuzz.py", campaign)
        self.assertIn("test_cam_converse_voice_gate", campaign)
        self.assertIn("presence-check.py", campaign)

    def test_cloud_agent_environment_json_present(self):
        env = ROOT / ".cursor" / "environment.json"
        self.assertTrue(env.is_file())
        cfg = json.loads(env.read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("install"), "./scripts/cloud-agent-install.sh")
        self.assertNotIn(cfg.get("install"), {"build", "promote illa build"})

    def test_serve_viz_repo_root(self):
        body = (ROOT / "scripts" / "serve-connectome-viz.sh").read_text(encoding="utf-8")
        self.assertIn("visualizations/connectome", body)
        self.assertIn("live-activity.json", body)
        self.assertIn("repo-root", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
