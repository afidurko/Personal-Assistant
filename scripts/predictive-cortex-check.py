#!/usr/bin/env python3
"""Confirm predictive-cortex wiring for Cam (config, connectome, tools, smoke).

Static + offline: loads the fixture experience stream, runs the prequential
evaluation, predicts one context, and checks the connectome route. No network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    cfg_path = ROOT / "config/enhancement/predictive-cortex.json"
    if not cfg_path.exists():
        errors.append("missing config/enhancement/predictive-cortex.json")
    cfg = load(cfg_path) if cfg_path.exists() else {}

    for key in ("library", "cli", "check", "tests", "fixture", "plan_doc", "proposal", "research_plan"):
        rel = cfg.get(key)
        if not rel:
            errors.append(f"config missing key:{key}")
        elif not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")
    for rel in cfg.get("briefs") or []:
        if not (ROOT / rel).exists():
            errors.append(f"missing brief:{rel}")

    sense_id = cfg.get("sense") or "sense.experience.outcome"
    hotspot_id = cfg.get("hotspot") or "hotspot.predict_from_experience"
    text = (ROOT / "config/connectome/sensory.json").read_text(encoding="utf-8")
    if sense_id not in text:
        errors.append(f"missing {sense_id}")
    hs = load(ROOT / "config/connectome/hotspots.json")
    hot = next((h for h in hs["hotspots"] if h["id"] == hotspot_id), None)
    if not hot:
        errors.append(f"missing {hotspot_id}")
    elif hot["pathway"][0] != sense_id or "motor.dl" not in hot["pathway"]:
        errors.append("hotspot pathway must run sense.experience.outcome → … → motor.dl")
    motor = load(ROOT / "config/connectome/motor.json")
    dl = next((e for e in motor["effectors"] if e["id"] == "motor.dl"), None)
    if not dl or "experience_predict" not in (dl.get("channel") or []):
        errors.append("motor.dl missing experience_predict channel")
    neurons = load(ROOT / "config/connectome/neurons.json")
    if not any(n["id"] == "neuron.predict_experience" for n in neurons["neurons"]):
        errors.append("missing neuron.predict_experience")
    syn = (ROOT / "config/connectome/synapses.json").read_text(encoding="utf-8")
    if sense_id not in syn:
        errors.append(f"missing synapse from {sense_id}")

    tools = load(ROOT / "config/tools/registry.json")
    if "tool.predict.experience" not in [t.get("id") for t in tools.get("tools") or []]:
        errors.append("tools registry missing tool.predict.experience")
    pieces = load(ROOT / "config/system/pieces.json")
    if "piece.predictive_cortex" not in [p.get("id") for p in pieces.get("pieces") or []]:
        errors.append("pieces.json missing piece.predictive_cortex")
    slm_dl = (ROOT / "config/enhancement/slm-dl.json").read_text(encoding="utf-8")
    if "experience_outcome_predict" not in slm_dl:
        soft.append("slm-dl.json does not list experience_outcome_predict job")
    team = (ROOT / "config/teams/agi-research-scan.json").read_text(encoding="utf-8")
    if "enhance_predictive_cortex" not in team:
        soft.append("agi-research-scan rubric lacks enhance_predictive_cortex")
    mcp = (ROOT / "scripts/cam-mcp-server.py").read_text(encoding="utf-8")
    if "predict_experience" not in mcp:
        soft.append("MCP server lacks predict_experience tool")

    # offline smoke — fixture stream, prequential metrics, one prediction
    smoke: dict = {}
    try:
        import cam_experience as ce

        exps, counts = ce.load_experiences(offline=True)
        if len(exps) < 20:
            errors.append(f"fixture too small: {len(exps)}")
        ev = ce.prequential(exps, ce.load_config())
        metrics = ev["metrics"]
        if metrics.get("n") != len(exps):
            errors.append("prequential n != experience count")
        for k in ("brier", "ece", "log_loss"):
            v = metrics.get(k)
            if not isinstance(v, (int, float)) or v < 0:
                errors.append(f"bad metric {k}={v}")
        if not (0.0 <= float(metrics.get("brier", 1.0)) <= 1.0):
            errors.append("brier out of range")
        pred = ev["model"].predict({"hotspot": "hotspot.loop_engineering", "center": "center.qa", "sense": "sense.loop.tick", "pattern": "daily-triage"})
        p = pred["p_success"]
        lo, hi = pred["credible_interval"]
        if not (0.0 <= lo <= p <= hi <= 1.0):
            errors.append(f"prediction interval inconsistent: {lo} {p} {hi}")
        if pred["evidence_level"] == "prior":
            errors.append("fixture prediction fell back to prior")
        smoke = {
            "experiences": len(exps),
            "sources": counts,
            "brier": metrics.get("brier"),
            "brier_skill": metrics.get("brier_skill"),
            "ece": metrics.get("ece"),
            "auroc": metrics.get("auroc"),
            "p_success_daily_triage": p,
            "credible_interval": [lo, hi],
            "evidence_level": pred["evidence_level"],
        }
    except Exception as exc:  # noqa: BLE001
        errors.append(f"smoke:{exc}")

    try:
        import cam_inproc

        route = cam_inproc.route(sense=sense_id, goal="predict outcome from experience")
        if route.get("hotspot_id") != hotspot_id:
            errors.append(f"route should hit {hotspot_id}, got {route.get('hotspot_id')}")
        if "motor.dl" not in route.get("motor_plan", []):
            errors.append("route missing motor.dl")
        if route.get("missing_explicit_edges"):
            errors.append(f"route missing edges: {route['missing_explicit_edges']}")
        # predictions must never arm enhance
        if "motor.enhance" in route.get("motor_plan", []):
            errors.append("predictive route must not plan motor.enhance")
        killed = cam_inproc.route(sense=sense_id, goal="predict", kill=True)
        if killed.get("motor_plan"):
            errors.append("kill switch did not silence predictive route")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"route_smoke:{exc}")

    report = {
        "ok": not errors,
        "hard_errors": errors,
        "soft_warnings": soft,
        "integration": "predictive-cortex",
        "status": cfg.get("status"),
        "act_gate": cfg.get("act_gate"),
        "smoke": smoke,
    }
    out_path = ROOT / "vault/10-Mesh-Distillates/predictive-cortex/check-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
