#!/usr/bin/env python3
"""Confirm Cam workspace + integration wiring for this checkout.

Checks persistence bundle coverage, team/enhancement configs, connectome
pathways, submodule checkouts, and (if present) PR#2 scan-workspace modules.
Does not require network. Exit 0 only when hard requirements pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "config" / "workspaces" / "registry.json"

HARD_PATHS = [
    "identity/persistence/mesh-seed.json",
    "identity/persistence/manifest.json",
    "identity/persistence/DAILY_AGI_SCAN.md",
    "identity/persistence/HAAS_CAM_PATTERNS.md",
    "identity/BOUNDARIES.md",
    "config/teams/agi-research-scan.json",
    "config/teams/capability.json",
    "config/teams/info.json",
    "config/teams/tooling.json",
    "config/swarm/privileges.json",
    "config/swarm/primitives.json",
    "config/swarm/autonomy-triad.json",
    "config/tools/registry.json",
    "config/enhancement/slm-dl.json",
    "config/enhancement/dual-process.json",
    "config/enhancement/social-harness.json",
    "config/enhancement/vision-grounding.json",
    "config/enhancement/science-agent-env.json",
    "config/memory/hmo-tiers.json",
    "config/memory/mesh-claim-schema.json",
    "config/connectome/trajectory-policies.json",
    "config/persona/consistency-checks.json",
    "config/pipelines/daily-agi-scan.json",
    "config/pipelines/cam-enhance-gate.json",
    "config/integrations/google-scholar.json",
    "config/integrations/google-scholar.md",
    "config/integrations/voicestudio.json",
    "config/integrations/voicestudio.md",
    "config/mcp/voicestudio.json",
    "scripts/voicestudio-health.py",
    "scripts/voicestudio-speak.py",
    "scripts/pack-voicestudio-result.py",
    "config/integrations/public-apis.json",
    "config/integrations/public-apis.md",
    "config/integrations/public-apis-addons.json",
    "docs/CAM_BRAIN.md",
    "docs/AGI_RESEARCH_TEAM.md",
    "docs/WORKSPACES_WORKFLOW.md",
    "docs/HAAS_CAM_PATTERNS.md",
    "scripts/agi-research-scan.py",
    "scripts/cam-enhance-propose.py",
    "scripts/scholar-search.py",
    "scripts/pack-scholar-result.py",
    "scripts/public-apis-search.py",
    "scripts/pack-public-apis-result.py",
    "scripts/public-apis-check.py",
    "scripts/public-apis-addon.py",
    "scripts/swarm-check.py",
    "scripts/persist-export.py",
    "scripts/persist-import.py",
    "scripts/trajectory-policy-check.py",
    "scripts/memory-tier-check.py",
    "scripts/pack-mesh-claim.py",
    "scripts/apply-cam-enhancements.py",
    "server/core/swarm-runtime.ts",
    "server/workspaces/swarm.ts",
    "shared/swarmPrivileges.ts",
    "shared/agentLayers.ts",
]

PERSIST_MUST_INCLUDE = [
    "identity/persistence/DAILY_AGI_SCAN.md",
    "identity/persistence/HAAS_CAM_PATTERNS.md",
    "identity/persistence/CAM_ENHANCE_BATCH_2026-09-17.md",
    "config/teams/agi-research-scan.json",
    "config/teams/capability.json",
    "config/teams/info.json",
    "config/teams/tooling.json",
    "config/swarm/privileges.json",
    "config/enhancement/slm-dl.json",
    "config/enhancement/dual-process.json",
    "config/memory/hmo-tiers.json",
    "config/memory/mesh-claim-schema.json",
    "config/connectome/trajectory-policies.json",
    "config/persona/consistency-checks.json",
    "config/workspaces/registry.json",
    "docs/CAM_BRAIN.md",
    "docs/AGI_RESEARCH_TEAM.md",
    "docs/WORKSPACES_WORKFLOW.md",
    "docs/HAAS_CAM_PATTERNS.md",
]


def load_export_includes() -> list[str]:
    text = (ROOT / "scripts" / "persist-export.py").read_text(encoding="utf-8")
    # naive extract of DEFAULT_INCLUDE list strings
    start = text.find("DEFAULT_INCLUDE = [")
    end = text.find("]", start)
    chunk = text[start:end]
    return [line.strip().strip(",").strip('"') for line in chunk.splitlines() if '"' in line]


def integration_ready(path: Path) -> bool:
    """True if a submodule dir is checked out, or a config-file connector exists."""
    if not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    # empty dir or gitlink without checkout → no files besides maybe .git
    entries = [p for p in path.iterdir() if p.name != ".git"]
    return len(entries) > 0


def mesh_flags(seed: dict) -> dict:
    prefs = seed.get("mesh/prefs", {})
    facts = seed.get("mesh/facts", {})
    research = seed.get("mesh/research", {})
    return {
        "daily_agi_research_scan": bool(
            prefs.get("daily_agi_research_scan")
            or facts.get("daily_agi_research_scan")
            or research.get("daily_agi_research_scan")
        ),
        "cam_enhance_apply_requires_aaron": bool(
            prefs.get("cam_enhance_apply_requires_aaron")
            or research.get("cam_enhance_apply_requires_aaron")
        ),
        "google_scholar": bool(research.get("google_scholar")),
        "public_apis": bool(
            research.get("public_apis")
            or prefs.get("public_apis")
            or (seed.get("mesh/tools") or {}).get("public_apis")
        ),
        "unlimited_subagents": bool(prefs.get("unlimited_subagents") or facts.get("unlimited_subagents")),
        "slm_cortex_enabled": bool(prefs.get("slm_cortex_enabled")),
        "dl_cortex_enabled": bool(prefs.get("dl_cortex_enabled")),
        "persistence_cross_workspace": bool(prefs.get("persistence_cross_workspace")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    hard_missing = [p for p in HARD_PATHS if not (ROOT / p).exists()]
    export_includes = load_export_includes()
    persist_gaps = [p for p in PERSIST_MUST_INCLUDE if p not in export_includes]

    seed = json.loads((ROOT / "identity/persistence/mesh-seed.json").read_text(encoding="utf-8"))
    flags = mesh_flags(seed)
    flag_gaps = [k for k, v in flags.items() if not v]

    registry = json.loads(REG.read_text(encoding="utf-8")) if REG.exists() else {}
    integrations = []
    for item in registry.get("layers", {}).get("integrations", []):
        path = ROOT / item["path"]
        integrations.append(
            {
                "id": item["id"],
                "path": item["path"],
                "populated": integration_ready(path),
                "policy_exists": (ROOT / item["policy"]).exists() if item.get("policy") else False,
            }
        )

    pr2_scan_server = (ROOT / "server/workspaces/index.ts").exists()
    connectome_ok = False
    connectome_detail = ""
    try:
        out = subprocess.check_output(
            [sys.executable, str(ROOT / "scripts" / "connectome-check.py"), "--json"],
            text=True,
        )
        report = json.loads(out)
        connectome_ok = bool(report.get("ok"))
        connectome_detail = f"senses={report.get('senses')} edges={report.get('edges')}"
    except Exception as exc:  # noqa: BLE001
        connectome_detail = str(exc)

    # Route smoke for daily AGI + enhance gate
    route_ok = True
    route_notes = []
    try:
        daily = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.clock.daily",
                    "--goal",
                    "daily agi scan",
                ],
                text=True,
            )
        )
        if "motor.web_fetch" not in daily.get("motor_plan", []):
            route_ok = False
            route_notes.append("daily scan missing motor.web_fetch")
        if daily.get("switch_state", {}).get("switch.cam_enhance") != "hold":
            route_ok = False
            route_notes.append("cam_enhance should default hold")
        hold = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.chat.aaron",
                    "--hotspot",
                    "hotspot.cam_enhance",
                    "--goal",
                    "apply enhance",
                ],
                text=True,
            )
        )
        if "motor.enhance" in hold.get("motor_plan", []):
            route_ok = False
            route_notes.append("enhance motor fired without --enhance")
        scholar = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.web.scholar",
                    "--goal",
                    "scholar search",
                ],
                text=True,
            )
        )
        if "motor.web_fetch" not in scholar.get("motor_plan", []):
            route_ok = False
            route_notes.append("scholar pathway missing motor.web_fetch")
        if scholar.get("hotspot_id") != "hotspot.google_scholar":
            route_ok = False
            route_notes.append("scholar sense should hit hotspot.google_scholar")
        public_apis = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.catalog.public_apis",
                    "--goal",
                    "find free weather api",
                ],
                text=True,
            )
        )
        if "motor.public_apis" not in public_apis.get("motor_plan", []):
            route_ok = False
            route_notes.append("public-apis pathway missing motor.public_apis")
        if public_apis.get("hotspot_id") != "hotspot.public_apis":
            route_ok = False
            route_notes.append("public-apis sense should hit hotspot.public_apis")
    except Exception as exc:  # noqa: BLE001
        route_ok = False
        route_notes.append(str(exc))

    soft = []
    hard_errors = []
    if not pr2_scan_server:
        soft.append("PR#2 scan workspaces (server/workspaces) not in this checkout yet")
    else:
        agi_mod = ROOT / "server/workspaces/agi-research.ts"
        if not agi_mod.exists():
            hard_errors.append("missing:server/workspaces/agi-research.ts")
        types_txt = (ROOT / "shared/types.ts").read_text(encoding="utf-8")
        if "agi_research" not in types_txt:
            hard_errors.append("missing_workspace_kind:agi_research")
    for integ in integrations:
        if not integ["populated"]:
            soft.append(f"integration empty: {integ['path']} (submodule init or create config)")
        if not integ["policy_exists"]:
            soft.append(f"missing policy for {integ['id']}")

    hard_errors += [f"missing:{p}" for p in hard_missing]
    hard_errors += [f"persist_export_missing:{p}" for p in persist_gaps]
    hard_errors += [f"mesh_flag_off:{k}" for k in flag_gaps]
    if not connectome_ok:
        hard_errors.append(f"connectome_check_failed:{connectome_detail}")
    if not route_ok:
        hard_errors += [f"route:{n}" for n in route_notes]

    report = {
        "ok": not hard_errors,
        "hard_errors": hard_errors,
        "soft_warnings": soft,
        "mesh_flags": flags,
        "integrations": integrations,
        "pr2_scan_workspaces_present": pr2_scan_server,
        "connectome": {"ok": connectome_ok, "detail": connectome_detail},
        "routes_ok": route_ok,
        "registry": str(REG.relative_to(ROOT)) if REG.exists() else None,
        "suggested_merge_order": ["PR#4 (this)", "PR#2 scan workspaces", "PR#3 Brodmann viz rebase"],
    }

    out_path = ROOT / "vault/10-Mesh-Distillates/workspace-integration-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"workspace-integration-check: {status}")
        for e in hard_errors[:20]:
            print(f"  HARD {e}")
        for w in soft[:20]:
            print(f"  SOFT {w}")
        print(f"  connectome={connectome_detail} routes_ok={route_ok} pr2={pr2_scan_server}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
