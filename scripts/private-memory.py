#!/usr/bin/env python3
"""private-memory — manage Cam's sealed store of Aaron's personal information.

  python3 scripts/private-memory.py doctor
  python3 scripts/private-memory.py list
  python3 scripts/private-memory.py put identity.aaron.timezone --value "Region/City"
  python3 scripts/private-memory.py put identity.aaron.visual_profile --file ~/notes/profile.md
  python3 scripts/private-memory.py put contacts.landlord --json '{"name": "...", "phone": "..."}'
  python3 scripts/private-memory.py get identity.aaron.timezone
  python3 scripts/private-memory.py delete contacts.landlord
  python3 scripts/private-memory.py import-legacy [--dry-run] [--no-working-copy]

`import-legacy` recovers the pre-redaction identity content from *local* git
history (the newest revision that still fails pii-guard), seals it under the
documented keys, and writes gitignored working copies the runtime reads. Run it
BEFORE purging history (scripts/purge-git-history.sh).

Store location: CAM_PRIVATE_HOME (default identity/aaron/local/private-memory/).
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

LOCAL = ROOT / "identity" / "aaron" / "local"

# key, tracked path, kind, working copy (gitignored) the runtime reads
LEGACY_FILES = [
    ("identity.aaron.visual_profile", "identity/aaron/VISUAL_PROFILE.md", "text", LOCAL / "VISUAL_PROFILE.md"),
    ("identity.aaron.enroll_index", "identity/aaron/enroll-index.json", "json", LOCAL / "enroll-index.json"),
]
LEGACY_FIELDS = [
    ("identity.aaron.timezone", "identity/ANSWERS_SESSION_01.json", ("human", "timezone")),
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
    print(json.dumps(rec.as_dict(), indent=2))
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
    ap.add_argument("--home", help="store directory (default CAM_PRIVATE_HOME or identity/aaron/local/private-memory)")
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
    p.set_defaults(fn=cmd_put)

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
    il.add_argument("--no-working-copy", action="store_true", help="seal only; do not write identity/aaron/local/ copies")
    il.set_defaults(fn=cmd_import_legacy)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except pm.PrivateMemoryError as exc:
        print(f"private-memory: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
