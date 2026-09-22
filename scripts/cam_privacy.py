#!/usr/bin/env python3
"""Cam privacy kernel — the one place that knows whose data a process holds
and what may leave it.

Policy: config/privacy/charter.json · Doc: docs/PRIVACY_CHARTER.md

Every Cam script that stores or shares anything goes through here:

  principal      one process serves one person (CAM_PRINCIPAL, default owner)
  scoped_dir     the only directory a principal may use for a given store
  enter          seal a directory to its principal, refuse a foreign one, chmod 700
  classify       find personal information / preferences / secrets in text
  redact         replace them with class tags (never echoes the value)
  assert_shareable   enforce the charter's sink table before anything is written
  seal_doc / verify_doc   HMAC seal for ledgers (tamper evidence)
  consent_allows what Aaron has explicitly allowed to leave, and to whom

    python3 scripts/cam_privacy.py doctor          # principal, seals, modes, keys
    python3 scripts/cam_privacy.py audit           # scan distillates / caches for leaks
    python3 scripts/cam_privacy.py classify --text "..."
    python3 scripts/cam_privacy.py redact --text "..."
    python3 scripts/cam_privacy.py principals list | add <id> --label "..." --aaron
    python3 scripts/cam_privacy.py consent list | grant <recipient> --classes personal_info --aaron
    python3 scripts/cam_privacy.py keygen --aaron  # identity/aaron/local/ledger.key

Findings never include the matched value — only the class, a count and where.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "config/privacy/charter.json"
OWNER = "aaron"
PRINCIPAL_ENV = "CAM_PRINCIPAL"
SEAL_FILE = ".principal"
KEY_ENV = "CAM_LEDGER_HMAC_KEY"
LOCAL_DIR = ROOT / "identity/aaron/local"
KEY_FILE = LOCAL_DIR / "ledger.key"
VOCAB_FILE = LOCAL_DIR / "personal-vocabulary.txt"
CONSENT_FILE = LOCAL_DIR / "consent.json"
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
RESERVED = {"aaron", "owner", "cam", "chief", "human", "system", "all", "shared", "mesh", "vault"}


class PrivacyViolation(SystemExit):
    """Raised (as a clean exit) when a write would breach the charter."""


# --- config -------------------------------------------------------------------

def charter() -> dict:
    return json.loads(CHARTER.read_text(encoding="utf-8"))


def iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- principals ---------------------------------------------------------------

def valid_principal_id(pid: str) -> bool:
    return bool(ID_RE.match(pid or ""))


def current_principal() -> str:
    pid = (os.environ.get(PRINCIPAL_ENV) or OWNER).strip().lower()
    if pid == OWNER:
        return OWNER
    if not valid_principal_id(pid) or pid in RESERVED:
        raise PrivacyViolation(f"invalid {PRINCIPAL_ENV}={pid!r}: guest ids are [a-z][a-z0-9_-]{{1,31}} and not reserved")
    return pid


def is_owner(pid: str | None = None) -> bool:
    return (pid or current_principal()) == OWNER


def principals_root() -> Path:
    override = os.environ.get("CAM_PRINCIPALS_ROOT")
    return Path(override) if override else ROOT / "data/principals"


def guest_root(pid: str) -> Path:
    if pid == OWNER:
        raise PrivacyViolation("the owner has no guest root")
    return principals_root() / pid


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def scoped_dir(kind: str, env_var: str | None, default: Path, pid: str | None = None) -> Path:
    """Owner: the pre-existing env override or default (unchanged behaviour).
    Guest: <guest_root>/<kind>; an env override is honoured only if it stays
    inside the guest root — pointing a guest at the owner's data is refused."""
    pid = pid or current_principal()
    override = os.environ.get(env_var) if env_var else None
    if pid == OWNER:
        return Path(override) if override else default
    root = guest_root(pid)
    if override:
        cand = Path(override)
        if not _inside(cand, root):
            raise PrivacyViolation(f"{env_var}={override!r} is outside principal {pid}'s root {root} — refused")
        return cand
    return root / kind


# --- seals + hardening ----------------------------------------------------------

def harden_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def harden_file(path: Path) -> None:
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        pass


def seal_path(path: Path) -> Path:
    return path / SEAL_FILE


def read_seal(path: Path) -> dict | None:
    p = seal_path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"principal": "?", "corrupt": True}


