#!/usr/bin/env python3
"""Cam hand gestures — list, explain, resolve, teach, forget, doctor.

    python3 scripts/cam-gestures.py list --context reading
    python3 scripts/cam-gestures.py explain gesture.handoff_grab
    python3 scripts/cam-gestures.py resolve --context home --identity \
        --segments "open_palm:hold:300,closed_fist:hold:200,closed_fist:translate_out:400"
    python3 scripts/cam-gestures.py teach --by Aaron --name "fist pump" \
        --meaning "next song" --action nav.page_next --context gallery \
        --steps "closed_fist:raise:300"
    python3 scripts/cam-gestures.py doctor

Segments are ``pose[:motion[:duration_ms[:confidence[:hands]]]]`` — what the
companion PWA recognizer emits after MediaPipe labels + landmark motion. No
camera frames are read here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_gestures as cg  # noqa: E402


def _parse_steps(text: str) -> list[dict]:
    steps = []
    for chunk in [c for c in text.split(",") if c.strip()]:
        seg = cg.Segment.parse(chunk.strip())
        step = {"pose": seg.pose, "motion": seg.motion, "min_ms": seg.duration_ms}
        steps.append(step)
    return steps


def _parse_segments(text: str, gap_ms: int = 50) -> list[cg.Segment]:
    t = 0
    out = []
    for chunk in [c for c in text.split(",") if c.strip()]:
        seg = cg.Segment.parse(chunk.strip(), t_ms=t)
        out.append(seg)
        t = seg.end_ms + gap_ms
    return out


def cmd_list(args: argparse.Namespace) -> int:
    rows = cg.catalog(context=args.context)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    for r in rows:
        flag = " [Aaron-only]" if r["aaron_only"] else ""
        print(f"{r['gesture']:<32} {r['how']}")
        print(f"    means: {r['meaning']}")
        print(f"    does:  {r['action']}{flag} — {r['does']}")
        print(f"    in:    {', '.join(r['contexts'])}  ({r['support']}, {r['source']})")
    learned = cg.load_learned()
    if learned["bindings"]:
        print(f"\nlearned ({len(learned['bindings'])}):")
        for b in learned["bindings"]:
            print(f"  {b['id']:<30} {b['meaning']} → {b['action']} in {b['contexts']} (taught {b['taught_at'][:10]})")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    vocab = cg.load_vocabulary()
    actions = {a["id"]: a for a in cg.load_actions()["actions"]}
    g = next((x for x in vocab["gestures"] if x["id"] == args.gesture), None)
    if g is None:
        g = next((b for b in cg.load_learned()["bindings"] if b["id"] == args.gesture), None)
    if g is None:
        print(f"unknown gesture {args.gesture}", file=sys.stderr)
        return 2
    doc = dict(g)
    doc["action_detail"] = actions.get(g.get("action"))
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    segments = _parse_segments(args.segments)
    for s in segments:
        s.device = args.device
    resolver = cg.GestureResolver(
        context=args.context,
        identity_ok=bool(args.identity),
        switch_act=not args.switch_hold,
    )
    intents = resolver.feed_many(segments)
    report = {
        "context_in": args.context,
        "context_out": resolver.context,
        "engaged_until_ms": resolver.engaged_until,
        "carrying": resolver.carry_deadline is not None,
        "segments": [s.__dict__ for s in segments],
        "intents": [i.to_dict() for i in intents],
        "mesh": [cg.pack_intent(i) for i in intents],
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if not intents:
        print("no gesture resolved")
    for i in intents:
        state = "FIRE" if i.fired else "HOLD"
        line = f"{state} {i.gesture} → {i.action}"
        if i.action_params:
            line += f" {json.dumps(i.action_params)}"
        print(line)
        print(f"     means: {i.meaning}")
        if i.hold_reason:
            print(f"     held:  {i.hold_reason} (wanted {i.requested_action})")
    print(f"context: {args.context} → {resolver.context}")
    return 0


def cmd_teach(args: argparse.Namespace) -> int:
    steps = _parse_steps(args.steps) if args.steps else None
    try:
        binding = cg.teach(
            name=args.name,
            meaning=args.meaning,
            action=args.action,
            contexts=args.context or ["*"],
            steps=steps,
            like=args.like,
            by=args.by,
            replace=args.replace,
            samples=args.samples,
            write=not args.dry_run,
        )
    except (PermissionError, ValueError) as exc:
        print(f"teach refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(binding, indent=2, ensure_ascii=False))
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    try:
        gone = cg.forget(args.binding, by=args.by, write=not args.dry_run)
    except (PermissionError, KeyError) as exc:
        print(f"forget refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(gone, indent=2, ensure_ascii=False))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    vocab = cg.load_vocabulary()
    actions = cg.load_actions()
    learned = cg.load_learned()
    errors = cg.validate(vocab, actions, learned)
    flagged = cg.recalibration_flags(learned)
    report = {
        "ok": not errors,
        "gestures": len(vocab["gestures"]),
        "actions": len(actions["actions"]),
        "learned": len(learned["bindings"]),
        "contexts": [c["id"] for c in vocab["contexts"]],
        "canned_labels": vocab["recognizer"]["canned_labels"],
        "needs_recalibration": flagged,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"cam-gestures doctor: {'PASS' if report['ok'] else 'FAIL'}")
        print(
            f"  gestures={report['gestures']} actions={report['actions']} "
            f"learned={report['learned']} recalibrate={flagged}"
        )
        for e in errors:
            print(f"  ERR {e}")
    return 0 if report["ok"] else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="gesture → meaning → action table")
    s.add_argument("--context")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("explain", help="one gesture or learned binding in full")
    s.add_argument("gesture")
    s.set_defaults(fn=cmd_explain)

    s = sub.add_parser("resolve", help="run recognizer segments through the resolver")
    s.add_argument("--segments", required=True)
    s.add_argument("--context", default="home")
    s.add_argument("--identity", action="store_true", help="switch.identity act (Aaron matched)")
    s.add_argument("--switch-hold", action="store_true", help="simulate switch.gesture_control hold")
    s.add_argument("--device")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_resolve)

    s = sub.add_parser("teach", help="Aaron binds a gesture to a meaning + action")
    s.add_argument("--by", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--meaning", required=True)
    s.add_argument("--action", required=True)
    s.add_argument("--context", action="append")
    s.add_argument("--steps", help="pose:motion:min_ms,... (new gesture)")
    s.add_argument("--like", help="existing gesture id whose shape to reuse")
    s.add_argument("--replace", action="store_true")
    s.add_argument("--samples", type=int, default=0)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_teach)

    s = sub.add_parser("forget", help="Aaron removes a learned binding")
    s.add_argument("binding")
    s.add_argument("--by", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_forget)

    s = sub.add_parser("doctor", help="validate the gesture database")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    args = p.parse_args()
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
