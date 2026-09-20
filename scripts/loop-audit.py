#!/usr/bin/env python3
"""Run loop-audit against Personal-Assistant (local submodule CLI preferred)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CLI = ROOT / "integrations/loop-engineering/tools/loop-audit/dist/cli.js"


def build_cmd(extra: list[str]) -> list[str]:
    if LOCAL_CLI.exists():
        return ["node", str(LOCAL_CLI), str(ROOT), *extra]
    if shutil.which("npx"):
        return ["npx", "--yes", "@cobusgreyling/loop-audit", str(ROOT), *extra]
    raise SystemExit("loop-audit CLI not found (submodule dist or npx)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suggest", action="store_true")
    p.add_argument("--badge", action="store_true")
    p.add_argument("--json", action="store_true", help="best-effort JSON envelope around CLI output")
    p.add_argument("extra", nargs="*", help="forwarded to loop-audit")
    args = p.parse_args()

    extra: list[str] = list(args.extra)
    if args.suggest:
        extra.append("--suggest")
    if args.badge:
        extra.append("--badge")

    cmd = build_cmd(extra)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    if args.json:
        print(
            json.dumps(
                {
                    "ok": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "cmd": cmd,
                    "output": out.strip(),
                },
                indent=2,
            )
        )
    else:
        sys.stdout.write(proc.stdout or "")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