def enter(path: Path, pid: str | None = None, create: bool = True) -> Path:
    """Claim a data directory for `pid`. First touch seals it; a later touch
    by a different principal refuses. Also applies owner-only permissions."""
    pid = pid or current_principal()
    if not create and not path.exists():
        return path
    harden_dir(path)
    seal = read_seal(path)
    if seal is None:
        seal_path(path).write_text(json.dumps({"principal": pid, "sealed": iso()}) + "\n", encoding="utf-8")
        harden_file(seal_path(path))
    elif seal.get("principal") != pid:
        raise PrivacyViolation(f"{path} is sealed to principal {seal.get('principal')!r}; "
                               f"process is {pid!r} — cross-principal access refused")
    return path


# --- classification -------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w.:-])(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?![\w-])|(?<![\w.+-])\+\d{10,14}(?![\w-])")
_NATIONAL_ID = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
_ADDRESS = re.compile(r"\b\d{1,6}\s+(?:[A-Z][a-z]+\.?\s+){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Way|Pl|Place|Terrace|Ter|Cir|Circle|Pkwy|Parkway)\b\.?(?:,?\s*(?:Apt|Suite|Unit|#)\s*\w+)?")
_DOB = re.compile(r"\b(?:DOB|date of birth|birthday|born(?: on)?)\b\s*[:\-]?\s*(?:\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:,? \d{4})?)", re.I)
_PREFERENCE = re.compile(r"\b(?:I|Aaron|he|she|they)\s+(?:really\s+)?(?:prefers?|likes?|loves?|hates?|dislikes?|can't stand|always wants?|never wants?|would rather)\b|\bmy (?:favou?rite|usual|go-to)\b", re.I)
_SENSITIVE = re.compile(r"\b(?:diagnos\w*|prescription|medication|therap\w+|psychiatr\w+|pregnan\w+|HIV|salary|net worth|bank account|routing number|passcode|password|home address|lives at|sexual|religio\w+|immigration status|criminal record)\b", re.I)
_API_KEY = re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj)?[-_]?[A-Za-z0-9]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bAKIA[0-9A-Z]{16}\b|\bxox[abprs]-[A-Za-z0-9-]{10,}\b|\bAIza[0-9A-Za-z_-]{30,}\b")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")
_ENV_ASSIGN = re.compile(r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)\s*[=:]\s*['\"]?[^\s'\"]{6,}")
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")

DETECTORS: dict[str, tuple[str, re.Pattern]] = {
    "email": ("personal_info", _EMAIL),
    "phone": ("personal_info", _PHONE),
    "national_id": ("personal_info", _NATIONAL_ID),
    "payment_card": ("personal_info", _CARD),
    "iban": ("personal_info", _IBAN),
    "street_address": ("personal_info", _ADDRESS),
    "date_of_birth": ("personal_info", _DOB),
    "preference_statement": ("personal_preference", _PREFERENCE),
    "sensitive_context": ("personal_preference", _SENSITIVE),
    "api_key": ("secret", _API_KEY),
    "bearer_token": ("secret", _BEARER),
    "env_assignment": ("secret", _ENV_ASSIGN),
    "private_key": ("secret", _PRIVATE_KEY),
}
TAGS = {
    "email": "[email]", "phone": "[phone]", "national_id": "[id-number]", "payment_card": "[card]",
    "iban": "[iban]", "street_address": "[address]", "date_of_birth": "[dob]",
    "preference_statement": "[preference]", "sensitive_context": "[sensitive]",
    "api_key": "[secret]", "bearer_token": "[secret]", "env_assignment": "[secret]",
    "private_key": "[secret]", "personal_term": "[personal]",
}


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def vocab_path() -> Path:
    override = os.environ.get("CAM_PRIVACY_VOCAB")
    return Path(override) if override else VOCAB_FILE


def personal_vocabulary() -> list[str]:
    """The owner's own list of identifying terms (family names, street, employer,
    nicknames …). Git-ignored; read as data; matched case-insensitively."""
    p = vocab_path()
    if not p.exists():
        return []
    terms = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        t = line.strip()
        if t and not t.startswith("#") and len(t) >= 3:
            terms.append(t)
    return terms


