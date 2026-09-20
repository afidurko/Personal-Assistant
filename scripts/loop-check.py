#!/usr/bin/env python3
"""Confirm Loop Engineering wiring for Cam (no network required).

Checks config, connectome nodes, registry, tools, spine files, and submodule.
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

    cfg_path = ROOT / "config/integrations/loop-engineering.json"
    md_path = ROOT / "config/integrations/loop-engineering.md"
    patterns_path = ROOT / "config/loops/patterns.json"
    if not cfg_path.exists():
        errors.append("missing config/integrations/loop-engineering.json")
    if not md_path.exists():
        errors.append("missing config/integrations/loop-engineering.md")
    if not patterns_path.exists():
        errors.append("missing config/loops/patterns.json")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    for key, rel in (cfg.get("scripts") or {}).items():
        if not (ROOT / rel).exists():
            errors.append(f"missing script {key}:{rel}")

    for spine in ("LOOP.md", "STATE.md", "loop-budget.md", "loop-run-log.md"):
        if not (ROOT / spine).exists():
            errors.append(f"missing spine file {spine}")

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.loop.tick"),
        ("config/connectome/motor.json", "motor.loop"),
        ("config/connectome/hotspots.json", "hotspot.loop_engineering"),
        ("config/connectome/synapses.json", "sense.loop.tick"),
        ("config/connectome/synapses.json", "motor.loop"),
        ("config/connectome/neurons.json", "neuron.loop_triage"),
        ("config/connectome/trajectory-policies.json", "motor.loop"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    reg = load(ROOT / "config/workspaces/registry.json")
    layers = reg.get("layers") or {}
    integ_ids = [i.get("id") for i in layers.get("integrations") or []]
    if "loop-engineering" not in integ_ids:
        errors.append("registry missing loop-engineering integration")
    coding_ids = [w.get("id") for w in layers.get("coding_workspaces") or []]
    if "loop-engineering" not in coding_ids:
        errors.append("registry missing loop-engineering coding workspace")
    flat_ids = [w.get("id") for w in reg.get("workspaces") or []]
    if "loop-engineering" not in flat_ids:
        errors.append("registry flat workspaces missing loop-engineering")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    for tid in ("tool.loop.check", "tool.loop.audit", "tool.loop.run"):
        if tid not in tool_ids:
            errors.append(f"tools registry missing {tid}")

    sub = ROOT / "integrations/loop-engineering"
    if not sub.exists():
        errors.append("missing integrations/loop-engineering path")
    else:
        entries = [p for p in sub.iterdir() if p.name not in {".git", ".gitignore"}]
        if not entries:
            soft.append("integrations/loop-engineering empty — run git submodule update --init")
        elif not (sub / "README.md").exists():
            soft.append("integrations/loop-engineering missing README.md")
        audit_cli = sub / "tools/loop-audit/dist/cli.js"
        if not audit_cli.exists():
            soft.append("loop-audit dist missing — build tools under submodule or use npx")

    gm = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    if "integrations/loop-engineering" not in gm:
        errors.append(".gitmodules missing integrations/loop-engineering")

    seed = load(ROOT / "identity/persistence/mesh-seed.json")
    tools_ns = seed.get("mesh/tools") or {}
    prefs = seed.get("mesh/prefs") or {}
    loops_ns = seed.get("mesh/loops") or {}
    if not (loops_ns or tools_ns.get("loop_engineering") or prefs.get("loop_engineering")):
        errors.append("mesh-seed missing loop_engineering / mesh/loops flag")

    report = {
        "ok": not errors,
        "errors": errors,
        "soft_warnings": soft,
        "motor": "motor.loop",
        "sense": "sense.loop.tick",
        "hotspot": "hotspot.loop_engineering",
        "week_one_mode": cfg.get("week_one_mode") or "L1",
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
