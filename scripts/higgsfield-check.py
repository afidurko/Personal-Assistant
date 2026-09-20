#!/usr/bin/env python3
"""Confirm Higgsfield wiring for Cam agents.

Checks config, connectome nodes, scripts, registry, tools, trajectory policy,
and a dry-run against the sample experiment. No GPU / no network / no SSH.
"""

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
    scripts = {
        "check": "scripts/higgsfield-check.py",
        "run": "scripts/higgsfield-run.py",
        "pack": "scripts/pack-higgsfield-result.py",
        **(cfg.get("scripts") or {}),
    }
    for key, rel in scripts.items():
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    fixture = ROOT / (
        cfg.get("fixture") or "scripts/testdata/sample-higgsfield-experiment.py"
    )
    if not fixture.exists():
        errors.append("missing sample experiment fixture")

    nodes_ex = ROOT / "config/integrations/higgsfield-nodes.example.json"
    if not nodes_ex.exists():
        soft.append("missing higgsfield-nodes.example.json")

    text_sense = (ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8")
    if "sense.train.higgsfield" not in text_sense:
        errors.append("missing sense.train.higgsfield")
    text_motor = (ROOT / "config/connectome/motor.json").read_text(encoding="utf-8")
    if "motor.higgsfield" not in text_motor:
        errors.append("missing motor.higgsfield")
    text_hot = (ROOT / "config/connectome/hotspots.json").read_text(encoding="utf-8")
    if "hotspot.higgsfield" not in text_hot:
        errors.append("missing hotspot.higgsfield")
    text_syn = (ROOT / "config/connectome/synapses.json").read_text(encoding="utf-8")
    if "sense.train.higgsfield" not in text_syn:
        errors.append("missing synapse from sense.train.higgsfield")
    if "motor.higgsfield" not in text_syn:
        errors.append("missing synapse involving motor.higgsfield")

    pol = load(ROOT / "config/connectome/trajectory-policies.json")
    pol_ids = [p.get("id") for p in pol.get("policies") or []]
    for need in (
        "no_higgsfield_without_aaron",
        "no_higgsfield_with_jobs_burst",
        "no_higgsfield_with_outbound_burst",
    ):
        if need not in pol_ids:
            errors.append(f"trajectory policy missing {need}")

    reg = load(ROOT / "config/workspaces/registry.json")
    integ_ids = [i.get("id") for i in (reg.get("layers") or {}).get("integrations") or []]
    if "higgsfield" not in integ_ids:
        errors.append("registry missing higgsfield integration")
    ws_ids = [w.get("id") for w in reg.get("workspaces") or []]
    if "higgsfield" not in ws_ids:
        errors.append("registry missing higgsfield workspace")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    for need in (
        "tool.higgsfield.run",
        "tool.higgsfield.pack",
        "tool.higgsfield.check",
    ):
        if need not in tool_ids:
            errors.append(f"tools registry missing {need}")

    sub = ROOT / (cfg.get("path") or "integrations/higgsfield")
    entries = [p for p in sub.iterdir() if p.name != ".git"] if sub.exists() else []
    checkout = "ok" if entries else "empty_or_missing"
    if checkout != "ok":
        soft.append("integrations/higgsfield empty (submodule init)")

    # Dry-run smoke (no GPU). Empty checkout → soft only (wiring still valid offline).
    try:
        out = subprocess.check_output(
            [sys.executable, str(ROOT / scripts["run"]), "--doctor"],
            text=True,
            cwd=str(ROOT),
        )
        plan = json.loads(out)
        if not plan.get("ok"):
            msg = f"dry-run failed: {plan.get('errors')}"
            if checkout != "ok":
                soft.append(msg)
            else:
                errors.append(msg)
        if plan.get("mode") != "dry_run":
            errors.append("doctor must stay dry_run")
    except Exception as e:  # noqa: BLE001
        msg = f"dry-run exception: {e}"
        if checkout != "ok":
            soft.append(msg)
        else:
            errors.append(msg)

    report = {
        "ok": not errors,
        "integration": "higgsfield",
        "checkout": checkout,
        "errors": errors,
        "soft": soft,
        "motor": cfg.get("motor") or "motor.higgsfield",
        "sense": cfg.get("sense") or "sense.train.higgsfield",
        "hotspot": cfg.get("hotspot") or "hotspot.higgsfield",
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
