#!/usr/bin/env python3
"""Confirm Aaron-only voice gate wiring (noisy-room filter)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HARD = [
    "config/identity/aaron-voice-gate.json",
    "src/lib/aaronVoiceGate.ts",
    "src/hooks/useCamVoice.ts",
    "companions/web/voice-gate.js",
    "companions/web/app.js",
    "server/core/aaron-voice-gate.ts",
    "server/core/aaron-voice-gate-addons.ts",
    "server/core/cam-converse.ts",
    "scripts/pack-aaron-voice-profile.py",
    "companions/ios/CamVoiceGate.swift",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    hard: list[str] = []
    soft: list[str] = []

    for rel in HARD:
        if not (ROOT / rel).exists():
            hard.append(f"missing:{rel}")

    cfg = json.loads((ROOT / "config/identity/aaron-voice-gate.json").read_text(encoding="utf-8"))
    if not cfg.get("aaron_only"):
        hard.append("config_aaron_only_false")
    if not cfg.get("noisy_environment_mode"):
        hard.append("config_noisy_mode_false")
    addons = cfg.get("addons") or {}
    for key in (
        "adaptive_noise",
        "profile_export",
        "reject_stats",
        "health_pulse",
        "ios_speaker_id",
    ):
        if key not in addons:
            hard.append(f"missing_addon:{key}")

    sensory = json.loads((ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8"))
    if "sense.aaron.voice" not in {n["id"] for n in sensory["neurons"]}:
        hard.append("missing_sense:sense.aaron.voice")

    neurons = json.loads((ROOT / "config/connectome/neurons.json").read_text(encoding="utf-8"))
    if "neuron.aaron_voice_gate" not in {n["id"] for n in neurons["neurons"]}:
        hard.append("missing_neuron:neuron.aaron_voice_gate")

    hotspots = json.loads((ROOT / "config/connectome/hotspots.json").read_text(encoding="utf-8"))
    ids = {h["id"] for h in hotspots["hotspots"]}
    if "hotspot.aaron_voice" not in ids:
        hard.append("missing_hotspot:hotspot.aaron_voice")
    if "hotspot.aaron_voice_noise" not in ids:
        hard.append("missing_hotspot:hotspot.aaron_voice_noise")

    app_js = (ROOT / "companions/web/app.js").read_text(encoding="utf-8")
    if "CamAaronVoiceGate" not in app_js and "gateUtterance" not in app_js:
        hard.append("web_companion_missing_gate")
    if "btnExport" not in app_js:
        soft.append("web_companion_missing_export_ui")

    hook = (ROOT / "src/hooks/useCamVoice.ts").read_text(encoding="utf-8")
    if "decideAaronVoiceGate" not in hook:
        hard.append("react_hook_missing_gate")
    if "exportProfile" not in hook:
        soft.append("react_hook_missing_export")

    ios = (ROOT / "companions/ios/CamVoiceGate.swift").read_text(encoding="utf-8")
    if "aaron_voice_score" not in ios:
        hard.append("ios_contract_missing_score_field")

    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import cam_inproc

        route = cam_inproc.route(
            sense="sense.aaron.voice",
            hotspot="hotspot.aaron_voice_noise",
            goal="filter room noise",
        )
        if route.get("hotspot_id") != "hotspot.aaron_voice_noise":
            hard.append("route_hotspot_mismatch")
    except Exception as exc:  # noqa: BLE001
        hard.append(f"route_error:{exc}")

    seed = json.loads((ROOT / "identity/persistence/mesh-seed.json").read_text(encoding="utf-8"))
    facts = seed.get("mesh/facts") or {}
    if not facts.get("aaron_voice_only_in_noise"):
        soft.append("mesh/facts.aaron_voice_only_in_noise not set")

    report = {
        "ok": not hard,
        "hard_errors": hard,
        "soft_warnings": soft,
        "config": cfg.get("id"),
        "addons": sorted(addons.keys()),
    }
    out = ROOT / "vault/10-Mesh-Distillates/aaron-voice-gate-check-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"aaron-voice-gate-check: {'PASS' if report['ok'] else 'FAIL'}")
        for e in hard[:20]:
            print(f"  HARD {e}")
        for w in soft[:20]:
            print(f"  SOFT {w}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
