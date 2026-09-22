#!/usr/bin/env python3
"""privacy-init — set up the personal-information safeguards for *you*.

One idempotent command for any operator, in this repository or in one that
received the stack via `scripts/privacy-kit.py export`:

  python3 scripts/privacy-init.py --operator sam --name "Sam" \\
      --protect "Samantha Q. Example" --protect "12 Example Street" \\
      --protect-file ~/private-facts.txt

What it does (and re-does safely):
  1. records your handle / display name in config/privacy/pii-guard.json — the only
     two facts about you that ever live in a tracked file
  2. makes sure .gitignore excludes identity/<handle>/local/ and **/private-memory/
  3. installs the pii-guard git hooks (pre-commit, pre-push)
  4. creates the sealed private-memory store and seals your protected terms
  5. runs pii-guard over the tracked tree and the private-memory doctor

Nothing you pass with --protect is printed or written anywhere except the sealed
store. Exit 0 when the tree is clean and the store is healthy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import private_memory as pm  # noqa: E402

CONFIG = ROOT / "config" / "privacy" / "pii-guard.json"
HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
GITIGNORE_LINES = [
    "# personal information — private memory and per-operator local trees (privacy-init)",
    "identity/*/local/",
    "**/private-memory/",
]


def _run(*cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=check)


def set_operator(handle: str | None, name: str | None) -> dict:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    op = dict(raw.get("operator") or {})
    changed = False
    if handle:
        if not HANDLE_RE.match(handle):
            raise SystemExit(f"privacy-init: handle {handle!r} must match {HANDLE_RE.pattern}")
        changed |= op.get("handle") != handle
        op["handle"] = handle
    if name:
        changed |= op.get("display_name") != name
        op["display_name"] = name
    op.setdefault("handle", "operator")
    op.setdefault("display_name", op["handle"].capitalize())
    if changed or raw.get("operator") != op:
        # keep the operator block near the top, right after "status"
        rebuilt = {}
        for k, v in raw.items():
            if k == "operator":
                continue
            rebuilt[k] = v
            if k == "status":
                rebuilt["operator"] = op
        if "operator" not in rebuilt:
            rebuilt["operator"] = op
        CONFIG.write_text(json.dumps(rebuilt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"handle": op["handle"], "display_name": op["display_name"], "changed": changed}


def ensure_gitignore() -> list[str]:
    gi = ROOT / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    have = {l.strip() for l in existing}
    missing = [l for l in GITIGNORE_LINES[1:] if l not in have]
    if missing:
        block = ["", GITIGNORE_LINES[0], *missing]
        gi.write_text("\n".join(existing + block) + "\n", encoding="utf-8")
    return missing


def install_hooks() -> dict:
    hooks_dir = ROOT / ".githooks"
    if not hooks_dir.is_dir():
        return {"installed": False, "reason": ".githooks/ missing — export the kit first"}
    installer = ROOT / "scripts" / "install-git-hooks.sh"
    if installer.exists():
        res = _run("bash", str(installer))
        ok = res.returncode == 0
    else:
        for h in hooks_dir.iterdir():
            h.chmod(h.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        ok = _run("git", "config", "core.hooksPath", ".githooks").returncode == 0
    path = _run("git", "config", "--get", "core.hooksPath").stdout.strip()
    return {"installed": ok and path == ".githooks", "hooks_path": path}


def seal_terms(store: pm.PrivateMemory, terms: list[str], files: list[str]) -> int:
    collected = list(terms)
    for f in files:
        for line in Path(f).expanduser().read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                collected.append(line)
    if collected:
        store.protect(collected)
    return len(store.protected_terms())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--operator", help="short lowercase handle, e.g. sam (used in identity/<handle>/…)")
    ap.add_argument("--name", help="display name used in labels, e.g. Sam")
    ap.add_argument("--protect", action="append", default=[], metavar="TERM", help="a personal fact to block everywhere (repeatable)")
    ap.add_argument("--protect-file", action="append", default=[], metavar="PATH", help="file with one term per line")
    ap.add_argument("--home", help="private-memory directory (default identity/<handle>/local/private-memory)")
    ap.add_argument("--allow-plaintext", action="store_true", help="permit an unencrypted store when neither `cryptography` nor openssl exists")
    ap.add_argument("--no-hooks", action="store_true")
    ap.add_argument("--no-scan", action="store_true", help="skip the pii-guard tree scan")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not CONFIG.exists():
        print("privacy-init: config/privacy/pii-guard.json missing — run `python3 scripts/privacy-kit.py export .` first", file=sys.stderr)
        return 2

    report: dict = {"operator": set_operator(args.operator, args.name)}
    report["gitignore_added"] = ensure_gitignore()

    handle = report["operator"]["handle"]
    local = ROOT / "identity" / handle / "local"
    local.mkdir(parents=True, exist_ok=True)
    pm._chmod(local, 0o700)
    report["private_tree"] = os.path.relpath(local, ROOT)

    report["hooks"] = {"installed": False, "skipped": True} if args.no_hooks else install_hooks()

    if args.home:
        os.environ["PRIVATE_MEMORY_HOME"] = str(Path(args.home).expanduser())
    store = pm.PrivateMemory(home=Path(args.home).expanduser() if args.home else None, allow_plaintext=args.allow_plaintext)
    report["protected_terms"] = seal_terms(store, args.protect, args.protect_file)
    doc = store.doctor()
    report["private_memory"] = {k: doc[k] for k in ("home", "backend", "gitignored", "ok", "problems", "warnings")}

    if not args.no_scan:
        env = dict(os.environ)
        res = subprocess.run([sys.executable, str(ROOT / "scripts" / "pii-guard.py"), "--all", "--json", "--quiet"], cwd=ROOT, capture_output=True, text=True, env=env)
        try:
            scan = json.loads(res.stdout)
            report["tree_scan"] = {"ok": scan["ok"], "blocking": scan["summary"]["blocking"], "warnings": scan["summary"]["warnings"], "by_rule": scan["summary"]["by_rule"]}
        except (json.JSONDecodeError, KeyError):
            report["tree_scan"] = {"ok": False, "error": (res.stderr or res.stdout).strip()[:300]}

    ok = report["private_memory"]["ok"] and report.get("tree_scan", {}).get("ok", True) and (args.no_hooks or report["hooks"].get("installed"))
    report["ok"] = bool(ok)
    report["next"] = [
        f"python3 scripts/private-memory.py protect --value \"<your full name>\"   # add more facts any time",
        f"python3 scripts/private-memory.py put identity.{handle}.timezone --value Region/City --protect",
        "python3 scripts/pii-guard.py --all      # what the hooks and CI enforce",
        "docs/PRIVACY_QUICKSTART.md              # the full walkthrough",
    ]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"privacy-init: operator={handle} ({report['operator']['display_name']})")
        print(f"  private tree     {report['private_tree']}/  (gitignored)")
        print(f"  private memory   {doc['home']}  backend={doc['backend']}  ok={doc['ok']}")
        print(f"  protected terms  {report['protected_terms']}")
        print(f"  git hooks        {'installed' if report['hooks'].get('installed') else 'NOT installed'}")
        if "tree_scan" in report:
            ts = report["tree_scan"]
            print(f"  tracked tree     {'clean' if ts.get('ok') else 'BLOCKING findings'} ({ts.get('blocking', '?')} blocking, {ts.get('warnings', '?')} warnings)")
        for w in doc["warnings"]:
            print(f"  warning: {w}")
        for p in doc["problems"]:
            print(f"  PROBLEM: {p}")
        print("  next:")
        for n in report["next"]:
            print(f"    {n}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
