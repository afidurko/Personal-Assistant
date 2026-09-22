#!/usr/bin/env python3
"""private-memory — manage the sealed store of the operator's personal information.

  python3 scripts/private-memory.py doctor
  python3 scripts/private-memory.py list
  python3 scripts/private-memory.py put identity.<handle>.timezone --value "Region/City" --protect
  python3 scripts/private-memory.py put identity.<handle>.visual_profile --file ~/notes/profile.md
  python3 scripts/private-memory.py put contacts.landlord --json '{"name": "...", "phone": "..."}'
  python3 scripts/private-memory.py get identity.<handle>.timezone
  python3 scripts/private-memory.py delete contacts.landlord
  python3 scripts/private-memory.py protect --value "Full Legal Name" --value "12 Example Street"
  python3 scripts/private-memory.py protect --file ~/my-private-facts.txt      # one term per line
  python3 scripts/private-memory.py protected                                  # count only
  python3 scripts/private-memory.py unprotect --value "old employer"
  python3 scripts/private-memory.py import-legacy [--dry-run] [--no-working-copy]

`protect` seals *your own* personal facts (names, street, employer, plate,
school, doctor, …). pii-guard blocks them in every commit / push / PR and every
runtime redaction path strips them — the list itself never leaves private memory.

`import-legacy` recovers the pre-redaction identity content from *local* git
history (the newest revision that still fails pii-guard), seals it under the
documented keys, and writes gitignored working copies the runtime reads. Run it
BEFORE purging history (scripts/purge-git-history.sh).

Store location: PRIVATE_MEMORY_HOME / CAM_PRIVATE_HOME (default identity/<handle>/local/private-memory/).
Key file:       CAM_PRIVATE_KEY_FILE (default <store>/.key).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import privacy  # noqa: E402
import private_memory as pm  # noqa: E402

HANDLE = pm.operator_handle()
LOCAL = ROOT / "identity" / HANDLE / "local"

# key, tracked path, kind, working copy (gitignored) the runtime reads
LEGACY_FILES = [
    (f"identity.{HANDLE}.visual_profile", f"identity/{HANDLE}/VISUAL_PROFILE.md", "text", LOCAL / "VISUAL_PROFILE.md"),
    (f"identity.{HANDLE}.enroll_index", f"identity/{HANDLE}/enroll-index.json", "json", LOCAL / "enroll-index.json"),
]
LEGACY_FIELDS = [
    (f"identity.{HANDLE}.timezone", "identity/ANSWERS_SESSION_01.json", ("human", "timezone")),
]


def _store(args) -> pm.PrivateMemory:
    return pm.PrivateMemory(
        home=Path(args.home) if args.home else None,
        key_file=Path(args.key_file) if args.key_file else None,
        allow_plaintext=args.allow_plaintext,
    )


def _git_blob(sha: str, rel: str) -> bytes | None:
    res = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=ROOT, capture_output=True, check=False)
    return res.stdout if res.returncode == 0 else None


def _history(rel: str) -> list[str]:
    res = subprocess.run(["git", "rev-list", "HEAD", "--", rel], cwd=ROOT, capture_output=True, text=True, check=False)
    return [s for s in res.stdout.split() if s]


def newest_legacy_blob(rel: str, cfg: dict) -> tuple[str, bytes] | None:
    """Newest revision of `rel` whose content still carries personal information."""
    for sha in _history(rel):
        blob = _git_blob(sha, rel)
        if blob is None:
            continue
        findings = privacy.scan_text(blob.decode("utf-8", "replace"), "<legacy>", cfg)
        if privacy.blocking(findings):
            return sha, blob
    return None


def newest_legacy_field(rel: str, keys: tuple[str, ...]) -> tuple[str, str] | None:
    for sha in _history(rel):
        blob = _git_blob(sha, rel)
        if blob is None:
            continue
        try:
            node = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for k in keys:
            node = node.get(k) if isinstance(node, dict) else None
        if isinstance(node, str) and node and node != "operator_local":
            return sha, node
    return None


def cmd_import_legacy(args) -> int:
    cfg = privacy.load_config()
    store = _store(args)
    report = {"imported": [], "skipped": [], "working_copies": []}
    for key, rel, kind, working in LEGACY_FILES:
        found = newest_legacy_blob(rel, cfg)
        if not found:
            report["skipped"].append({"key": key, "reason": f"no legacy revision of {rel} in local history"})
            continue
        sha, blob = found
        if args.dry_run:
            report["imported"].append({"key": key, "from": f"{sha[:10]}:{rel}", "bytes": len(blob), "dry_run": True})
            continue
        value = json.loads(blob) if kind == "json" else blob.decode("utf-8")
        rec = store.put(key, value, kind=kind, source=f"git:{sha[:10]}:{rel}")
        report["imported"].append({"key": key, "from": f"{sha[:10]}:{rel}", "bytes": rec.bytes, "cipher": rec.cipher})
        if not args.no_working_copy:
            working.parent.mkdir(parents=True, exist_ok=True)
            pm._chmod(working.parent, 0o700)
            working.write_bytes(blob)
            pm._chmod(working, 0o600)
            report["working_copies"].append(str(working.relative_to(ROOT)))
    for key, rel, path in LEGACY_FIELDS:
        found = newest_legacy_field(rel, path)
        if not found:
            report["skipped"].append({"key": key, "reason": f"no legacy value at {rel}:{'.'.join(path)}"})
            continue
        sha, value = found
        if args.dry_run:
            report["imported"].append({"key": key, "from": f"{sha[:10]}:{rel}", "dry_run": True})
            continue
        rec = store.put(key, value, kind="text", source=f"git:{sha[:10]}:{rel}")
        report["imported"].append({"key": key, "from": f"{sha[:10]}:{rel}", "cipher": rec.cipher})
    print(json.dumps(report, indent=2))
    if not args.dry_run and report["imported"]:
        print("\nNext: verify with `private-memory.py list`, then purge history: scripts/purge-git-history.sh", file=sys.stderr)
    return 0 if report["imported"] or args.dry_run else 1


def cmd_put(args) -> int:
    store = _store(args)
    if args.value is not None:
        value = args.value
        kind = "text"
    elif args.json is not None:
        value = json.loads(args.json)
        kind = "json"
    elif args.file:
        p = Path(args.file).expanduser()
        raw = p.read_bytes()
        try:
            value = raw.decode("utf-8")
            kind = "text"
        except UnicodeDecodeError:
            value = raw
            kind = "bytes"
    else:
        value = sys.stdin.read()
        kind = "text"
    rec = store.put(args.key, value, kind=kind, source=args.source or "")
    out = rec.as_dict()
    if args.protect:
        if kind == "text" and 3 <= len(value.strip()) <= 200 and "\n" not in value.strip():
            out["protected_terms"] = store.protect([value.strip()])
        else:
            out["protect_skipped"] = "only short single-line text values can be protected terms"
    print(json.dumps(out, indent=2))
    return 0


def _terms_from_args(args) -> list[str]:
    terms = list(args.value or [])
    if args.file:
        for line in Path(args.file).expanduser().read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    if not terms:
        terms = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
    return terms


def cmd_protect(args) -> int:
    store = _store(args)
    terms = _terms_from_args(args)
    if not terms:
        print("private-memory: nothing to protect (pass --value / --file or pipe one term per line)", file=sys.stderr)
        return 1
    total = store.protect(terms)
    print(json.dumps({"protected_terms": total, "added_or_present": len(terms), "key": pm.PERSONAL_TERMS_KEY}, indent=2))
    return 0


def cmd_unprotect(args) -> int:
    store = _store(args)
    total = store.unprotect(_terms_from_args(args))
    print(json.dumps({"protected_terms": total}, indent=2))
    return 0


def cmd_protected(args) -> int:
    store = _store(args)
    terms = store.protected_terms()
    if args.reveal:
        for t in terms:
            print(t)
    else:
        print(json.dumps({"protected_terms": len(terms), "reveal": "private-memory.py protected --reveal (local terminal only)"}, indent=2))
    return 0


def cmd_get(args) -> int:
    store = _store(args)
    try:
        data = store.get_bytes(args.key)
    except KeyError:
        print(f"private-memory: no record {args.key!r}", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out).expanduser()
        out.write_bytes(data)
        pm._chmod(out, 0o600)
        print(f"wrote {out}")
        return 0
    sys.stdout.buffer.write(data if data.endswith(b"\n") else data + b"\n")
    return 0


def cmd_list(args) -> int:
    store = _store(args)
    rows = [r.as_dict() for r in store.list()]
    if args.json_out:
        print(json.dumps(rows, indent=2))
    else:
        if not rows:
            print("(empty)")
        for r in rows:
            print(f"{r['key']:<40} {r['kind']:<5} {r['cipher']:<20} {r['bytes']:>7} B  updated {r['updated_at']}")
    return 0


def cmd_delete(args) -> int:
    store = _store(args)
    print("deleted" if store.delete(args.key) else "not found")
    return 0


def cmd_doctor(args) -> int:
    store = pm.PrivateMemory(
        home=Path(args.home) if args.home else None,
        key_file=Path(args.key_file) if args.key_file else None,
        allow_plaintext=args.allow_plaintext,
        create=False,
    )
    rep = store.doctor()
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--home", help=f"store directory (default PRIVATE_MEMORY_HOME / CAM_PRIVATE_HOME or identity/{HANDLE}/local/private-memory)")
    ap.add_argument("--key-file", help="key file (default CAM_PRIVATE_KEY_FILE or <store>/.key)")
    ap.add_argument("--allow-plaintext", action="store_true", help="permit unencrypted records when no backend exists")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("put", help="seal a value under a key")
    p.add_argument("key")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--value")
    src.add_argument("--json")
    src.add_argument("--file")
    p.add_argument("--source", help="provenance note (no values)")
    p.add_argument("--protect", action="store_true", help="also add the value to the protected personal terms")
    p.set_defaults(fn=cmd_put)

    pr = sub.add_parser("protect", help="seal your own personal facts so pii-guard blocks them everywhere")
    pr.add_argument("--value", action="append", help="a term (repeatable)")
    pr.add_argument("--file", help="text file, one term per line (# comments allowed)")
    pr.set_defaults(fn=cmd_protect)

    up = sub.add_parser("unprotect", help="remove protected terms")
    up.add_argument("--value", action="append")
    up.add_argument("--file")
    up.set_defaults(fn=cmd_unprotect)

    pd = sub.add_parser("protected", help="how many terms are protected (values only with --reveal)")
    pd.add_argument("--reveal", action="store_true")
    pd.set_defaults(fn=cmd_protected)

    g = sub.add_parser("get", help="print (or --out write) a sealed value")
    g.add_argument("key")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_get)

    l = sub.add_parser("list", help="list keys and metadata — never values")
    l.add_argument("--json", dest="json_out", action="store_true")
    l.set_defaults(fn=cmd_list)

    d = sub.add_parser("delete", help="remove a record")
    d.add_argument("key")
    d.set_defaults(fn=cmd_delete)

    doc = sub.add_parser("doctor", help="store health: cipher, permissions, gitignore, hooks")
    doc.set_defaults(fn=cmd_doctor)

    il = sub.add_parser("import-legacy", help="recover pre-redaction identity content from local git history")
    il.add_argument("--dry-run", action="store_true")
    il.add_argument("--no-working-copy", action="store_true", help=f"seal only; do not write identity/{HANDLE}/local/ copies")
    il.set_defaults(fn=cmd_import_legacy)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except pm.PrivateMemoryError as exc:
        print(f"private-memory: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
