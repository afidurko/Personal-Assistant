#!/usr/bin/env python3
"""Confirm MemoryBear is wired throughout Cam (config, connectome, registry, mesh).

Does not require a live MemoryBear server. Exit 0 only when hard requirements pass.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HARD_PATHS = [
    "config/integrations/memorybear.json",
    "config/integrations/memorybear.md",
    "scripts/memorybear.py",
    "scripts/pack-memorybear-result.py",
    "scripts/testdata/sample-memorybear-read.json",
    "vault/10-Mesh-Distillates/memorybear/README.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    hard: list[str] = []
    soft: list[str] = []

    for rel in HARD_PATHS:
        if not (ROOT / rel).exists():
            hard.append(f"missing:{rel}")

    cfg_path = ROOT / "config/integrations/memorybear.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    if cfg.get("sense") != "sense.memorybear.hit":
        hard.append("config_sense_mismatch")
    if cfg.get("motor") != "motor.memorybear":
        hard.append("config_motor_mismatch")

    sensory = json.loads((ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8"))
    motor = json.loads((ROOT / "config/connectome/motor.json").read_text(encoding="utf-8"))
    hotspots = json.loads((ROOT / "config/connectome/hotspots.json").read_text(encoding="utf-8"))
    sense_ids = {n["id"] for n in sensory.get("neurons", [])}
    motor_ids = {e["id"] for e in motor.get("effectors", [])}
    hotspot_ids = {h["id"] for h in hotspots.get("hotspots", [])}
    if "sense.memorybear.hit" not in sense_ids:
        hard.append("missing_sense:sense.memorybear.hit")
    if "motor.memorybear" not in motor_ids:
        hard.append("missing_motor:motor.memorybear")
    for hid in ("hotspot.memorybear_recall", "hotspot.memorybear_write"):
        if hid not in hotspot_ids:
            hard.append(f"missing_hotspot:{hid}")

    registry = json.loads((ROOT / "config/workspaces/registry.json").read_text(encoding="utf-8"))
    integ_ids = {i["id"] for i in registry.get("layers", {}).get("integrations", [])}
    coding_ids = {w["id"] for w in registry.get("layers", {}).get("coding_workspaces", [])}
    if "memorybear" not in integ_ids:
        hard.append("registry_integrations_missing_memorybear")
    if "memorybear" not in coding_ids:
        hard.append("registry_coding_workspaces_missing_memorybear")

    seed = json.loads((ROOT / "identity/persistence/mesh-seed.json").read_text(encoding="utf-8"))
    mb = seed.get("mesh/memorybear") or {}
    if not mb.get("enabled"):
        hard.append("mesh_flag_off:memorybear")
    if not (seed.get("mesh/facts") or {}).get("memorybear_cognitive_memory"):
        soft.append("mesh/facts.memorybear_cognitive_memory not set")

    # Route smoke
    route_ok = True
    route_notes: list[str] = []
    try:
        recall = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts/connectome-route.py"),
                    "--sense",
                    "sense.memorybear.hit",
                    "--goal",
                    "memorybear recall",
                ],
                text=True,
            )
        )
        if "motor.memorybear" not in recall.get("motor_plan", []):
            route_ok = False
            route_notes.append("recall pathway missing motor.memorybear")
        if recall.get("hotspot_id") != "hotspot.memorybear_recall":
            route_ok = False
            route_notes.append("sense should hit hotspot.memorybear_recall")
    except Exception as exc:  # noqa: BLE001
        route_ok = False
        route_notes.append(str(exc))

    if not route_ok:
        hard += [f"route:{n}" for n in route_notes]

    # Offline client smoke
    try:
        doctor = json.loads(
            subprocess.check_output(
                [sys.executable, str(ROOT / "scripts/memorybear.py"), "--doctor", "--offline"],
                text=True,
            )
        )
        if not doctor.get("ok"):
            hard.append("offline_doctor_failed")
    except Exception as exc:  # noqa: BLE001
        hard.append(f"offline_doctor_error:{exc}")

    sub_dir = ROOT / "integrations" / "memorybear"
    if not sub_dir.exists():
        soft.append("integrations/memorybear dir missing (gitlink ok until init)")
    elif not any(p.name != ".git" for p in sub_dir.iterdir()):
        soft.append("integrations/memorybear empty until git submodule update --init")

    report = {
        "ok": not hard,
        "hard_errors": hard,
        "soft_warnings": soft,
        "config_id": cfg.get("id"),
        "mesh": mb,
    }
    out = ROOT / "vault/10-Mesh-Distillates/memorybear/check-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"memorybear-check: {status}")
        for e in hard[:20]:
            print(f"  HARD {e}")
        for w in soft[:20]:
            print(f"  SOFT {w}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
