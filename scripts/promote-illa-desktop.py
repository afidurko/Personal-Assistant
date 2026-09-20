#!/usr/bin/env python3
"""Promote integrations/illa-desktop → afidurko/illa-builder:electron/.

Requires write access to afidurko/illa-builder (set ILLA_BUILDER_GITHUB_TOKEN
or use a gh credential that can push). Default: dry-run / local clone only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "integrations" / "illa-desktop"
PIN = "26.16.1"
REMOTE_REPO = "afidurko/illa-builder"
BASE_BRANCH = "beta"
FEATURE_BRANCH = "cursor/desktop-electron-26-16-1"
DEST_DIRNAME = "electron"

SKIP_NAMES = {
    "node_modules",
    "release",
    "dist",
    ".git",
    "package-lock.json",  # regenerate inside electron/ after copy
}


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def token() -> str | None:
    return (
        os.environ.get("ILLA_BUILDER_GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )


def remote_url(tok: str | None) -> str:
    if tok:
        return f"https://x-access-token:{tok}@github.com/{REMOTE_REPO}.git"
    return f"https://github.com/{REMOTE_REPO}.git"


def assert_pin() -> None:
    pkg = json.loads((SRC / "package.json").read_text(encoding="utf-8"))
    ver = (pkg.get("devDependencies") or {}).get("electron-builder")
    if ver != PIN:
        raise SystemExit(f"pin mismatch: electron-builder={ver!r} expected {PIN}")


def copy_tree(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for path in SRC.rglob("*"):
        rel = path.relative_to(SRC)
        if any(part in SKIP_NAMES for part in rel.parts):
            continue
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def patch_root_package(repo: Path) -> None:
    pkg_path = repo / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    scripts = pkg.setdefault("scripts", {})
    scripts["desktop"] = "npm --prefix electron run dev"
    scripts["desktop:dist"] = "npm --prefix electron run dist"
    scripts["desktop:dist:dir"] = "npm --prefix electron run dist:dir"
    scripts["desktop:check:pin"] = "npm --prefix electron run check:pin"
    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")


def write_promote_note(repo: Path) -> None:
    note = repo / "electron" / "PROMOTE.md"
    note.write_text(
        f"""# Promoted from Personal-Assistant

Source: `integrations/illa-desktop`  
Packager pin: electron-builder@{PIN}  
Base branch: `{BASE_BRANCH}`  
Feature branch: `{FEATURE_BRANCH}`

Do not bump to electron-builder v27 / fork master without an explicit migrate.
""",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="build tree under /tmp only")
    ap.add_argument("--push", action="store_true", help="push branch and print PR URL hint")
    ap.add_argument("--workdir", default="", help="existing illa-builder checkout")
    args = ap.parse_args()

    if not SRC.is_dir():
        raise SystemExit(f"missing source {SRC}")
    assert_pin()

    tok = token()
    work = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="illa-promote-"))
    created = not args.workdir

    if not args.workdir:
        run(["git", "clone", "--depth", "1", "--branch", BASE_BRANCH, remote_url(tok), str(work)])

    dest = work / DEST_DIRNAME
    copy_tree(dest)
    write_promote_note(work)
    patch_root_package(work)

    # ensure .gitignore inside electron
    gi = dest / ".gitignore"
    if not gi.exists():
        gi.write_text("node_modules/\nrelease/\ndist/\n*.log\n.DS_Store\n", encoding="utf-8")

    report = {
        "ok": True,
        "source": str(SRC),
        "dest": str(dest),
        "pin": PIN,
        "base": BASE_BRANCH,
        "branch": FEATURE_BRANCH,
        "push": bool(args.push),
        "has_token": bool(tok),
        "workdir": str(work),
    }

    if args.dry_run and not args.push:
        print(json.dumps(report, indent=2))
        print(f"dry-run tree ready at {dest}", file=sys.stderr)
        return 0

    run(["git", "checkout", "-B", FEATURE_BRANCH], cwd=work)
    run(["git", "add", DEST_DIRNAME, "package.json"], cwd=work)
    # commit if there is a diff
    st = subprocess.run(["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True)
    if not st.stdout.strip():
        print(json.dumps({**report, "committed": False, "note": "no changes"}, indent=2))
        return 0

    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "Cam")
    env.setdefault("GIT_AUTHOR_EMAIL", "cam@local")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    run(
        [
            "git",
            "commit",
            "-m",
            f"Add Electron desktop shell pinned to electron-builder@{PIN}",
        ],
        cwd=work,
        env=env,
    )

    if args.push:
        if not tok and "x-access-token" not in remote_url(tok):
            # still try — may have credential helper
            pass
        try:
            run(["git", "remote", "set-url", "origin", remote_url(tok)], cwd=work)
            run(["git", "push", "-u", "origin", FEATURE_BRANCH], cwd=work)
            report["pushed"] = True
            report["pr_hint"] = (
                f"https://github.com/{REMOTE_REPO}/compare/{BASE_BRANCH}...{FEATURE_BRANCH}?expand=1"
            )
        except subprocess.CalledProcessError as exc:
            report["ok"] = False
            report["pushed"] = False
            report["error"] = str(exc)
            report["blocker"] = (
                "No push access. Set ILLA_BUILDER_GITHUB_TOKEN with Contents+PR write "
                f"on {REMOTE_REPO}, then re-run with --push."
            )
            print(json.dumps(report, indent=2))
            return 1

    print(json.dumps(report, indent=2))
    if created and not args.push:
        print(f"local promote checkout: {work}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
