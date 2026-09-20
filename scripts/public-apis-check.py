#!/usr/bin/env python3
"""Confirm public-apis wiring for all Cam agents.

Checks config, connectome nodes, scripts, registry, tools entry, and a smoke
search against the local catalog or fixture. No network required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def has_id(items: list, node_id: str) -> bool:
    return any(isinstance(x, dict) and x.get("id") == node_id for x in items)


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    cfg_path = ROOT / "config/integrations/public-apis.json"
    md_path = ROOT / "config/integrations/public-apis.md"
    if not cfg_path.exists():
        errors.append("missing config/integrations/public-apis.json")
    if not md_path.exists():
        errors.append("missing config/integrations/public-apis.md")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    for script in ("search", "pack", "check"):
        rel = (cfg.get("scripts") or {}).get(script) or f"scripts/public-apis-{script}.py"
        if script == "pack":
            rel = (cfg.get("scripts") or {}).get("pack") or "scripts/pack-public-apis-result.py"
        if script == "check":
            rel = (cfg.get("scripts") or {}).get("check") or "scripts/public-apis-check.py"
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    sensory = load(ROOT / "config/connectome/sensory.json")
    motor = load(ROOT / "config/connectome/motor.json")
    hotspots = load(ROOT / "config/connectome/hotspots.json")
    synapses = load(ROOT / "config/connectome/synapses.json")

    if not has_id(sensory.get("senses") or sensory.get("nodes") or [], "sense.catalog.public_apis"):
        # sensory.json uses "inputs" or top-level list — detect structure
        senses = sensory.get("senses") or sensory.get("inputs") or sensory.get("nodes")
        if senses is None and isinstance(sensory.get("items"), list):
            senses = sensory["items"]
        # Fall back: scan raw text
        text = (ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8")
        if "sense.catalog.public_apis" not in text:
            errors.append("missing sense.catalog.public_apis")
    text_motor = (ROOT / "config/connectome/motor.json").read_text(encoding="utf-8")
    if "motor.public_apis" not in text_motor:
        errors.append("missing motor.public_apis")
    text_hot = (ROOT / "config/connectome/hotspots.json").read_text(encoding="utf-8")
    if "hotspot.public_apis" not in text_hot:
        errors.append("missing hotspot.public_apis")
    text_syn = (ROOT / "config/connectome/synapses.json").read_text(encoding="utf-8")
    if "sense.catalog.public_apis" not in text_syn:
        errors.append("missing synapse from sense.catalog.public_apis")

    reg = load(ROOT / "config/workspaces/registry.json")
    integ_ids = [i.get("id") for i in (reg.get("layers") or {}).get("integrations") or []]
    if "public-apis" not in integ_ids:
        errors.append("registry missing public-apis integration")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    if "tool.public_apis.search" not in tool_ids:
        errors.append("tools registry missing tool.public_apis.search")
    if "tool.public_apis.addon" not in tool_ids:
        errors.append("tools registry missing tool.public_apis.addon")

    addons_path = ROOT / "config/integrations/public-apis-addons.json"
    if not addons_path.exists():
        errors.append("missing config/integrations/public-apis-addons.json")
    else:
        addons = load(addons_path)
        if not addons.get("addons"):
            errors.append("public-apis-addons.json has empty addons list")
        try:
            doctor = json.loads(
                subprocess.check_output(
                    [sys.executable, str(ROOT / "scripts/public-apis-addon.py"), "doctor"],
                    text=True,
                )
            )
            if not doctor.get("ok"):
                errors.append(f"addon_doctor:{doctor}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"addon_doctor:{exc}")

    for team in ("info", "tooling", "capability", "agi-research-scan"):
        tpath = ROOT / f"config/teams/{team}.json"
        raw = tpath.read_text(encoding="utf-8")
        if "public-apis" not in raw and "public_apis" not in raw:
            soft.append(f"team {team} does not mention public-apis")

    catalog = ROOT / "integrations/public-apis/README.md"
    if not catalog.exists():
        soft.append("submodule README empty — using fixture until git submodule update --init")

    # Smoke search (offline fixture always works)
    try:
        out = subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "scripts/public-apis-search.py"),
                "--query",
                "weather",
                "--offline",
                "--num",
                "3",
            ],
            text=True,
        )
        payload = json.loads(out)
        if not payload.get("results"):
            errors.append("offline search returned no results")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"search_smoke:{exc}")

    # Route smoke (in-process)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import cam_inproc

        route = cam_inproc.route(
            sense="sense.catalog.public_apis",
            goal="find free weather api",
        )
        if "motor.public_apis" not in route.get("motor_plan", []):
            errors.append("route missing motor.public_apis")
        if route.get("hotspot_id") != "hotspot.public_apis":
            errors.append("route should hit hotspot.public_apis")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"route_smoke:{exc}")

    report = {
        "ok": not errors,
        "hard_errors": errors,
        "soft_warnings": soft,
        "integration": "public-apis",
        "available_to": cfg.get("available_to"),
        "teams": cfg.get("teams"),
    }
    out_path = ROOT / "vault/10-Mesh-Distillates/public-apis/check-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