def classify(text: str) -> list[dict]:
    """Return findings [{detector, class, count}] for one string. Never the values."""
    text = text or ""
    found: dict[str, int] = {}
    for det, (cls, rx) in DETECTORS.items():
        hits = 0
        for m in rx.finditer(text):
            if det == "payment_card":
                digits = re.sub(r"\D", "", m.group(0))
                if not (13 <= len(digits) <= 19 and _luhn(digits)):
                    continue
            hits += 1
        if hits:
            found[det] = hits
    vocab = personal_vocabulary()
    if vocab:
        low = text.lower()
        n = sum(low.count(t.lower()) for t in vocab)
        if n:
            found["personal_term"] = n
    return [{"detector": d, "class": DETECTORS[d][0] if d in DETECTORS else "personal_info", "count": c}
            for d, c in found.items()]


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Replace every detected span with its class tag."""
    text = text or ""
    counts: dict[str, int] = {}

    def sub(det: str, rx: re.Pattern, s: str) -> str:
        def repl(m: re.Match) -> str:
            if det == "payment_card":
                digits = re.sub(r"\D", "", m.group(0))
                if not (13 <= len(digits) <= 19 and _luhn(digits)):
                    return m.group(0)
            counts[det] = counts.get(det, 0) + 1
            return TAGS[det]
        return rx.sub(repl, s)

    # secrets first (they can contain '@'), then identifiers, then context
    for det in ("private_key", "bearer_token", "env_assignment", "api_key", "email", "iban", "payment_card",
                "national_id", "phone", "street_address", "date_of_birth", "preference_statement",
                "sensitive_context"):
        text = sub(det, DETECTORS[det][1], text)
    for term in sorted(personal_vocabulary(), key=len, reverse=True):
        rx = re.compile(re.escape(term), re.I)
        text, n = rx.subn(TAGS["personal_term"], text)
        if n:
            counts["personal_term"] = counts.get("personal_term", 0) + n
    return text, counts


SECRET_DETECTORS = ("private_key", "bearer_token", "env_assignment", "api_key")


def redact_secrets(text: str) -> tuple[str, int]:
    """Only the secret class — for artefacts that may carry personal context
    (drafts, briefs) but must never carry a credential."""
    n = 0
    for det in SECRET_DETECTORS:
        text, k = DETECTORS[det][1].subn(TAGS[det], text or "")
        n += k
    return text, n


def walk_strings(obj, path: str = "$"):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")


def findings_in(obj) -> list[dict]:
    out: list[dict] = []
    for where, s in walk_strings(obj):
        for f in classify(s):
            out.append({**f, "where": where})
    return out


def redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)[0]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


# --- sink enforcement -------------------------------------------------------------

def sink_policy(sink: str) -> dict:
    sinks = charter()["sinks"]
    if sink not in sinks:
        raise PrivacyViolation(f"unknown sink {sink!r}; charter sinks: {sorted(sinks)}")
    return sinks[sink]


def assert_shareable(obj, sink: str, pid: str | None = None):
    """Apply the charter's sink table to `obj` before it is written / returned.
    deny → PrivacyViolation (counts only in the message), redact → redacted
    copy, allow → obj unchanged. Owner-only sinks refuse guest principals."""
    pid = pid or current_principal()
    pol = sink_policy(sink)
    scope = pol.get("scope")
    if scope == "never":
        raise PrivacyViolation(f"sink {sink!r} is never allowed for personal data (charter)")
    if scope == "owner_only" and pid != OWNER:
        raise PrivacyViolation(f"sink {sink!r} is owner-only; principal {pid!r} keeps its data in its own root")
    found = findings_in(obj)
    if not found:
        return obj
    by_class: dict[str, int] = {}
    for f in found:
        by_class[f["class"]] = by_class.get(f["class"], 0) + f["count"]
    denied = {c: n for c, n in by_class.items() if pol.get(c) == "deny"}
    if denied:
        raise PrivacyViolation(f"refusing to write to sink {sink!r}: contains {denied} (charter: deny)")
    if any(pol.get(c) == "redact" for c in by_class):
        return redact_obj(obj)
    return obj


def assert_operational(obj, label: str):
    """Counts-only check independent of principal scope: any personal class or
    secret anywhere in `obj` refuses. Used for guest-root distillates, which
    have no sanctioned sink beyond the guest's own directory."""
    found = findings_in(obj)
    if found:
        by_class: dict[str, int] = {}
        for f in found:
            by_class[f["class"]] = by_class.get(f["class"], 0) + f["count"]
        raise PrivacyViolation(f"{label} must be counts-only; contains {by_class}")
    return obj


# --- HMAC seals for ledgers ----------------------------------------------------------

