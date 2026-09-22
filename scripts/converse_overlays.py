#!/usr/bin/env python3
"""Load Cam converse overlays from config — no server fork for new phrases.

The same config drives three reply paths (Python converse server, TS home
server via shared/converseOverlays.ts, web companion via
companions/web/converse-overlays.js). `scripts/converse-parity-check.py`
asserts the three stay byte-identical on the probe corpus.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "persona" / "converse-overlays.json"
_CACHE: dict | None = None
_MTIME: float | None = None
_REGEX_CACHE: dict[str, re.Pattern[str]] = {}

DEFAULT_INTENT_ORDER = ("greeting", "mic_check", "ack", "presence_chatter")
DEFAULT_SPEAK = {"rate": 0.95, "pitch": 1.05, "lang": "en-US"}


def invalidate_cache() -> None:
    global _CACHE, _MTIME
    _CACHE = None
    _MTIME = None
    _REGEX_CACHE.clear()


def load_overlays(*, force: bool = False) -> dict:
    global _CACHE, _MTIME
    try:
        mtime = CONFIG.stat().st_mtime
    except OSError:
        mtime = None
    if force or _CACHE is None or mtime != _MTIME:
        _CACHE = json.loads(CONFIG.read_text(encoding="utf-8"))
        _MTIME = mtime
        _REGEX_CACHE.clear()
    return _CACHE


def _word_hit(low: str, word: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", low) is not None


def _matches(low: str, rule: dict) -> bool:
    any_phrases = rule.get("any") or []
    if any_phrases and any(p in low for p in any_phrases):
        return True
    words = rule.get("words") or []
    if words and any(_word_hit(low, w) for w in words):
        return True
    groups = rule.get("all_groups") or []
    if groups and all(any(p in low for p in group) for group in groups):
        return True
    return False


def match_overlay(low: str, cfg: dict | None = None) -> dict | None:
    cfg = cfg or load_overlays()
    for rule in cfg.get("overlays") or []:
        if _matches(low, rule):
            return rule
    return None


def _intent_regex(spec: dict) -> re.Pattern[str] | None:
    pattern = str(spec.get("regex") or "")
    if not pattern:
        return None
    compiled = _REGEX_CACHE.get(pattern)
    if compiled is None:
        compiled = re.compile(pattern, re.I)
        _REGEX_CACHE[pattern] = compiled
    return compiled


def intent_order(cfg: dict | None = None) -> list[str]:
    cfg = cfg or load_overlays()
    order = cfg.get("intent_order") or list(DEFAULT_INTENT_ORDER)
    return [str(x) for x in order]


def classify_intents(text: str, cfg: dict | None = None) -> list[str]:
    """Config-driven fast intents (mirrors cam_reason._FAST_PATTERNS).

    Used by the TS/JS mirrors, which have no cam_reason; Python callers keep
    using cam_reason.classify_intent and `check_overlays` proves both agree.
    """
    cfg = cfg or load_overlays()
    rules = cfg.get("intent_rules") or {}
    text = (text or "").strip()
    hits: list[str] = []
    for name in intent_order(cfg):
        spec = rules.get(name)
        if not isinstance(spec, dict):
            continue
        pat = _intent_regex(spec)
        if pat and pat.search(text):
            hits.append(name)
    return hits


def last_aaron_line(history: list[dict] | None) -> str:
    """Last Aaron utterance from either history shape.

    Python server turns: {"aaron": text, "cam": reply, ...}
    TS / companion turns: {"role": "aaron", "text": text}
    """
    for item in reversed(history or []):
        if not isinstance(item, dict):
            continue
        if item.get("aaron"):
            return str(item["aaron"])
        if item.get("role") == "aaron" and item.get("text"):
            return str(item["text"])
    return ""


def shorten(text: str, cfg: dict | None = None) -> str:
    cfg = cfg or load_overlays()
    limit = int(cfg.get("short_max") or 120)
    return text if len(text) < limit else text[: limit - 3] + "…"


def speak_params(cfg: dict | None = None) -> dict:
    cfg = cfg or load_overlays()
    speak = dict(DEFAULT_SPEAK)
    speak.update({k: v for k, v in (cfg.get("speak") or {}).items() if v is not None})
    return speak


def explain_reply(
    aaron_text: str,
    trace: dict,
    history: list[dict] | None = None,
    cfg: dict | None = None,
) -> dict:
    """Reply text + which config branch produced it.

    Returns {"text", "kind", "id"} where kind ∈
    empty | overlay | intent | slow_plan | echo_repeat | echo.
    """
    cfg = cfg or load_overlays()
    t = (aaron_text or "").strip()
    if not t:
        return {
            "text": str(cfg.get("empty") or "I'm here, Aaron."),
            "kind": "empty",
            "id": None,
        }
    low = t.lower()
    rule = match_overlay(low, cfg)
    if rule:
        return {
            "text": str(rule.get("reply") or ""),
            "kind": "overlay",
            "id": str(rule.get("id") or ""),
        }
    intents = list((trace.get("classification") or {}).get("intents") or [])
    if not intents:
        intents = classify_intents(t, cfg)
    intent_replies = cfg.get("intents") or {}
    for key in intent_order(cfg):
        if key in intents and intent_replies.get(key):
            return {"text": str(intent_replies[key]), "kind": "intent", "id": key}
    if (trace.get("path") or "") == "slow":
        hotspot = trace.get("hotspot_id") or "capability"
        motors = ", ".join(trace.get("motor_plan") or ["motor.mesh"])
        text = str(cfg.get("slow_plan") or "I have a plan.").format(
            hotspot=hotspot, motors=motors
        )
        return {"text": text, "kind": "slow_plan", "id": str(hotspot)}
    short = shorten(t, cfg)
    previous = last_aaron_line(history).strip().lower()
    if previous and previous == low and cfg.get("echo_repeat"):
        return {
            "text": str(cfg["echo_repeat"]).format(short=short),
            "kind": "echo_repeat",
            "id": None,
        }
    return {
        "text": str(cfg.get("echo") or "I heard you: “{short}”.").format(short=short),
        "kind": "echo",
        "id": None,
    }


def speak_from_trace(
    aaron_text: str,
    trace: dict,
    history: list[dict] | None = None,
    cfg: dict | None = None,
) -> str:
    """Warm spoken reply from one reason() trace + config overlays."""
    return str(explain_reply(aaron_text, trace, history, cfg)["text"])


def overlay_probes(cfg: dict | None = None) -> list[tuple[str, str, str]]:
    """(overlay_id, probe_text, must_contain) rows for fuzz / units."""
    cfg = cfg or load_overlays()
    rows: list[tuple[str, str, str]] = []
    for rule in cfg.get("overlays") or []:
        must = (rule.get("must_contain") or [" "])[0]
        for probe in rule.get("probes") or []:
            rows.append((str(rule.get("id") or ""), str(probe), str(must)))
    return rows


def parity_corpus(cfg: dict | None = None) -> list[dict]:
    """Deterministic cases every mirror must answer identically.

    Each case: {"text", "intents", "path", "hotspot_id", "motor_plan", "history"}.
    """
    cfg = cfg or load_overlays()
    cases: list[dict] = [{"text": "", "intents": [], "path": "fast"}]
    for _oid, probe, _must in overlay_probes(cfg):
        cases.append({"text": probe, "intents": [], "path": "fast"})
    for intent, probe in (cfg.get("intent_probes") or {}).items():
        cases.append({"text": probe, "intents": [intent], "path": "fast"})
        cases.append({"text": probe, "intents": [], "path": "fast"})
    cases.append(
        {
            "text": "implement a small refactor",
            "intents": ["general"],
            "path": "slow",
            "hotspot_id": "hotspot.coding",
            "motor_plan": ["motor.cline"],
        }
    )
    cases.append({"text": "ping", "intents": ["general"], "path": "fast"})
    cases.append(
        {
            "text": "ping",
            "intents": ["general"],
            "path": "fast",
            "history": [{"role": "aaron", "text": "ping"}],
        }
    )
    cases.append(
        {
            "text": "ping",
            "intents": ["general"],
            "path": "fast",
            "history": [{"aaron": "Ping", "cam": "x"}],
        }
    )
    cases.append(
        {
            "text": "x" * 200,
            "intents": ["general"],
            "path": "fast",
        }
    )
    return cases


def run_parity_case(case: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or load_overlays()
    trace = {
        "classification": {"intents": list(case.get("intents") or [])},
        "path": case.get("path") or "fast",
        "hotspot_id": case.get("hotspot_id"),
        "motor_plan": case.get("motor_plan"),
    }
    out = explain_reply(case.get("text") or "", trace, case.get("history"), cfg)
    out["intents_from_config"] = classify_intents(case.get("text") or "", cfg)
    return out


def check_overlays(cfg: dict | None = None) -> dict:
    cfg = cfg or load_overlays()
    errors: list[str] = []
    ids: list[str] = []
    for rule in cfg.get("overlays") or []:
        rid = rule.get("id") or ""
        if not rid:
            errors.append("overlay_missing_id")
            continue
        if rid in ids:
            errors.append(f"duplicate_overlay:{rid}")
        ids.append(rid)
        if not (rule.get("reply") or "").strip():
            errors.append(f"empty_reply:{rid}")
        if not (rule.get("any") or rule.get("all_groups") or rule.get("words")):
            errors.append(f"no_matchers:{rid}")
        must = (rule.get("must_contain") or [None])[0]
        if must and must not in (rule.get("reply") or ""):
            errors.append(f"must_contain_missing:{rid}")
        if not rule.get("probes"):
            errors.append(f"no_probes:{rid}")
        for probe in rule.get("probes") or []:
            hit = match_overlay(probe.lower(), cfg)
            if not hit or hit.get("id") != rid:
                errors.append(f"probe_mismatch:{rid}:{probe}")
    if not (cfg.get("empty") or "").strip():
        errors.append("empty_line_missing")
    for key in ("echo", "echo_repeat"):
        if "{short}" not in str(cfg.get(key) or ""):
            errors.append(f"template_missing_short:{key}")
    if "{hotspot}" not in str(cfg.get("slow_plan") or ""):
        errors.append("template_missing_hotspot:slow_plan")
    order = intent_order(cfg)
    rules = cfg.get("intent_rules") or {}
    probes = cfg.get("intent_probes") or {}
    for key in order:
        if not (cfg.get("intents") or {}).get(key):
            errors.append(f"intent_missing:{key}")
        if not isinstance(rules.get(key), dict) or not rules[key].get("regex"):
            errors.append(f"intent_rule_missing:{key}")
            continue
        try:
            _intent_regex(rules[key])
        except re.error:
            errors.append(f"intent_rule_invalid:{key}")
            continue
        probe = probes.get(key)
        if not probe:
            errors.append(f"intent_probe_missing:{key}")
        elif key not in classify_intents(str(probe), cfg):
            errors.append(f"intent_probe_mismatch:{key}:{probe}")
    # Intent regexes must be the same ones cam_reason uses on the fast gate
    try:
        import cam_reason as cr  # noqa: PLC0415

        fast = {name: pat.pattern for name, pat in cr._FAST_PATTERNS}
        for key in order:
            spec = rules.get(key) or {}
            if key in fast and spec.get("regex") != fast[key]:
                errors.append(f"intent_rule_drift:{key}")
        for key, probe in probes.items():
            if key not in (cr.classify_intent(str(probe)).get("intents") or []):
                errors.append(f"cam_reason_intent_mismatch:{key}:{probe}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cam_reason_unavailable:{type(exc).__name__}")
    speak = cfg.get("speak") or {}
    for key in ("rate", "pitch"):
        if not isinstance(speak.get(key), (int, float)):
            errors.append(f"speak_missing:{key}")
    if not speak.get("lang"):
        errors.append("speak_missing:lang")
    return {
        "ok": not errors,
        "errors": errors,
        "overlay_count": len(ids),
        "intent_count": len(order),
        "version": cfg.get("version"),
    }
