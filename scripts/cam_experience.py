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
  base rate, computed by predicting each experience *before* seeing it

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
FIXTURE = ROOT / "scripts" / "testdata" / "sample-experiences.jsonl"
RUNTIME_LOG = ROOT / "data" / "runtime" / "experiences.jsonl"
DISTILL_DIR = ROOT / "vault" / "10-Mesh-Distillates" / "predictive-cortex"

LOOP_LOG = ROOT / "loop-run-log.md"
LOOP_LATEST = ROOT / "vault" / "10-Mesh-Distillates" / "loop-runs" / "latest.json"
QA_CYCLES = ROOT / "vault" / "10-Mesh-Distillates" / "qa-cycles"
REASONING = ROOT / "vault" / "10-Mesh-Distillates" / "reasoning"

BACKOFF_ORDER = ("hotspot", "pattern", "center", "sense", "global")

_CACHE: dict[str, Any] = {}


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
    return {
        "kind": "experience",
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
        "notes": notes[:240],
        "ref": ref,
    }


def context_keys(ctx: dict[str, Any]) -> dict[str, str | None]:
    return {
        "hotspot": f"hotspot:{ctx['hotspot']}" if ctx.get("hotspot") else None,
        "pattern": f"pattern:{ctx['pattern']}" if ctx.get("pattern") else None,
        "center": f"center:{ctx['center']}" if ctx.get("center") else None,
        "sense": f"sense:{ctx['sense']}" if ctx.get("sense") else None,
        "global": "global",
    }


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
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
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


def record_experience(exp: dict[str, Any], path: Path | None = None) -> Path:
    path = path or runtime_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(exp, ensure_ascii=False) + "\n")
    return path


