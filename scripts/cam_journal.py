"""Append-only intent journal for Cam motors (Muse Code audit-log pattern).

One JSONL file per UTC day under data/runtime/journal/. Each line is an
envelope {sequence, recorded_at, kind, session_id, payload}. The intent to act
(and the authorization it carries) is written BEFORE the effect runs, so the
log — not the chat — is the record of what Cam did and who allowed it.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_DIR = ROOT / "data" / "runtime" / "journal"

KINDS = (
    "proposed",
    "approval.requested",
    "decision_applied",
    "side_effect_intent",
    "effect.started",
    "effect.terminal",
    "session.end",
)

_REDACT = [
    (re.compile(r"(?i)(authorization\s*[:=]\s*)([A-Za-z]+\s+)?(\S+)"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), "[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}"), "[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED]"),
    (re.compile(r"(?i)\b([a-z0-9_]*(?:secret|token|password|api_key|apikey)[a-z0-9_]*\s*[:=]\s*)(['\"]?)[^\s'\",]{6,}\2"), r"\1[REDACTED]"),
]


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def redact(text: str) -> str:
    out = text
    for pat, rep in _REDACT:
        out = pat.sub(rep, out)
    return out


_SECRET_KEY = re.compile(r"(?i)(secret|token|password|passwd|api_key|apikey|private_key|credential)")


def _redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, list):
        return [_redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if _SECRET_KEY.search(str(k)) and v not in (None, "", [], {}) else _redact_obj(v))
            for k, v in obj.items()
        }
    return obj


def path_for(day: str | None = None, journal_dir: Path | None = None) -> Path:
    return (journal_dir or JOURNAL_DIR) / f"{day or today()}.jsonl"


def read(day: str | None = None, journal_dir: Path | None = None) -> list[dict]:
    p = path_for(day, journal_dir)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"sequence": None, "kind": "unparseable", "payload": {"raw": line[:200]}})
    return rows


def append(
    kind: str,
    payload: dict,
    *,
    session_id: str = "cli",
    day: str | None = None,
    journal_dir: Path | None = None,
) -> dict:
    """Append one envelope. Sequence is monotonic per day file."""
    if kind not in KINDS:
        raise ValueError(f"unknown journal kind: {kind}")
    p = path_for(day, journal_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    last = 0
    if p.exists():
        with p.open("rb") as fh:
            try:
                fh.seek(-4096, 2)
            except OSError:
                fh.seek(0)
            tail = fh.read().decode("utf-8", errors="ignore").strip().splitlines()
        for line in reversed(tail):
            try:
                last = int(json.loads(line).get("sequence") or 0)
                break
            except (json.JSONDecodeError, ValueError, AttributeError):
                continue
    env = {
        "sequence": last + 1,
        "recorded_at": utc(),
        "kind": kind,
        "session_id": session_id,
        "payload": _redact_obj(payload),
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(env, ensure_ascii=False, sort_keys=True) + "\n")
    return env


def idempotency_key(motor: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join([motor, *parts]).encode("utf-8")).hexdigest()[:12]
    return f"{motor}:{digest}"


def unconfirmed_intents(rows: list[dict]) -> list[dict]:
    """Intents with no effect.terminal — what a crash-safe resume must verify, not retry."""
    terminal = {
        (r.get("payload") or {}).get("idempotency_key")
        for r in rows
        if r.get("kind") == "effect.terminal"
    }
    return [
        r
        for r in rows
        if r.get("kind") == "side_effect_intent"
        and (r.get("payload") or {}).get("idempotency_key") not in terminal
    ]


def export(day: str | None = None, journal_dir: Path | None = None) -> dict:
    """Pure function of the log bytes — same file, same document."""
    rows = read(day, journal_dir)
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[str(r.get("kind"))] = kinds.get(str(r.get("kind")), 0) + 1
    pending = {
        (r.get("payload") or {}).get("pending_id")
        for r in rows
        if r.get("kind") == "approval.requested"
    }
    decided = {
        (r.get("payload") or {}).get("pending_id")
        for r in rows
        if r.get("kind") == "decision_applied"
    }
    return {
        "export_schema_version": 1,
        "day": day or today(),
        "record_count": len(rows),
        "kinds": dict(sorted(kinds.items())),
        "open_approvals": sorted(p for p in (pending - decided) if p),
        "unconfirmed_intents": [
            (r.get("payload") or {}).get("idempotency_key") for r in unconfirmed_intents(rows)
        ],
        "unparseable_lines": kinds.get("unparseable", 0),
        "events": rows,
    }


def ledger_lines(rows: list[dict]) -> list[str]:
    """One row per journaled action, stamped with how it was authorized."""
    out = []
    for r in rows:
        p = r.get("payload") or {}
        seq = r.get("sequence")
        kind = r.get("kind")
        if kind == "side_effect_intent":
            out.append(f"{seq:>5}  intent    {p.get('motor', ''):<18} auth={p.get('policy_decision', '')}")
        elif kind == "approval.requested":
            out.append(f"{seq:>5}  approval  REQUESTED  {p.get('motor', '')}: {p.get('purpose', '')}")
        elif kind == "decision_applied":
            src = p.get("decision_source") or {}
            out.append(f"{seq:>5}  approval  {str(p.get('decision', '')).upper()}  by {src.get('kind', '')}")
        elif kind == "effect.terminal":
            out.append(f"{seq:>5}  terminal  {p.get('motor', ''):<18} outcome={p.get('outcome', '')}")
        elif kind == "proposed":
            out.append(f"{seq:>5}  proposed  {','.join(p.get('motor_plan') or [])}")
    return out
