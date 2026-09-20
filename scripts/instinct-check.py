#!/usr/bin/env python3
"""Confirm Cam Instinct wiring (offline, no credential required).

Checks config, connectome nodes, registries, tools entries, engine presence,
and the draft-only guardrails demanded by .clinerules.
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

    cfg_path = ROOT / "config/integrations/instinct.json"
    md_path = ROOT / "config/integrations/instinct.md"
    if not cfg_path.exists():
        errors.append("missing config/integrations/instinct.json")
    if not md_path.exists():
        errors.append("missing config/integrations/instinct.md")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    for rel in ((cfg.get("scripts") or {}).get("engine") or "scripts/instinct.py",
                (cfg.get("scripts") or {}).get("check") or "scripts/instinct-check.py"):
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.instinct.followup"),
        ("config/connectome/motor.json", "motor.instinct"),
        ("config/connectome/hotspots.json", "hotspot.instinct"),
        ("config/connectome/synapses.json", "sense.instinct.followup"),
        ("config/connectome/trajectory-policies.json", "instinct_followup_draft_only"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    # Guardrails: motor.instinct must NOT be an outbound-capable effector, and
    # the config must keep drafts-only + no credential + no spend.
    motor = load(ROOT / "config/connectome/motor.json")
    eff = next((e for e in motor["effectors"] if e["id"] == "motor.instinct"), None)
    if eff is None:
        errors.append("motor.json missing motor.instinct effector")
    else:
        if "switch.kill" not in (eff.get("requires_switch") or []):
            errors.append("motor.instinct must respect switch.kill")
        outbound_channels = {"email", "sms", "phone", "imessage", "whatsapp"}
        if outbound_channels & set(eff.get("channel") or []):
            errors.append("motor.instinct must not own outbound channels (hand to motor.inkbox)")
    defaults = cfg.get("defaults") or {}
    if defaults.get("draft_only") is not True:
        errors.append("instinct defaults must keep draft_only=true")
    if defaults.get("no_spend") is not True:
        errors.append("instinct defaults must keep no_spend=true")
    if cfg.get("credential_env"):
        errors.append("instinct must not require a credential (local-first)")

    reg = load(ROOT / "config/workspaces/registry.json")
    integ_ids = [i.get("id") for i in (reg.get("layers") or {}).get("integrations") or []]
    if "instinct" not in integ_ids:
        errors.append("registry missing instinct integration")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    for tid in ("tool.instinct.check", "tool.instinct.scan"):
        if tid not in tool_ids:
            errors.append(f"tools registry missing {tid}")

    seed = load(ROOT / "identity/persistence/mesh-seed.json")
    if not (seed.get("mesh/tools") or {}).get("instinct"):
        errors.append("mesh-seed missing instinct flag")

    data_dir = ROOT / "data/instinct"
    if not data_dir.exists():
        soft.append("data/instinct not initialized yet — first ingest/scan will create it")

    report = {
        "ok": not errors,
        "errors": errors,
        "soft_warnings": soft,
        "motor": "motor.instinct",
        "sense": "sense.instinct.followup",
        "hotspot": "hotspot.instinct",
        "outbound_handoff": cfg.get("outbound_handoff"),
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
