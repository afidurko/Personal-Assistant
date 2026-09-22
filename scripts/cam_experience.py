#!/usr/bin/env python3
"""Cam predictive cortex — outcome prediction from Cam's own experiences.

Pure-stdlib library behind ``scripts/cam-predict.py``. Ingests Cam's run
history (loop runs, QA cycles, reasoning traces, recorded experiences) into a
normalized *experience* stream and turns it into predictive measures:

* success probability — Beta-Bernoulli posterior with exponential forgetting
  and hierarchical backoff (hotspot → pattern → center → sense → global)
* expected score / duration — recency-weighted means with dispersion
* TD(0) value + reward-prediction error ("surprise") per context
* prequential calibration — Brier, log loss, ECE, AUROC, Brier skill vs the
  running base rate, computed by predicting each experience *before* seeing it

Survival measures (why an earlier draft would have failed, and the fix):
* the same run reported by two sources was counted twice → cross-source dedup
* records with unknown timestamps were treated as *fresh* → discounted weight
* one corrupt source file killed the whole load → per-source error isolation
* a stable rate that silently shifted stayed confident → EWMA-surprise drift
  detection inflates uncertainty until the new regime is learned
* a parent rate dominated by one child bled into siblings → diversity-aware backoff
* runs that never wrote a distillate were invisible → staleness / coverage report
* unbounded runtime log → rotation; kill switch (``CAM_KILL``) refuses writes

Ethical measures (``config/ethics/research-ethics.json``): PII/secret redaction
on write, protected contexts → human judgment only, abstention when evidence is
thin, per-context calibration parity, right-to-forget, and a prediction card
with stated limitations plus a hedged narration Cam can actually say.

Advisory only: predictions are a report for Cam's centers and Aaron. Using
them to alter routing or fire motors stays behind ``switch.cam_enhance``.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config" / "enhancement" / "predictive-cortex.json"
ETHICS_PATH = ROOT / "config" / "ethics" / "research-ethics.json"
FIXTURE = ROOT / "scripts" / "testdata" / "sample-experiences.jsonl"
RUNTIME_LOG = ROOT / "data" / "runtime" / "experiences.jsonl"
DISTILL_DIR = ROOT / "vault" / "10-Mesh-Distillates" / "predictive-cortex"

LOOP_LOG = ROOT / "loop-run-log.md"
LOOP_LATEST = ROOT / "vault" / "10-Mesh-Distillates" / "loop-runs" / "latest.json"
QA_CYCLES = ROOT / "vault" / "10-Mesh-Distillates" / "qa-cycles"
REASONING = ROOT / "vault" / "10-Mesh-Distillates" / "reasoning"

BACKOFF_ORDER = ("hotspot", "pattern", "center", "sense", "global")
SCHEMA_VERSION = 1

_CACHE: dict[str, Any] = {}
LAST_SOURCE_ERRORS: list[dict[str, str]] = []


class KillSwitchActive(RuntimeError):
    """Raised when a write is attempted while CAM_KILL is set."""


# --- time helpers -------------------------------------------------------------

def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def kill_active() -> bool:
    return os.environ.get("CAM_KILL", "").strip().lower() in {"1", "true", "yes", "on"}


# --- config -------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    "half_life_days": 14.0,
    "prior_alpha": 1.0,
    "prior_beta": 1.0,
    "backoff_prior_strength": 2.0,
    "prior_floor": 0.5,
    "td_alpha": 0.2,
    "ece_bins": 10,
    "credible_mass": 0.9,
    "min_effective_n": 1.0,
    "evidence_limit": 5,
    "low_confidence_below": 0.5,
    "high_surprise_above": 0.6,
    "min_n_for_verdict": 30,
    "min_outcomes_each_class": 5,
    # survival
    "unknown_ts_weight": 0.25,
    "drift_ewma_beta": 0.3,
    "drift_surprise_above": 0.6,
    "drift_inflation": 0.5,
    "backoff_single_child_factor": 0.5,
    "stale_after_days": 7.0,
    "max_runtime_rows": 5000,
    "keep_runtime_rows": 1000,
}


def load_config() -> dict[str, Any]:
    if "cfg" not in _CACHE:
        cfg = dict(DEFAULTS)
        if CFG_PATH.exists():
            raw = json.loads(CFG_PATH.read_text(encoding="utf-8"))
            cfg.update(raw.get("predictor") or {})
            cfg["_raw"] = raw
        _CACHE["cfg"] = cfg
    return _CACHE["cfg"]


def load_ethics() -> dict[str, Any]:
    if "ethics" not in _CACHE:
        _CACHE["ethics"] = json.loads(ETHICS_PATH.read_text(encoding="utf-8")) if ETHICS_PATH.exists() else {}
    return _CACHE["ethics"]


# --- ethics: redaction + protected contexts ----------------------------------

def redact(text: str) -> tuple[str, list[str]]:
    """Strip PII / secrets from free text before it is persisted."""
    if not text:
        return text, []
    eth = load_ethics().get("redaction") or {}
    patterns = eth.get("patterns") or {}
    template = eth.get("replacement") or "[redacted:{kind}]"
    kinds: list[str] = []
    out = text
    for kind, pattern in patterns.items():
        try:
            new = re.sub(pattern, template.format(kind=kind), out)
        except re.error:
            continue
        if new != out:
            kinds.append(kind)
            out = new
    return out, kinds


def is_protected(ctx: dict[str, Any]) -> bool:
    """True when the context touches people, money, identity or outbound action."""
    prot = load_ethics().get("protected_contexts") or {}
    blob = " ".join(
        str(ctx.get(k) or "") for k in ("hotspot", "pattern", "center", "sense")
    ).lower()
    if any(tok in blob for tok in prot.get("hotspot_patterns") or []):
        return True
    motors = {str(m) for m in (ctx.get("motors") or [])}
    return any(m in motors for m in prot.get("motor_patterns") or [])


# --- experience schema --------------------------------------------------------

def make_experience(
    *,
    ok: bool,
    ts: str | None = None,
    source: str = "manual",
    sense: str | None = None,
    hotspot: str | None = None,
    center: str | None = None,
    pattern: str | None = None,
    motors: Iterable[str] | None = None,
    score: float | None = None,
    duration_s: float | None = None,
    notes: str = "",
    ref: str | None = None,
) -> dict[str, Any]:
    """Normalized experience record. ``ok`` is the Bernoulli outcome."""
    clean_notes, kinds = redact((notes or "")[:240])
    clean_ref, ref_kinds = redact(ref or "")
    exp = {
        "kind": "experience",
        "schema": SCHEMA_VERSION,
        "ts": ts or utc(),
        "source": source,
        "context": {
            "sense": sense,
            "hotspot": hotspot,
            "center": center,
            "pattern": pattern,
            "motors": sorted(set(motors or [])),
        },
        "outcome": {
            "ok": bool(ok),
            "score": None if score is None else float(score),
            "duration_s": None if duration_s is None else float(duration_s),
        },
        "notes": clean_notes,
        "ref": clean_ref or None,
    }
    if kinds or ref_kinds:
        exp["redacted"] = sorted(set(kinds + ref_kinds))
    return exp


def context_keys(ctx: dict[str, Any]) -> dict[str, str | None]:
    return {
        "hotspot": f"hotspot:{ctx['hotspot']}" if ctx.get("hotspot") else None,
        "pattern": f"pattern:{ctx['pattern']}" if ctx.get("pattern") else None,
        "center": f"center:{ctx['center']}" if ctx.get("center") else None,
        "sense": f"sense:{ctx['sense']}" if ctx.get("sense") else None,
        "global": "global",
    }


def identity_key(exp: dict[str, Any]) -> tuple:
    """Same run seen through two sources must collapse to one experience."""
    ctx = exp.get("context") or {}
    return (exp.get("ts"), ctx.get("hotspot") or ctx.get("center"), ctx.get("pattern"))


# --- ingestion ----------------------------------------------------------------

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and doc.get("kind") == "experience":
            out.append(doc)
    return out


def ingest_loop_log(path: Path = LOOP_LOG) -> list[dict[str, Any]]:
    """Rows of loop-run-log.md → experiences (pattern/level/status/score)."""
    if not path.exists():
        return []
    out = []
    row_re = re.compile(r"^\|\s*(?P<when>[^|]+?)\s*\|\s*`?(?P<pattern>[^|`]+?)`?\s*\|\s*(?P<level>[^|]+?)\s*\|\s*(?P<status>[^|]+?)\s*\|\s*(?P<score>[^|]+?)\s*\|\s*(?P<notes>[^|]*?)\s*\|\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = row_re.match(line)
        if not m:
            continue
        when = m.group("when")
        if not parse_ts(when):
            continue
        status = m.group("status").strip().lower()
        score_txt = m.group("score").strip()
        try:
            score = float(score_txt)
        except ValueError:
            score = None
        out.append(
            make_experience(
                ok=status in ("ok", "green", "pass", "passed"),
                ts=when,
                source="loop_run_log",
                sense="sense.loop.tick",
                hotspot="hotspot.loop_engineering",
                center="center.qa",
                pattern=m.group("pattern").strip(),
                motors=["motor.loop"],
                score=score,
                notes=f"{m.group('level').strip()} {m.group('notes').strip()}".strip(),
                ref=_rel(path),
            )
        )
    return out


def ingest_loop_latest(path: Path = LOOP_LATEST) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    payload = doc.get("payload") if isinstance(doc.get("payload"), dict) else doc
    status = str(payload.get("status") or doc.get("status") or "").lower()
    if not status:
        return []
    score = payload.get("score", doc.get("score"))
    return [
        make_experience(
            ok=status == "ok",
            ts=payload.get("at") or doc.get("at"),
            source="loop_run_latest",
            sense="sense.loop.tick",
            hotspot="hotspot.loop_engineering",
            center="center.qa",
            pattern=payload.get("pattern") or doc.get("pattern"),
            motors=["motor.loop"],
            score=float(score) if isinstance(score, (int, float)) else None,
            notes=str(payload.get("notes") or ""),
            ref=_rel(path),
        )
    ]


def ingest_qa_cycles(root: Path = QA_CYCLES) -> list[dict[str, Any]]:
    """qa-cycles/<stamp>/cycle.json → experiences (pattern qa-cycle)."""
    if not root.exists():
        return []
    out = []
    for cycle in sorted(root.glob("*/cycle.json")):
        try:
            doc = json.loads(cycle.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        status = str(doc.get("status") or "").lower()
        metrics = doc.get("metrics") or {}
        n = metrics.get("n") or 0
        passed = metrics.get("passed") or 0
        score = (100.0 * passed / n) if n else None
        out.append(
            make_experience(
                ok=status == "green",
                ts=doc.get("at"),
                source="qa_cycle",
                sense="sense.chat.aaron",
                hotspot="hotspot.qa_cycle",
                center="center.qa",
                pattern="qa-cycle",
                motors=["motor.mesh"],
                score=score,
                duration_s=metrics.get("qa_wall_s"),
                notes=f"findings={len(doc.get('findings') or [])}",
                ref=_rel(cycle),
            )
        )
    return out


def ingest_reasoning(root: Path = REASONING) -> list[dict[str, Any]]:
    """reasoning/<day>.jsonl traces → experiences (ok = no trajectory violations)."""
    if not root.exists():
        return []
    out = []
    for path in sorted(root.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                trace = json.loads(line)
            except json.JSONDecodeError:
                continue
            if trace.get("kind") != "reasoning_trace":
                continue
            route = trace.get("route") or {}
            violations = trace.get("violations") or []
            out.append(
                make_experience(
                    ok=not violations and bool(trace.get("accepted", True)),
                    ts=trace.get("ts"),
                    source="reasoning_trace",
                    sense=trace.get("sense") or route.get("sense"),
                    hotspot=trace.get("hotspot_id") or route.get("hotspot_id"),
                    center=route.get("center"),
                    pattern=trace.get("path"),
                    motors=trace.get("motor_plan") or route.get("motor_plan") or [],
                    notes=str(trace.get("goal") or "")[:120],
                    ref=_rel(path),
                )
            )
    return out


def runtime_log_path() -> Path:
    override = os.environ.get("CAM_EXPERIENCE_LOG")
    return Path(override) if override else RUNTIME_LOG


def _rotate_if_needed(path: Path, cfg: dict[str, Any]) -> Path | None:
    """Archive an oversized runtime log, keeping the most recent rows live."""
    max_rows = int(cfg.get("max_runtime_rows") or 0)
    if max_rows <= 0 or not path.exists():
        return None
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) <= max_rows:
        return None
    keep = int(cfg.get("keep_runtime_rows") or max_rows // 5)
    archive = path.with_name(f"{path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{path.suffix}")
    archive.write_text("\n".join(lines[:-keep]) + "\n", encoding="utf-8")
    path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
    return archive


def record_experience(exp: dict[str, Any], path: Path | None = None, cfg: dict[str, Any] | None = None) -> Path:
    if kill_active():
        raise KillSwitchActive("CAM_KILL is set — refusing to write experience")
    path = path or runtime_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(exp, ensure_ascii=False) + "\n")
    _rotate_if_needed(path, cfg or load_config())
    return path


def forget_experiences(*, ref_contains: str | None = None, key: str | None = None, path: Path | None = None) -> int:
    """Right-to-forget: drop runtime experiences by ref substring or context key."""
    if kill_active():
        raise KillSwitchActive("CAM_KILL is set — refusing to rewrite experience log")
    path = path or runtime_log_path()
    if not path.exists():
        return 0
    kept, dropped = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        keys = set(v for v in context_keys(doc.get("context") or {}).values() if v)
        hit = (ref_contains and ref_contains in str(doc.get("ref") or "")) or (key and key in keys)
        if hit:
            dropped += 1
        else:
            kept.append(line)
    path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    return dropped


def dedupe(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collapse the same run reported by several sources; keep the richest record."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    out: list[dict[str, Any]] = []
    removed = 0
    for d in docs:
        src = str(d.get("source", ""))
        # only *different* sources describing the same moment collapse; two records
        # from one source in the same second (e.g. two QA cycles) are distinct runs
        merge_into = next(
            (k for k in groups.get(identity_key(d), []) if src not in str(k.get("source", "")).split("+")),
            None,
        )
        if merge_into is None:
            groups.setdefault(identity_key(d), []).append(d)
            out.append(d)
            continue
        removed += 1
        for field in ("score", "duration_s"):
            if merge_into["outcome"].get(field) is None and d.get("outcome", {}).get(field) is not None:
                merge_into["outcome"][field] = d["outcome"][field]
        srcs = set(str(merge_into.get("source", "")).split("+")) | {src}
        merge_into["source"] = "+".join(sorted(s for s in srcs if s))
    return out, removed


def load_experiences(*, offline: bool = False, extra: Iterable[Path] = ()) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge every experience source, chronologically sorted, with per-source counts.

    A broken source is reported (``LAST_SOURCE_ERRORS``, ``counts['_source_errors']``)
    instead of taking the whole stream down.
    """
    global LAST_SOURCE_ERRORS
    LAST_SOURCE_ERRORS = []
    sources: dict[str, list[dict[str, Any]]] = {}
    loaders: list[tuple[str, Any]] = [("fixture", lambda: read_jsonl(FIXTURE))] if offline else [
        ("loop_run_log", ingest_loop_log),
        ("loop_run_latest", ingest_loop_latest),
        ("qa_cycle", ingest_qa_cycles),
        ("reasoning_trace", ingest_reasoning),
        ("runtime_log", lambda: read_jsonl(runtime_log_path())),
    ]
    loaders += [(f"extra:{Path(p).name}", lambda p=p: read_jsonl(Path(p))) for p in extra]
    for name, fn in loaders:
        try:
            sources[name] = fn()
        except Exception as exc:  # noqa: BLE001 — isolate, report, continue
            sources[name] = []
            LAST_SOURCE_ERRORS.append({"source": name, "error": f"{type(exc).__name__}: {exc}"[:200]})
    merged_raw = [d for docs in sources.values() for d in docs]
    merged, removed = dedupe(merged_raw)
    far_past = datetime.min.replace(tzinfo=timezone.utc)
    merged.sort(key=lambda d: parse_ts(d.get("ts")) or far_past)
    counts = {k: len(v) for k, v in sources.items()}
    counts["_duplicates_removed"] = removed
    counts["_source_errors"] = len(LAST_SOURCE_ERRORS)
    counts["_unknown_ts"] = sum(1 for d in merged if parse_ts(d.get("ts")) is None)
    return merged, counts


