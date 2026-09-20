#!/usr/bin/env python3
"""Cam live reasoning core — the piece that was missing.

Previously `cam_reply()` was keyword→canned-phrase matching and
`cam_reason.py` was an explicit dry-run stub, so Cam never actually
thought about anything. This module is a real reasoning core with two
layers:

1. **Live LLM layer** (best answers, used when reachable):
   - Any OpenAI-compatible endpoint via `CAM_LLM_BASE_URL` (+ optional
     `CAM_LLM_API_KEY`, `CAM_LLM_MODEL`) — covers LM Studio, llama.cpp,
     vLLM, OpenRouter, etc.
   - OpenAI via `OPENAI_API_KEY`
   - Anthropic via `ANTHROPIC_API_KEY`
   - Local Ollama via `OLLAMA_HOST` (default http://127.0.0.1:11434)

2. **Local cortex** (always available, no network): intent parsing,
   durable memory (remember/recall), vault retrieval grounding, math,
   date/time, reminders, and task dispatch to agent teams.

Everything persists under `data/runtime/` so Cam remembers across
restarts. Stdlib + optional numpy only.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime"
MEMORY_PATH = RUNTIME / "cam-memory.json"
HISTORY_PATH = RUNTIME / "cam-history.jsonl"
VAULT = ROOT / "vault"

AARON_TZ = "America/New_York"

PERSONA_PROMPT = (
    "You are Cam, Aaron's personal assistant: 32, from Argentina, blue eyes, "
    "brown hair, soft airy calm fluent English. Aaron is your sole operator. "
    "Be warm, concise, and useful. Prefer facts from the provided memory and "
    "vault context over inventing anything. If you don't know, say so and "
    "offer the next step. Never send outbound messages yourself; Cam's "
    "message center handles delivery."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def aaron_now() -> datetime:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(AARON_TZ))
        except Exception:
            pass
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Safe math
# --------------------------------------------------------------------------

_MATH_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MATH_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "log": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "floor": math.floor,
    "ceil": math.ceil,
}


def safe_math(expr: str) -> float | None:
    """Evaluate arithmetic safely via the AST. Returns None if not math."""
    expr = expr.strip().rstrip("?=").strip()
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
    if not re.fullmatch(r"[0-9a-z_+\-*/%().,\s*]{1,200}", expr, re.I):
        return None
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _MATH_OPS:
            return _MATH_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _MATH_OPS:
            return _MATH_OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = _MATH_FUNCS.get(node.func.id.lower())
            if fn is None:
                raise ValueError(f"function {node.func.id} not allowed")
            return fn(*[ev(a) for a in node.args])
        raise ValueError("unsupported expression")

    try:
        result = ev(tree)
    except (ValueError, ZeroDivisionError, TypeError, OverflowError):
        return None
    if isinstance(result, (int, float)) and math.isfinite(result):
        return float(result)
    return None


# --------------------------------------------------------------------------
# Durable memory
# --------------------------------------------------------------------------

class Memory:
    """Persistent facts Aaron tells Cam. Simple, transparent JSON."""

    def __init__(self, path: Path = MEMORY_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.facts: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                doc = json.loads(self.path.read_text(encoding="utf-8"))
                self.facts = list(doc.get("facts") or [])
            except (json.JSONDecodeError, OSError):
                self.facts = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = {"subject": "Aaron", "updated": utc_now(), "facts": self.facts}
        self.path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def remember(self, text: str, source: str = "chat") -> dict:
        fact = {"id": f"fact-{len(self.facts) + 1}-{int(datetime.now().timestamp())}",
                "text": text.strip(), "at": utc_now(), "source": source}
        with self._lock:
            self.facts.append(fact)
            self._save()
        return fact

    def forget(self, needle: str) -> int:
        n = needle.strip().lower()
        with self._lock:
            before = len(self.facts)
            self.facts = [f for f in self.facts if n not in f.get("text", "").lower()]
            removed = before - len(self.facts)
            if removed:
                self._save()
        return removed

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        words = [w for w in re.findall(r"[a-z0-9']+", query.lower()) if len(w) > 2]
        scored: list[tuple[int, dict]] = []
        for fact in self.facts:
            text = fact.get("text", "").lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, fact))
        scored.sort(key=lambda p: (-p[0], p[1].get("at", "")))
        return [f for _, f in scored[:limit]]

    def all(self, limit: int = 50) -> list[dict]:
        return self.facts[-limit:]


# --------------------------------------------------------------------------
# Vault retrieval (grounding)
# --------------------------------------------------------------------------

_STOPWORDS = {
    "the", "and", "for", "you", "with", "that", "this", "what", "when", "where",
    "how", "why", "can", "could", "would", "should", "about", "tell", "know",
    "cam", "please", "into", "from", "your", "are", "was", "were", "have",
}


def vault_search(query: str, limit: int = 4, vault: Path = VAULT) -> list[dict]:
    """Rank vault markdown files by query-term hits; return snippets."""
    words = [w for w in re.findall(r"[a-z0-9']+", query.lower())
             if len(w) > 2 and w not in _STOPWORDS]
    if not words or not vault.exists():
        return []
    hits: list[tuple[int, Path, str]] = []
    for md in vault.rglob("*.md"):
        if "10-Mesh-Distillates" in md.parts:
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        low = text.lower()
        score = sum(low.count(w) for w in words)
        if score:
            # first line containing any query word as the snippet
            snippet = ""
            for line in text.splitlines():
                ll = line.lower()
                if any(w in ll for w in words) and line.strip():
                    snippet = line.strip()[:220]
                    break
            hits.append((score, md, snippet))
    hits.sort(key=lambda t: -t[0])
    return [
        {"path": str(p.relative_to(vault.parent)), "score": s, "snippet": snip}
        for s, p, snip in hits[:limit]
    ]


# --------------------------------------------------------------------------
# LLM backends (all optional; short timeouts; never crash the loop)
# --------------------------------------------------------------------------

class LLMBackend:
    """Picks the first reachable chat-completion backend, if any."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resolved: dict | None = None
        self._checked = False

    def _candidates(self) -> list[dict]:
        cands: list[dict] = []
        base = os.environ.get("CAM_LLM_BASE_URL")
        if base:
            cands.append({
                "name": "custom", "kind": "openai",
                "url": base.rstrip("/") + "/chat/completions",
                "key": os.environ.get("CAM_LLM_API_KEY", ""),
                "model": os.environ.get("CAM_LLM_MODEL", "default"),
            })
        if os.environ.get("OPENAI_API_KEY"):
            cands.append({
                "name": "openai", "kind": "openai",
                "url": "https://api.openai.com/v1/chat/completions",
                "key": os.environ["OPENAI_API_KEY"],
                "model": os.environ.get("CAM_OPENAI_MODEL", "gpt-4o-mini"),
            })
        if os.environ.get("ANTHROPIC_API_KEY"):
            cands.append({
                "name": "anthropic", "kind": "anthropic",
                "url": "https://api.anthropic.com/v1/messages",
                "key": os.environ["ANTHROPIC_API_KEY"],
                "model": os.environ.get("CAM_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            })
        ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        if not ollama.startswith("http"):
            ollama = "http://" + ollama
        cands.append({
            "name": "ollama", "kind": "openai",
            "url": ollama.rstrip("/") + "/v1/chat/completions",
            "key": "", "model": os.environ.get("CAM_OLLAMA_MODEL", "llama3.2"),
            "probe": ollama.rstrip("/") + "/api/tags",
        })
        return cands

    def resolve(self, force: bool = False) -> dict | None:
        with self._lock:
            if self._checked and not force:
                return self._resolved
            self._checked = True
            self._resolved = None
            for cand in self._candidates():
                probe = cand.get("probe")
                if probe:
                    try:
                        req = urllib.request.Request(probe, method="GET")
                        with urllib.request.urlopen(req, timeout=2):
                            pass
                    except (urllib.error.URLError, OSError, ValueError):
                        continue
                    self._resolved = cand
                    return cand
                # Keyed backends: trust config, fail at call time gracefully.
                self._resolved = cand
                return cand
            return self._resolved

    def chat(self, messages: list[dict], max_tokens: int = 500) -> str | None:
        cand = self.resolve()
        if not cand:
            return None
        try:
            if cand["kind"] == "anthropic":
                system = "\n".join(m["content"] for m in messages if m["role"] == "system")
                body = {
                    "model": cand["model"],
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [m for m in messages if m["role"] != "system"],
                }
                headers = {
                    "content-type": "application/json",
                    "x-api-key": cand["key"],
                    "anthropic-version": "2023-06-01",
                }
            else:
                body = {"model": cand["model"], "max_tokens": max_tokens, "messages": messages}
                headers = {"content-type": "application/json"}
                if cand["key"]:
                    headers["authorization"] = f"Bearer {cand['key']}"
            req = urllib.request.Request(
                cand["url"], data=json.dumps(body).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                doc = json.loads(resp.read().decode("utf-8"))
            if cand["kind"] == "anthropic":
                parts = doc.get("content") or []
                return "".join(p.get("text", "") for p in parts).strip() or None
            choices = doc.get("choices") or []
            if choices:
                return (choices[0].get("message") or {}).get("content", "").strip() or None
        except (urllib.error.URLError, OSError, ValueError, KeyError, json.JSONDecodeError):
            return None
        return None

    def status(self) -> dict:
        cand = self.resolve()
        if not cand:
            return {"live_llm": False, "backend": None, "engine": "local_cortex"}
        return {"live_llm": True, "backend": cand["name"], "model": cand["model"],
                "engine": f"llm:{cand['name']}"}


# --------------------------------------------------------------------------
# Reminder time parsing
# --------------------------------------------------------------------------

_REL_RE = re.compile(
    r"\bin\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b", re.I)
_AT_RE = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)
_TOMORROW_RE = re.compile(r"\btomorrow\b", re.I)


def parse_due(text: str, now: datetime | None = None) -> datetime | None:
    now = now or aaron_now()
    m = _REL_RE.search(text)
    if m:
        qty = float(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("sec"):
            delta = timedelta(seconds=qty)
        elif unit.startswith(("min",)):
            delta = timedelta(minutes=qty)
        elif unit.startswith(("hour", "hr")):
            delta = timedelta(hours=qty)
        else:
            delta = timedelta(days=qty)
        return now + delta
    m = _AT_RE.search(text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        due = now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
        if _TOMORROW_RE.search(text) or due <= now:
            due += timedelta(days=1)
        return due
    if _TOMORROW_RE.search(text):
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return None


# --------------------------------------------------------------------------
# The brain
# --------------------------------------------------------------------------

_REMEMBER_RE = re.compile(
    r"^(?:cam[,\s]+)?(?:please\s+)?remember(?:\s+that)?\s+(.+)$", re.I)
_FORGET_RE = re.compile(r"^(?:cam[,\s]+)?forget(?:\s+about)?\s+(.+)$", re.I)
_RECALL_RE = re.compile(
    r"\b(what (?:do you|did i) (?:remember|say|tell you) about|do you remember|recall)\b", re.I)
_REMIND_RE = re.compile(r"\bremind me\b(?:\s+to\s+)?(.*)", re.I)
_TASK_RE = re.compile(
    r"^(?:cam[,\s]+)?(?:task|run task|work on|research|investigate|dig into)\s*[:\-]?\s+(.+)$", re.I)
_SEE_RE = re.compile(r"\b(what (?:do|can) you see|describe (?:the|what's on) camera|"
                     r"what am i (?:holding|looking at)|any objects)\b", re.I)
_TIME_RE = re.compile(r"\b(what time|what's the time|what day|what date|today'?s date)\b", re.I)
_STATUS_RE = re.compile(r"\b(status|system (?:check|pulse)|are you (?:ok|online|working)|health)\b", re.I)
_GREET_RE = re.compile(r"^(hi|hello|hey|good (morning|afternoon|evening))\b", re.I)
_MATH_HINT_RE = re.compile(r"^[\s\d(.\-]|what is\s+[\d(]|calculate|compute", re.I)


class CamBrain:
    """Head reasoning core. Hooks let the server wire in teams/messages/vision
    without circular imports."""

    def __init__(
        self,
        *,
        memory: Memory | None = None,
        llm: LLMBackend | None = None,
        task_dispatch: Callable[[str], dict] | None = None,
        reminder_create: Callable[[str, datetime], dict] | None = None,
        vision_latest: Callable[[], dict | None] | None = None,
        status_provider: Callable[[], dict] | None = None,
    ) -> None:
        self.memory = memory or Memory()
        self.llm = llm or LLMBackend()
        self.task_dispatch = task_dispatch
        self.reminder_create = reminder_create
        self.vision_latest = vision_latest
        self.status_provider = status_provider
        self.history: list[dict] = []
        self._lock = threading.Lock()

    # -- public ------------------------------------------------------------

    def status(self) -> dict:
        st = self.llm.status()
        st["memory_facts"] = len(self.memory.facts)
        st["history_turns"] = len(self.history)
        return st

    def respond(self, text: str, source: str = "text") -> dict:
        """One conversational turn. Always returns a real answer."""
        text = (text or "").strip()
        turn: dict[str, Any] = {
            "at": utc_now(), "source": source, "aaron": text,
            "engine": "local_cortex", "actions": [],
        }
        if not text:
            turn["cam"] = "I'm here, Aaron — listening. Say the word."
            return self._finish(turn)

        handled = self._local_skills(text, turn)
        if handled is not None:
            turn["cam"] = handled
            return self._finish(turn)

        # General conversation → LLM with grounding, else grounded local reply
        context = self._build_context(text)
        llm_reply = self._llm_reply(text, context)
        if llm_reply:
            turn["engine"] = self.llm.status().get("engine", "llm")
            turn["cam"] = llm_reply
            return self._finish(turn)

        turn["cam"] = self._grounded_reply(text, context)
        return self._finish(turn)

    # -- internals -----------------------------------------------------------

    def _finish(self, turn: dict) -> dict:
        with self._lock:
            self.history.append(turn)
            if len(self.history) > 400:
                self.history = self.history[-200:]
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with HISTORY_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(turn, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return turn

    def _local_skills(self, text: str, turn: dict) -> str | None:
        """Deterministic skills that must be handled locally and reliably."""
        m = _REMEMBER_RE.match(text)
        if m:
            fact = self.memory.remember(m.group(1))
            turn["actions"].append({"kind": "remember", "fact_id": fact["id"]})
            return f"Got it — I'll remember: “{fact['text']}”. That's {len(self.memory.facts)} facts I'm keeping for you."

        m = _FORGET_RE.match(text)
        if m:
            removed = self.memory.forget(m.group(1))
            turn["actions"].append({"kind": "forget", "removed": removed})
            if removed:
                return f"Done — I dropped {removed} matching {'memory' if removed == 1 else 'memories'}."
            return "I didn't have anything matching that to forget."

        if _RECALL_RE.search(text):
            hits = self.memory.recall(text)
            turn["actions"].append({"kind": "recall", "hits": len(hits)})
            if hits:
                lines = "\n".join(f"• {h['text']} (noted {h['at'][:10]})" for h in hits)
                return f"Here's what I have:\n{lines}"
            return ("I don't have a memory matching that yet. Tell me "
                    "“remember …” and I'll keep it.")

        m = _REMIND_RE.search(text)
        if m and self.reminder_create:
            due = parse_due(text)
            what = re.sub(_REL_RE, "", m.group(1))
            what = re.sub(_AT_RE, "", what)
            what = re.sub(_TOMORROW_RE, "", what).strip(" ,.-") or "your reminder"
            if due is None:
                due = aaron_now() + timedelta(hours=1)
                note = " I couldn't read a time, so I set it for one hour from now."
            else:
                note = ""
            rem = self.reminder_create(what, due)
            turn["actions"].append({"kind": "reminder", "id": rem.get("id"), "due": rem.get("due")})
            local = due.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")
            return f"Reminder set — “{what}” at {local}.{note} I'll message you when it's time."

        m = _TASK_RE.match(text)
        if m and self.task_dispatch:
            job = self.task_dispatch(m.group(1))
            turn["actions"].append({"kind": "task", "task_id": job.get("id"), "team": job.get("team")})
            agents = job.get("subtask_count", 0)
            return (f"On it. I put “{m.group(1)[:80]}” with the {job.get('team_name', job.get('team'))} — "
                    f"{agents} subagents are working it in parallel now. "
                    "I'll drop the results in your messages when they finish.")

        if _SEE_RE.search(text) and self.vision_latest:
            latest = self.vision_latest()
            turn["actions"].append({"kind": "vision_query"})
            if not latest or not latest.get("objects"):
                return ("My eyes aren't seeing anything yet — open the Camera panel and "
                        "point me at something, then ask again.")
            objs = latest["objects"]
            names = {}
            for o in objs:
                names[o.get("label", "object")] = names.get(o.get("label", "object"), 0) + 1
            described = ", ".join(f"{v}× {k}" if v > 1 else k for k, v in names.items())
            src = "live detector" if latest.get("source") == "cocossd" else "my local visual cortex"
            return f"Right now I can see: {described} (via {src})."

        if _TIME_RE.search(text):
            now = aaron_now()
            return ("It's " + now.strftime("%I:%M %p").lstrip("0") +
                    " on " + now.strftime("%A, %B %d, %Y") + " (New York time).")

        if _STATUS_RE.search(text):
            st = self.status()
            extra = self.status_provider() if self.status_provider else {}
            live = st.get("live_llm")
            parts = [
                "All systems up.",
                f"Reasoning: {'live LLM (' + str(st.get('backend')) + ')' if live else 'local cortex (no LLM configured — I still think, just plainer)'}.",
                f"Memory: {st['memory_facts']} facts.",
            ]
            if extra.get("tasks_running") is not None:
                parts.append(f"Tasks running: {extra['tasks_running']}.")
            if extra.get("unread_messages") is not None:
                parts.append(f"Unread messages: {extra['unread_messages']}.")
            return " ".join(parts)

        if _MATH_HINT_RE.search(text):
            expr = re.sub(r"^(what is|calculate|compute)\s*", "", text, flags=re.I)
            val = safe_math(expr)
            if val is not None:
                pretty = int(val) if float(val).is_integer() else round(val, 6)
                turn["actions"].append({"kind": "math", "result": pretty})
                return f"That's {pretty}."

        if _GREET_RE.match(text) and len(text) < 40:
            hour = aaron_now().hour
            slot = "morning" if hour < 12 else ("afternoon" if hour < 18 else "evening")
            return (f"Hey Aaron — good {slot}. I'm listening and my reasoning core is live. "
                    "Ask me anything, set a reminder, or give a team a task.")

        return None

    def _build_context(self, text: str) -> dict:
        mem = self.memory.recall(text, limit=4)
        vault = vault_search(text, limit=3)
        vision = None
        if self.vision_latest:
            latest = self.vision_latest()
            if latest and latest.get("objects"):
                vision = [o.get("label") for o in latest["objects"]][:8]
        return {"memory": mem, "vault": vault, "vision": vision}

    def _llm_reply(self, text: str, context: dict) -> str | None:
        ctx_lines = []
        for f in context["memory"]:
            ctx_lines.append(f"MEMORY: {f['text']}")
        for v in context["vault"]:
            ctx_lines.append(f"VAULT {v['path']}: {v['snippet']}")
        if context.get("vision"):
            ctx_lines.append("CAMERA now sees: " + ", ".join(context["vision"]))
        system = PERSONA_PROMPT
        if ctx_lines:
            system += "\n\nGrounding context (prefer this over invention):\n" + "\n".join(ctx_lines)
        messages: list[dict] = [{"role": "system", "content": system}]
        with self._lock:
            recent = self.history[-6:]
        for t in recent:
            if t.get("aaron"):
                messages.append({"role": "user", "content": t["aaron"]})
            if t.get("cam"):
                messages.append({"role": "assistant", "content": t["cam"]})
        messages.append({"role": "user", "content": text})
        return self.llm.chat(messages)

    def _grounded_reply(self, text: str, context: dict) -> str:
        """No LLM reachable: honest, grounded reply from retrieval — never fake."""
        pieces: list[str] = []
        if context["memory"]:
            lines = "; ".join(f"“{f['text']}”" for f in context["memory"][:3])
            pieces.append(f"From what you've told me before: {lines}.")
        if context["vault"]:
            lines = "; ".join(f"{v['path']} — {v['snippet']}" for v in context["vault"][:2] if v["snippet"])
            if lines:
                pieces.append(f"Your vault has related notes: {lines}")
        if context.get("vision"):
            pieces.append("On camera right now: " + ", ".join(context["vision"]) + ".")
        if pieces:
            pieces.append("No live language model is connected, so that's my grounded take. "
                          "Point CAM_LLM_BASE_URL or an API key at me for deeper reasoning.")
            return " ".join(pieces)
        return ("I don't have notes or memories on that yet, and no live language model is "
                "connected for open-ended reasoning. You can teach me (“remember …”), give it "
                "to a team (“task: …”), or connect a model via OLLAMA/OPENAI_API_KEY/"
                "CAM_LLM_BASE_URL and I'll think it through properly.")