def load_experiences(*, offline: bool = False, extra: Iterable[Path] = ()) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge every experience source, chronologically sorted, with per-source counts."""
    sources: dict[str, list[dict[str, Any]]] = {}
    if offline:
        sources["fixture"] = read_jsonl(FIXTURE)
    else:
        sources["loop_run_log"] = ingest_loop_log()
        sources["loop_run_latest"] = ingest_loop_latest()
        sources["qa_cycle"] = ingest_qa_cycles()
        sources["reasoning_trace"] = ingest_reasoning()
        sources["runtime_log"] = read_jsonl(runtime_log_path())
    for p in extra:
        sources[f"extra:{p.name}"] = read_jsonl(Path(p))
    merged: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for docs in sources.values():
        for d in docs:
            key = (d.get("ts"), d.get("source"), json.dumps(d.get("context"), sort_keys=True), d.get("ref"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(d)
    merged.sort(key=lambda d: parse_ts(d.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    return merged, {k: len(v) for k, v in sources.items()}


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


def beta_quantile(q: float, a: float, b: float, tol: float = 1e-7) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# --- predictor ----------------------------------------------------------------

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
            return 1.0
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
            },
        )

    # -- learning ------------------------------------------------------------
    def update(self, exp: dict[str, Any]) -> dict[str, Any]:
        ctx = exp.get("context") or {}
        out = exp.get("outcome") or {}
        y = 1.0 if out.get("ok") else 0.0
        reward = (float(out["score"]) / 100.0) if isinstance(out.get("score"), (int, float)) else y
        ts = parse_ts(exp.get("ts"))
        alpha = float(self.cfg["td_alpha"])
        surprise_by_key: dict[str, float] = {}
        for level, key in context_keys(ctx).items():
            if not key:
                continue
            b = self._bucket(key)
            b["events"].append((ts, y, out.get("score"), out.get("duration_s")))
            v = b["td_value"]
            if v is None:
                # first visit: seed at reward, surprise measured against neutral 0.5
                rpe = reward - 0.5
                b["td_value"] = reward
            else:
                rpe = reward - v
                b["td_value"] = v + alpha * rpe
            b["td_updates"] += 1
            b["last_surprise"] = abs(rpe)
            b["surprises"].append(abs(rpe))
            surprise_by_key[level] = round(abs(rpe), 4)
        self.history.append(exp)
        return surprise_by_key

    # -- inference -----------------------------------------------------------
    def _posterior(self, key: str, ref: datetime, prior_a: float, prior_b: float) -> tuple[float, float, float]:
        b = self.stats.get(key)
        a, bb, n_eff = prior_a, prior_b, 0.0
        if b:
            for ts, y, _s, _d in b["events"]:
                w = self._decay(ts, ref)
                a += w * y
                bb += w * (1.0 - y)
                n_eff += w
        return a, bb, n_eff

    def predict(self, ctx: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        ref = now or self.now or datetime.now(timezone.utc)
        keys = context_keys(ctx)
        cfg = self.cfg
        strength = float(cfg["backoff_prior_strength"])

        # hierarchical backoff: coarse → fine, each level's posterior mean becomes
        # the next finer level's prior (shrinkage toward the parent)
        prior_a, prior_b = float(cfg["prior_alpha"]), float(cfg["prior_beta"])
        chain = []
        final = (prior_a, prior_b, 0.0, "prior", "global")
        for level in reversed(BACKOFF_ORDER):
            key = keys.get(level)
            if not key:
                continue
            a, b, n_eff = self._posterior(key, ref, prior_a, prior_b)
            mean = a / (a + b)
            chain.append({"level": level, "key": key, "n_effective": round(n_eff, 3), "mean": round(mean, 4)})
            # floor keeps a near-certain parent from collapsing the child's interval on 2-3 events
            floor = float(cfg["prior_floor"])
            prior_a, prior_b = max(floor, strength * mean), max(floor, strength * (1.0 - mean))
            final = (a, b, n_eff, level, key)
        a, b, n_eff, _level_used, key_used = final
        # the finest level with real evidence is what the number "means"
        min_n = float(cfg["min_effective_n"])
        evidence_level = next((c["level"] for c in reversed(chain) if c["n_effective"] >= min_n), "prior")
        evidence_key = next((c["key"] for c in reversed(chain) if c["n_effective"] >= min_n), "global")
        mass = float(cfg["credible_mass"])
        lo = beta_quantile((1.0 - mass) / 2.0, a, b)
        hi = beta_quantile(1.0 - (1.0 - mass) / 2.0, a, b)
        p = a / (a + b)

        score_stats = self._weighted_stats(evidence_key, ref, index=2)
        dur_stats = self._weighted_stats(evidence_key, ref, index=3)
        bucket = self.stats.get(evidence_key) or {}
        td_value = bucket.get("td_value")
        evidence = self._evidence(keys, ref)
        result = {
            "p_success": round(p, 4),
            "credible_interval": [round(lo, 4), round(hi, 4)],
            "credible_mass": mass,
            "n_effective": round(n_eff, 3),
            "evidence_level": evidence_level,
            "evidence_key": evidence_key,
            "resolved_key": key_used,
            "backoff_chain": chain,
            "expected_score": score_stats,
            "expected_duration_s": dur_stats,
            "td_value": None if td_value is None else round(td_value, 4),
            "td_updates": bucket.get("td_updates", 0),
            "last_surprise": None if bucket.get("last_surprise") is None else round(bucket["last_surprise"], 4),
            "surprise_if_fail": round(-math.log(max(1e-9, 1.0 - p)), 4),
            "surprise_if_ok": round(-math.log(max(1e-9, p)), 4),
            "confidence": round(1.0 - (hi - lo), 4),
            "evidence": evidence,
        }
        result["advice"] = self._advice(result)
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
        low_conf = r["confidence"] < float(self.cfg["low_confidence_below"])
        risky = r["p_success"] < 0.5
        high_surprise = (r["last_surprise"] or 0.0) > float(self.cfg["high_surprise_above"])
        if r["evidence_level"] == "prior":
            stance = "no_experience_yet"
        elif low_conf:
            stance = "thin_evidence"
        elif risky:
            stance = "expect_friction"
        else:
            stance = "expect_success"
        return {
            "stance": stance,
            "suggest_qa_hold": bool(risky or high_surprise),
            "suggest_gather_more": bool(low_conf),
            "note": "advisory only — acting on predictions requires switch.cam_enhance",
        }


# --- prequential evaluation ---------------------------------------------------

def _auroc(pairs: list[tuple[float, float]]) -> float | None:
    pos = [p for p, y in pairs if y >= 0.5]
    neg = [p for p, y in pairs if y < 0.5]
    if not pos or not neg:
        return None
    # rank-sum with tie handling
    ranked = sorted(pairs, key=lambda t: t[0])
    ranks: dict[float, float] = {}
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        ranks[ranked[i][0]] = avg
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
        idx = min(bins - 1, int(p * bins))
        buckets[idx].append((p, y))
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
    return {
        "n": n,
        "brier": round(brier, 4),
        "brier_base_rate": round(brier_base, 4),
        "brier_skill": None if skill is None else round(skill, 4),
        "log_loss": round(logloss, 4),
        "ece": round(ece, 4),
        "auroc": None if (a := _auroc(pairs)) is None else round(a, 4),
        "base_rate": round(base_rate, 4),
        "sharpness": round(sharpness, 4),
        "reliability": reliability,
    }


def prequential(experiences: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Predict-then-update over the chronological stream; returns metrics + model."""
    model = ExperiencePredictor(cfg)
    pairs: list[tuple[float, float]] = []
    surprises: list[float] = []
    score_pairs: list[tuple[float, float, float]] = []  # (pred_mean, pred_std, actual)
    for exp in experiences:
        ctx = exp.get("context") or {}
        ts = parse_ts(exp.get("ts")) or datetime.now(timezone.utc)
        pred = model.predict(ctx, now=ts)
        y = 1.0 if (exp.get("outcome") or {}).get("ok") else 0.0
        pairs.append((pred["p_success"], y))
        actual_score = (exp.get("outcome") or {}).get("score")
        if pred["expected_score"] and isinstance(actual_score, (int, float)):
            score_pairs.append((pred["expected_score"]["mean"], pred["expected_score"]["std"], float(actual_score)))
        rpe = model.update(exp)
        if rpe:
            surprises.append(max(rpe.values()))
    metrics = calibration_metrics(pairs, int((cfg or DEFAULTS).get("ece_bins", 10)))
    if score_pairs:
        mae = sum(abs(m - a) for m, _s, a in score_pairs) / len(score_pairs)
        covered = sum(1 for m, s, a in score_pairs if abs(a - m) <= 1.645 * max(s, 1e-9)) / len(score_pairs)
        metrics["score_mae"] = round(mae, 3)
        metrics["score_interval_coverage_90"] = round(covered, 3)
        metrics["score_pairs"] = len(score_pairs)
    metrics["mean_surprise"] = round(sum(surprises) / len(surprises), 4) if surprises else None
    return {"metrics": metrics, "model": model}