# --- math: beta distribution without scipy -----------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    max_it, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > fpmin else fpmin)
    h = d
    for m in range(1, max_it + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / (c if abs(c) > fpmin else fpmin)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / (c if abs(c) > fpmin else fpmin)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(q: float, a: float, b: float, tol: float = 1e-12) -> float:
    """Inverse regularized incomplete beta — bracketed Newton with bisection fallback.

    Tolerance is in x; the CDF is near-vertical in the tails for skewed (a, b),
    so a loose x tolerance would put the quantile visibly off in probability.
    Below min(a, b) ≈ 0.3 the tail quantile sits closer to 0/1 than a double can
    resolve; the predictor stays clear of that via ``prior_floor`` (≥ 0.5).
    """
    if q <= 0.0:
        return 0.0
    if q >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    lo, hi = 0.0, 1.0
    x = a / (a + b)
    for _ in range(200):
        err = beta_cdf(x, a, b) - q
        if abs(err) < 1e-10:
            return x
        if err < 0.0:
            lo = x
        else:
            hi = x
        # Newton step on the bracketed root; bisect whenever Newton leaves the bracket
        pdf = math.exp(lbeta + (a - 1.0) * math.log(x) + (b - 1.0) * math.log(1.0 - x)) if 0.0 < x < 1.0 else 0.0
        nxt = x - err / pdf if pdf > 0.0 else -1.0
        if not (lo < nxt < hi):
            nxt = 0.5 * (lo + hi)
        if abs(nxt - x) < tol or hi - lo < tol:
            return nxt
        x = nxt
    return 0.5 * (lo + hi)


# --- predictor ----------------------------------------------------------------

def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


class ExperiencePredictor:
    """Online predictor over Cam's experience stream.

    Feed experiences chronologically with :meth:`update`; ask :meth:`predict`
    at any point. Prequential evaluation simply interleaves predict → update.
    """

    def __init__(self, cfg: dict[str, Any] | None = None, now: datetime | None = None):
        self.cfg = dict(DEFAULTS)
        self.cfg.update({k: v for k, v in (cfg or {}).items() if not k.startswith("_")})
        self.now = now
        self.stats: dict[str, dict[str, Any]] = {}
        self.history: list[dict[str, Any]] = []

    # -- weights -----------------------------------------------------------
    def _decay(self, ts: datetime | None, ref: datetime) -> float:
        if ts is None:
            # unknown age must not masquerade as fresh evidence
            return float(self.cfg["unknown_ts_weight"])
        age_days = max(0.0, (ref - ts).total_seconds() / 86400.0)
        return 0.5 ** (age_days / float(self.cfg["half_life_days"]))

    def _bucket(self, key: str) -> dict[str, Any]:
        return self.stats.setdefault(
            key,
            {
                "events": [],  # (ts, y, score, duration)
                "td_value": None,
                "td_updates": 0,
                "last_surprise": None,
                "surprises": [],
                "ewma_surprise": None,
                "children": set(),
            },
        )

    def drift_suspected(self, key: str) -> bool:
        b = self.stats.get(key)
        if not b or b.get("ewma_surprise") is None or len(b["events"]) < 3:
            return False
        return b["ewma_surprise"] > float(self.cfg["drift_surprise_above"])

    # -- learning ------------------------------------------------------------
    def update(self, exp: dict[str, Any]) -> dict[str, float]:
        ctx = exp.get("context") or {}
        out = exp.get("outcome") or {}
        y = 1.0 if out.get("ok") else 0.0
        reward = (float(out["score"]) / 100.0) if isinstance(out.get("score"), (int, float)) else y
        ts = parse_ts(exp.get("ts"))
        alpha = float(self.cfg["td_alpha"])
        beta = float(self.cfg["drift_ewma_beta"])
        keys = context_keys(ctx)
        finest = keys.get("hotspot") or keys.get("pattern") or keys.get("center") or "global"
        surprise_by_key: dict[str, float] = {}
        for level, key in keys.items():
            if not key:
                continue
            b = self._bucket(key)
            b["events"].append((ts, y, out.get("score"), out.get("duration_s")))
            b["children"].add(finest)
            v = b["td_value"]
            if v is None:
                rpe = reward - 0.5  # first visit: measured against neutral
                b["td_value"] = reward
            else:
                rpe = reward - v
                b["td_value"] = v + alpha * rpe
            b["td_updates"] += 1
            b["last_surprise"] = abs(rpe)
            b["surprises"].append(abs(rpe))
            b["ewma_surprise"] = abs(rpe) if b["ewma_surprise"] is None else (1 - beta) * b["ewma_surprise"] + beta * abs(rpe)
            surprise_by_key[level] = round(abs(rpe), 4)
        self.history.append(exp)
        return surprise_by_key

    # -- inference -----------------------------------------------------------
    def _posterior(self, key: str, ref: datetime, prior_a: float, prior_b: float) -> tuple[float, float, float]:
        b = self.stats.get(key)
        a, bb, n_eff = prior_a, prior_b, 0.0
        if b:
            inflate = float(self.cfg["drift_inflation"]) if self.drift_suspected(key) else 1.0
            for ts, y, _s, _d in b["events"]:
                w = self._decay(ts, ref) * inflate
                a += w * y
                bb += w * (1.0 - y)
                n_eff += w
        return a, bb, n_eff

    def _backoff(self, keys: dict[str, str | None], ref: datetime) -> dict[str, Any]:
        """Hierarchical backoff, coarse → fine: each level's posterior mean becomes
        the next finer level's prior (shrinkage toward the parent)."""
        cfg = self.cfg
        strength, floor = float(cfg["backoff_prior_strength"]), float(cfg["prior_floor"])
        prior_a, prior_b = float(cfg["prior_alpha"]), float(cfg["prior_beta"])
        a, b, n_eff, key_used = prior_a, prior_b, 0.0, "global"
        chain: list[dict[str, Any]] = []
        for level in reversed(BACKOFF_ORDER):
            key = keys.get(level)
            if not key:
                continue
            a, b, n_eff = self._posterior(key, ref, prior_a, prior_b)
            key_used = key
            mean = a / (a + b)
            children = len((self.stats.get(key) or {}).get("children") or ())
            chain.append({"level": level, "key": key, "n_effective": round(n_eff, 3), "mean": round(mean, 4), "children": children, "drift": self.drift_suspected(key)})
            # a parent whose evidence comes from a single child is a weak prior for its siblings
            eff = strength * (float(cfg["backoff_single_child_factor"]) if children <= 1 else 1.0)
            prior_a, prior_b = max(floor, eff * mean), max(floor, eff * (1.0 - mean))
        min_n = float(cfg["min_effective_n"])
        with_evidence = next((c for c in reversed(chain) if c["n_effective"] >= min_n), None)
        return {
            "a": a,
            "b": b,
            "n_effective": n_eff,
            "key_used": key_used,
            "chain": chain,
            "drift_flags": [c["key"] for c in chain if c["drift"]],
            "evidence_level": with_evidence["level"] if with_evidence else "prior",
            "evidence_key": with_evidence["key"] if with_evidence else "global",
        }

    def predict(self, ctx: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        ref = now or self.now or datetime.now(timezone.utc)
        keys = context_keys(ctx)
        bo = self._backoff(keys, ref)
        a, b = bo["a"], bo["b"]
        mass = float(self.cfg["credible_mass"])
        lo = beta_quantile((1.0 - mass) / 2.0, a, b)
        hi = beta_quantile(1.0 - (1.0 - mass) / 2.0, a, b)
        p = a / (a + b)
        bucket = self.stats.get(bo["evidence_key"]) or {}
        result = {
            "p_success": round(p, 4),
            "credible_interval": [round(lo, 4), round(hi, 4)],
            "credible_mass": mass,
            "n_effective": round(bo["n_effective"], 3),
            "evidence_level": bo["evidence_level"],
            "evidence_key": bo["evidence_key"],
            "resolved_key": bo["key_used"],
            "backoff_chain": bo["chain"],
            "expected_score": self._weighted_stats(bo["evidence_key"], ref, index=2),
            "expected_duration_s": self._weighted_stats(bo["evidence_key"], ref, index=3),
            "td_value": _round_or_none(bucket.get("td_value")),
            "td_updates": bucket.get("td_updates", 0),
            "last_surprise": _round_or_none(bucket.get("last_surprise")),
            "surprise_if_fail": round(-math.log(max(1e-9, 1.0 - p)), 4),
            "surprise_if_ok": round(-math.log(max(1e-9, p)), 4),
            "confidence": round(1.0 - (hi - lo), 4),
            "drift_suspected": bo["drift_flags"],
            "protected_context": is_protected(ctx),
            "evidence": self._evidence(keys, ref),
            "limitations": (load_ethics().get("prediction_card") or {}).get("limitations") or [],
        }
        result["advice"] = self._advice(result)
        result["narration"] = narrate(result)
        return result

    def _weighted_stats(self, key: str, ref: datetime, index: int) -> dict[str, Any] | None:
        b = self.stats.get(key)
        if not b:
            return None
        num = den = sq = 0.0
        for ev in b["events"]:
            val = ev[index]
            if not isinstance(val, (int, float)):
                continue
            w = self._decay(ev[0], ref)
            num += w * float(val)
            den += w
            sq += w * float(val) ** 2
        if den <= 0.0:
            return None
        mean = num / den
        var = max(0.0, sq / den - mean * mean)
        return {"mean": round(mean, 3), "std": round(math.sqrt(var), 3), "n_effective": round(den, 3)}

    def _evidence(self, keys: dict[str, str | None], ref: datetime) -> list[dict[str, Any]]:
        limit = int(self.cfg["evidence_limit"])
        wanted = {k for k in keys.values() if k and k != "global"}
        picks = []
        for exp in reversed(self.history):
            ck = set(v for v in context_keys(exp.get("context") or {}).values() if v)
            if wanted and not (wanted & ck):
                continue
            picks.append(
                {
                    "ts": exp.get("ts"),
                    "source": exp.get("source"),
                    "ok": (exp.get("outcome") or {}).get("ok"),
                    "score": (exp.get("outcome") or {}).get("score"),
                    "hotspot": (exp.get("context") or {}).get("hotspot"),
                    "pattern": (exp.get("context") or {}).get("pattern"),
                    "weight": round(self._decay(parse_ts(exp.get("ts")), ref), 3),
                    "ref": exp.get("ref"),
                }
            )
            if len(picks) >= limit:
                break
        return picks

    def _advice(self, r: dict[str, Any]) -> dict[str, Any]:
        eth = load_ethics()
        abst = eth.get("abstention") or {}
        width = r["credible_interval"][1] - r["credible_interval"][0]
        abstain = (
            r["evidence_level"] == "prior"
            or r["n_effective"] < float(abst.get("min_effective_n", 0.0))
            or width > float(abst.get("max_interval_width", 1.0))
        )
        low_conf = r["confidence"] < float(self.cfg["low_confidence_below"])
        risky = r["p_success"] < 0.5
        high_surprise = (r["last_surprise"] or 0.0) > float(self.cfg["high_surprise_above"])
        drifting = bool(r.get("drift_suspected"))
        if r["protected_context"]:
            stance = (eth.get("protected_contexts") or {}).get("stance", "human_judgment_required")
        elif r["evidence_level"] == "prior":
            stance = "no_experience_yet"
        elif abstain:
            stance = "abstain"
        elif low_conf:
            stance = "thin_evidence"
        elif risky:
            stance = "expect_friction"
        else:
            stance = "expect_success"
        return {
            "stance": stance,
            "abstain": bool(abstain),
            # never propose automation for protected contexts — people decide there
            "suggest_qa_hold": bool((risky or high_surprise or drifting) and not r["protected_context"]),
            "suggest_gather_more": bool(low_conf or abstain or drifting),
            "note": "advisory only — acting on predictions requires switch.cam_enhance",
        }


def narrate(r: dict[str, Any]) -> str:
    """A hedged sentence Cam can say out loud — numbers always come with their doubt.

    Driven by ``advice.stance`` so the spoken line can never disagree with the card.
    """
    lo, hi = r["credible_interval"]
    n = r["n_effective"]
    stance = r["advice"]["stance"]
    if stance == "human_judgment_required":
        if r["evidence_level"] == "prior" or n < 1.0:
            return "This touches people or something I shouldn't decide alone, and I have no real experience with it — no number from me. The call is yours."
        return (
            "This touches people or something I shouldn't decide alone, so take this only as background: "
            f"in about {n:.1f} weighted past runs it went well roughly {r['p_success']:.0%} of the time "
            f"({lo:.0%} to {hi:.0%}). The call is yours."
        )
    if stance == "no_experience_yet":
        return "I haven't done anything like this before, so I won't give you a number — let's try it and I'll learn."
    if stance == "abstain":
        have = "almost no experience with this exact situation" if n < 1.0 else f"only about {n:.1f} runs' worth of experience here"
        return f"I have {have}, and the honest range is {lo:.0%} to {hi:.0%} — too wide to call. I'd rather say I don't know yet."
    drift = " Recent runs surprised me, so I'm holding this looser than usual." if r["drift_suspected"] else ""
    return (
        f"From about {n:.1f} weighted past runs, I'd expect this to go well roughly {r['p_success']:.0%} of the time "
        f"(somewhere between {lo:.0%} and {hi:.0%}).{drift}"
    )


# --- prequential evaluation ---------------------------------------------------

def _auroc(pairs: list[tuple[float, float]]) -> float | None:
    pos = [p for p, y in pairs if y >= 0.5]
    neg = [p for p, y in pairs if y < 0.5]
    if not pos or not neg:
        return None
    ranked = sorted(pairs, key=lambda t: t[0])
    ranks: dict[float, float] = {}
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        ranks[ranked[i][0]] = (i + j) / 2.0 + 1.0
        i = j + 1
    rank_sum = sum(ranks[p] for p in pos)
    return (rank_sum - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def calibration_metrics(pairs: list[tuple[float, float]], bins: int = 10) -> dict[str, Any]:
    """pairs = [(predicted p, observed y)] → Brier, log loss, ECE, AUROC, skill."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    eps = 1e-9
    logloss = -sum(y * math.log(max(eps, p)) + (1 - y) * math.log(max(eps, 1 - p)) for p, y in pairs) / n
    base_rate = sum(y for _, y in pairs) / n
    # climatology baseline, also prequential: Laplace running mean before each outcome
    brier_base, seen, hits = 0.0, 0, 0.0
    for _p, y in pairs:
        guess = (hits + 1.0) / (seen + 2.0)
        brier_base += (guess - y) ** 2
        seen += 1
        hits += y
    brier_base /= n
    skill = None if brier_base == 0 else 1.0 - brier / brier_base
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for p, y in pairs:
        buckets[min(bins - 1, int(p * bins))].append((p, y))
    ece = 0.0
    reliability = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(y for _, y in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(acc - conf)
        reliability.append({"bin": f"{i / bins:.1f}-{(i + 1) / bins:.1f}", "n": len(bucket), "confidence": round(conf, 3), "accuracy": round(acc, 3)})
    sharpness = sum(abs(p - 0.5) for p, _ in pairs) / n
    auroc = _auroc(pairs)
    return {
        "n": n,
        "brier": round(brier, 4),
        "brier_base_rate": round(brier_base, 4),
        "brier_skill": None if skill is None else round(skill, 4),
        "log_loss": round(logloss, 4),
        "ece": round(ece, 4),
        "auroc": None if auroc is None else round(auroc, 4),
        "base_rate": round(base_rate, 4),
        "sharpness": round(sharpness, 4),
        "reliability": reliability,
    }


def prequential(experiences: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Predict-then-update over the chronological stream; returns metrics + model."""
    model = ExperiencePredictor(cfg)
    pairs: list[tuple[float, float]] = []
    by_group: dict[str, list[tuple[float, float]]] = {}
    surprises: list[float] = []
    abstained = 0
    protected = 0
    score_pairs: list[tuple[float, float, float]] = []
    for exp in experiences:
        ctx = exp.get("context") or {}
        ts = parse_ts(exp.get("ts")) or datetime.now(timezone.utc)
        pred = model.predict(ctx, now=ts)
        y = 1.0 if (exp.get("outcome") or {}).get("ok") else 0.0
        pairs.append((pred["p_success"], y))
        by_group.setdefault(str(ctx.get("hotspot") or ctx.get("center") or "unknown"), []).append((pred["p_success"], y))
        abstained += 1 if pred["advice"]["abstain"] else 0
        protected += 1 if pred["protected_context"] else 0
        actual_score = (exp.get("outcome") or {}).get("score")
        if pred["expected_score"] and isinstance(actual_score, (int, float)):
            score_pairs.append((pred["expected_score"]["mean"], pred["expected_score"]["std"], float(actual_score)))
        rpe = model.update(exp)
        if rpe:
            surprises.append(max(rpe.values()))
    bins = int((cfg or DEFAULTS).get("ece_bins", 10))
    metrics = calibration_metrics(pairs, bins)
    if score_pairs:
        mae = sum(abs(m - a) for m, _s, a in score_pairs) / len(score_pairs)
        covered = sum(1 for m, s, a in score_pairs if abs(a - m) <= 1.645 * max(s, 1e-9)) / len(score_pairs)
        metrics["score_mae"] = round(mae, 3)
        metrics["score_interval_coverage_90"] = round(covered, 3)
        metrics["score_pairs"] = len(score_pairs)
    metrics["mean_surprise"] = round(sum(surprises) / len(surprises), 4) if surprises else None
    metrics["abstention_rate"] = round(abstained / len(pairs), 4) if pairs else None
    metrics["protected_predictions"] = protected
    metrics["parity"] = calibration_parity(by_group, metrics.get("ece"), bins)
    return {"metrics": metrics, "model": model}


def calibration_parity(by_group: dict[str, list[tuple[float, float]]], aggregate_ece: float | None, bins: int) -> dict[str, Any]:
    """Per-context ECE so one domain cannot hide another's over-confidence."""
    par = load_ethics().get("calibration_parity") or {}
    min_n = int(par.get("min_group_n", 8))
    max_gap = float(par.get("max_group_ece_gap", 0.15))
    rows, flagged = [], []
    for group, pairs in sorted(by_group.items()):
        if len(pairs) < min_n:
            continue
        m = calibration_metrics(pairs, bins)
        gap = None if aggregate_ece is None else round(m["ece"] - aggregate_ece, 4)
        row = {"group": group, "n": len(pairs), "ece": m["ece"], "brier": m["brier"], "base_rate": m["base_rate"], "ece_gap": gap}
        row["flag"] = bool(gap is not None and gap > max_gap)
        rows.append(row)
        if row["flag"]:
            flagged.append(group)
    return {"groups": rows, "flagged": flagged, "max_group_ece_gap": max_gap, "min_group_n": min_n}


# --- reports ------------------------------------------------------------------

def summarize_keys(model: ExperiencePredictor, now: datetime | None = None) -> list[dict[str, Any]]:
    ref = now or datetime.now(timezone.utc)
    rows = []
    for key, b in model.stats.items():
        a, bb, n_eff = model._posterior(key, ref, float(model.cfg["prior_alpha"]), float(model.cfg["prior_beta"]))
        last_ts = next((e[0] for e in reversed(b["events"]) if e[0]), None)
        rows.append(
            {
                "key": key,
                "n": len(b["events"]),
                "n_effective": round(n_eff, 3),
                "p_success": round(a / (a + bb), 4),
                "td_value": None if b["td_value"] is None else round(b["td_value"], 4),
                "mean_surprise": round(sum(b["surprises"]) / len(b["surprises"]), 4) if b["surprises"] else None,
                "ewma_surprise": None if b.get("ewma_surprise") is None else round(b["ewma_surprise"], 4),
                "drift_suspected": model.drift_suspected(key),
                "children": len(b.get("children") or ()),
                "last_ts": last_ts.strftime("%Y-%m-%dT%H:%M:%SZ") if last_ts else None,
                "staleness_days": None if last_ts is None else round((ref - last_ts).total_seconds() / 86400.0, 2),
            }
        )
    rows.sort(key=lambda r: (-r["n"], r["key"]))
    return rows


def build_report(*, offline: bool = False, extra: Iterable[Path] = (), cfg: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    experiences, counts = load_experiences(offline=offline, extra=extra)
    ev = prequential(experiences, cfg)
    model: ExperiencePredictor = ev["model"]
    if now is None and offline:
        # a frozen fixture is judged on its own clock, not the wall clock
        stamps = [parse_ts(e.get("ts")) for e in experiences]
        now = max((s for s in stamps if s), default=None)
    ref = now or datetime.now(timezone.utc)
    rows = summarize_keys(model, now=ref)
    watch = [
        r for r in rows
        if r["key"] != "global" and (r["p_success"] < 0.5 or (r["mean_surprise"] or 0) > float(cfg["high_surprise_above"]) or r["drift_suspected"])
    ]
    stale_after = float(cfg["stale_after_days"])
    stale = [
        {"key": r["key"], "staleness_days": r["staleness_days"], "n": r["n"]}
        for r in rows
        if r["key"] != "global" and r["n"] >= 2 and r["staleness_days"] is not None and r["staleness_days"] > stale_after
    ]
    met = ev["metrics"]
    skill = met.get("brier_skill")
    n_ok = sum(1 for e in experiences if (e.get("outcome") or {}).get("ok"))
    n_fail = len(experiences) - n_ok
    min_each = int(cfg["min_outcomes_each_class"])
    if not experiences:
        verdict = "no_experience_yet"
    elif len(experiences) < int(cfg["min_n_for_verdict"]) or min(n_ok, n_fail) < min_each:
        verdict = (
            f"insufficient_sample — n={len(experiences)} (ok={n_ok}, fail={n_fail}); "
            f"need ≥{cfg['min_n_for_verdict']} experiences with ≥{min_each} of each outcome before trusting skill/ECE"
        )
    elif skill is None or skill <= 0.0:
        verdict = "not_yet_skillful — predictions no better than the running base rate; keep gathering experience"
    elif (met.get("ece") or 0.0) > 0.1:
        verdict = "skillful_but_miscalibrated — beats base rate; ECE above 0.1"
    else:
        verdict = "skillful_and_calibrated"
    ethics = load_ethics()
    redacted = sum(1 for e in experiences if e.get("redacted"))
    return {
        "kind": "predictive_cortex_report",
        "verdict": verdict,
        "namespace": (cfg.get("_raw") or {}).get("mesh_namespace", "mesh/enhance/dl/predict"),
        "at": utc(),
        "offline": offline,
        "experience_count": len(experiences),
        "sources": counts,
        "coverage": {
            "duplicates_removed": counts.get("_duplicates_removed", 0),
            "unknown_timestamps": counts.get("_unknown_ts", 0),
            "source_errors": list(LAST_SOURCE_ERRORS),
            "stale_contexts": stale,
            "note": "silent failures that wrote no distillate are invisible; stale contexts hint at them",
        },
        "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "calibration": met,
        "contexts": rows,
        "watch": watch,
        "ethics": {
            "config": _rel(ETHICS_PATH),
            "principles": [p.get("id") for p in ethics.get("principles") or []],
            "protected_predictions": met.get("protected_predictions"),
            "abstention_rate": met.get("abstention_rate"),
            "redacted_records": redacted,
            "parity_flagged": (met.get("parity") or {}).get("flagged"),
            "kill_switch": "act" if kill_active() else "armed_allow",
        },
        "gate": "advisory_only — switch.cam_enhance required to act on predictions",
    }


def write_distillate(doc: dict[str, Any], name: str = "latest.json") -> Path:
    if kill_active():
        raise KillSwitchActive("CAM_KILL is set — refusing to write distillate")
    DISTILL_DIR.mkdir(parents=True, exist_ok=True)
    path = DISTILL_DIR / name
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path
