"""Cam privacy core — one definition of "personal information" for every layer.

Used by:
  * scripts/pii-guard.py          — pre-commit / pre-push / CI scanner
  * scripts/cam_journal.py        — intent journal redaction
  * scripts/activity_emit.py      — live-activity distillates
  * scripts/sync-cline-session.py — session distillates
  * scripts/cam_sentinel.py       — private-path deny at the motor boundary
  * scripts/system-health-scan.py — neuron.privacy_guard

Policy lives in config/privacy/pii-guard.json (a Sentinel guardrail path). The
policy is operator-agnostic: `operator.handle` / `operator.display_name` are
expanded into paths and patterns, and the operator's own personal facts come
from private memory (`privacy.personal_terms`) — never from a tracked file.
This module never prints or stores what it finds unredacted: findings carry a
redacted snippet only.

Portable: scripts/privacy-kit.py exports this stack into any other repository;
scripts/privacy-init.py sets it up for a new operator.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "privacy" / "pii-guard.json"

# Sealed list of the operator's own personal facts (name, street, employer, …).
# Lives only in private memory; the guard blocks and redacts every occurrence.
PERSONAL_TERMS_KEY = "privacy.personal_terms"
PERSONAL_TERMS_RULE = "personal_term"
MIN_TERM_LEN = 3

_CFG_CACHE: dict | None = None
_RULES_CACHE: list["Rule"] | None = None
_TERMS_CACHE: list[str] | None = None


# --- config -------------------------------------------------------------------

DEFAULT_OPERATOR = {"handle": "operator", "display_name": "the operator"}


def operator(cfg: dict | None = None) -> dict:
    """Who this checkout protects. Only a handle and a display name — nothing personal."""
    raw = dict((cfg or load_config()).get("operator") or {})
    out = dict(DEFAULT_OPERATOR)
    out.update({k: v for k, v in raw.items() if isinstance(v, str) and v})
    return out


def _expand(node, op: dict):
    """Replace {handle} / {display_name} placeholders in every string of the policy."""
    if isinstance(node, str):
        return node.replace("{handle}", op["handle"]).replace("{display_name}", op["display_name"])
    if isinstance(node, list):
        return [_expand(x, op) for x in node]
    if isinstance(node, dict):
        return {k: (v if k == "operator" else _expand(v, op)) for k, v in node.items()}
    return node


def load_config(path: Path | None = None, *, force: bool = False) -> dict:
    global _CFG_CACHE, _RULES_CACHE, _TERMS_CACHE
    if path is None and _CFG_CACHE is not None and not force:
        return _CFG_CACHE
    raw = json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))
    cfg = _expand(raw, operator(raw))
    if path is None:
        _CFG_CACHE = cfg
        _RULES_CACHE = None
        _TERMS_CACHE = None
    return cfg


def personal_terms(*, force: bool = False) -> list[str]:
    """The operator's protected terms from private memory (empty when no store / no key).

    Never raises and never logs: CI runners have no store and must simply see no terms.
    Set PII_GUARD_SKIP_PRIVATE_TERMS=1 to disable (tests, throwaway machines).
    """
    global _TERMS_CACHE
    if _TERMS_CACHE is not None and not force:
        return _TERMS_CACHE
    terms: list[str] = []
    import os

    if os.environ.get("PII_GUARD_SKIP_PRIVATE_TERMS") != "1":
        try:
            import private_memory as pm  # local import: private_memory must not import privacy

            store = pm.PrivateMemory(create=False)
            if store.home.exists() and store.has(PERSONAL_TERMS_KEY):
                terms = normalize_terms(store.get_json(PERSONAL_TERMS_KEY))
        except Exception:
            terms = []
    _TERMS_CACHE = terms
    return terms


def normalize_terms(values) -> list[str]:
    out: list[str] = []
    for v in values or []:
        if not isinstance(v, str):
            continue
        t = " ".join(v.split())
        if len(t) >= MIN_TERM_LEN and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    return out


def personal_terms_rule(terms: list[str]) -> "Rule | None":
    """One case-insensitive rule for every protected term (longest first, flexible whitespace)."""
    terms = normalize_terms(terms)
    if not terms:
        return None
    alts = [re.escape(t).replace(r"\ ", r"\s+") for t in sorted(terms, key=len, reverse=True)]
    return Rule(
        id=PERSONAL_TERMS_RULE,
        severity="block",
        label="protected personal term (sealed in private memory)",
        regex=re.compile(r"(?i)(?<![\w@])(?:" + "|".join(alts) + r")(?![\w@])"),
    )


@dataclass
class Rule:
    id: str
    severity: str
    label: str
    regex: re.Pattern
    allow: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    validator: Callable[[str], bool] | None = None

    def applies_to(self, rel: str) -> bool:
        # Virtual labels such as "<text>" or "<pr-body>" have no path: every rule applies.
        if not rel.startswith("<") and self.paths and not any(glob_match(rel, g) for g in self.paths):
            return False
        return not any(glob_match(rel, g) for g in self.exclude)


def _luhn(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    if len(set(digits)) == 1:
        return False
    total, parity = 0, len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _ipv4_public(candidate: str) -> bool:
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_reserved or ip.is_link_local:
        return False
    # Private LAN ranges are low-risk documentation values (192.168.x, 10.x); the
    # tailnet rule handles 100.64/10 separately.
    if ip.is_private:
        return False
    # Documentation / example ranges (RFC 5737) are fine.
    for doc in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"):
        if ip in ipaddress.ip_network(doc):
            return False
    return True


def _phone_real(candidate: str) -> bool:
    """False for fictional North-American numbers: 555 area code or the 555-01xx exchange range."""
    digits = "".join(c for c in candidate if c.isdigit())
    if digits.startswith("1") and len(digits) in (8, 11):
        digits = digits[1:]
    if digits.startswith("555"):
        return False
    return not (len(digits) == 10 and digits[3:8] == "55501")


_RESERVED_MAIL_DOMAINS = re.compile(
    r"(?:^|\.)(?:example\.(?:com|net|org)|example|test|invalid|localhost|local|lan|internal)$",
    re.IGNORECASE,
)


def _email_real(candidate: str) -> bool:
    """False for RFC 2606 / RFC 6761 reserved domains (example.com, .example, .test, .invalid...)."""
    domain = candidate.rsplit("@", 1)[-1]
    return _RESERVED_MAIL_DOMAINS.search(domain) is None


_VALIDATORS: dict[str, Callable[[str], bool]] = {
    "luhn": _luhn,
    "ipv4_public": _ipv4_public,
    "phone_real": _phone_real,
    "email_real": _email_real,
}


def compile_rules(cfg: dict | None = None) -> list[Rule]:
    global _RULES_CACHE
    if cfg is None:
        cfg = load_config()
        if _RULES_CACHE is not None:
            return _RULES_CACHE
    rules: list[Rule] = []
    for raw in cfg.get("rules") or []:
        rules.append(
            Rule(
                id=raw["id"],
                severity=raw.get("severity", "block"),
                label=raw.get("label", raw["id"]),
                regex=re.compile(raw["pattern"]),
                allow=list(raw.get("allow") or []),
                paths=list(raw.get("paths") or []),
                exclude=list(raw.get("exclude") or []),
                validator=_VALIDATORS.get(raw.get("validator") or ""),
            )
        )
    term_rule = personal_terms_rule(personal_terms())
    if term_rule is not None:
        rules.append(term_rule)
    if cfg is _CFG_CACHE:
        _RULES_CACHE = rules
    return rules


# --- path matching -----------------------------------------------------------

def normalize_rel(path: str | Path, root: Path | None = None) -> str:
    rel = str(path).replace("\\", "/")
    base = str(root or ROOT).replace("\\", "/").rstrip("/") + "/"
    if rel.startswith(base):
        rel = rel[len(base):]
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.lstrip("/")


def _glob_rx(pattern: str) -> str:
    return re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")


def glob_match(rel: str, pattern: str) -> bool:
    """Match a repo-relative path against a gitignore-flavoured glob.

    - `dir/`         → anything under dir
    - `**/name/`     → a `name` directory at any depth
    - `a/**`, `**/*.ext`, `*.ext` (basename) → fnmatch semantics
    - plain path     → exact match
    """
    rel = rel.lstrip("/")
    if pattern.endswith("/"):
        body = pattern.rstrip("/")
        if body.startswith("**/") and "*" not in body[3:]:
            needle = "/" + body[3:] + "/"
            return ("/" + rel).find(needle) >= 0 and not ("/" + rel).endswith(needle.rstrip("/"))
        if "*" in body or "?" in body:
            return re.fullmatch(_glob_rx(body) + "(?:/.*)?", rel) is not None
        return rel == body or rel.startswith(body + "/")
    if "**" in pattern:
        return re.fullmatch(_glob_rx(pattern), rel) is not None
    if "/" not in pattern:
        return fnmatch.fnmatchcase(Path(rel).name, pattern) or fnmatch.fnmatchcase(rel, pattern)
    return fnmatch.fnmatchcase(rel, pattern)


def is_skipped(rel: str, cfg: dict | None = None) -> bool:
    cfg = cfg or load_config()
    return any(glob_match(rel, g) for g in cfg.get("skip_paths") or [])


def path_violation(rel: str, cfg: dict | None = None) -> str | None:
    """Return a reason if this path must never be tracked, else None."""
    cfg = cfg or load_config()
    rel = rel.lstrip("/")
    if any(glob_match(rel, g) for g in cfg.get("private_path_exceptions") or []):
        return None
    for g in cfg.get("private_paths") or []:
        if glob_match(rel, g):
            return f"private path ({g}) — personal information never enters git"
    name = Path(rel).name
    if name in (cfg.get("blocked_basenames") or []):
        return f"blocked filename ({name}) — secrets / biometric material"
    lower = rel.lower()
    for ext in cfg.get("blocked_extensions") or []:
        if lower.endswith(ext):
            return f"blocked extension ({ext}) — media / key material"
    for ext in cfg.get("image_extensions") or []:
        if lower.endswith(ext):
            if any(rel.startswith(p) for p in cfg.get("image_allowed_prefixes") or []):
                return None
            return "image outside allowed asset folders — photos of people never enter git"
    return None


# --- scanning -----------------------------------------------------------------

@dataclass
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    label: str
    snippet: str  # already redacted

    def as_dict(self) -> dict:
        return asdict(self)


def is_binary(blob: bytes) -> bool:
    sample = blob[:8000]
    if b"\0" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _allowed(rule: Rule, line: str, match: str) -> bool:
    for token in rule.allow:
        if token in match or token in line:
            return True
    return False


def scan_text(text: str, rel: str, cfg: dict | None = None, rules: list[Rule] | None = None) -> list[Finding]:
    cfg = cfg or load_config()
    rules = rules if rules is not None else compile_rules(cfg)
    pragma = cfg.get("allow_pragma") or "pii-guard: allow"
    active = [r for r in rules if r.applies_to(rel)]
    if not active:
        return []
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pragma in line:
            continue
        for rule in active:
            for m in rule.regex.finditer(line):
                hit = m.group(0)
                if rule.validator and not rule.validator(hit):
                    continue
                if _allowed(rule, line, hit):
                    continue
                out.append(
                    Finding(
                        path=rel,
                        line=lineno,
                        rule=rule.id,
                        severity=rule.severity,
                        label=rule.label,
                        snippet=redact_line_for_display(line, rules=active),
                    )
                )
                break  # one finding per rule per line is enough
    return out


def scan_bytes(blob: bytes, rel: str, cfg: dict | None = None, rules: list[Rule] | None = None) -> list[Finding]:
    cfg = cfg or load_config()
    if len(blob) > int(cfg.get("max_file_bytes") or 2_000_000):
        return []
    if is_binary(blob):
        return []
    return scan_text(blob.decode("utf-8", errors="replace"), rel, cfg, rules)


def scan_file(path: Path, rel: str | None = None, cfg: dict | None = None, rules: list[Rule] | None = None) -> list[Finding]:
    cfg = cfg or load_config()
    rel = rel or normalize_rel(path)
    findings: list[Finding] = []
    reason = path_violation(rel, cfg)
    if reason:
        findings.append(Finding(rel, 0, "private_path", "block", reason, ""))
    if is_skipped(rel, cfg) or not path.is_file():
        return findings
    try:
        blob = path.read_bytes()
    except OSError:
        return findings
    findings.extend(scan_bytes(blob, rel, cfg, rules))
    return findings


def scan_paths(paths: Iterable[Path | str], root: Path | None = None, cfg: dict | None = None) -> list[Finding]:
    cfg = cfg or load_config()
    rules = compile_rules(cfg)
    root = root or ROOT
    out: list[Finding] = []
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            path = root / path
        out.extend(scan_file(path, normalize_rel(path, root), cfg, rules))
    return out


def blocking(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "block"]


# --- redaction ----------------------------------------------------------------

def redact(text: str, cfg: dict | None = None, rules: list[Rule] | None = None, *, rel: str = "") -> str:
    """Replace every personal-information match with [REDACTED:<rule>].

    Path-scoped rules are ignored here (a runtime string has no path), so
    redaction is stricter than scanning — which is what a log wants.
    """
    if not text:
        return text
    cfg = cfg or load_config()
    rules = rules if rules is not None else compile_rules(cfg)
    out = text
    for rule in rules:
        if rule.exclude and rel and any(glob_match(rel, g) for g in rule.exclude):
            continue

        def _sub(m: re.Match, _rule: Rule = rule) -> str:
            hit = m.group(0)
            if _rule.validator and not _rule.validator(hit):
                return hit
            if any(tok in hit for tok in _rule.allow):
                return hit
            return f"[REDACTED:{_rule.id}]"

        out = rule.regex.sub(_sub, out)
    return out


def redact_line_for_display(line: str, rules: list[Rule] | None = None, width: int = 160) -> str:
    red = redact(line.strip(), rules=rules)
    return red if len(red) <= width else red[: width - 1] + "…"


_PRIVATE_KEY_NAMES = re.compile(
    r"(?i)^(?:timezone|tz|phone|phone_number|mobile|email|e-mail|address|street|home_address|"
    r"dob|date_of_birth|birthday|ssn|passport|licen[cs]e|latitude|longitude|lat|lng|lon|"
    r"voiceprint|faceprint|embedding|embeddings|face_vector|voice_vector)$"
)


def scrub_obj(obj, cfg: dict | None = None, rules: list[Rule] | None = None):
    """Walk dict/list/str and redact PII; blank values under private-looking keys."""
    cfg = cfg or load_config()
    rules = rules if rules is not None else compile_rules(cfg)
    if isinstance(obj, str):
        return redact(obj, cfg, rules)
    if isinstance(obj, list):
        return [scrub_obj(x, cfg, rules) for x in obj]
    if isinstance(obj, tuple):
        return tuple(scrub_obj(x, cfg, rules) for x in obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _PRIVATE_KEY_NAMES.match(str(k)) and v not in (None, "", [], {}, "operator_local"):
                out[k] = "[REDACTED:private_field]"
            else:
                out[k] = scrub_obj(v, cfg, rules)
        return out
    return obj


def contains_private_path(paths: Iterable[str | Path], cfg: dict | None = None) -> str | None:
    """First private path in a motor plan's touched paths, or None."""
    cfg = cfg or load_config()
    for raw in paths:
        rel = normalize_rel(raw)
        for g in cfg.get("private_paths") or []:
            if glob_match(rel, g):
                return rel
    return None


def summary(findings: list[Finding]) -> dict:
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    return {
        "total": len(findings),
        "blocking": len(blocking(findings)),
        "warnings": len([f for f in findings if f.severity != "block"]),
        "by_rule": dict(sorted(by_rule.items())),
    }
