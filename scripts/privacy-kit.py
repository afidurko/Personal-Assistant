#!/usr/bin/env python3
"""privacy-kit — carry the personal-information safeguards into any repository.

  python3 scripts/privacy-kit.py manifest                 # what ships
  python3 scripts/privacy-kit.py export ~/src/my-repo     # copy the stack there
  python3 scripts/privacy-kit.py export ~/src/my-repo --operator sam --name Sam
  python3 scripts/privacy-kit.py diff   ~/src/my-repo     # which kit files drifted

Then, inside the target repository:

  python3 scripts/privacy-init.py --operator sam --name Sam --protect "<full name>" ...

The kit is self-contained (Python 3.10+, git; `cryptography` or openssl for
encryption). It never copies private memory, identity trees, or anything under
a private path — only the guard, the store code, the hooks, the CI workflow,
the PR template, the tests, and the docs.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every file that makes the stack work somewhere else. Paths are repo-relative and
# identical in source and target so the scripts' relative lookups keep working.
MANIFEST = [
    "config/privacy/pii-guard.json",
    "scripts/privacy.py",
    "scripts/pii-guard.py",
    "scripts/private_memory.py",
    "scripts/private-memory.py",
    "scripts/privacy-init.py",
    "scripts/privacy-kit.py",
    "scripts/install-git-hooks.sh",
    "scripts/test_privacy.py",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    ".github/workflows/privacy-guard.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/PRIVACY_QUICKSTART.md",
    "docs/PRIVACY_SAFEGUARDS.md",
]
EXECUTABLE = {".githooks/pre-commit", ".githooks/pre-push", "scripts/install-git-hooks.sh", "scripts/pii-guard.py", "scripts/private-memory.py", "scripts/privacy-init.py", "scripts/privacy-kit.py"}


def _target(path: str) -> Path:
    t = Path(path).expanduser().resolve()
    if not t.is_dir():
        raise SystemExit(f"privacy-kit: {t} is not a directory")
    return t


def cmd_manifest(_args) -> int:
    for rel in MANIFEST:
        mark = "ok " if (ROOT / rel).exists() else "MISSING"
        print(f"{mark} {rel}")
    return 0


def _set_operator(cfg_path: Path, handle: str | None, name: str | None) -> None:
    if not (handle or name):
        return
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    op = dict(raw.get("operator") or {})
    if handle:
        op["handle"] = handle
    if name:
        op["display_name"] = name
    raw["operator"] = op
    cfg_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_export(args) -> int:
    target = _target(args.target)
    if target == ROOT.resolve():
        raise SystemExit("privacy-kit: target is this repository; nothing to export")
    copied, skipped, same = [], [], []
    for rel in MANIFEST:
        src = ROOT / rel
        if not src.exists():
            skipped.append((rel, "missing in source"))
            continue
        dst = target / rel
        if dst.exists():
            if filecmp.cmp(src, dst, shallow=False):
                same.append(rel)
                continue
            if not args.force:
                skipped.append((rel, "exists — use --force to overwrite"))
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if rel in EXECUTABLE:
            dst.chmod(dst.stat().st_mode | 0o111)
        copied.append(rel)
    _set_operator(target / "config/privacy/pii-guard.json", args.operator, args.name)

    print(f"privacy-kit: exported to {target}")
    for rel in copied:
        print(f"  + {rel}")
    for rel in same:
        print(f"  = {rel} (identical)")
    for rel, why in skipped:
        print(f"  ! {rel}: {why}")
    handle = args.operator or "<handle>"
    print(
        "\nnext, inside the target repository:\n"
        f"  python3 scripts/privacy-init.py --operator {handle} --name \"<Display Name>\" --protect \"<your full name>\"\n"
        "  git add config/privacy scripts/privacy.py scripts/pii-guard.py scripts/private_memory.py scripts/private-memory.py \\\n"
        "          scripts/privacy-init.py scripts/privacy-kit.py scripts/install-git-hooks.sh scripts/test_privacy.py \\\n"
        "          .githooks .github docs/PRIVACY_QUICKSTART.md docs/PRIVACY_SAFEGUARDS.md .gitignore\n"
        "  git commit -m \"Add personal-information safeguards\"\n"
        "  (see docs/PRIVACY_QUICKSTART.md)"
    )
    return 1 if any(why.startswith("exists") for _, why in skipped) else 0


def cmd_diff(args) -> int:
    target = _target(args.target)
    drift = 0
    for rel in MANIFEST:
        src, dst = ROOT / rel, target / rel
        if not dst.exists():
            print(f"  missing  {rel}")
            drift += 1
        elif not src.exists():
            print(f"  extra    {rel} (not in this kit)")
        elif rel.endswith("pii-guard.json"):
            a = json.loads(src.read_text(encoding="utf-8")); b = json.loads(dst.read_text(encoding="utf-8"))
            a.pop("operator", None); b.pop("operator", None); a.pop("authorized_at", None); b.pop("authorized_at", None)
            if a != b:
                print(f"  changed  {rel} (policy differs beyond the operator block)")
                drift += 1
        elif not filecmp.cmp(src, dst, shallow=False):
            print(f"  changed  {rel}")
            drift += 1
    print("privacy-kit: in sync" if not drift else f"privacy-kit: {drift} file(s) differ — re-export with --force to update")
    return 1 if drift else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("manifest", help="list the files that ship").set_defaults(fn=cmd_manifest)
    ex = sub.add_parser("export", help="copy the stack into another repository")
    ex.add_argument("target")
    ex.add_argument("--operator", help="set operator.handle in the exported policy")
    ex.add_argument("--name", help="set operator.display_name in the exported policy")
    ex.add_argument("--force", action="store_true", help="overwrite files that already exist in the target")
    ex.set_defaults(fn=cmd_export)
    df = sub.add_parser("diff", help="report kit files that differ from this source")
    df.add_argument("target")
    df.set_defaults(fn=cmd_diff)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
