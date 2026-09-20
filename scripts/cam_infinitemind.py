#!/usr/bin/env python3
"""Cam ↔ InfiniteMind adapter (Phase C thin slice).

Wraps formal logic, meta-strategy, abductive explanation, and epistemic
confidence from integrations/infinitemind — no torch, no qiskit, no OpenAI
idea generator. Aaron-only / switch-gated; never fires motors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INFINITEMIND = ROOT / "integrations" / "infinitemind"
REASONING_CFG = ROOT / "config" / "enhancement" / "reasoning-logic.json"

# Deterministic strategy pick — avoids MetaReasoning.select_strategy RNG for dry-run.
_STRATEGY_BY_INTENT: dict[str, str] = {
    "enhance": "analytical",
    "outbound": "analytical",
    "careers_submit": "systematic",
    "money": "analytical",
    "identity_boundary": "analytical",
    "explicit_plan": "systematic",
    "research_cite": "systematic",
    "multi_step": "systematic",
    "personal_fact": "analogical",
    "general": "creative",
}


def _jsonable(obj: Any) -> Any:
    """Coerce numpy scalars / nested structures into JSON-safe Python types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    # numpy bool_/integer/floating
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return _jsonable(obj.item())
        except Exception:
            pass
    return str(obj)


def _ensure_path() -> None:
    p = str(INFINITEMIND)
    if p not in sys.path:
        sys.path.insert(0, p)


def available() -> bool:
    return (INFINITEMIND / "logic_engine.py").is_file()


_ENGINES: dict[str, Any] | None = None


def load_engines() -> dict[str, Any]:
    """Import InfiniteMind engines once per process."""
    global _ENGINES
    if _ENGINES is not None:
        return _ENGINES
    _ensure_path()
    from logic_engine import LogicEngine  # type: ignore
    from epistemic_confidence import EpistemicConfidence  # type: ignore
    from abductive_reasoning import AbductiveHypothesisGenerator  # type: ignore

    _ENGINES = {
        "LogicEngine": LogicEngine,
        "EpistemicConfidence": EpistemicConfidence,
        "AbductiveHypothesisGenerator": AbductiveHypothesisGenerator,
    }
    return _ENGINES


def pick_strategy(intents: list[str]) -> str:
    for intent in intents:
        if intent in _STRATEGY_BY_INTENT:
            return _STRATEGY_BY_INTENT[intent]
    return "systematic"


def _assert_cam_axioms(engine: Any, *, kill: bool, enhance_intent: bool, not_aaron: bool) -> list[str]:
    asserted: list[str] = []
    engine.assert_proposition("aaron_only_tasking", 1.0)
    asserted.append("aaron_only_tasking")
    engine.assert_proposition("prefer_mesh_before_invent", 1.0)
    asserted.append("prefer_mesh_before_invent")
    if not_aaron:
        engine.assert_proposition("non_aaron_actor", 1.0)
        asserted.append("non_aaron_actor")
    if kill:
        engine.assert_proposition("kill_active", 1.0)
        asserted.append("kill_active")
    if enhance_intent:
        engine.assert_proposition("enhance_intent", 1.0)
        asserted.append("enhance_intent")

    # Rules
    engine.add_rule(["aaron_only_tasking"], "tasking_ok", 0.99)
    engine.add_rule(["prefer_mesh_before_invent"], "no_invent_aaron_facts", 0.95)
    engine.add_rule(["kill_active"], "motors_silenced", 0.99)
    engine.add_rule(["non_aaron_actor"], "reject_task", 0.99)
    engine.add_rule(["enhance_intent"], "needs_enhance_switch", 0.9)
    engine.add_rule(["tasking_ok"], "may_plan_motor", 0.9)
    return asserted


def _recall_propositions(engine: Any, recall: dict[str, Any] | None) -> list[str]:
    added: list[str] = []
    if not recall:
        return added
    hits = recall.get("hits") or {}
    for tier, items in hits.items():
        for i, item in enumerate(items or []):
            note = (item.get("note") or item.get("ns") or f"{tier}_{i}")[:80]
            key = f"recall_{tier}_{i}"
            # Soft evidence
            amp = 0.85 if tier == "primary" else 0.7 if tier == "secondary" else 0.55
            engine.assert_proposition(key, amp)
            engine.assert_proposition(f"note:{note}", amp * 0.9)
            added.append(key)
    return added


def enrich(
    *,
    goal: str,
    intents: list[str] | None = None,
    confidence: float = 0.7,
    escalate: bool = True,
    escalate_reasons: list[str] | None = None,
    recall: dict[str, Any] | None = None,
    kill: bool = False,
    enhance_intent: bool = False,
    not_aaron: bool = False,
    threshold: float = 0.65,
) -> dict[str, Any]:
    """Run InfiniteMind engines; return toolkit-shaped result for reasoning_trace."""
    return _jsonable(
        _enrich_raw(
            goal=goal,
            intents=intents,
            confidence=confidence,
            escalate=escalate,
            escalate_reasons=escalate_reasons,
            recall=recall,
            kill=kill,
            enhance_intent=enhance_intent,
            not_aaron=not_aaron,
            threshold=threshold,
        )
    )