# --- reports ------------------------------------------------------------------

def summarize_keys(model: ExperiencePredictor, now: datetime | None = None) -> list[dict[str, Any]]:
    ref = now or datetime.now(timezone.utc)
    rows = []
    for key, b in model.stats.items():
        a, bb, n_eff = model._posterior(key, ref, float(model.cfg["prior_alpha"]), float(model.cfg["prior_beta"]))
        p = a / (a + bb)
        rows.append(
            {
                "key": key,
                "n": len(b["events"]),
                "n_effective": round(n_eff, 3),
                "p_success": round(p, 4),
                "td_value": None if b["td_value"] is None else round(b["td_value"], 4),
                "mean_surprise": round(sum(b["surprises"]) / len(b["surprises"]), 4) if b["surprises"] else None,
                "last_ts": next((e[0].strftime("%Y-%m-%dT%H:%M:%SZ") for e in reversed(b["events"]) if e[0]), None),
            }
        )
    rows.sort(key=lambda r: (-r["n"], r["key"]))
    return rows


def build_report(*, offline: bool = False, extra: Iterable[Path] = (), cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    experiences, counts = load_experiences(offline=offline, extra=extra)
    ev = prequential(experiences, cfg)
    model: ExperiencePredictor = ev["model"]
    rows = summarize_keys(model)
    watch = [
        r for r in rows
        if r["key"] != "global" and (r["p_success"] < 0.5 or (r["mean_surprise"] or 0) > float(cfg["high_surprise_above"]))
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
    return {
        "verdict": verdict,
        "kind": "predictive_cortex_report",
        "namespace": (cfg.get("_raw") or {}).get("mesh_namespace", "mesh/enhance/dl/predict"),
        "at": utc(),
        "offline": offline,
        "experience_count": len(experiences),
        "sources": counts,
        "config": {k: v for k, v in cfg.items() if not k.startswith("_")},
        "calibration": ev["metrics"],
        "contexts": rows,
        "watch": watch,
        "gate": "advisory_only — switch.cam_enhance required to act on predictions",
    }


def write_distillate(doc: dict[str, Any], name: str = "latest.json") -> Path:
    DISTILL_DIR.mkdir(parents=True, exist_ok=True)
    path = DISTILL_DIR / name
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path
