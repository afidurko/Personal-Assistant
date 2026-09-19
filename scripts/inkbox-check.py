#!/usr/bin/env python3
"""Confirm Inkbox wiring for Cam (no network / no API key required).

Checks config, connectome nodes, registry, tools entry, and submodule presence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    cfg_path = ROOT / "config/integrations/inkbox.json"
    md_path = ROOT / "config/integrations/inkbox.md"
    if not cfg_path.exists():
        errors.append("missing config/integrations/inkbox.json")
    if not md_path.exists():
        errors.append("missing config/integrations/inkbox.md")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    check_rel = (cfg.get("scripts") or {}).get("check") or "scripts/inkbox-check.py"
    if not (ROOT / check_rel).exists():
        errors.append(f"missing:{check_rel}")

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.inkbox.event"),
        ("config/connectome/motor.json", "motor.inkbox"),
        ("config/connectome/hotspots.json", "hotspot.inkbox"),
        ("config/connectome/synapses.json", "sense.inkbox.event"),
        ("config/connectome/switches.json", "motor.inkbox"),
        ("config/connectome/trajectory-policies.json", "motor.inkbox"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    reg = load(ROOT / "config/workspaces/registry.json")
    layers = reg.get("layers") or {}
    integ_ids = [i.get("id") for i in layers.get("integrations") or []]
    if "inkbox" not in integ_ids:
        errors.append("registry missing inkbox integration")
    coding_ids = [w.get("id") for w in layers.get("coding_workspaces") or []]
    if "inkbox" not in coding_ids:
        errors.append("registry missing inkbox coding workspace")
    flat_ids = [w.get("id") for w in reg.get("workspaces") or []]
    if "inkbox" not in flat_ids:
        errors.append("registry flat workspaces missing inkbox")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    if "tool.inkbox.check" not in tool_ids:
        errors.append("tools registry missing tool.inkbox.check")

    sub = ROOT / "integrations/inkbox"
    if not sub.exists():
        errors.append("missing integrations/inkbox path")
    else:
        entries = [p for p in sub.iterdir() if p.name not in {".git", ".gitignore"}]
        if not entries:
            soft.append("integrations/inkbox empty — run git submodule update --init")
        elif not (sub / "README.md").exists():
            soft.append("integrations/inkbox missing README.md")

    gm = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    if "integrations/inkbox" not in gm:
        errors.append(".gitmodules missing integrations/inkbox")

    seed = load(ROOT / "identity/persistence/mesh-seed.json")
    tools_ns = seed.get("mesh/tools") or {}
    prefs = seed.get("mesh/prefs") or {}
    facts = seed.get("mesh/facts") or {}
    if not (
        tools_ns.get("inkbox")
        or prefs.get("inkbox")
        or facts.get("inkbox")
        or (seed.get("mesh/comms") or {}).get("inkbox")
    ):
        errors.append("mesh-seed missing inkbox flag")

    report = {
        "ok": not errors,
        "errors": errors,
        "soft_warnings": soft,
        "motor": "motor.inkbox",
        "sense": "sense.inkbox.event",
        "hotspot": "hotspot.inkbox",
        "credential_env": cfg.get("credential_env") or "INKBOX_API_KEY",
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
