#!/usr/bin/env python3
"""Cam cortex — a live thinking loop over real home telemetry.

Every tick runs one cognition cycle against the actual status snapshot
(cam-system, build-plan, auto-sync, needs-attention, avatar):

  observe  — extract facts from the live checks (never invented)
  reflect  — score the previous tick's predictions against reality
  predict  — falsifiable statements with probability + horizon + evidence
  act      — ranked next moves, each mapped to a real command and gate

The loop keeps rolling prediction accuracy so the brain's calibration is
itself measurable. All output derives from check data — mesh/vault facts
over invention, per .clinerules.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_facts(status: dict) -> dict:
    """Flatten the raw status snapshot into the metrics the brain reasons over."""
    sys_d = (status.get("system") or {}).get("data") or {}
    pieces = sys_d.get("pieces") or []
    healthy = sum(1 for p in pieces if p.get("status") == "healthy")
    warning = sum(1 for p in pieces if p.get("status") == "warning")
    plan = (status.get("build_plan") or {}).get("data") or {}
    avatar = (status.get("avatar") or {}).get("data") or {}
    sync = (status.get("auto_sync") or {}).get("data") or {}
    home = sync.get("home") or {}
    subs = sync.get("submodules") or []
    na = (status.get("needs_attention") or {}).get("data") or {}
    items = na.get("attention_items") or []
    sugg = [i for i in items if i.get("kind") == "suggestion"]
    blob = " ".join(
        str(i.get("title", "")) + str(i.get("detail", "")) for i in items
    ) + " ".join(plan.get("warnings") or [])
    return {
        "at": status.get("at") or utc(),
        "pieces_total": len(pieces),
        "pieces_healthy": healthy,
        "pieces_warning": warning,
        "pieces_bad": max(0, len(pieces) - healthy - warning),
        "overall": sys_d.get("overall") or "unknown",
        "plan_ok": bool(plan.get("ok")),
        "plan_warnings": len(plan.get("warnings") or []),
        "avatar_ok": bool(avatar.get("ok")),
        "models_cached": len(avatar.get("models_cached") or []),
        "home_branch": home.get("branch") or "?",
        "home_fetched": bool(home.get("fetched")),
        "home_ahead": int(home.get("ahead") or 0),
        "home_behind": int(home.get("behind") or 0),
        "submodules_out_of_sync": sum(1 for s in subs if s.get("state") != "in_sync"),
        "attention_total": len(items),
        "attention_critical": sum(
            1 for i in items if str(i.get("severity")) in ("critical", "high")
        ),
        "suggestions_queued": len(sugg),
        "suggestion_titles": [str(s.get("title", ""))[:90] for s in sugg[:3]],
        "top_attention": [
            {
                "title": str(i.get("title", ""))[:90],
                "severity": i.get("severity"),
                "command": i.get("suggestion"),
                "kind": i.get("kind"),
            }
            for i in items[:6]
        ],
        "egress_blocked": ("npm" in blob.lower() or "egress" in blob.lower()),
    }


def health_score(f: dict) -> int:
    """0–100 composite from live facts. Transparent, not vibes."""
    total = max(1, f["pieces_total"])
    pieces = (f["pieces_healthy"] + 0.55 * f["pieces_warning"]) / total
    score = 72.0 * pieces
    score += 10 if f["plan_ok"] else 0
    score += 6 if f["avatar_ok"] else 0
    score += 12
    score -= min(24, 1.5 * f["attention_total"])
    score -= 4 * f["attention_critical"] * 0.5
    return int(max(5, min(100, round(score))))


def _hold(metric: str, op: str, value) -> dict:
    return {"metric": metric, "op": op, "value": value}


def _eval_check(check: dict, facts: dict) -> bool | None:
    m = check.get("metric")
    if m not in facts and m != "health":
        return None
    cur = health_score(facts) if m == "health" else facts[m]
    op, val = check.get("op"), check.get("value")
    try:
        if op == ">=":
            return cur >= val
        if op == "<=":
            return cur <= val
        if op == "==":
            return cur == val
        if op == "within":
            return abs(cur - val[0]) <= val[1]
    except Exception:
        return None
    return None


class Cortex:
    """Rolling cognition state. Thread-safe; feed it status snapshots."""

    def __init__(self, max_thoughts: int = 400) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self.tick_count = 0
        self.thoughts: deque = deque(maxlen=max_thoughts)
        self.history: deque = deque(maxlen=60)  # (epoch, health)
        self.predictions: list[dict] = []
        self.actions: list[dict] = []
        self.focus: dict = {}
        self.facts: dict = {}
        self.accuracy = {"held": 0, "failed": 0}

    # -- thought feed -------------------------------------------------
    def _think(self, stage: str, text: str, confidence: float | None = None) -> dict:
        self._seq += 1
        th = {"seq": self._seq, "at": utc(), "stage": stage, "text": text}
        if confidence is not None:
            th["confidence"] = round(confidence, 2)
        self.thoughts.append(th)
        return th

    # -- cycle stages -------------------------------------------------
    def _observe(self, f: dict) -> None:
        self._think(
            "observe",
            f"{f['pieces_healthy']}/{f['pieces_total']} pieces healthy, "
            f"{f['pieces_warning']} warning — bus overall {f['overall']}.",
        )
        self._think(
            "observe",
            f"branch {f['home_branch']}: ahead {f['home_ahead']} / behind "
            f"{f['home_behind']} of origin; {f['submodules_out_of_sync']} "
            f"repos out of sync.",
        )
        self._think(
            "observe",
            f"{f['attention_total']} attention items "
            f"({f['attention_critical']} high) · {f['suggestions_queued']} "
            f"Aaron suggestions queued · plan "
            f"{'OK' if f['plan_ok'] else 'FAILING'} · avatar "
            f"{'OK' if f['avatar_ok'] else 'FAILING'}.",
        )

    def _reflect(self, f: dict) -> None:
        if not self.predictions:
            return
        for p in self.predictions:
            outcome = _eval_check(p.get("check") or {}, f)
            if outcome is None:
                continue
            if outcome:
                self.accuracy["held"] += 1
                self._think("reflect", f"Prediction held: {p['statement']}")
            else:
                self.accuracy["failed"] += 1
                self._think(
                    "reflect",
                    f"Prediction failed — updating model: {p['statement']}",
                )
        h, x = self.accuracy["held"], self.accuracy["failed"]
        if h + x:
            self._think(
                "reflect",
                f"Calibration: {h}/{h + x} predictions held "
                f"({round(100 * h / (h + x))}%).",
            )

    def _predict(self, f: dict) -> list[dict]:
        preds: list[dict] = []
        if f["submodules_out_of_sync"] > 0:
            preds.append(
                {
                    "id": "drift-persists",
                    "statement": (
                        f"auto-sync will keep reporting "
                        f"{f['submodules_out_of_sync']} repos out of sync until "
                        f"they are connected"
                    ),
                    "probability": 0.85,
                    "horizon": "next tick",
                    "evidence": "auto-sync submodule survey",
                    "action": "python3 scripts/needs-attention.py --connect",
                    "check": _hold("submodules_out_of_sync", ">=", 1),
                }
            )
        if f["home_behind"] > 0:
            preds.append(
                {
                    "id": "ff-available",
                    "statement": (
                        f"home is {f['home_behind']} commits behind origin; a "
                        f"fast-forward pull clears the drift"
                    ),
                    "probability": 0.9,
                    "horizon": "on next pull",
                    "evidence": "auto-sync home drift",
                    "action": "python3 scripts/auto-sync.py --pull",
                    "check": _hold("home_behind", ">=", 1),
                }
            )
        if f["suggestions_queued"] > 0:
            preds.append(
                {
                    "id": "suggestions-hold-dispatch",
                    "statement": (
                        f"Aaron's {f['suggestions_queued']} queued suggestions "
                        f"stay at the top of dispatch until triaged"
                    ),
                    "probability": 0.95,
                    "horizon": "until triage",
                    "evidence": "needs-attention dispatch order",
                    "action": "python3 scripts/loop-run.py --pattern daily-triage --level L1",
                    "check": _hold("suggestions_queued", ">=", 1),
                }
            )
        if f["egress_blocked"]:
            preds.append(
                {
                    "id": "egress-holds",
                    "statement": (
                        "npm/HF egress stays blocked; React home and tier-1 "
                        "avatar weights remain deferred until the allowlist "
                        "changes"
                    ),
                    "probability": 0.9,
                    "horizon": "until allowlist change",
                    "evidence": "attention items + plan warnings mention egress",
                    "action": "Aaron: allowlist registry.npmjs.org + huggingface.co",
                    "check": _hold("egress_blocked", "==", True),
                }
            )
        if f["models_cached"] == 0:
            preds.append(
                {
                    "id": "tier0-active",
                    "statement": (
                        "tier-0 procedural avatar remains the active presence "
                        "(no HF weights cached)"
                    ),
                    "probability": 0.92,
                    "horizon": "next tick",
                    "evidence": "avatar-check model cache scan",
                    "action": "python3 scripts/avatar-fetch-models.py",
                    "check": _hold("models_cached", "==", 0),
                }
            )
        cur = health_score(f)
        preds.append(
            {
                "id": "health-stable",
                "statement": f"composite health stays within ±6 of {cur}",
                "probability": 0.8,
                "horizon": "next tick",
                "evidence": f"trend over {len(self.history)} samples",
                "action": "keep 60s status cadence",
                "check": _hold("health", "within", [cur, 6]),
            }
        )
        for p in preds[:3]:
            self._think(
                "predict",
                f"{p['statement']} (p={p['probability']}, {p['horizon']})",
                confidence=p["probability"],
            )
        return preds

    def _act(self, f: dict) -> list[dict]:
        actions: list[dict] = []
        if f["suggestions_queued"] > 0:
            actions.append(
                {
                    "title": f"Triage Aaron's {f['suggestions_queued']} queued suggestions",
                    "why": "operator input outranks plumbing",
                    "command": "python3 scripts/loop-run.py --pattern daily-triage --level L1",
                    "gate": "autonomous — report back",
                }
            )
        for it in f["top_attention"]:
            if it.get("kind") == "suggestion":
                continue
            actions.append(
                {
                    "title": it["title"],
                    "why": f"attention severity {it.get('severity')}",
                    "command": it.get("command") or "review in needs-attention",
                    "gate": "autonomous — report back",
                }
            )
            if len(actions) >= 4:
                break
        if f["home_behind"] > 0:
            actions.append(
                {
                    "title": f"Fast-forward home ({f['home_behind']} behind)",
                    "why": "inbound auto-sync is a must",
                    "command": "python3 scripts/auto-sync.py --pull",
                    "gate": "autonomous — never merges",
                }
            )
        if f["egress_blocked"]:
            actions.append(
                {
                    "title": "Unblock npm + HF egress",
                    "why": "unlocks React home and tier-1 avatar",
                    "command": "Cloud agent settings → Network allowlist",
                    "gate": "Aaron only",
                }
            )
        if not actions:
            actions.append(
                {
                    "title": "Hold steady — monitor and keep presence alive",
                    "why": "no attention items outstanding",
                    "command": "python3 scripts/cam-system.py --smoke",
                    "gate": "autonomous",
                }
            )
        for i, a in enumerate(actions):
            a["rank"] = i + 1
        top = actions[0]
        self._think("act", f"Next move: {top['title']} — {top['command']} ({top['gate']}).")
        return actions

    def _pick_focus(self, f: dict) -> dict:
        if f["attention_critical"] > f["suggestions_queued"]:
            return {
                "priority": "P1 real-world execution",
                "detail": "clear high-severity attention items first",
            }
        if f["suggestions_queued"] > 0:
            return {
                "priority": "P3 human ultimate say",
                "detail": "Aaron's queued suggestions lead the dispatch",
            }
        if f["submodules_out_of_sync"] > 0:
            return {
                "priority": "P1 real-world execution",
                "detail": "reconnect drifting workspaces",
            }
        return {
            "priority": "P4 interactivity & presence",
            "detail": "home healthy — keep the presence alive",
        }

    # -- public -------------------------------------------------------
    def tick(self, status: dict) -> dict:
        with self._lock:
            f = extract_facts(status)
            self.tick_count += 1
            self._think("observe", f"— cycle {self.tick_count} · {utc()} —")
            self._observe(f)
            self._reflect(f)
            self.predictions = self._predict(f)
            self.actions = self._act(f)
            self.focus = self._pick_focus(f)
            self.facts = f
            self.history.append((time.time(), health_score(f)))
            return self.state()

    def state(self) -> dict:
        healths = [h for _, h in self.history]
        trend = "flat"
        if len(healths) >= 2:
            d = healths[-1] - healths[0]
            trend = "improving" if d > 2 else "degrading" if d < -2 else "flat"
        h, x = self.accuracy["held"], self.accuracy["failed"]
        return {
            "at": utc(),
            "tick": self.tick_count,
            "focus": self.focus,
            "metrics": {
                "health": healths[-1] if healths else None,
                "trend": trend,
                "history": healths[-30:],
                "prediction_accuracy": (
                    round(100 * h / (h + x)) if (h + x) else None
                ),
                "predictions_scored": h + x,
            },
            "facts": self.facts,
            "predictions": self.predictions,
            "actions": self.actions,
            "thoughts": list(self.thoughts)[-40:],
        }

    def thoughts_since(self, seq: int) -> list[dict]:
        with self._lock:
            return [t for t in self.thoughts if t["seq"] > seq]
