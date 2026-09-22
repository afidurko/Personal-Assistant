#!/usr/bin/env python3
"""Confirm hand-gesture wiring for Cam (no camera, no network).

Validates the gesture database (config/gestures/*.json), connectome nodes,
Sentinel class, trajectory policies, tools + workspace registries, and that
the resolver still turns the canonical Huawei-style grab → carry → release
into a handoff. Exit 0 only when hard requirements pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_gestures as cg  # noqa: E402


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def resolver_demos() -> tuple[list[dict], list[str]]:
    """Deterministic scenarios that must keep resolving the same way."""
    errors: list[str] = []
    demos: list[dict] = []

    def run(name: str, context: str, identity: bool, switch_act: bool, segs: list[str], expect: list[tuple[str, bool]]):
        t = 0
        segments = []
        for s in segs:
            seg = cg.Segment.parse(s, t_ms=t)
            segments.append(seg)
            t = seg.end_ms + 50
        r = cg.GestureResolver(context=context, identity_ok=identity, switch_act=switch_act)
        got = [(i.action, i.fired) for i in r.feed_many(segments)]
        ok = got == expect
        if not ok:
            errors.append(f"resolver_demo_failed:{name}:{got}")
        demos.append({"case": name, "context_out": r.context, "got": got, "ok": ok})

    run(
        "grab_release_collapses",
        "home", True, True,
        ["open_palm:hold:300", "closed_fist:hold:200", "open_palm:hold:150"],
        [("system.engage", True), ("ui.collapse", True)],
    )
    run(
        "fist_burst_expands",
        "home", False, True,
        ["closed_fist:hold:300", "open_palm:push_in:300"],
        [("ui.expand", True)],
    )
    run(
        "huawei_air_transfer_iphone_to_ipad",
        "home", True, True,
        ["open_palm:hold:300", "closed_fist:hold:200", "closed_fist:translate_out:400", "closed_fist:hold:400", "open_palm:hold:250"],
        [("system.engage", True), ("device.handoff_grab", True), ("device.handoff_release", True)],
    )
    run(
        "handoff_needs_aaron",
        "home", False, True,
        ["open_palm:hold:300", "closed_fist:hold:200", "closed_fist:translate_out:400"],
        [("system.engage", True), ("system.log_only", False)],
    )
    run(
        "switch_hold_logs_only",
        "reading", True, False,
        ["open_palm:hold:400", "open_palm:flick_down:200"],
        [("system.log_only", False), ("system.log_only", False)],
    )
    run(
        "stop_only_while_speaking",
        "speaking", False, True,
        ["open_palm:hold:1000"],
        [("converse.stop", True)],
    )
    run(
        "thumb_up_is_yes_in_prompt",
        "prompt", True, True,
        ["thumb_up:hold:600"],
        [("converse.confirm", True)],
    )
    run(
        "two_palms_hold_everything",
        "home", True, True,
        ["open_palm:hold:1200:0.95:2"],
        [("presence.hold_all", True)],
    )
    return demos, errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    errors: list[str] = []
    soft: list[str] = []

    for rel in (
        "config/gestures/gestures.json",
        "config/gestures/actions.json",
        "config/integrations/hand-gestures.json",
        "config/integrations/hand-gestures.md",
        "docs/HAND_GESTURES.md",
        "scripts/cam_gestures.py",
        "scripts/cam-gestures.py",
    ):
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    vocab = cg.load_vocabulary()
    actions = cg.load_actions()
    learned = cg.load_learned()
    errors.extend(cg.validate(vocab, actions, learned))

    # Aaron's named use cases must exist in the vocabulary.
    action_ids = {g["action"] for g in vocab["gestures"]}
    for must in ("ui.collapse", "ui.expand", "device.handoff_grab", "device.handoff_release", "system.engage"):
        if must not in action_ids:
            errors.append(f"vocabulary_missing_use_case:{must}")
    if not any(g.get("source") == "huawei" for g in vocab["gestures"]):
        errors.append("no_huawei_parity_gestures")

    for rel, needle in (
        ("config/connectome/sensory.json", "sense.vision.gesture"),
        ("config/connectome/motor.json", "motor.gesture"),
        ("config/connectome/hotspots.json", "hotspot.gesture"),
        ("config/connectome/synapses.json", "sense.vision.gesture"),
        ("config/connectome/switches.json", "switch.gesture_control"),
        ("config/connectome/trajectory-policies.json", "gesture_requires_aaron_identity"),
        ("config/connectome/trajectory-policies.json", "gesture_never_outbound"),
        ("config/connectome/sentinel-policy.json", "motor.gesture"),
    ):
        if needle not in (ROOT / rel).read_text(encoding="utf-8"):
            errors.append(f"missing {needle} in {rel}")

    motors = load("config/connectome/motor.json")["effectors"]
    gesture_motor = next((e for e in motors if e["id"] == "motor.gesture"), None)
    if gesture_motor is None:
        errors.append("motor.gesture missing")
    else:
        for req in ("switch.gesture_control", "switch.identity", "switch.kill"):
            if req not in gesture_motor.get("requires_switch", []):
                errors.append(f"motor.gesture missing requires_switch:{req}")

    switches = load("config/connectome/switches.json")["switches"]
    gsw = next((s for s in switches if s["id"] == "switch.gesture_control"), None)
    if gsw and not str(gsw.get("default", "")).startswith("hold"):
        soft.append("switch.gesture_control is not hold — Aaron enabled live gesture control")

    reg = load("config/workspaces/registry.json")
    integ_ids = [i.get("id") for i in (reg.get("layers") or {}).get("integrations") or []]
    if "hand-gestures" not in integ_ids:
        errors.append("registry missing hand-gestures integration")

    # Aaron's repos: submodule declared, registered, and mapped onto the vocabulary.
    gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    coding_ids = [w.get("id") for w in (reg.get("layers") or {}).get("coding_workspaces") or []]
    repos = {k: v for k, v in (vocab.get("repos") or {}).items() if isinstance(v, dict)}
    repo_status: dict[str, str] = {}
    for rid, spec in repos.items():
        rel = spec.get("path") or f"integrations/{rid}"
        if rel not in gitmodules:
            errors.append(f".gitmodules missing {rel}")
        if rid not in integ_ids:
            errors.append(f"registry integrations missing {rid}")
        if rid not in coding_ids:
            errors.append(f"registry coding_workspaces missing {rid}")
        sub = ROOT / rel
        entries = [p for p in sub.iterdir() if p.name not in {".git", ".gitignore"}] if sub.exists() else []
        repo_status[rid] = "populated" if entries else "empty"
        if not entries:
            soft.append(f"{rel} empty — run git submodule update --init")
    if repo_status.get("hagrid") == "populated":
        consts = (ROOT / "integrations/hagrid/constants.py").read_text(encoding="utf-8")
        for label in repos["hagrid"].get("labels") or []:
            if f'"{label}"' not in consts:
                errors.append(f"hagrid_label_not_in_constants:{label}")
    if repo_status.get("hand-gesture-mediapipe") == "populated":
        model = ROOT / "integrations/hand-gesture-mediapipe/model"
        kp = (model / "keypoint_classifier/keypoint_classifier_label.csv").read_text(encoding="utf-8-sig").split()
        ph = [l.strip() for l in (model / "point_history_classifier/point_history_classifier_label.csv").read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        spec = repos["hand-gesture-mediapipe"]
        if sorted(kp) != sorted(spec.get("keypoint_labels") or []):
            errors.append(f"hand-gesture-mediapipe keypoint labels drifted: {kp}")
        if sorted(ph) != sorted(spec.get("point_history_labels") or []):
            errors.append(f"hand-gesture-mediapipe point-history labels drifted: {ph}")

    tools = load("config/tools/registry.json")
    tool_ids = [t.get("id") for t in tools.get("tools") or []]
    for tid in ("tool.gesture.resolve", "tool.gesture.check"):
        if tid not in tool_ids:
            errors.append(f"tools registry missing {tid}")

    pieces = load("config/system/pieces.json")
    if not any(pc.get("id") == "piece.gestures" for pc in pieces.get("pieces") or []):
        errors.append("pieces.json missing piece.gestures")

    seed = load("identity/persistence/mesh-seed.json")
    if not (seed.get("mesh/gestures") or {}).get("vocabulary"):
        soft.append("mesh-seed missing mesh/gestures.vocabulary")

    demos, demo_errors = resolver_demos()
    errors.extend(demo_errors)

    recal = cg.recalibration_flags(learned)
    if recal:
        soft.append(f"needs_recalibration:{','.join(recal)}")

    report = {
        "ok": not errors,
        "gestures": len(vocab["gestures"]),
        "actions": len(actions["actions"]),
        "learned": len(learned["bindings"]),
        "huawei_parity": sorted({g["id"] for g in vocab["gestures"] if g.get("source") == "huawei"}),
        "repos": repo_status,
        "switch_default": (gsw or {}).get("default"),
        "demos": demos,
        "errors": errors,
        "soft": soft,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"gesture-check: {'PASS' if report['ok'] else 'FAIL'}")
        print(
            f"  gestures={report['gestures']} actions={report['actions']} learned={report['learned']} "
            f"huawei_parity={len(report['huawei_parity'])} switch={report['switch_default']}"
        )
        print(f"  repos={report['repos']}")
        for d in demos:
            print(f"  {'OK ' if d['ok'] else 'BAD'} {d['case']} → {[a for a, _ in d['got']]}")
        for e in errors:
            print(f"  ERR {e}")
        for s in soft:
            print(f"  soft {s}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
