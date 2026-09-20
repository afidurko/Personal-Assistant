#!/usr/bin/env python3
"""Confirm Higgsfield wiring for Cam (no network / no API key required)."""

from __future__ import annotations

import json
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

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.higgsfield.health"),
        ("config/connectome/sensory.json", "sense.higgsfield.result"),
        ("config/connectome/motor.json", "motor.higgsfield"),
        ("config/connectome/hotspots.json", "hotspot.higgsfield"),
        ("config/connectome/synapses.json", "sense.higgsfield.result"),
        ("config/connectome/switches.json", "motor.higgsfield"),
        ("config/connectome/trajectory-policies.json", "motor.higgsfield"),
        ("config/system/pieces.json", "piece.higgsfield"),
        ("config/persona/avatar.json", "higgsfield"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    if "tool.higgsfield.check" not in tool_ids:
        errors.append("tools registry missing tool.higgsfield.check")

    dry = subprocess.run(
        [sys.executable, str(ROOT / "scripts/higgsfield.py"), "speak", "--text", "hi", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if dry.returncode != 0:
        errors.append(f"dry-run failed: {dry.stderr or dry.stdout}")
    else:
        try:
            payload = json.loads(dry.stdout)
            if not payload.get("ok") or not payload.get("dry_run"):
                errors.append("dry-run did not report ok/dry_run")
        except json.JSONDecodeError:
            errors.append("dry-run did not return JSON")

    report = {"ok": not errors, "errors": errors, "soft": soft}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
