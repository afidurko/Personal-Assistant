#!/usr/bin/env python3
"""Load Cam converse overlays from config — no server fork for new phrases."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "persona" / "converse-overlays.json"
_CACHE: dict | None = None
_MTIME: float | None = None


def invalidate_cache() -> None:
    global _CACHE, _MTIME
    _CACHE = None
    _MTIME = None


def load_overlays(*, force: bool = False) -> dict:
    global _CACHE, _MTIME
    try:
        mtime = CONFIG.stat().st_mtime
    except OSError:
        mtime = None
    if force or _CACHE is None or mtime != _MTIME:
        _CACHE = json.loads(CONFIG.read_text(encoding="utf-8"))
        _MTIME = mtime
    return _CACHE


def _matches(low: str, rule: dict) -> bool:
    any_phrases = rule.get("any") or []
    if any_phrases and any(p in low for p in any_phrases):
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


def speak_from_trace(
    aaron_text: str,
    trace: dict,
    history: list[dict] | None = None,
    cfg: dict | None = None,
) -> str:
    """Warm spoken reply from one reason() trace + config overlays."""
    del history  # reserved for later turn-memory phrasing
    cfg = cfg or load_overlays()
    t = (aaron_text or "").strip()
    if not t:
        return str(cfg.get("empty") or "I'm here, Aaron.")
    rule = match_overlay(t.lower(), cfg)
    if rule:
        return str(rule.get("reply") or "")
    intents = set((trace.get("classification") or {}).get("intents") or [])
    intent_replies = cfg.get("intents") or {}
    for key in ("greeting", "mic_check", "ack", "presence_chatter"):
        if key in intents and intent_replies.get(key):
            return str(intent_replies[key])
    if (trace.get("path") or "") == "slow":
        hotspot = trace.get("hotspot_id") or "capability"
        motors = ", ".join(trace.get("motor_plan") or ["motor.mesh"])
        return str(cfg.get("slow_plan") or "I have a plan.").format(
            hotspot=hotspot, motors=motors
        )
    short = t if len(t) < 120 else t[:117] + "…"
    return str(cfg.get("echo") or "I heard you: “{short}”.").format(short=short)


def overlay_probes(cfg: dict | None = None) -> list[tuple[str, str, str]]:
    """(overlay_id, probe_text, must_contain) rows for fuzz / units."""
    cfg = cfg or load_overlays()
    rows: list[tuple[str, str, str]] = []
    for rule in cfg.get("overlays") or []:
        must = (rule.get("must_contain") or [" "])[0]
        for probe in rule.get("probes") or []:
            rows.append((str(rule.get("id") or ""), str(probe), str(must)))
    return rows


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
        if not (rule.get("any") or rule.get("all_groups")):
            errors.append(f"no_matchers:{rid}")
        must = (rule.get("must_contain") or [None])[0]
        if must and must not in (rule.get("reply") or ""):
            errors.append(f"must_contain_missing:{rid}")
        for probe in rule.get("probes") or []:
            hit = match_overlay(probe.lower(), cfg)
            if not hit or hit.get("id") != rid:
                errors.append(f"probe_mismatch:{rid}:{probe}")
    if not (cfg.get("empty") or "").strip():
        errors.append("empty_line_missing")
    for key in ("greeting", "mic_check", "ack", "presence_chatter"):
        if not (cfg.get("intents") or {}).get(key):
            errors.append(f"intent_missing:{key}")
    return {"ok": not errors, "errors": errors, "overlay_count": len(ids)}
