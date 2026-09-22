"""Private memory — sealed, host-only storage for the operator's personal information.

Everything that describes the operator as a person (visual profile, enrollment
refs, timezone, contact details, device inventory, …) is written here and
*referenced* from tracked files by key. Works for any operator: the handle comes
from config/privacy/pii-guard.json (`operator.handle`). The store is:

  * outside git — default `identity/<handle>/local/private-memory/` (gitignored and a
    pii-guard private path), overridable with `PRIVATE_MEMORY_HOME` / `CAM_PRIVATE_HOME`
    (e.g. ~/.cam/private)
  * encrypted at rest — Fernet (AES-128-CBC + HMAC) when `cryptography` is
    importable, else `openssl enc -aes-256-cbc -pbkdf2`; plaintext only when the
    operator explicitly allows it
  * permission-tight — directory 0700, key + records 0600
  * value-blind in metadata — index.json holds keys, sizes, hashes; never values

Nothing in this module prints a value unless asked (`get`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "privacy" / "pii-guard.json"
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,120}$")
ENVELOPE_VERSION = 1
PERSONAL_TERMS_KEY = "privacy.personal_terms"


def operator_handle() -> str:
    """Read operator.handle straight from the policy file (no import of privacy.py → no cycle)."""
    try:
        op = json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("operator") or {}
        handle = str(op.get("handle") or "").strip()
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", handle):
            return handle
    except (OSError, json.JSONDecodeError):
        pass
    return "operator"


def default_home() -> Path:
    return ROOT / "identity" / operator_handle() / "local" / "private-memory"


DEFAULT_HOME = default_home()

try:  # optional strong backend
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:  # pragma: no cover - depends on host
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PrivateMemoryError(RuntimeError):
    pass


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def resolve_home(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home)
    env = os.environ.get("PRIVATE_MEMORY_HOME") or os.environ.get("CAM_PRIVATE_HOME")
    return Path(env).expanduser() if env else default_home()


def resolve_key_file(home: Path, key_file: Path | None = None) -> Path:
    if key_file is not None:
        return Path(key_file)
    env = os.environ.get("CAM_PRIVATE_KEY_FILE")
    return Path(env).expanduser() if env else home / ".key"


def detect_backend(allow_plaintext: bool = False) -> str:
    if Fernet is not None:
        return "fernet"
    if shutil.which("openssl"):
        return "aes-256-cbc-pbkdf2"
    if allow_plaintext or os.environ.get("CAM_PRIVATE_ALLOW_PLAINTEXT") == "1":
        return "none"
    raise PrivateMemoryError(
        "no encryption backend: install `cryptography` (pip install cryptography) or openssl; "
        "set CAM_PRIVATE_ALLOW_PLAINTEXT=1 only for a throwaway machine"
    )


@dataclass
class Record:
    key: str
    kind: str
    cipher: str
    bytes: int
    sha256: str
    created_at: str
    updated_at: str
    source: str = ""

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class PrivateMemory:
    def __init__(
        self,
        home: Path | None = None,
        key_file: Path | None = None,
        *,
        allow_plaintext: bool = False,
        create: bool = True,
    ) -> None:
        self.home = resolve_home(home)
        self.key_file = resolve_key_file(self.home, key_file)
        self.records_dir = self.home / "records"
        self.index_path = self.home / "index.json"
        self.allow_plaintext = allow_plaintext
        if create:
            self._ensure_layout()

    # --- layout / key ---------------------------------------------------------

    def _ensure_layout(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        _chmod(self.home, 0o700)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        _chmod(self.records_dir, 0o700)
        if not self.index_path.exists():
            self._write_index({})
        if not (self.home / "README.txt").exists():
            (self.home / "README.txt").write_text(
                "Private memory. Sealed personal information for the operator only.\n"
                "Never copy this folder into a repository, a PR, a chat, or a cloud VM.\n"
                "Manage with: python3 scripts/private-memory.py {list,get,put,delete,protect,doctor}\n",
                encoding="utf-8",
            )
            _chmod(self.home / "README.txt", 0o600)

    def _load_key(self, create: bool = True) -> bytes:
        if self.key_file.exists():
            key = self.key_file.read_bytes().strip()
            if key:
                return key
        if not create:
            raise PrivateMemoryError(f"no key at {self.key_file}")
        key = Fernet.generate_key() if Fernet is not None else base64.urlsafe_b64encode(os.urandom(32))
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        _chmod(self.key_file.parent, 0o700)
        fd = os.open(str(self.key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key + b"\n")
        _chmod(self.key_file, 0o600)
        return key

    # --- crypto ---------------------------------------------------------------

    def _seal(self, plaintext: bytes) -> tuple[str, str]:
        backend = detect_backend(self.allow_plaintext)
        if backend == "fernet":
            token = Fernet(self._load_key()).encrypt(plaintext)
            return backend, token.decode("ascii")
        if backend == "aes-256-cbc-pbkdf2":
            self._load_key()
            out = subprocess.run(
                ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "310000", "-salt", "-pass", f"file:{self.key_file}"],
                input=plaintext,
                capture_output=True,
                check=True,
            ).stdout
            return backend, base64.b64encode(out).decode("ascii")
        return "none", base64.b64encode(plaintext).decode("ascii")

    def _open(self, cipher: str, payload: str) -> bytes:
        if cipher == "fernet":
            if Fernet is None:
                raise PrivateMemoryError("record sealed with Fernet but `cryptography` is not installed here")
            try:
                return Fernet(self._load_key(create=False)).decrypt(payload.encode("ascii"))
            except InvalidToken as exc:
                raise PrivateMemoryError("wrong key or corrupted record") from exc
        if cipher == "aes-256-cbc-pbkdf2":
            res = subprocess.run(
                ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "310000", "-pass", f"file:{self.key_file}"],
                input=base64.b64decode(payload),
                capture_output=True,
                check=False,
            )
            if res.returncode != 0:
                raise PrivateMemoryError("openssl could not open record (wrong key?)")
            return res.stdout
        if cipher == "none":
            return base64.b64decode(payload)
        raise PrivateMemoryError(f"unknown cipher {cipher!r}")

    # --- index ----------------------------------------------------------------

    def _read_index(self) -> dict:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8")).get("records") or {}
        except json.JSONDecodeError:
            return {}

    def _write_index(self, records: dict) -> None:
        doc = {"version": ENVELOPE_VERSION, "updated_at": utc(), "records": records}
        fd = os.open(str(self.index_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        _chmod(self.index_path, 0o600)

    @staticmethod
    def _check_key(key: str) -> str:
        if not KEY_RE.match(key):
            raise PrivateMemoryError(f"bad key {key!r}: use lowercase dotted names like identity.{operator_handle()}.timezone")
        return key

    def _record_path(self, key: str) -> Path:
        return self.records_dir / (key + ".sealed")

    # --- public API -----------------------------------------------------------

    def put(self, key: str, value: str | bytes | dict | list, *, kind: str | None = None, source: str = "") -> Record:
        key = self._check_key(key)
        if isinstance(value, (dict, list)):
            plaintext = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
            kind = kind or "json"
        elif isinstance(value, str):
            plaintext = value.encode("utf-8")
            kind = kind or "text"
        else:
            plaintext = bytes(value)
            kind = kind or "bytes"
        cipher, payload = self._seal(plaintext)
        now = utc()
        index = self._read_index()
        prev = index.get(key) or {}
        env = {
            "v": ENVELOPE_VERSION,
            "key": key,
            "kind": kind,
            "cipher": cipher,
            "created_at": prev.get("created_at") or now,
            "updated_at": now,
            "payload": payload,
        }
        path = self._record_path(key)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(env, sort_keys=True) + "\n")
        _chmod(path, 0o600)
        rec = Record(
            key=key,
            kind=kind,
            cipher=cipher,
            bytes=len(plaintext),
            sha256=hashlib.sha256(plaintext).hexdigest()[:16],
            created_at=env["created_at"],
            updated_at=now,
            source=source or prev.get("source", ""),
        )
        index[key] = rec.as_dict()
        self._write_index(index)
        return rec

    def get_bytes(self, key: str) -> bytes:
        key = self._check_key(key)
        path = self._record_path(key)
        if not path.exists():
            raise KeyError(key)
        env = json.loads(path.read_text(encoding="utf-8"))
        return self._open(env["cipher"], env["payload"])

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")

    def get_json(self, key: str):
        return json.loads(self.get_text(key))

    def get(self, key: str):
        meta = self._read_index().get(key) or {}
        if meta.get("kind") == "json":
            return self.get_json(key)
        if meta.get("kind") == "bytes":
            return self.get_bytes(key)
        return self.get_text(key)

    def has(self, key: str) -> bool:
        return self._record_path(self._check_key(key)).exists()

    def delete(self, key: str) -> bool:
        key = self._check_key(key)
        path = self._record_path(key)
        existed = path.exists()
        if existed:
            path.unlink()
        index = self._read_index()
        index.pop(key, None)
        self._write_index(index)
        return existed

    def list(self) -> list[Record]:
        out = []
        for key, meta in sorted(self._read_index().items()):
            out.append(Record(**{k: meta.get(k, "") for k in Record.__dataclass_fields__}))
        return out

    # --- protected personal terms -----------------------------------------------
    # The operator's own facts (full name, street, employer, plate, …) sealed as one
    # JSON list. pii-guard and every redaction path block them wherever they appear.

    def protected_terms(self) -> list[str]:
        if not self.has(PERSONAL_TERMS_KEY):
            return []
        data = self.get_json(PERSONAL_TERMS_KEY)
        return [t for t in data if isinstance(t, str)] if isinstance(data, list) else []

    def protect(self, terms: list[str]) -> int:
        """Add terms; returns the new total. Terms shorter than 3 characters are ignored."""
        current = self.protected_terms()
        lowered = {t.lower() for t in current}
        for raw in terms:
            t = " ".join(str(raw).split())
            if len(t) >= 3 and t.lower() not in lowered:
                current.append(t)
                lowered.add(t.lower())
        self.put(PERSONAL_TERMS_KEY, current, kind="json", source="private-memory protect")
        return len(current)

    def unprotect(self, terms: list[str]) -> int:
        drop = {" ".join(str(t).split()).lower() for t in terms}
        current = [t for t in self.protected_terms() if t.lower() not in drop]
        self.put(PERSONAL_TERMS_KEY, current, kind="json", source="private-memory unprotect")
        return len(current)

    # --- health ---------------------------------------------------------------

    def doctor(self) -> dict:
        problems: list[str] = []
        warnings: list[str] = []
        try:
            backend = detect_backend(self.allow_plaintext)
        except PrivateMemoryError as exc:
            backend = "unavailable"
            problems.append(str(exc))
        if backend == "none":
            warnings.append("records are stored in plaintext — install `cryptography` or openssl")

        def mode_of(p: Path) -> str:
            try:
                return oct(stat.S_IMODE(p.stat().st_mode))
            except OSError:
                return "missing"

        if self.home.exists() and os.name == "posix":
            if stat.S_IMODE(self.home.stat().st_mode) & 0o077:
                problems.append(f"{self.home} is group/world accessible — chmod 700")
        if self.key_file.exists() and os.name == "posix":
            if stat.S_IMODE(self.key_file.stat().st_mode) & 0o077:
                problems.append(f"{self.key_file} is group/world readable — chmod 600")

        inside_repo = str(self.home.resolve()).startswith(str(ROOT.resolve()))
        gitignored = None
        tracked: list[str] = []
        if inside_repo and (ROOT / ".git").exists():
            rel = os.path.relpath(self.home, ROOT)
            gitignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, capture_output=True).returncode == 0
            if not gitignored:
                problems.append(f"{rel} is NOT gitignored")
            ls = subprocess.run(["git", "ls-files", "-z", rel], cwd=ROOT, capture_output=True)
            tracked = [p for p in ls.stdout.decode("utf-8", "replace").split("\0") if p]
            if tracked:
                problems.append(f"{len(tracked)} private-memory file(s) are tracked by git")

        hooks_ok = False
        if (ROOT / ".git").exists():
            hp = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
            hooks_ok = hp == ".githooks"
            if not hooks_ok:
                warnings.append("pii-guard git hooks not installed — run scripts/install-git-hooks.sh")

        records = self.list()
        stale_plain = [r.key for r in records if r.cipher == "none"]
        if stale_plain and backend != "none":
            warnings.append(f"{len(stale_plain)} record(s) sealed in plaintext — re-put them to encrypt")
        try:
            n_terms = len(self.protected_terms()) if self.home.exists() else 0
        except PrivateMemoryError:
            n_terms = -1
            problems.append("protected terms exist but cannot be opened (wrong key?)")
        if n_terms == 0:
            warnings.append("no protected personal terms — add your own facts with `private-memory.py protect`")

        return {
            "ok": not problems,
            "operator": operator_handle(),
            "home": str(self.home),
            "protected_terms": n_terms,
            "inside_repo": inside_repo,
            "gitignored": gitignored,
            "tracked_private_files": tracked,
            "key_file": str(self.key_file),
            "key_present": self.key_file.exists(),
            "backend": backend,
            "home_mode": mode_of(self.home),
            "key_mode": mode_of(self.key_file),
            "record_count": len(records),
            "records": [r.key for r in records],
            "hooks_installed": hooks_ok,
            "problems": problems,
            "warnings": warnings,
        }