def _enrich_raw(
    *,
    goal: str,
    intents: list[str] | None = None,
    confidence: float = 0.7,
    escalate: bool = True,
    escalate_reasons: list[str] | None = None,
    recall: dict[str, Any] | None = None,
    kill: bool = False,
    enhance_intent: bool = False,
    not_aaron: bool = False,
    threshold: float = 0.65,
) -> dict[str, Any]:
    intents = list(intents or [])
    escalate_reasons = list(escalate_reasons or [])

    if not available():
        return {
            "tool": "InfiniteMindEnrich",
            "ok": False,
            "error": "integrations/infinitemind missing — git submodule update --init",
            "skipped": True,
        }

    engines = load_engines()
    LogicEngine = engines["LogicEngine"]
    EpistemicConfidence = engines["EpistemicConfidence"]
    AbductiveHypothesisGenerator = engines["AbductiveHypothesisGenerator"]

    logic = LogicEngine()
    asserted = _assert_cam_axioms(
        logic, kill=kill, enhance_intent=enhance_intent, not_aaron=not_aaron
    )
    recall_props = _recall_propositions(logic, recall)
    chain = logic.forward_chain_to_fixpoint(max_iterations=8)

    strategy = pick_strategy(intents)
    load = min(1.0, len(escalate_reasons) * 0.15 + (0.2 if escalate else 0.05))
    refined = {
        "goal": (goal or "")[:200],
        "intents": intents,
        "strategy": strategy,
        "escalate": escalate,
    }

    # Abductive: best explanation for path choice
    observations = {
        "goal_len": len(goal or ""),
        "intents": intents,
        "escalate_reasons": escalate_reasons,
        "confidence": confidence,
    }
    priors = {
        "stay_fast": max(0.05, confidence if not escalate else 1.0 - confidence),
        "escalate_sgr": max(0.05, (1.0 - confidence) if not escalate else confidence),
        "ask_aaron_clarify": 0.25 if "personal_fact" in intents else 0.1,
        "hold_gated_motor": 0.4 if enhance_intent or kill else 0.1,
    }
    if kill or not_aaron:
        priors = {"hold_gated_motor": 0.8, "reject_task": 0.9, "stay_fast": 0.05, "escalate_sgr": 0.05}
    abducer = AbductiveHypothesisGenerator()
    abduction = abducer.generate_hypothesis(observations, priors)

    # Epistemic gate on the chosen explanation
    evidence = {
        "evidence_strength": min(1.0, 0.4 + 0.15 * len(recall_props)),
        "source_reliability": 0.95 if recall and not recall.get("invented") else 0.5,
        "internal_consistency": 0.9 if chain.get("converged") else 0.55,
        "temporal_relevance": 0.8,
    }
    if kill or not_aaron:
        evidence["internal_consistency"] = 1.0
    epistemic = EpistemicConfidence(base_threshold=threshold)
    best_hyp = (abduction.get("best") or "escalate_sgr") if isinstance(abduction, dict) else "escalate_sgr"
    assessment = epistemic.multi_dimensional_assess(best_hyp, evidence)

    derived = list(chain.get("unique_derived") or [])
    motors_silenced = "motors_silenced" in derived or kill
    reject = "reject_task" in derived or not_aaron
    needs_enhance_switch = "needs_enhance_switch" in derived

    return {
        "tool": "InfiniteMindEnrich",
        "ok": True,
        "skipped": False,
        "source": "integrations/infinitemind",
        "strategy": strategy,
        "meta": {
            "cognitive_load": load,
            "should_deepen": load < 0.3,
            "refined": refined,
        },
        "logic": {
            "asserted": asserted,
            "recall_propositions": recall_props,
            "derived": derived,
            "converged": bool(chain.get("converged")),
            "iterations": int(chain.get("iterations") or 0),
            "motors_silenced": bool(motors_silenced),
            "reject_task": bool(reject),
            "needs_enhance_switch": bool(needs_enhance_switch),
        },
        "abduction": abduction,
        "epistemic": assessment,
        "recommendation": {
            "path_hint": "reject"
            if reject
            else "killed"
            if motors_silenced
            else ("slow" if escalate or best_hyp == "escalate_sgr" else "fast"),
            "clarify": best_hyp == "ask_aaron_clarify",
            "hold_gated": best_hyp == "hold_gated_motor" or needs_enhance_switch,
            "accepted_epistemic": bool(assessment.get("accepted")),
        },
    }


def load_reasoning_infinitemind_cfg() -> dict[str, Any]:
    if not REASONING_CFG.exists():
        return {}
    cfg = json.loads(REASONING_CFG.read_text(encoding="utf-8"))
    return dict(cfg.get("infinitemind") or {})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", default="think carefully and make a plan")
    ap.add_argument("--confidence", type=float, default=0.55)
    ap.add_argument("--escalate", action="store_true", default=True)
    ap.add_argument("--fast", action="store_true", help="mark escalate false")
    ap.add_argument("--kill", action="store_true")
    ap.add_argument("--enhance-intent", action="store_true")
    ap.add_argument("--not-aaron", action="store_true")
    ap.add_argument("--intent", action="append", default=[])
    args = ap.parse_args(argv)

    escalate = not args.fast
    intents = args.intent or (["explicit_plan"] if escalate else ["greeting"])
    result = enrich(
        goal=args.goal,
        intents=intents,
        confidence=args.confidence,
        escalate=escalate,
        escalate_reasons=["cli"] if escalate else [],
        kill=args.kill,
        enhance_intent=args.enhance_intent,
        not_aaron=args.not_aaron,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") or result.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
