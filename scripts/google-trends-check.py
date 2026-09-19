#!/usr/bin/env python3
"""Confirm google-trends wiring for Cam agents.

Checks config, connectome nodes, scripts, registry, tools entry, and a smoke
search against the offline fixture. No network required.
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

    cfg_path = ROOT / "config/integrations/google-trends.json"
    md_path = ROOT / "config/integrations/google-trends.md"
    if not cfg_path.exists():
        errors.append("missing config/integrations/google-trends.json")
    if not md_path.exists():
        errors.append("missing config/integrations/google-trends.md")

    cfg = load(cfg_path) if cfg_path.exists() else {}
    for key, default in (
        ("search", "scripts/google-trends-search.py"),
        ("pack", "scripts/pack-google-trends-result.py"),
        ("check", "scripts/google-trends-check.py"),
    ):
        rel = (cfg.get("scripts") or {}).get(key) or default
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    fixture = ROOT / (
        cfg.get("fixture") or "scripts/testdata/sample-google-trends-catalog.json"
    )
    if not fixture.exists():
        errors.append("missing offline fixture")

    text_sense = (ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8")
    if "sense.catalog.google_trends" not in text_sense:
        errors.append("missing sense.catalog.google_trends")
    text_motor = (ROOT / "config/connectome/motor.json").read_text(encoding="utf-8")
    if "motor.google_trends" not in text_motor:
        errors.append("missing motor.google_trends")
    text_hot = (ROOT / "config/connectome/hotspots.json").read_text(encoding="utf-8")
    if "hotspot.google_trends" not in text_hot:
        errors.append("missing hotspot.google_trends")
    text_syn = (ROOT / "config/connectome/synapses.json").read_text(encoding="utf-8")
    if "sense.catalog.google_trends" not in text_syn:
        errors.append("missing synapse from sense.catalog.google_trends")
    if "motor.google_trends" not in text_syn:
        errors.append("missing synapse involving motor.google_trends")

    reg = load(ROOT / "config/workspaces/registry.json")
    integ_ids = [i.get("id") for i in (reg.get("layers") or {}).get("integrations") or []]
    if "google-trends" not in integ_ids:
        errors.append("registry missing google-trends integration")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    if "tool.google_trends.search" not in tool_ids:
        errors.append("tools registry missing tool.google_trends.search")
    if "tool.google_trends.addon" not in tool_ids:
        errors.append("tools registry missing tool.google_trends.addon")

    addons_path = ROOT / "config/integrations/google-trends-addons.json"
    if not addons_path.exists():
        errors.append("missing config/integrations/google-trends-addons.json")
    else:
        addons = load(addons_path)
        if not addons.get("addons"):
            errors.append("google-trends-addons.json has empty addons list")
        try:
            doctor = json.loads(
                subprocess.check_output(
                    [sys.executable, str(ROOT / "scripts/google-trends-addon.py"), "doctor"],
                    text=True,
                )
            )
            if not doctor.get("ok"):
                errors.append(f"addon_doctor:{doctor}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"addon_doctor:{exc}")

    for team in ("info", "capability", "agi-research-scan"):
        tpath = ROOT / f"config/teams/{team}.json"
        raw = tpath.read_text(encoding="utf-8")
        if "google-trends" not in raw and "google_trends" not in raw:
            soft.append(f"team {team} does not mention google-trends")

    try:
        out = subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "scripts/google-trends-search.py"),
                "--query",
                "election",
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

    try:
        route = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.catalog.google_trends",
                    "--goal",
                    "google trends election dataset",
                ],
                text=True,
            )
        )
        if "motor.google_trends" not in route.get("motor_plan", []):
            errors.append("route missing motor.google_trends")
        if route.get("hotspot_id") != "hotspot.google_trends":
            errors.append("route should hit hotspot.google_trends")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"route_smoke:{exc}")

    report = {
        "ok": not errors,
        "hard_errors": errors,
        "soft_warnings": soft,
        "integration": "google-trends",
        "available_to": cfg.get("available_to"),
        "teams": cfg.get("teams"),
        "source_repo": cfg.get("remote"),
    }
    out_path = ROOT / "vault/10-Mesh-Distillates/google-trends/check-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
