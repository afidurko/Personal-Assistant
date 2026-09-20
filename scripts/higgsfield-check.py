#!/usr/bin/env python3
"""Confirm Higgsfield wiring for Cam (no paid API call required)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    cfg_path = ROOT / "config/integrations/higgsfield.json"
    md_path = ROOT / "config/integrations/higgsfield.md"
    if not cfg_path.exists():
        errors.append("missing config/integrations/higgsfield.json")
    if not md_path.exists():
        errors.append("missing config/integrations/higgsfield.md")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    for rel in (
        (cfg.get("scripts") or {}).get("client") or "scripts/higgsfield.py",
        (cfg.get("scripts") or {}).get("check") or "scripts/higgsfield-check.py",
    ):
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    provider = cfg.get("provider") or {}
    if provider.get("upload_path") != "/files/generate-upload-url":
        errors.append("provider.upload_path must be /files/generate-upload-url")
    if "api.higgsfield.ai" not in str(provider.get("files_base_default") or ""):
        errors.append("provider.files_base_default must be api.higgsfield.ai")
    if "HF_CREDENTIALS" not in json.dumps(provider.get("credential_aliases") or []):
        errors.append("provider.credential_aliases must include official HF_CREDENTIALS")
    if cfg.get("status") != "rejected" or cfg.get("presence") is not False:
        errors.append("higgsfield.json must stay rejected and presence=false (Aaron: looks creepy)")

    avatar = load(ROOT / "config/persona/avatar.json")
    clips = (avatar.get("avatar") or {}).get("clips") or {}
    if clips.get("engine") == "higgsfield":
        errors.append("avatar.json must not use higgsfield as a presence clip engine")

    for rel in ("src/components/CamStage.tsx", "src/components/CamFace.tsx"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for banned in ("higgsfield", "clipUrl", "clipActive", "Render Speak clip", "Play Speak clip"):
            if banned.lower() in text.lower():
                errors.append(f"{rel} must not surface Higgsfield ({banned})")

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.higgsfield.health"),
        ("config/connectome/sensory.json", "sense.higgsfield.result"),
        ("config/connectome/motor.json", "motor.higgsfield"),
        ("config/connectome/hotspots.json", "hotspot.higgsfield"),
        ("config/connectome/synapses.json", "sense.higgsfield.result"),
        ("config/connectome/switches.json", "motor.higgsfield"),
        ("config/connectome/trajectory-policies.json", "motor.higgsfield"),
        ("config/system/pieces.json", "piece.higgsfield"),
        ("scripts/higgsfield.py", "generate-upload-url"),
        ("scripts/higgsfield.py", "HF_CREDENTIALS"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    if "tool.higgsfield.check" not in tool_ids:
        errors.append("tools registry missing tool.higgsfield.check")

    env = os.environ.copy()
    env.pop("HIGGSFIELD_IMAGE_URL", None)
    env.pop("HIGGSFIELD_AUDIO_URL", None)
    dry = subprocess.run(
        [sys.executable, str(ROOT / "scripts/higgsfield.py"), "speak", "--text", "Hello Aaron", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    if dry.returncode != 0:
        errors.append(f"dry-run failed: {dry.stderr or dry.stdout}")
    else:
        try:
            payload = json.loads(dry.stdout)
            if not payload.get("ok") or not payload.get("dry_run"):
                errors.append("dry-run did not report ok/dry_run")
            if not payload.get("local_image"):
                errors.append("dry-run did not resolve local portrait (the real-life failure)")
            steps = " ".join(payload.get("planned_steps") or [])
            if "generate-upload-url" not in steps:
                errors.append("dry-run planned_steps missing generate-upload-url")
            if payload.get("body", {}).get("input_image", {}).get("image_url") not in {
                "(upload local portrait)",
                "(set)",
            }:
                errors.append("dry-run should not require a public image URL")
        except json.JSONDecodeError:
            errors.append("dry-run did not return JSON")

    tests = subprocess.run(
        [sys.executable, str(ROOT / "scripts/test_higgsfield.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if tests.returncode != 0:
        errors.append(f"test_higgsfield failed: {tests.stderr or tests.stdout}")

    report = {"ok": not errors, "errors": errors, "soft": soft}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
