#!/usr/bin/env python3
"""Import Cam persistence bundle into this workspace (future workspaces too)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="src", required=True, help="path to cam-persistence.zip")
    parser.add_argument(
        "--keep-local",
        action="store_true",
        help="do not overwrite files that already exist",
    )
    parser.add_argument(
        "--install-cline-rules",
        action="store_true",
        default=True,
        help="propagate .clinerules into registered workspaces after import (default on)",
    )
    parser.add_argument(
        "--no-install-cline-rules",
        action="store_true",
        help="skip rules propagation",
    )
    parser.add_argument(
        "--sync-schedules",
        action="store_true",
        default=True,
        help="refresh cline schedule export into cache (default on)",
    )
    parser.add_argument("--no-sync-schedules", action="store_true")
    args = parser.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"missing bundle: {src}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(tmp_path)
        for path in tmp_path.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(tmp_path)
            dest = ROOT / rel
            if args.keep_local and dest.exists():
                print(f"skip {rel}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            print(f"restored {rel}")

    if args.install_cline_rules and not args.no_install_cline_rules:
        script = ROOT / "scripts" / "install-cline-rules.py"
        if script.exists():
            subprocess.run([sys.executable, str(script), "--force"], check=False)

    if args.sync_schedules and not args.no_sync_schedules:
        script = ROOT / "scripts" / "sync-cline-schedules.py"
        if script.exists():
            subprocess.run(
                [sys.executable, str(script), "--apply-cache"],
                check=False,
            )

    print("import complete — re-attach secrets locally; verify identity/PROFILE.md")
    print("next: git submodule update --init --recursive && cline auth && python3 scripts/run-cline.py --doctor --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
