#!/usr/bin/env python3
"""Cam cortex — a live thinking loop over real home telemetry.

Every tick runs one cognition cycle against the actual status snapshot
(cam-system, build-plan, auto-sync, needs-attention, avatar):

  observe  — extract named facts from the live checks (never invented)
  analyze  — diff against the previous cycle: what actually changed and why
  reflect  — score the previous tick's predictions against reality
  predict  — falsifiable statements with probability + horizon + evidence
  act      — ranked next moves, each mapped to a real command and gate

The loop keeps rolling prediction accuracy so the brain's calibration is
itself measurable, and exposes an anatomical activity feed: each thought
stage fires the matching cortical areas/tracts of the connectome viz
(observe→sensory intake, analyze→semantic+ACC, reflect→MTL memory loop,
predict→DLPFC/aPFC planning, act→premotor/M1 output). External events —
Aaron making Cam speak, filing a suggestion — arrive as sensory notes and
light the language pathways. All of it derives from check data: mesh/vault
facts over invention, per .clinerules.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- facts

def extract_facts(status: dict) -> dict:
    """Flatten the raw status snapshot into named metrics the brain reasons over."""
    sys_d = (status.get("system") or {}).get("data") or {}
    pieces = sys_d.get("pieces") or []
    piece_status = {
        (p.get("id") or p.get("title") or f"piece{i}"): p.get("status", "?")
        for i, p in enumerate(pieces)
    }
    healthy = sum(1 for s in piece_status.values() if s == "healthy")
    warning_names = sorted(k for k, s in piece_status.items() if s == "warning")
    bad_names = sorted(
        k for k, s in piece_status.items() if s not in ("healthy", "warning")
    )
    plan = (status.get("build_plan") or {}).get("data") or {}
    avatar = (status.get("avatar") or {}).get("data") or {}
    sync = (status.get("auto_sync") or {}).get("data") or {}
    home = sync.get("home") or {}
    subs = sync.get("submodules") or []
    out_names = sorted(
        s.get("path", "?") for s in subs if s.get("state") != "in_sync"
    )
    na = (status.get("needs_attention") or {}).get("data") or {}
    items = na.get("attention_items") or []
    sugg = [i for i in items if i.get("kind") == "suggestion"]
    events = []
    for e in (status.get("recent_events") or [])[-6:]:
        title = e.get("title") or ""
        if not title:
            neuron = str(e.get("neuron") or e.get("source") or "").replace("neuron.", "")
            reason = str(e.get("reason") or e.get("kind") or e.get("event") or "")
            title = f"{neuron} {reason}".strip()
        events.append(
            {
                "at": str(e.get("at") or e.get("ts") or ""),
                "title": str(title)[:90],
            }
        )
    blob = " ".join(
        str(i.get("title", "")) + str(i.get("detail", "")) for i in items
    ) + " ".join(plan.get("warnings") or [])
    return {
        "at": status.get("at") or utc(),
        "pieces_total": len(pieces),
        "pieces_healthy": healthy,
        "pieces_warning": len(warning_names),
        "pieces_bad": len(bad_names),
        "piece_status": piece_status,
        "warning_pieces": warning_names,
        "bad_pieces": bad_names,
        "overall": sys_d.get("overall") or "unknown",
        "plan_ok": bool(plan.get("ok")),
        "plan_warnings": len(plan.get("warnings") or []),
        "avatar_ok": bool(avatar.get("ok")),
        "models_cached": len(avatar.get("models_cached") or []),
        "home_branch": home.get("branch") or "?",
        "home_fetched": bool(home.get("fetched")),
        "home_ahead": int(home.get("ahead") or 0),
        "home_behind": int(home.get("behind") or 0),
        "submodules_out_of_sync": len(out_names),
        "out_of_sync_names": out_names,
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
        "recent_events": events,
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


def _names(names: list[str], keep: int = 3) -> str:
    if not names:
        return "none"
    head = ", ".join(names[:keep])
    extra = len(names) - keep
    return f"{head} +{extra} more" if extra > 0 else head


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


# ------------------------------------------------- anatomy of a thought

# Each cognition stage fires the matching cortical circuitry of the
# connectome viz (areas/tracts/neurons are the viz's real ids).
STAGE_ANATOMY: dict[str, list[dict]] = {
    "observe": [
        {"neuron": "neuron.research", "area": "area.visual",
         "tracts": ["tract.ilf", "tract.vof"]},
        {"neuron": "neuron.language_in", "area": "area.wernicke",
         "tracts": ["tract.arcuate", "tract.mdlf"]},
    ],
    "analyze": [
        {"neuron": "neuron.semantic", "area": "area.temporal",
         "tracts": ["tract.emc", "tract.uncinate"]},
        {"neuron": "neuron.qa_cycle", "area": "area.cingulate",
         "tracts": ["tract.cingulum", "tract.slf"]},
    ],
    "reflect": [
        {"neuron": "neuron.memory", "area": "area.mtl",
         "tracts": ["tract.fornix", "tract.cingulum", "tract.cingulum2"]},
    ],
    "predict": [
        {"neuron": "neuron.plan_loop", "area": "area.dlpfc",
         "tracts": ["tract.slf", "tract.forceps_minor"]},
        {"neuron": "neuron.cartographer", "area": "area.apfc",
         "tracts": ["tract.ifof"]},
    ],
    "act": [
        {"neuron": "neuron.motor_plan", "area": "area.premotor",
         "tracts": ["tract.fat"]},
        {"neuron": "neuron.effector", "area": "area.motor",
         "tracts": ["tract.corticospinal"]},
    ],
    "speech": [
        {"neuron": "neuron.speak_loop", "area": "area.broca",
         "tracts": ["tract.arcuate", "tract.fat", "tract.corticospinal"]},
        {"neuron": "neuron.asr", "area": "area.auditory",
         "tracts": ["tract.mdlf"]},
    ],
    "input": [
        {"neuron": "neuron.language_in", "area": "area.wernicke",
         "tracts": ["tract.arcuate", "tract.af_posterior"]},
        {"neuron": "neuron.memory", "area": "area.mtl",
         "tracts": ["tract.cingulum"]},
    ],
}


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
        self.prev_facts: dict = {}
        self.accuracy = {"held": 0, "failed": 0}

    # -- thought feed -------------------------------------------------
    def _think(self, stage: str, text: str, confidence: float | None = None) -> dict:
        self._seq += 1
        th = {
            "seq": self._seq,
            "at": utc(),
            "ts": time.time(),
            "stage": stage,
            "text": text,
        }
        if confidence is not None:
            th["confidence"] = round(confidence, 2)
        self.thoughts.append(th)
        return th

    def note(self, stage: str, text: str) -> dict:
        """External sensory/motor event (Aaron spoke to her, she spoke, …)."""
        with self._lock:
            return self._think(stage, text)

    def note_speech(self, text: str) -> dict:
        return self.note("speech", f"Speaking for Aaron: “{text[:90]}”")

    def note_input(self, text: str) -> dict:
        return self.note("input", f"Aaron filed a suggestion: “{text[:90]}”")

    # -- cycle stages -------------------------------------------------
    def _observe(self, f: dict) -> None:
        warn_txt = (
            f" — warning: {_names(f['warning_pieces'])}" if f["warning_pieces"] else ""
        )
        bad_txt = f" — down: {_names(f['bad_pieces'])}" if f["bad_pieces"] else ""
        self._think(
            "observe",
            f"{f['pieces_healthy']}/{f['pieces_total']} pieces healthy on the bus"
            f"{warn_txt}{bad_txt}.",
        )
        drift_names = (
            f" ({_names(f['out_of_sync_names'])})" if f["out_of_sync_names"] else ""
        )
        self._think(
            "observe",
            f"branch {f['home_branch']}: ahead {f['home_ahead']} / behind "
            f"{f['home_behind']} of origin; {f['submodules_out_of_sync']} repos "
            f"out of sync{drift_names}.",
        )
        top = f["top_attention"][0]["title"] if f["top_attention"] else "none"
        self._think(
            "observe",
            f"{f['attention_total']} attention items "
            f"({f['attention_critical']} high) — top: {top}.",
        )
        if f["recent_events"]:
            e = f["recent_events"][-1]
            self._think("observe", f"last bus event: {e['title']} ({e['at']}).")

    def _analyze(self, f: dict) -> None:
        prev = self.prev_facts
        if not prev:
            self._think(
                "analyze",
                f"first cycle — baseline set: health {health_score(f)}, "
                f"{f['attention_total']} attention items, "
                f"{f['submodules_out_of_sync']} repos drifting.",
            )
            return
        changes: list[str] = []
        for pid, cur in f["piece_status"].items():
            old = (prev.get("piece_status") or {}).get(pid)
            if old is not None and old != cur:
                changes.append(f"{pid}: {old}→{cur}")
        for key, label in (
            ("attention_total", "attention items"),
            ("submodules_out_of_sync", "repos drifting"),
            ("suggestions_queued", "Aaron suggestions"),
            ("home_behind", "commits behind origin"),
        ):
            if prev.get(key) is not None and prev[key] != f[key]:
                changes.append(f"{label} {prev[key]}→{f[key]}")
        dh = health_score(f) - health_score(prev)
        if changes:
            self._think(
                "analyze",
                f"since last cycle: {'; '.join(changes[:5])} — health "
                f"{'+' if dh >= 0 else ''}{dh}.",
            )
        else:
            self._think(
                "analyze",
                f"no state change across {f['pieces_total']} pieces and "
                f"{f['attention_total']} attention items — steady state; "
                f"confidence in standing predictions deepens.",
            )
        prev_ev = {e["title"] for e in prev.get("recent_events") or []}
        fresh = [e for e in f["recent_events"] if e["title"] not in prev_ev]
        if fresh:
            self._think(
                "analyze",
                f"new bus activity: {_names([e['title'] for e in fresh], 2)}.",
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
                        f"{_names(f['out_of_sync_names'], 2)} stay out of sync "
                        f"until reconnected ({f['submodules_out_of_sync']} total)"
                    ),
                    "probability": 0.85,
                    "horizon": "next tick",
                    "evidence": f"auto-sync survey: {_names(f['out_of_sync_names'], 3)}",
                    "action": "python3 scripts/needs-attention.py --connect",
                    "check": _hold("submodules_out_of_sync", ">=", 1),
                }
            )
        if f["home_behind"] > 0:
            preds.append(
                {
                    "id": "ff-available",
                    "statement": (
                        f"{f['home_branch']} is {f['home_behind']} commits behind "
                        f"origin; a fast-forward pull clears the drift"
                    ),
                    "probability": 0.9,
                    "horizon": "on next pull",
                    "evidence": f"auto-sync home drift on {f['home_branch']}",
                    "action": "python3 scripts/auto-sync.py --pull",
                    "check": _hold("home_behind", ">=", 1),
                }
            )
        if f["suggestions_queued"] > 0:
            first = f["suggestion_titles"][0] if f["suggestion_titles"] else ""
            preds.append(
                {
                    "id": "suggestions-hold-dispatch",
                    "statement": (
                        f"Aaron's {f['suggestions_queued']} queued suggestions "
                        f"(“{first[:60]}…”) stay at the top of dispatch until triaged"
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
                        "avatar weights remain deferred until the allowlist changes"
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
            self._analyze(f)
            self._reflect(f)
            self.predictions = self._predict(f)
            self.actions = self._act(f)
            self.focus = self._pick_focus(f)
            self.prev_facts = f
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

    def activity(self, window_s: float = 90.0) -> dict:
        """Anatomical firing feed for the connectome viz — her thinking, live.

        Recent thoughts fire their stage's cortical areas/tracts with
        recency-decayed intensity; the reason string is the actual thought.
        Shape matches vault/10-Mesh-Distillates/live-activity.json.
        """
        with self._lock:
            now = time.time()
            latest: dict[str, dict] = {}
            for th in self.thoughts:
                age = now - th.get("ts", now)
                if age > window_s:
                    continue
                cur = latest.get(th["stage"])
                if cur is None or th["seq"] > cur["seq"]:
                    latest[th["stage"]] = th
            firing: list[dict] = []
            for stage, th in latest.items():
                age = now - th.get("ts", now)
                intensity = max(0.35, 0.95 - (age / window_s) * 0.6)
                for unit in STAGE_ANATOMY.get(stage, []):
                    firing.append(
                        {
                            "neuron": unit["neuron"],
                            "kind": f"thought.{stage}",
                            "area": unit["area"],
                            "intensity": round(intensity, 2),
                            "tracts": unit["tracts"],
                            "reason": f"{stage}: {th['text'][:110]}",
                            "ts": th["at"],
                        }
                    )
            firing.sort(key=lambda x: -x["intensity"])
            return {
                "at": utc(),
                "epoch": int(now),
                "source": "cam_cortex",
                "tick": self.tick_count,
                "firing": firing,
                "active_areas": sorted({f["area"] for f in firing}),
                "active_tracts": sorted(
                    {t for f in firing for t in f["tracts"]}
                ),
                "firing_count": len(firing),
                "health_overall": (
                    "ok" if (self.history and self.history[-1][1] >= 60) else "warning"
                ),
            }
