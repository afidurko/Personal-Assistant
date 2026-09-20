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
        ("config/loops/patterns.json", "instinct-followups"),
        ("config/workspaces/schedules.json", "cam-nightly-instinct-scan"),
        ("scripts/loop-run.py", "instinct_scan"),
        ("scripts/needs-attention.py", "scan_instinct_escalations"),
        ("scripts/cam-mcp-server.py", "instinct_scan"),
        ("scripts/test_instinct.py", "InstinctBase"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"missing {needle} in {rel}")

    # MCP server must expose the instinct tools (outbox review stays Aaron-only CLI)
    mcp_text = (ROOT / "scripts/cam-mcp-server.py").read_text(encoding="utf-8")
    for tool in ("instinct_scan", "instinct_report", "instinct_brief", "instinct_stats"):
        if f'"{tool}"' not in mcp_text:
            errors.append(f"cam-mcp-server missing tool {tool}")
    for banned in ("instinct_outbox_approve", "instinct_approve"):
        if banned in mcp_text:
            errors.append("outbox approval must not be exposed over MCP (Aaron-only CLI)")

    # Engine must ship the add-on + cross-workspace commands
    engine_text = (ROOT / "scripts/instinct.py").read_text(encoding="utf-8")
    for needle in ("cmd_outbox", "cmd_stats", "cmd_find", "parse_when",
                   "cmd_workspaces", "cmd_dispatch", "cmd_attention_sync", "cmd_distill",
                   "track_cline_run", "resolve_workspace",
                   "cmd_delegate", "resolve_delegation", "pick_role"):
        if needle not in engine_text:
            errors.append(f"engine missing {needle}")

    # Cross-workspace wiring: every coding workspace feeds and reads the ledger
    for rel, needle in (
        ("scripts/run-cline.py", "track_instinct_run"),
        ("scripts/loop-run.py", "instinct_sync"),
        ("scripts/loop-run.py", "instinct_distill"),
        (".clinerules", "motor.instinct"),
        ("scripts/install-cline-rules.py", "Instinct"),
        (".cursor/rules/cam-cline.mdc", "Instinct"),
    ):
        if needle not in (ROOT / rel).read_text(encoding="utf-8"):
            errors.append(f"cross-workspace wiring missing {needle} in {rel}")
    for tool in ("instinct_workspaces", "instinct_dispatch", "instinct_delegate",
                 "swarm_spawn", "swarm_tree", "connectors_list", "calendar_sync", "inkbox_inbound"):
        if f'"{tool}"' not in mcp_text:
            errors.append(f"cam-mcp-server missing tool {tool}")

    # Agents + connectors upgrade: team, spawn runtime, bridges, registry
    for rel in ("config/teams/follow-through.json", "config/connectors/registry.json",
                "scripts/cam_swarm.py", "scripts/calendar-sync.py", "scripts/inkbox-inbound.py",
                "scripts/connectors-check.py", "scripts/test_cam_swarm.py", "scripts/test_connectors.py",
                "scripts/test_mcp_guards.py", "docs/SWARM_CONNECTORS_SECURITY_REVIEW.md"):
        if not (ROOT / rel).exists():
            errors.append(f"missing {rel}")
    for role in ("follow-through-lead", "scheduler", "inbox-triage", "errand-runner", "negotiator", "watcher"):
        if not (ROOT / "config/roles" / f"{role}.md").exists():
            errors.append(f"missing role prompt {role}")
    privs = load(ROOT / "config/swarm/privileges.json")
    aaron_only = set(privs["privilege_catalog"]["aaron_only"])
    if not {"outbound_send", "careers_submit"} <= set(privs["privilege_catalog"].get("non_inheritable") or []):
        errors.append("privileges.non_inheritable must keep outbound_send + careers_submit chief-only")
    for needle in ("RESERVED_ROLES", "resolve_actor", "lineage_cycles", "non_inheritable"):
        if needle not in (ROOT / "scripts/cam_swarm.py").read_text(encoding="utf-8"):
            errors.append(f"cam_swarm missing guard {needle}")
    if "never act as Aaron over MCP" not in mcp_text:
        errors.append("cam-mcp-server missing Aaron-impersonation guard on swarm tools")
    if "--note-ignored-ics" not in mcp_text:
        errors.append("cam-mcp-server calendar_sync must not forward agent-supplied ics sources")
    for role, entry in privs["role_defaults"].items():
        if role == "chief":
            continue
        if "outbound_send" in entry["privileges"]:
            errors.append(f"role default {role} must not carry outbound_send (Aaron flips switch.outbound)")
        if set(entry["privileges"]) & aaron_only:
            errors.append(f"role default {role} carries Aaron-only privileges")
    centers = load(ROOT / "config/connectome/centers.json")
    if "team.follow-through" not in (centers.get("teams") or []):
        errors.append("centers.teams missing team.follow-through")
    for needle in ("connectors_pull", "swarm_distill"):
        if needle not in (ROOT / "scripts/loop-run.py").read_text(encoding="utf-8"):
            errors.append(f"loop-run missing action {needle}")
    reg_full = load(ROOT / "config/workspaces/registry.json")
    pa_signal = next((s for s in (reg_full.get("chooser") or {}).get("signals") or []
                      if s.get("id") == "personal-assistant"), {})
    if "instinct" not in (pa_signal.get("match_any") or []):
        errors.append("chooser signals missing 'instinct' → personal-assistant")
    pats_full = load(ROOT / "config/loops/patterns.json")
    pat_actions = next((p.get("actions") or [] for p in pats_full.get("patterns") or []
                        if p.get("id") == "instinct-followups"), [])
    for act in ("connectors_pull", "instinct_sync", "instinct_scan", "instinct_distill", "swarm_distill"):
        if act not in pat_actions:
            errors.append(f"instinct-followups loop missing action {act}")
    # dispatch must be print-only: the engine must never invoke run-cline itself
    if "subprocess" in engine_text:
        errors.append("engine must not shell out (dispatch is print-only)")

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

    # The nightly loop must stay report/draft-only (no cline dispatch, no auto-fix)
    pats = load(ROOT / "config/loops/patterns.json")
    pat = next((p for p in pats.get("patterns") or [] if p.get("id") == "instinct-followups"), None)
    if pat is None:
        errors.append("loops patterns missing instinct-followups")
    else:
        if pat.get("cline_dispatch"):
            errors.append("instinct-followups loop must not dispatch cline")
        if pat.get("level") != "L1":
            errors.append("instinct-followups loop must stay L1 report-only")

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
