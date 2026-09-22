"""Cam hand gestures — vocabulary, resolver, and learned bindings.

Cam recognizes hand signals with the vocabulary in ``config/gestures/gestures.json``
and remembers what Aaron teaches on top of it (``data/gestures/learned.json``).
The recognizer (MediaPipe in the companion PWA) turns camera frames into
*segments* — ``pose`` held with a ``motion`` for ``duration_ms`` — and this module
turns segments into an *intent*: which gesture fired, what it means, and the
action Cam should take, after context, engagement, identity, and switch gates.

No frames ever reach this module. Only Aaron may teach or forget.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = ROOT / "config" / "gestures" / "gestures.json"
ACTIONS_PATH = ROOT / "config" / "gestures" / "actions.json"
LEARNED_PATH = ROOT / "data" / "gestures" / "learned.json"

SOLE_OPERATOR = "Aaron"
LOG_ONLY = "system.log_only"
ENGAGE = "system.engage"
KIND_RANK = {"sequence": 3, "dynamic": 2, "static": 1}
HANDS_COUNT = {"one": 1, "two": 2}
VALID_SUPPORT = {"canned", "landmark_rule", "custom", "sequence"}
VALID_KINDS = set(KIND_RANK)
VALID_SOURCES = {"huawei", "mediapipe", "cam", "apple", "learned"}
_SLUG = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- load


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_vocabulary(path: Path | None = None) -> dict:
    return load_json(path or VOCAB_PATH)


def load_actions(path: Path | None = None) -> dict:
    return load_json(path or ACTIONS_PATH)


def load_learned(path: Path | None = None) -> dict:
    p = path or LEARNED_PATH
    if not p.exists():
        return {"version": 1, "bindings": [], "feedback": []}
    doc = load_json(p)
    doc.setdefault("bindings", [])
    doc.setdefault("feedback", [])
    return doc


def save_learned(doc: dict, path: Path | None = None) -> Path:
    p = path or LEARNED_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(text: str) -> str:
    return _SLUG.sub("_", text.strip().lower()).strip("_")


# ----------------------------------------------------------------------- validate


def validate(vocab: dict | None = None, actions: dict | None = None, learned: dict | None = None) -> list[str]:
    """Static integrity of the gesture database. Empty list == sound."""
    vocab = vocab or load_vocabulary()
    actions = actions or load_actions()
    errors: list[str] = []

    action_ids = {a["id"] for a in actions.get("actions", [])}
    for a in actions.get("actions", []):
        for key in ("category", "title", "effect", "target", "motor", "sentinel_class"):
            if not a.get(key):
                errors.append(f"action_missing_field:{a.get('id')}:{key}")
        if a.get("category") not in (actions.get("categories") or {}):
            errors.append(f"action_unknown_category:{a.get('id')}:{a.get('category')}")
        if a.get("target") not in (actions.get("targets") or []):
            errors.append(f"action_unknown_target:{a.get('id')}:{a.get('target')}")
        if a.get("sentinel_class") in ("egress", "spend", "self_modify"):
            errors.append(f"action_high_risk_class_not_allowed_for_gesture:{a.get('id')}")
    if len(action_ids) != len(actions.get("actions", [])):
        errors.append("duplicate_action_ids")
    for required in (LOG_ONLY, ENGAGE):
        if required not in action_ids:
            errors.append(f"missing_required_action:{required}")

    pose_ids = {p["id"] for p in vocab["primitives"]["poses"]}
    motion_ids = {m["id"] for m in vocab["primitives"]["motions"]}
    context_ids = {c["id"] for c in vocab.get("contexts", [])}
    canned = set(vocab.get("recognizer", {}).get("canned_labels") or [])
    for p in vocab["primitives"]["poses"]:
        if p.get("support") == "canned" and p.get("label") not in canned:
            errors.append(f"pose_canned_label_unknown:{p['id']}:{p.get('label')}")

    gestures = vocab.get("gestures", [])
    ids = [g["id"] for g in gestures]
    if len(set(ids)) != len(ids):
        errors.append("duplicate_gesture_ids")
    signatures: dict[tuple, list[str]] = {}
    for g in gestures:
        gid = g.get("id", "?")
        if g.get("kind") not in VALID_KINDS:
            errors.append(f"gesture_bad_kind:{gid}")
        if g.get("hands") not in HANDS_COUNT:
            errors.append(f"gesture_bad_hands:{gid}")
        if g.get("support") not in VALID_SUPPORT:
            errors.append(f"gesture_bad_support:{gid}")
        if g.get("source") not in VALID_SOURCES:
            errors.append(f"gesture_bad_source:{gid}")
        if not g.get("meaning"):
            errors.append(f"gesture_missing_meaning:{gid}")
        if g.get("action") not in action_ids:
            errors.append(f"gesture_unknown_action:{gid}:{g.get('action')}")
        steps = g.get("steps") or []
        if not steps:
            errors.append(f"gesture_no_steps:{gid}")
        if g.get("kind") == "sequence" and len(steps) < 2:
            errors.append(f"sequence_needs_two_steps:{gid}")
        if g.get("kind") == "static" and any(s.get("motion") != "hold" for s in steps):
            errors.append(f"static_gesture_must_hold:{gid}")
        for i, s in enumerate(steps):
            if s.get("pose") not in pose_ids:
                errors.append(f"step_unknown_pose:{gid}:{i}:{s.get('pose')}")
            if s.get("motion") not in motion_ids:
                errors.append(f"step_unknown_motion:{gid}:{i}:{s.get('motion')}")
            if s.get("min_ms", 0) < 0 or ("max_ms" in s and s["max_ms"] < s.get("min_ms", 0)):
                errors.append(f"step_bad_duration:{gid}:{i}")
        for c in g.get("contexts") or []:
            if c not in context_ids:
                errors.append(f"gesture_unknown_context:{gid}:{c}")
        if not g.get("contexts"):
            errors.append(f"gesture_no_contexts:{gid}")
        cmin = g.get("confidence_min", 0)
        if not 0.5 <= cmin <= 1.0:
            errors.append(f"gesture_confidence_out_of_range:{gid}")
        for c in g.get("contexts") or []:
            signatures.setdefault(_signature(g, c), []).append(gid)
    for sig, gids in signatures.items():
        if len(gids) > 1:
            errors.append(f"ambiguous_binding:{sig[0]}:{'+'.join(sorted(gids))}")

    if learned is not None:
        for b in learned.get("bindings", []):
            if b.get("taught_by") != SOLE_OPERATOR:
                errors.append(f"learned_not_taught_by_aaron:{b.get('id')}")
            if b.get("action") not in action_ids:
                errors.append(f"learned_unknown_action:{b.get('id')}:{b.get('action')}")
    return errors


def _signature(g: dict, context: str) -> tuple:
    """Two bindings with the same steps, hands, and context are ambiguous."""
    steps = tuple(
        (s["pose"], s["motion"], s.get("min_ms", 0), s.get("max_ms"))
        for s in g.get("steps") or []
    )
    return (context, g.get("hands"), steps)


# ------------------------------------------------------------------------ resolver


@dataclass
class Segment:
    """One recognizer output: a pose held with a motion for a duration."""

    pose: str
    motion: str = "hold"
    duration_ms: int = 300
    confidence: float = 0.9
    hands: int = 1
    t_ms: int = 0
    device: str | None = None

    @classmethod
    def parse(cls, text: str, t_ms: int = 0, device: str | None = None) -> "Segment":
        """``pose[:motion[:duration_ms[:confidence[:hands]]]]``."""
        parts = text.split(":")
        pose = parts[0]
        motion = parts[1] if len(parts) > 1 and parts[1] else "hold"
        duration = int(parts[2]) if len(parts) > 2 and parts[2] else 300
        conf = float(parts[3]) if len(parts) > 3 and parts[3] else 0.9
        hands = int(parts[4]) if len(parts) > 4 and parts[4] else 1
        return cls(pose, motion, duration, conf, hands, t_ms, device)

    @property
    def end_ms(self) -> int:
        return self.t_ms + self.duration_ms


@dataclass
class Intent:
    gesture: str
    name: str
    meaning: str
    action: str
    action_params: dict = field(default_factory=dict)
    context: str = "*"
    bound_in: str = "*"
    source: str = "default"
    confidence: float = 0.0
    fired: bool = True
    hold_reason: str | None = None
    requested_action: str | None = None
    sentinel_class: str = "write_local"
    motor: str = "motor.gesture"
    device: str | None = None
    t_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class GestureResolver:
    """Turn recognizer segments into intents under Cam's gates.

    Gates, in order: switch.gesture_control act → context binding → engagement
    window → confidence → cooldown → Aaron identity (per action). Anything that
    fails a gate after recognition becomes ``system.log_only`` so it can be
    taught later, never a silent drop.
    """

    def __init__(
        self,
        vocab: dict | None = None,
        actions: dict | None = None,
        learned: dict | None = None,
        context: str = "home",
        identity_ok: bool = False,
        switch_act: bool = True,
    ) -> None:
        self.vocab = vocab or load_vocabulary()
        self.actions = {a["id"]: a for a in (actions or load_actions())["actions"]}
        self.learned = learned if learned is not None else load_learned()
        self.context = context
        self.identity_ok = identity_ok
        self.switch_act = switch_act
        g = self.vocab["grammar"]
        self.engagement_poses = set(g["engagement"]["poses"])
        self.engagement_dwell = int(g["engagement"]["dwell_ms"])
        self.engagement_window = int(g["engagement"]["window_ms"])
        self.sequence_timeout = int(g["sequence_timeout_ms"])
        self.carry_ttl = int(g["carry_ttl_ms"])
        self.default_conf = float(g["default_confidence_min"])
        self.default_cooldown = int(g["default_cooldown_ms"])
        self.buffer: list[Segment] = []
        self.engaged_until = -1
        self.carry_deadline: int | None = None
        self.previous_context: str | None = None
        self.last_fired: dict[str, int] = {}
        self.intents: list[Intent] = []

    # -- bindings ---------------------------------------------------------

    def bindings(self) -> list[dict]:
        """Default gestures plus learned bindings, normalized to gesture dicts."""
        out = [dict(g, _source="default") for g in self.vocab.get("gestures", [])]
        for b in self.learned.get("bindings", []):
            base = next((g for g in out if g["id"] == b.get("gesture")), None)
            g = dict(base) if base else {}
            g.update(
                {
                    "id": b["id"],
                    "name": b.get("name") or (base or {}).get("name") or b["id"],
                    "meaning": b.get("meaning"),
                    "action": b.get("action"),
                    "action_params": b.get("action_params") or {},
                    "contexts": b.get("contexts") or ["*"],
                    "steps": b.get("steps") or (base or {}).get("steps") or [],
                    "hands": b.get("hands") or (base or {}).get("hands") or "one",
                    "kind": b.get("kind") or (base or {}).get("kind") or _kind_for(b.get("steps") or (base or {}).get("steps") or []),
                    "confidence_min": b.get("confidence_min", (base or {}).get("confidence_min", self.default_conf)),
                    "cooldown_ms": b.get("cooldown_ms", (base or {}).get("cooldown_ms", self.default_cooldown)),
                    "requires_engagement": b.get("requires_engagement", (base or {}).get("requires_engagement", False)),
                    "priority": b.get("priority", (base or {}).get("priority", 5)),
                    "_source": "learned",
                    "_shadows": b.get("gesture"),
                }
            )
            out.append(g)
        return out

    def bound_in(self, g: dict) -> str | None:
        ctxs = g.get("contexts") or []
        if self.context in ctxs:
            return self.context
        if "*" in ctxs:
            return "*"
        return None

    # -- feeding ----------------------------------------------------------

    def feed(self, seg: Segment) -> list[Intent]:
        out = self._expire(seg.t_ms)
        # Segments older than one sequence timeout before this one can no
        # longer be part of the same gesture.
        while self.buffer and seg.t_ms - self.buffer[0].end_ms > self.sequence_timeout:
            self.buffer.pop(0)
        self.buffer.append(seg)

        # An engagement pose held long enough opens the command window even
        # before any command gesture resolves.
        if seg.pose in self.engagement_poses and seg.motion == "hold" and seg.duration_ms >= self.engagement_dwell and seg.hands == 1:
            self.engaged_until = max(self.engaged_until, seg.end_ms + self.engagement_window)

        candidates = [m for m in (self._match(g, seg) for g in self.bindings()) if m]
        if not candidates:
            return out
        candidates.sort(key=self._rank, reverse=True)
        g, matched = candidates[0]
        intent = self._emit(g, matched, seg)
        # The engage palm stays in the buffer: it is the first step of the
        # grab family. Every other match consumes its segments.
        if g["action"] != ENGAGE:
            self.buffer.clear()
        self.intents.append(intent)
        out.append(intent)
        return out

    def feed_many(self, segments: list[Segment]) -> list[Intent]:
        out: list[Intent] = []
        for s in segments:
            out.extend(self.feed(s))
        return out

    def _expire(self, t_ms: int) -> list[Intent]:
        if self.carry_deadline is None or t_ms <= self.carry_deadline:
            return []
        self.carry_deadline = None
        self.context = self.previous_context or "home"
        self.previous_context = None
        intent = Intent(
            gesture="gesture.handoff_grab",
            name="Carry expired",
            meaning="Handoff window closed without a release; Cam stays on the origin device.",
            action="device.handoff_cancel",
            context=self.context,
            source="timeout",
            fired=True,
            t_ms=t_ms,
        )
        self.intents.append(intent)
        return [intent]

    # -- matching ---------------------------------------------------------

    def _match(self, g: dict, seg: Segment) -> tuple[dict, list[Segment]] | None:
        if self.bound_in(g) is None:
            return None
        steps = g.get("steps") or []
        if not steps or len(steps) > len(self.buffer):
            return None
        need_hands = HANDS_COUNT.get(g.get("hands"), 1)
        tail = self.buffer[-len(steps):]
        for a, b in zip(tail, tail[1:]):
            if b.t_ms - a.end_ms > self.sequence_timeout:
                return None
        cmin = float(g.get("confidence_min", self.default_conf))
        for step, s in zip(steps, tail):
            if s.pose != step["pose"] or s.motion != step.get("motion", "hold"):
                return None
            if s.hands != need_hands:
                return None
            if s.duration_ms < int(step.get("min_ms", 0)):
                return None
            if "max_ms" in step and s.duration_ms > int(step["max_ms"]):
                return None
            if s.confidence < cmin:
                return None
        return g, tail

    def _rank(self, cand: tuple[dict, list[Segment]]) -> tuple:
        """Tie-break order mirrors ``grammar.tie_break`` in gestures.json."""
        g, _ = cand
        return (
            1 if g.get("_source") == "learned" else 0,
            len(g.get("steps") or []),
            1 if self.bound_in(g) == self.context and self.context != "*" else 0,
            KIND_RANK.get(g.get("kind"), 0),
            int(g.get("priority", 0)),
        )

    # -- emitting ---------------------------------------------------------

    def _emit(self, g: dict, matched: list[Segment], seg: Segment) -> Intent:
        action_id = g["action"]
        action = self.actions.get(action_id) or self.actions[LOG_ONLY]
        conf = min(s.confidence for s in matched)
        intent = Intent(
            gesture=g["id"],
            name=g.get("name", g["id"]),
            meaning=g.get("meaning", ""),
            action=action_id,
            action_params=dict(g.get("action_params") or {}),
            context=self.context,
            bound_in=self.bound_in(g) or "*",
            source=g.get("_source", "default"),
            confidence=round(conf, 3),
            sentinel_class=action.get("sentinel_class", "write_local"),
            motor=action.get("motor", "motor.gesture"),
            device=seg.device,
            t_ms=seg.end_ms,
        )
        hold = self._gate(g, action, matched, seg)
        if hold:
            intent.fired = False
            intent.hold_reason = hold
            intent.requested_action = action_id
            intent.action = LOG_ONLY
            intent.motor = self.actions[LOG_ONLY]["motor"]
            intent.sentinel_class = self.actions[LOG_ONLY]["sentinel_class"]
            return intent
        self.last_fired[g["id"]] = seg.end_ms
        self._transition(action_id, seg)
        return intent

    def _gate(self, g: dict, action: dict, matched: list[Segment], seg: Segment) -> str | None:
        if not self.switch_act:
            return "switch.gesture_control hold — Aaron has not enabled live gesture control"
        if g.get("requires_engagement"):
            first = matched[0]
            self_engaging = first.pose in self.engagement_poses and first.motion == "hold" and first.duration_ms >= self.engagement_dwell
            if not self_engaging and self.engaged_until < first.t_ms:
                return "not engaged — hold an open palm to the screen first"
        last = self.last_fired.get(g["id"])
        cooldown = int(g.get("cooldown_ms", self.default_cooldown))
        if last is not None and seg.end_ms - last < cooldown and action["id"] != ENGAGE:
            return f"cooldown {cooldown} ms"
        if action.get("aaron_identity_required") and not self.identity_ok:
            return "aaron_identity_required — switch.identity must see Aaron's face/voice"
        if action.get("confirm"):
            return "confirm required — thumb_up or voice yes"
        return None

    def _transition(self, action_id: str, seg: Segment) -> None:
        if action_id == "device.handoff_grab":
            self.previous_context = self.context
            self.context = "carrying"
            self.carry_deadline = seg.end_ms + self.carry_ttl
        elif action_id in ("device.handoff_release", "device.handoff_cancel"):
            self.carry_deadline = None
            self.context = self.previous_context or "home"
            self.previous_context = None
        elif action_id == ENGAGE:
            self.engaged_until = max(self.engaged_until, seg.end_ms + self.engagement_window)


def _kind_for(steps: list[dict]) -> str:
    if len(steps) >= 2:
        return "sequence"
    if steps and steps[0].get("motion", "hold") != "hold":
        return "dynamic"
    return "static"


# -------------------------------------------------------------------- remembering


def find_binding(vocab: dict, learned: dict, steps: list[dict], hands: str, contexts: list[str]) -> list[dict]:
    """Existing default or learned gestures with the same signature in any of ``contexts``."""
    probe = {"steps": steps, "hands": hands}
    hits: list[dict] = []
    for g in list(vocab.get("gestures", [])) + list(learned.get("bindings", [])):
        g_steps = g.get("steps") or next(
            (d.get("steps") for d in vocab.get("gestures", []) if d["id"] == g.get("gesture")), []
        )
        g_hands = g.get("hands") or next(
            (d.get("hands") for d in vocab.get("gestures", []) if d["id"] == g.get("gesture")), "one"
        )
        candidate = {"steps": g_steps, "hands": g_hands}
        for c in contexts:
            if _signature(candidate, c) == _signature(probe, c) and c in (g.get("contexts") or []):
                hits.append(g)
                break
    return hits


def teach(
    *,
    name: str,
    meaning: str,
    action: str,
    contexts: list[str] | None = None,
    steps: list[dict] | None = None,
    like: str | None = None,
    by: str = "",
    replace: bool = False,
    samples: int = 0,
    vocab: dict | None = None,
    actions: dict | None = None,
    learned: dict | None = None,
    learned_path: Path | None = None,
    write: bool = True,
) -> dict:
    """Aaron binds a gesture (new steps, or ``like`` an existing gesture) to a meaning + action."""
    if by != SOLE_OPERATOR:
        raise PermissionError(f"only {SOLE_OPERATOR} may teach gestures (got {by!r})")
    vocab = vocab or load_vocabulary()
    actions = actions or load_actions()
    learned = learned if learned is not None else load_learned(learned_path)
    action_ids = {a["id"] for a in actions["actions"]}
    if action not in action_ids:
        raise ValueError(f"unknown action {action!r}; see config/gestures/actions.json")
    contexts = contexts or ["*"]
    context_ids = {c["id"] for c in vocab.get("contexts", [])}
    unknown = [c for c in contexts if c not in context_ids]
    if unknown:
        raise ValueError(f"unknown contexts {unknown}")

    base = None
    if like:
        base = next((g for g in vocab.get("gestures", []) if g["id"] == like), None)
        if base is None:
            raise ValueError(f"unknown gesture {like!r} to teach like")
    steps = steps or (base or {}).get("steps")
    if not steps:
        raise ValueError("teach needs --steps or --like <gesture>")
    hands = (base or {}).get("hands", "one")
    pose_ids = {p["id"] for p in vocab["primitives"]["poses"]}
    motion_ids = {m["id"] for m in vocab["primitives"]["motions"]}
    for s in steps:
        if s.get("pose") not in pose_ids or s.get("motion", "hold") not in motion_ids:
            raise ValueError(f"step uses unknown pose/motion: {s}")

    conflicts = find_binding(vocab, learned, steps, hands, contexts)
    if conflicts and not replace:
        existing = ", ".join(f"{c.get('id')} → {c.get('action')} ({c.get('meaning')})" for c in conflicts)
        raise ValueError(f"already bound in {contexts}: {existing}; pass replace to override")

    bid = f"learned.{slug(name)}"
    learned["bindings"] = [b for b in learned["bindings"] if b["id"] != bid]
    binding = {
        "id": bid,
        "gesture": like,
        "name": name,
        "meaning": meaning,
        "action": action,
        "contexts": contexts,
        "steps": steps,
        "hands": hands,
        "kind": _kind_for(steps),
        "taught_by": by,
        "taught_at": _now_iso(),
        "samples": samples,
        "replaced": [c.get("id") for c in conflicts],
        "uses": 0,
        "confirms": 0,
        "rejects": 0,
    }
    learned["bindings"].append(binding)
    if write:
        save_learned(learned, learned_path)
    return binding


def forget(binding_id: str, *, by: str = "", learned: dict | None = None, learned_path: Path | None = None, write: bool = True) -> dict:
    if by != SOLE_OPERATOR:
        raise PermissionError(f"only {SOLE_OPERATOR} may forget gestures (got {by!r})")
    learned = learned if learned is not None else load_learned(learned_path)
    hit = next((b for b in learned["bindings"] if b["id"] == binding_id), None)
    if hit is None:
        raise KeyError(f"no learned binding {binding_id}")
    learned["bindings"] = [b for b in learned["bindings"] if b["id"] != binding_id]
    if write:
        save_learned(learned, learned_path)
    return hit


def feedback(binding_id: str, *, confirmed: bool, learned: dict | None = None, learned_path: Path | None = None, write: bool = True) -> dict:
    """Reinforcement from thumb_up / thumb_down after a learned gesture fired."""
    learned = learned if learned is not None else load_learned(learned_path)
    hit = next((b for b in learned["bindings"] if b["id"] == binding_id), None)
    if hit is None:
        raise KeyError(f"no learned binding {binding_id}")
    hit["uses"] = int(hit.get("uses", 0)) + 1
    hit["confirms" if confirmed else "rejects"] = int(hit.get("confirms" if confirmed else "rejects", 0)) + 1
    learned["feedback"].append({"binding": binding_id, "confirmed": confirmed, "at": _now_iso()})
    if write:
        save_learned(learned, learned_path)
    return hit


def recalibration_flags(learned: dict, min_uses: int = 20, reject_rate: float = 0.3) -> list[str]:
    flagged = []
    for b in learned.get("bindings", []):
        uses = int(b.get("uses", 0))
        if uses >= min_uses and int(b.get("rejects", 0)) / uses > reject_rate:
            flagged.append(b["id"])
    return flagged


# ------------------------------------------------------------------------- mesh


def pack_intent(intent: Intent, *, namespace: str | None = None) -> dict:
    """Distill one intent for mesh/gestures — no frames, no landmarks."""
    ns = namespace or load_vocabulary().get("mesh_namespace", "mesh/gestures")
    return {
        "ns": ns,
        "kind": "gesture_intent",
        "at": _now_iso(),
        "gesture": intent.gesture,
        "meaning": intent.meaning,
        "action": intent.action,
        "requested_action": intent.requested_action,
        "fired": intent.fired,
        "hold_reason": intent.hold_reason,
        "context": intent.context,
        "device": intent.device,
        "confidence": intent.confidence,
        "source": intent.source,
    }


def catalog(vocab: dict | None = None, actions: dict | None = None, context: str | None = None) -> list[dict]:
    """Human table: gesture → meaning → action, optionally filtered by context."""
    vocab = vocab or load_vocabulary()
    acts = {a["id"]: a for a in (actions or load_actions())["actions"]}
    rows = []
    for g in vocab.get("gestures", []):
        if context and context not in g.get("contexts", []) and "*" not in g.get("contexts", []):
            continue
        a = acts.get(g["action"], {})
        rows.append(
            {
                "gesture": g["id"],
                "name": g["name"],
                "how": " → ".join(f"{s['pose']}/{s.get('motion', 'hold')}≥{s.get('min_ms', 0)}ms" for s in g["steps"]),
                "meaning": g["meaning"],
                "action": g["action"],
                "does": a.get("effect", ""),
                "contexts": g.get("contexts", []),
                "aaron_only": bool(a.get("aaron_identity_required")),
                "support": g.get("support"),
                "source": g.get("source"),
            }
        )
    return rows
