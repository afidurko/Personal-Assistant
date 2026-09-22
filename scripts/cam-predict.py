#!/usr/bin/env python3
"""Cam predictive cortex CLI — predict outcomes from Cam's own experiences.

Usage:
  python3 scripts/cam-predict.py --goal "daily agi scan" --sense sense.clock.daily
  python3 scripts/cam-predict.py --hotspot hotspot.loop_engineering --pattern daily-triage
  python3 scripts/cam-predict.py --report                 # prequential calibration report
  python3 scripts/cam-predict.py --report --offline       # fixture only, no repo history
  python3 scripts/cam-predict.py --record --ok --hotspot hotspot.coding --score 88 --notes "..."

Advisory only: nothing here fires motors or changes routing. Acting on a
prediction still needs Aaron via switch.cam_enhance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_experience as ce  # noqa: E402
import cam_inproc  # noqa: E402


def context_from_route(sense: str, goal: str) -> tuple[dict, dict]:
    doc = cam_inproc.route(sense=sense, goal=goal)
    ctx = {
        "sense": sense,
        "hotspot": doc.get("hotspot_id"),
        "center": doc.get("center"),
        "pattern": None,
        "motors": doc.get("motor_plan") or [],
    }
    return ctx, {
        "hotspot_id": doc.get("hotspot_id"),
        "behavior": doc.get("behavior"),
        "motor_plan": doc.get("motor_plan"),
        "accepted": doc.get("accepted"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--goal", default="", help="Aaron goal text — routed through the connectome to derive context")
    p.add_argument("--sense", default="sense.chat.aaron", help="sense.* id used with --goal")
    p.add_argument("--hotspot", default="", help="explicit hotspot id")
    p.add_argument("--center", default="", help="explicit center id")
    p.add_argument("--pattern", default="", help="loop pattern / reasoning path id")
    p.add_argument("--report", action="store_true", help="prequential calibration + per-context report")
    p.add_argument("--record", action="store_true", help="append an experience to data/runtime/experiences.jsonl")
    p.add_argument("--ok", action="store_true", help="recorded outcome succeeded")
    p.add_argument("--fail", action="store_true", help="recorded outcome failed")
    p.add_argument("--score", type=float, default=None, help="recorded score 0-100")
    p.add_argument("--duration", type=float, default=None, help="recorded duration seconds")
    p.add_argument("--notes", default="", help="recorded note")
    p.add_argument("--offline", action="store_true", help="fixture experiences only")
    p.add_argument("--extra", action="append", default=[], help="additional experience JSONL file(s)")
    p.add_argument("--no-write", action="store_true", help="skip vault distillate write")
    p.add_argument("--json", action="store_true", help="JSON only (default output is JSON already)")
    args = p.parse_args()

    if args.record:
        if args.ok == args.fail:
            print(json.dumps({"ok": False, "error": "--record needs exactly one of --ok / --fail"}))
            return 2
        exp = ce.make_experience(
            ok=args.ok,
            source="manual",
            sense=args.sense,
            hotspot=args.hotspot or None,
            center=args.center or None,
            pattern=args.pattern or None,
            score=args.score,
            duration_s=args.duration,
            notes=args.notes,
            ref="scripts/cam-predict.py --record",
        )
        path = ce.record_experience(exp)
        print(json.dumps({"ok": True, "recorded": exp, "path": str(path)}, indent=2))
        return 0

    cfg = ce.load_config()
    extra = [Path(x) for x in args.extra]

    if args.report:
        report = ce.build_report(offline=args.offline, extra=extra, cfg=cfg)
        if not args.no_write and not args.offline:
            report["distillate"] = str(ce.write_distillate(report).relative_to(ROOT))
        print(json.dumps(report, indent=2))
        return 0 if report["experience_count"] >= 0 else 1

    route_info = None
    if args.hotspot or args.center or args.pattern:
        ctx = {
            "sense": args.sense,
            "hotspot": args.hotspot or None,
            "center": args.center or None,
            "pattern": args.pattern or None,
            "motors": [],
        }
    else:
        ctx, route_info = context_from_route(args.sense, args.goal)

    experiences, counts = ce.load_experiences(offline=args.offline, extra=extra)
    ev = ce.prequential(experiences, cfg)
    model: ce.ExperiencePredictor = ev["model"]
    prediction = model.predict(ctx)
    out = {
        "kind": "experience_prediction",
        "at": ce.utc(),
        "goal": args.goal,
        "context": ctx,
        "route": route_info,
        "prediction": prediction,
        "calibration_so_far": {
            k: ev["metrics"].get(k) for k in ("n", "brier", "brier_skill", "ece", "auroc", "mean_surprise")
        },
        "experience_count": len(experiences),
        "sources": counts,
        "offline": args.offline,
        "gate": "advisory_only — switch.cam_enhance required to act on predictions",
    }
    if not args.no_write and not args.offline:
        out["distillate"] = str(ce.write_distillate(out, "last-prediction.json").relative_to(ROOT))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
