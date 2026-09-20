#!/usr/bin/env python3
"""Cam reasoning loop — Phase B thin slice (dry-run first).

Accept → fast heuristics → escalate bar → recall → stub SGR Reason schema
→ dual-stream → trajectory reflect → motor plan → reasoning_trace.

Does not call LitServe, converse, or live LLMs. See docs/CAM_REASONING.md.

Phase C: optional InfiniteMind logic/meta/epistemic/abductive enrichment on
the slow path (integrations/infinitemind) — still dry-run, no motors fired.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trajectory_policies as tp  # noqa: E402

REASONING_CFG = ROOT / "config" / "enhancement" / "reasoning-logic.json"
HMO_CFG = ROOT / "config" / "memory" / "hmo-tiers.json"
DISTILL_DIR = ROOT / "vault" / "10-Mesh-Distillates" / "reasoning"

_CACHE: dict[str, Any] = {}


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_reasoning_config() -> dict:
    if "reasoning" not in _CACHE:
        _CACHE["reasoning"] = json.loads(REASONING_CFG.read_text(encoding="utf-8"))
    return _CACHE["reasoning"]


def _load_hyphen_module(name: str, filename: str):
    if name in _CACHE:
        return _CACHE[name]
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _CACHE[name] = mod
    return mod


def connectome_route():
    return _load_hyphen_module("connectome_route", "connectome-route.py")


def dual_stream_router():
    return _load_hyphen_module("dual_stream_router", "dual-stream-router.py")


def _connectome_json(name: str) -> dict:
    key = f"cj:{name}"
    if key not in _CACHE:
        _CACHE[key] = connectome_route().load(name)
    return _CACHE[key]

# --- intent / escalate -------------------------------------------------------

_FAST_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greeting", re.compile(r"\b(hi|hello|hey)\b|hi cam|hey cam", re.I)),
    ("ack", re.compile(r"^(ok|okay|thanks|thank you|got it|cool)\.?$", re.I)),
    ("mic_check", re.compile(r"\b(mic|microphone|hear me|listening)\b", re.I)),
    ("presence_chatter", re.compile(r"\b(how are you|you there|still there)\b", re.I)),
]

_SLOW_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("enhance", re.compile(r"\b(enhance|upgrade cam|apply (?:the )?batch|cam.?function)\b", re.I)),
    ("outbound", re.compile(r"\b(text aaron|send (?:a )?text|call |facetime|outbound)\b", re.I)),
    ("careers_submit", re.compile(r"\b(apply(ing)? (?:to|for)|submit (?:the )?application)\b", re.I)),
    ("money", re.compile(r"\b(wire|paypal|venmo|send money|payment)\b", re.I)),
    ("identity_boundary", re.compile(r"\b(change (?:your|cam) (?:name|persona|identity)|kill switch)\b", re.I)),
    ("explicit_plan", re.compile(r"\b(think carefully|make a plan|plan (?:this|it)|reason step)\b", re.I)),
    ("research_cite", re.compile(r"\b(research|cite|scholar|arxiv|paper)\b", re.I)),
    ("multi_step", re.compile(r"\b(then |after that|step \d|multi[- ]step)\b", re.I)),
]

_PERSONAL_FACT = re.compile(
    r"\b(my (?:pref|preference|birthday|address|phone)|do you remember|what do i)\b",
    re.I,
)


def classify_intent(goal: str) -> dict[str, Any]:
    text = (goal or "").strip()
    intents: list[str] = []
    for name, pat in _FAST_PATTERNS:
        if pat.search(text):
            intents.append(name)
    for name, pat in _SLOW_PATTERNS:
        if pat.search(text):
            intents.append(name)
    if _PERSONAL_FACT.search(text):
        intents.append("personal_fact")
    if not intents:
        intents.append("general")
    # confidence: short fast phrases high; long / slow keywords lower
    if intents[0] in {"greeting", "ack", "mic_check", "presence_chatter"} and len(intents) == 1:
        confidence = 0.92
    elif any(i in intents for i in ("enhance", "outbound", "careers_submit", "money", "identity_boundary")):
        confidence = 0.4
    elif "personal_fact" in intents:
        confidence = 0.55
    elif len(text) > 160:
        confidence = 0.5
    else:
        confidence = 0.7
    return {"intents": intents, "confidence": confidence, "length": len(text)}


def should_escalate(classification: dict[str, Any], cfg: dict) -> tuple[bool, list[str]]:
    esc = cfg.get("escalation") or {}
    reasons: list[str] = []
    intents = set(classification.get("intents") or [])
    always_slow = set(esc.get("always_slow_intents") or [])
    always_fast = set(esc.get("always_fast_intents") or [])
    threshold = float(esc.get("confidence_below") or 0.65)

    if intents & always_slow:
        reasons.append("always_slow_intent:" + ",".join(sorted(intents & always_slow)))
    if classification.get("confidence", 1.0) < threshold:
        reasons.append("low_confidence")
    if "personal_fact" in intents:
        reasons.append("weak_personal_fact_hits")  # dry-run treats as escalate for recall
    if classification.get("length", 0) > 220:
        reasons.append("length_bar")

    # Fast override only when exclusively fast intents and no slow reasons
    if intents and intents <= always_fast and not (intents & always_slow) and "low_confidence" not in reasons:
        return False, ["always_fast_intent"]

    if reasons:
        return True, reasons
    return False, []


def bar_allows_converse(goal: str, cfg: dict) -> bool:
    """True when converse should invoke reasoner (not every mic turn)."""
    classification = classify_intent(goal)
    escalate, _ = should_escalate(classification, cfg)
    return escalate


# --- toolkit stubs -----------------------------------------------------------

def mesh_recall(goal: str, personal_fact: bool) -> dict[str, Any]:
    if "hmo" not in _CACHE:
        _CACHE["hmo"] = json.loads(HMO_CFG.read_text(encoding="utf-8")) if HMO_CFG.exists() else {}
    hmo = _CACHE["hmo"]
    tiers = [t.get("id") for t in (hmo.get("tiers") or [])]
    hits = {
        "primary": [
            {"ns": "mesh/persona", "note": "Cam; sole operator Aaron"},
            {"ns": "mesh/prefs", "note": "prefer vault/mesh before invent"},
        ],
        "secondary": [],
        "archive": [],
    }
    if personal_fact:
        hits["secondary"].append(
            {"ns": "mesh/facts", "note": "dry-run stub — search vault before inventing"}
        )
    return {
        "tool": "MeshRecallTool",
        "order": tiers or ["primary", "secondary", "archive"],
        "hits": hits,
        "invented": False,
        "goal_excerpt": (goal or "")[:120],
    }


def _switch_state(*, kill: bool, enhance: bool) -> dict[str, str]:
    key = f"sw:{int(kill)}:{int(enhance)}"
    if key not in _CACHE:
        cr = connectome_route()
        _CACHE[key] = cr.resolve_switches(
            _connectome_json("switches.json"),
            kill=kill,
            autonomy=True,
            enhance=enhance,
            research_scan=True,
            slm=True,
            dl=True,
        )
    return _CACHE[key]


def connectome_route_tool(
    sense: str,
    goal: str,
    *,
    kill: bool = False,
    enhance: bool = False,
    not_aaron: bool = False,
    hotspot_id: str | None = None,
) -> dict[str, Any]:
    cr = connectome_route()
    sensory = _connectome_json("sensory.json")
    motor = _connectome_json("motor.json")
    hotspots = _connectome_json("hotspots.json")

    if "sense_ids" not in _CACHE:
        _CACHE["sense_ids"] = {n["id"] for n in sensory["neurons"]}
    if sense not in _CACHE["sense_ids"]:
        return {"tool": "ConnectomeRouteTool", "error": f"unknown sense: {sense}", "motor_plan": []}

    if not_aaron:
        return {
            "tool": "ConnectomeRouteTool",
            "accepted": False,
            "reason": "switch.tasking hold — only Aaron may assign tasks",
            "motor_plan": [],
        }

    switch_state = _switch_state(kill=kill, enhance=enhance)
    req_key = "effector_reqs"
    if req_key not in _CACHE:
        _CACHE[req_key] = {e["id"]: list(e.get("requires_switch") or []) for e in motor["effectors"]}
    effector_reqs = _CACHE[req_key]
    candidates = cr.hotspots_for_sense(hotspots, sense)
    hotspot = cr.pick_hotspot(candidates, goal, hotspot_id)
    if hotspot:
        pathway = list(hotspot["pathway"])
        planned = cr.motors_from_pathway(pathway, switch_state, effector_reqs)
        for side in hotspot.get("side_effects") or []:
            if side not in planned and cr.motor_allowed(side, effector_reqs, switch_state):
                planned.append(side)
        behavior = hotspot["behavior"]
        hotspot_id = hotspot.get("id")
        area = hotspot.get("area") or hotspot.get("center")
    else:
        pathway = [sense, "area.wernicke", "area.dlpfc", "area.mtl", "switch.autonomy", "motor.mesh"]
        planned = ["motor.mesh"] if cr.motor_allowed("motor.mesh", effector_reqs, switch_state) else []
        behavior = "generic_integrate_and_remember"
        hotspot_id = None
        area = "area.dlpfc"

    known = {e["id"] for e in motor["effectors"]}
    planned = [m for m in planned if m in known]
    if kill:
        planned = []
    return {
        "tool": "ConnectomeRouteTool",
        "accepted": not kill and not not_aaron,
        "sense": sense,
        "goal": goal,
        "hotspot_id": hotspot_id,
        "area": area,
        "behavior": behavior,
        "pathway": pathway,
        "switch_state": switch_state,
        "motor_plan": planned,
    }


def trajectory_check_tool(motor_plan: list[str], switch_state: dict[str, str]) -> dict[str, Any]:
    revised, violations = tp.apply_policies(motor_plan, switch_state)
    return {
        "tool": "TrajectoryCheckTool",
        "motor_plan_in": list(motor_plan),
        "motor_plan": revised,
        "violations": violations,
    }


def final_answer_tool(path: str, stream: str, summary: str) -> dict[str, Any]:
    return {
        "tool": "FinalAnswerTool",
        "path": path,
        "stream": stream,
        "summary": summary,
        "dry_run": True,
    }


def cam_reasoning_tool(
    *,
    goal: str,
    hotspot_id: str | None,
    switch_state: dict[str, str],
    stream: str,
    path: str,
    iteration: int = 1,
) -> dict[str, Any]:
    """Dry-run Cam ReasoningTool schema (SGR-compatible fields + Cam extras)."""
    risks = [
        s
        for s, st in (switch_state or {}).items()
        if s.startswith("switch.") and st != "act" and s in {
            "switch.cam_enhance",
            "switch.outbound",
            "switch.careers_submit",
            "switch.kill",
        }
    ]
    if switch_state.get("switch.kill") == "act":
        risks = ["switch.kill"]
    steps = [
        "Assess Aaron goal against connectome gates",
        "Recall mesh/vault before inventing facts",
        "Propose motor plan only on act switches",
    ]
    return {
        "tool": "CamReasoningTool",
        "tool_name": "camreasoningtool",
        "reasoning_steps": steps[:3],
        "current_situation": f"dry-run path={path}; goal={(goal or '')[:180]}",
        "plan_status": "dry-run stub — no live SGR LLM",
        "enough_data": path == "fast",
        "remaining_steps": ["emit_trace", "stop"] if iteration >= 1 else ["route", "reflect"],
        "task_completed": True,
        # Cam extensions
        "hotspot_id": hotspot_id,
        "switch_risks": risks,
        "stream": stream,
        "iteration": iteration,
    }


def pick_stream_act(goal: str, intents: list[str]) -> str:
    g = (goal or "").lower()
    if "research" in intents or "research" in g or "scholar" in g or "arxiv" in g:
        return "research"
    if "doc" in g or "brief" in g or "write" in g:
        return "docs"
    if "career" in intents or "job" in g:
        return "careers"
    return "speak"


# --- main loop ---------------------------------------------------------------

def _trace(write: bool, **fields: Any) -> dict[str, Any]:
    out = {
        "kind": "reasoning_trace",
        "persona": {"name": "Cam", "sole_operator": "Aaron"},
        "ts": utc(),
        **fields,
    }
    if write:
        _write_trace(out)
    return out


def reason(
    *,
    goal: str = "",
    sense: str = "sense.chat.aaron",
    dry_run: bool = True,
    kill: bool = False,
    enhance: bool = False,
    not_aaron: bool = False,
    write_trace: bool = True,
    force_path: str | None = None,
) -> dict[str, Any]:
    """Single-pass loop: classify once → fast assemble or slow enrich. No double route."""
    cfg = load_reasoning_config()
    classification = classify_intent(goal)
    escalate, esc_reasons = should_escalate(classification, cfg)
    if force_path == "fast":
        escalate, esc_reasons = False, ["forced_fast"]
    elif force_path == "slow":
        escalate, esc_reasons = True, list(dict.fromkeys(esc_reasons + ["forced_slow"]))

    if not_aaron:
        return _trace(
            write_trace,
            sense=sense,
            goal=goal,
            path="rejected",
            engine=None,
            accepted=False,
            reason="switch.tasking hold — only Aaron may assign tasks",
            stages=["accept"],
            motor_plan=[],
            violations=[],
            dry_run=dry_run,
        )

    if kill:
        return _trace(
            write_trace,
            sense=sense,
            goal=goal,
            path="killed",
            engine=None,
            accepted=False,
            reason="switch.kill act — all motor silenced",
            stages=["accept", "fast", "gate", "reflect", "motor"],
            classification=classification,
            escalation=esc_reasons,
            hotspot_id=None,
            motor_plan=[],
            violations=[{"id": "kill_silences_all", "action": "clear_all_motors"}],
            dry_run=dry_run,
        )

    # Fast gate: one classify already done — assemble, do not scan connectome.
    if not escalate:
        import cam_fast as cf  # noqa: PLC0415 — lazy so greetings skip InfiniteMind import

        fast_result = cf.run_fast(
            goal=goal,
            sense=sense,
            kill=False,
            enhance=enhance,
            classification=classification,
            decided=True,
        )
        toolkit = [fast_result, final_answer_tool("fast", "dorsal", f"Fast path; motors={fast_result.get('motor_plan')}")]
        return _trace(
            write_trace,
            sense=sense,
            goal=goal,
            path="fast",
            engine="system1_fast_heuristics",
            accepted=True,
            dry_run=dry_run,
            escalation=fast_result.get("escalation") or esc_reasons,
            stages=list(fast_result.get("stages") or ["accept", "fast", "gate", "stream", "motor", "distill"]),
            stages_skipped=fast_result.get("stages_skipped"),
            classification=classification,
            hotspot_id=fast_result.get("hotspot_id"),
            area=None,
            pathway=None,
            stream="dorsal",
            stream_act="speak",
            reasoning_steps=None,
            switch_risks=[],
            sgr_iterations=0,
            infinitemind=None,
            compute=fast_result.get("compute"),
            recall=None,
            motor_plan=list(fast_result.get("motor_plan") or []),
            violations=[],
            toolkit=[t.get("tool") for t in toolkit],
            toolkit_results=toolkit if dry_run else None,
        )

    # Slow gate: route once, then recall → InfiniteMind → SGR stub → OCL.
    import cam_infinitemind as cim  # noqa: PLC0415

    stages = ["accept", "fast", "gate"]
    route = connectome_route_tool(sense, goal, kill=False, enhance=enhance)
    switch_state = route.get("switch_state") or {}
    toolkit_results: list[dict] = []
    intents = list(classification.get("intents") or [])

    stream_act = pick_stream_act(goal, intents)
    dsr = dual_stream_router()
    stream_result = dsr.route_act(stream_act if stream_act in {"speak", "docs", "research", "careers"} else "speak")
    stream = stream_result.get("winner") or "dorsal"

    stages.append("recall")
    recall = mesh_recall(goal, personal_fact="personal_fact" in intents)
    toolkit_results.append(recall)

    im_result = None
    if (cfg.get("infinitemind") or {}).get("enabled_dry_run", True):
        stages.append("logic")
        im_result = cim.enrich(
            goal=goal,
            intents=intents,
            confidence=float(classification.get("confidence") or 0.7),
            escalate=True,
            escalate_reasons=esc_reasons,
            recall=recall,
            kill=False,
            enhance_intent="enhance" in intents,
            not_aaron=False,
            threshold=float((cfg.get("escalation") or {}).get("confidence_below") or 0.65),
        )
        toolkit_results.append(im_result)

    stages.append("sgr")
    reasoning_schema = cam_reasoning_tool(
        goal=goal,
        hotspot_id=route.get("hotspot_id"),
        switch_state=switch_state,
        stream=stream,
        path="slow",
        iteration=1,
    )
    if im_result and im_result.get("ok"):
        reasoning_schema["infinitemind_strategy"] = im_result.get("strategy")
        reasoning_schema["infinitemind_path_hint"] = (im_result.get("recommendation") or {}).get("path_hint")
    reasoning_schema["max_iterations_cap"] = int(((cfg.get("sgr_limits") or {}).get("max_iterations_dry_run")) or 4)
    toolkit_results.append(reasoning_schema)

    stages.append("stream")
    toolkit_results.append({"tool": "DualStream", **stream_result})

    stages.append("reflect")
    motor_plan = list(route.get("motor_plan") or [])
    if "enhance" in intents and not enhance and "motor.enhance" not in motor_plan:
        motor_plan.append("motor.enhance")
    traj = trajectory_check_tool(motor_plan, switch_state)
    toolkit_results.append(traj)
    motor_plan = list(traj.get("motor_plan") or [])

    stages.extend(["switch", "motor"])
    summary = f"Slow SGR stub; hotspot={route.get('hotspot_id')}; motors={motor_plan}"
    if im_result and im_result.get("ok"):
        summary += f"; im_strategy={im_result.get('strategy')}"
    toolkit_results.append(final_answer_tool("slow", stream, summary))
    stages.append("distill")

    return _trace(
        write_trace,
        sense=sense,
        goal=goal,
        path="slow",
        engine="sgr_tool_calling_agent_stub+infinitemind"
        if im_result and im_result.get("ok")
        else "sgr_tool_calling_agent_stub",
        accepted=True,
        dry_run=dry_run,
        escalation=esc_reasons,
        stages=stages,
        classification=classification,
        hotspot_id=route.get("hotspot_id"),
        area=route.get("area"),
        pathway=route.get("pathway"),
        stream=stream,
        stream_act=stream_act,
        reasoning_steps=reasoning_schema.get("reasoning_steps"),
        switch_risks=reasoning_schema.get("switch_risks"),
        sgr_iterations=1,
        infinitemind={
            "strategy": im_result.get("strategy"),
            "recommendation": im_result.get("recommendation"),
            "abduction_best": (im_result.get("abduction") or {}).get("best"),
        }
        if im_result and im_result.get("ok")
        else None,
        compute=None,
        recall=recall,
        motor_plan=motor_plan,
        violations=traj.get("violations") or [],
        toolkit=[t.get("tool") for t in toolkit_results],
        toolkit_results=toolkit_results if dry_run else None,
    )


def _write_trace(trace: dict) -> Path:
    DISTILL_DIR.mkdir(parents=True, exist_ok=True)
    day = (trace.get("ts") or utc())[:10]
    path = DISTILL_DIR / f"{day}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(trace, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", default="", help="Aaron goal / utterance")
    ap.add_argument("--sense", default="sense.chat.aaron")
    ap.add_argument("--dry-run", action="store_true", default=True, help="default on")
    ap.add_argument("--live", action="store_true", help="mark dry_run false (still no LLM in Phase B)")
    ap.add_argument("--kill", action="store_true")
    ap.add_argument("--enhance", action="store_true", help="flip switch.cam_enhance act")
    ap.add_argument("--not-aaron", action="store_true")
    ap.add_argument("--force-path", choices=["fast", "slow"], default=None)
    ap.add_argument("--no-write", action="store_true", help="skip JSONL distill")
    ap.add_argument("--bar-check", action="store_true", help="print whether converse bar allows reasoner")
    args = ap.parse_args(argv)

    cfg = load_reasoning_config()
    if args.bar_check:
        allowed = bar_allows_converse(args.goal, cfg)
        print(json.dumps({"goal": args.goal, "bar_allows_reasoner": allowed}, indent=2))
        return 0

    result = reason(
        goal=args.goal,
        sense=args.sense,
        dry_run=not args.live,
        kill=args.kill,
        enhance=args.enhance,
        not_aaron=args.not_aaron,
        write_trace=not args.no_write,
        force_path=args.force_path,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("accepted", True) or result.get("path") in {"killed", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