def hmac_key() -> bytes | None:
    val = os.environ.get(KEY_ENV)
    if val:
        return val.encode("utf-8")
    if KEY_FILE.exists():
        try:
            return KEY_FILE.read_text(encoding="utf-8").strip().encode("utf-8") or None
        except OSError:
            return None
    return None


def _canonical(doc: dict) -> bytes:
    body = {k: v for k, v in doc.items() if k != "_seal"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def seal_doc(doc: dict, key: bytes | None = None) -> dict:
    key = key if key is not None else hmac_key()
    if not key:
        doc.pop("_seal", None)
        return doc
    sig = hmac.new(key, _canonical(doc), hashlib.sha256).hexdigest()
    doc["_seal"] = {"alg": "hmac-sha256", "sig": sig, "at": iso()}
    return doc


def verify_doc(doc: dict, key: bytes | None = None) -> str:
    """'ok' | 'mismatch' | 'unsealed' (key present, no seal) | 'nokey'."""
    key = key if key is not None else hmac_key()
    if not key:
        return "nokey"
    seal = doc.get("_seal") or {}
    if not seal.get("sig"):
        return "unsealed"
    want = hmac.new(key, _canonical(doc), hashlib.sha256).hexdigest()
    return "ok" if hmac.compare_digest(want, str(seal["sig"])) else "mismatch"


def keygen(force: bool = False) -> Path:
    harden_dir(LOCAL_DIR)
    if KEY_FILE.exists() and not force:
        raise PrivacyViolation(f"{KEY_FILE} exists; pass --force to rotate (existing seals will read as mismatch until re-saved)")
    KEY_FILE.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    harden_file(KEY_FILE)
    return KEY_FILE


# --- consent --------------------------------------------------------------------------

def consent_path() -> Path:
    override = os.environ.get("CAM_PRIVACY_CONSENT")
    return Path(override) if override else CONSENT_FILE


def load_consent() -> dict:
    p = consent_path()
    if not p.exists():
        return {"version": 1, "grants": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "grants": [], "corrupt": True}


def consent_allows(recipient: str, cls: str, now: datetime | None = None) -> bool:
    """Has Aaron explicitly allowed class `cls` to go to `recipient`? Default no."""
    now = now or datetime.now(timezone.utc)
    rec = (recipient or "").strip().lower()
    for g in load_consent().get("grants") or []:
        if g.get("recipient", "").lower() != rec or g.get("revoked"):
            continue
        if cls not in (g.get("classes") or []):
            continue
        exp = g.get("expires")
        if exp:
            try:
                if datetime.fromisoformat(exp.replace("Z", "+00:00")) < now:
                    continue
            except ValueError:
                continue
        return True
    return False


def consent_grant(recipient: str, classes: list[str], expires: str | None, note: str | None) -> dict:
    doc = load_consent()
    grant = {"recipient": recipient.strip().lower(), "classes": sorted(set(classes)),
             "granted": iso(), "expires": expires, "note": note, "by": "human.aaron"}
    doc.setdefault("grants", []).append(grant)
    harden_dir(consent_path().parent)
    consent_path().write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    harden_file(consent_path())
    return grant


def consent_revoke(recipient: str) -> int:
    doc = load_consent()
    n = 0
    for g in doc.get("grants") or []:
        if g.get("recipient") == recipient.strip().lower() and not g.get("revoked"):
            g["revoked"] = iso()
            n += 1
    consent_path().write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return n


# --- guest onboarding -------------------------------------------------------------------

GUEST_PROMPT_TEMPLATE = ROOT / "config/privacy/guest-prompt-template.md"


def add_principal(pid: str, label: str | None) -> dict:
    pid = (pid or "").strip().lower()
    if not valid_principal_id(pid) or pid in RESERVED:
        raise PrivacyViolation(f"invalid guest id {pid!r}")
    root = guest_root(pid)
    if root.exists():
        raise PrivacyViolation(f"principal {pid} already exists at {root}")
    enter(root, pid)
    for sub in ("instinct", "swarm", "inkbox/inbound", "distill"):
        enter(root / sub, pid)
    profile = {"id": pid, "label": label or pid, "kind": "guest", "created": iso(),
               "consent": {"keeps": ["own thread", "own jobs", "own drafts"], "shares_with": "nobody"},
               "isolation": "memory and prompts are individual; never merged with any other person"}
    (root / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    harden_file(root / "profile.json")
    template = GUEST_PROMPT_TEMPLATE.read_text(encoding="utf-8") if GUEST_PROMPT_TEMPLATE.exists() else "# {label}\n"
    (root / "prompt.md").write_text(template.replace("{id}", pid).replace("{label}", profile["label"]), encoding="utf-8")
    harden_file(root / "prompt.md")
    return {"ok": True, "principal": profile, "root": str(root),
            "run": f"{PRINCIPAL_ENV}={pid} python3 scripts/cam-mcp-server.py"}


def list_principals() -> list[dict]:
    rows = [{"id": OWNER, "kind": "owner", "root": "data/ (owner roots)"}]
    root = principals_root()
    if root.exists():
        for p in sorted(root.iterdir()):
            if p.is_dir() and (p / "profile.json").exists():
                try:
                    prof = json.loads((p / "profile.json").read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    prof = {"id": p.name}
                rows.append({"id": prof.get("id", p.name), "kind": "guest", "label": prof.get("label"),
                             "root": str(p), "sealed_to": (read_seal(p) or {}).get("principal")})
    return rows


# --- doctor / audit -------------------------------------------------------------------------

def _mode_of(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def owner_data_dirs() -> list[Path]:
    return [ROOT / "data/instinct", ROOT / "data/swarm", ROOT / "data/inkbox", LOCAL_DIR]


def doctor() -> dict:
    pid = current_principal()
    problems: list[str] = []
    notes: list[str] = []
    key = hmac_key()
    if not key:
        notes.append(f"no ledger HMAC key ({KEY_ENV} or {KEY_FILE.relative_to(ROOT)}) — run `cam_privacy.py keygen --aaron` for tamper evidence")
    for d in owner_data_dirs():
        if not d.exists():
            continue
        mode = _mode_of(d)
        if mode is not None and mode & 0o077:
            problems.append(f"{d.relative_to(ROOT)} is group/world accessible (mode {oct(mode)}); expected 700")
        seal = read_seal(d)
        if seal and seal.get("principal") != OWNER:
            problems.append(f"{d.relative_to(ROOT)} sealed to {seal.get('principal')!r}, not the owner")
    proot = principals_root()
    if proot.exists():
        for p in proot.iterdir():
            if not p.is_dir():
                continue
            seal = read_seal(p)
            if not seal:
                problems.append(f"guest root {p.name} has no seal")
            elif seal.get("principal") != p.name:
                problems.append(f"guest root {p.name} sealed to {seal.get('principal')!r}")
            mode = _mode_of(p)
            if mode is not None and mode & 0o077:
                problems.append(f"guest root {p.name} mode {oct(mode)}; expected 700")
    if not VOCAB_FILE.exists() and pid == OWNER:
        notes.append("no personal vocabulary yet (identity/aaron/local/personal-vocabulary.txt) — detectors run on patterns only")
    consent = load_consent()
    if consent.get("corrupt"):
        problems.append("consent record is corrupt")
    return {"ok": not problems, "principal": pid, "owner": OWNER, "hmac_key": bool(key),
            "vocabulary_terms": len(personal_vocabulary()), "consent_grants": len(consent.get("grants") or []),
            "principals": list_principals(), "problems": problems, "notes": notes}


AUDIT_TARGETS = [
    ("mesh_distillate", "vault/10-Mesh-Distillates/instinct/latest.json"),
    ("mesh_distillate", "vault/10-Mesh-Distillates/agent-lineage/latest.json"),
    ("mesh_distillate", "vault/10-Mesh-Distillates/needs-attention/latest.json"),
    ("mesh_distillate", "vault/10-Mesh-Distillates/system-integration-latest.json"),
    ("mesh_note", "identity/persistence/cline-session-cache.json"),
]


def git_tracked(prefixes: list[str]) -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--", *prefixes], cwd=str(ROOT), capture_output=True,
                             text=True, timeout=20)
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def audit(extra_paths: list[str] | None = None) -> dict:
    """Scan every sanctioned cross-boundary artefact for personal classes and
    confirm private material is not tracked by git. Counts only, never values."""
    findings: list[dict] = []
    targets = list(AUDIT_TARGETS) + [("mesh_distillate", p) for p in (extra_paths or [])]
    for sink, rel in targets:
        p = ROOT / rel if not os.path.isabs(rel) else Path(rel)
        if not p.exists():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            findings.append({"severity": "warn", "where": rel, "issue": "unreadable json"})
            continue
        pol = sink_policy(sink)
        for f in findings_in(doc):
            verdict = pol.get(f["class"], "allow")
            if verdict in ("deny", "redact"):
                findings.append({"severity": "high" if verdict == "deny" else "medium", "where": f"{rel}:{f['where']}",
                                 "class": f["class"], "detector": f["detector"], "count": f["count"], "sink": sink})
    tracked = git_tracked(["data/principals", "identity/aaron/local", "data/instinct", "data/swarm", "data/inkbox"])
    for t in tracked:
        findings.append({"severity": "high", "where": t, "issue": "private path tracked by git"})
    for d in owner_data_dirs():
        mode = _mode_of(d)
        if d.exists() and mode is not None and mode & 0o077:
            findings.append({"severity": "medium", "where": str(d.relative_to(ROOT)), "issue": f"mode {oct(mode)} (expected 700)"})
    # ledger seals
    for rel in ("data/swarm/lineage.json", "data/instinct/ledger.json"):
        p = ROOT / rel
        if p.exists():
            try:
                state = verify_doc(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                state = "unreadable"
            if state == "mismatch":
                findings.append({"severity": "high", "where": rel, "issue": "HMAC seal mismatch (tampered or rotated key)"})
    return {"ok": not any(f["severity"] == "high" for f in findings), "at": iso(),
            "principal": current_principal(), "findings": findings,
            "scanned": [rel for _, rel in targets if (ROOT / rel).exists()]}


# --- CLI ---------------------------------------------------------------------------------------

def _dump(obj) -> int:
    print(json.dumps(obj, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cam privacy kernel")
    parser.add_argument("--aaron", action="store_true", help="I am Aaron at the CLI (principals add, consent, keygen)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="principal, seals, modes, keys")
    p = sub.add_parser("audit", help="scan distillates / caches / git for personal classes")
    p.add_argument("--path", action="append", help="extra JSON file to audit as a mesh distillate")
    p = sub.add_parser("classify", help="findings for a text (counts only)")
    p.add_argument("--text", required=True)
    p = sub.add_parser("redact", help="redacted text")
    p.add_argument("--text", required=True)
    p = sub.add_parser("principals", help="list | add <id>")
    p.add_argument("action", choices=["list", "add"])
    p.add_argument("id", nargs="?")
    p.add_argument("--label")
    p = sub.add_parser("consent", help="list | grant <recipient> | revoke <recipient>")
    p.add_argument("action", choices=["list", "grant", "revoke", "check"])
    p.add_argument("recipient", nargs="?")
    p.add_argument("--classes", default="personal_info")
    p.add_argument("--expires")
    p.add_argument("--note")
    p = sub.add_parser("keygen", help="create identity/aaron/local/ledger.key")
    p.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        rep = doctor()
        _dump(rep)
        return 0 if rep["ok"] else 1
    if args.cmd == "audit":
        rep = audit(args.path)
        _dump(rep)
        return 0 if rep["ok"] else 1
    if args.cmd == "classify":
        return _dump({"findings": classify(args.text)})
    if args.cmd == "redact":
        text, counts = redact(args.text)
        return _dump({"text": text, "redacted": counts})
    if args.cmd == "principals":
        if args.action == "list":
            return _dump(list_principals())
        if not args.aaron:
            raise PrivacyViolation("adding a person is Aaron's decision: re-run with --aaron")
        if not args.id:
            raise PrivacyViolation("principals add needs an id")
        return _dump(add_principal(args.id, args.label))
    if args.cmd == "consent":
        if args.action == "list":
            return _dump(load_consent())
        if args.action == "check":
            return _dump({"recipient": args.recipient, "classes": {
                c: consent_allows(args.recipient or "", c) for c in args.classes.split(",")}})
        if not args.aaron:
            raise PrivacyViolation("consent is Aaron's alone: re-run with --aaron (never over MCP)")
        if not args.recipient:
            raise PrivacyViolation("consent grant/revoke needs a recipient")
        if args.action == "grant":
            return _dump({"ok": True, "grant": consent_grant(args.recipient, args.classes.split(","), args.expires, args.note)})
        return _dump({"ok": True, "revoked": consent_revoke(args.recipient)})
    if args.cmd == "keygen":
        if not args.aaron:
            raise PrivacyViolation("keygen is Aaron's call: re-run with --aaron")
        path = keygen(force=args.force)
        return _dump({"ok": True, "key_file": str(path.relative_to(ROOT)), "mode": "600",
                      "note": f"export {KEY_ENV} instead if you prefer an env var"})
    return 2


if __name__ == "__main__":
    sys.exit(main())
