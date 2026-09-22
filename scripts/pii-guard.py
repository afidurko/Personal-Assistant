#!/usr/bin/env python3
"""pii-guard — refuse to let personal information reach git, a PR, or CI logs.

Modes (pick one; default is --all):
  --staged          scan the index (pre-commit hook) — reads blob content from the index
  --diff BASE       scan files changed since BASE (pre-push / PR) — e.g. origin/main
  --all             scan every tracked file (CI, ci-static-gate)
  --paths P [P...]  scan specific files or directories
  --text -          scan stdin (e.g. a PR body or a distillate before writing it)

Exit 0 = clean (warnings allowed), 1 = blocking finding, 2 = tool error.
Snippets are redacted before printing — the guard never re-leaks what it finds.
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


def _git(*args: str, cwd: Path = ROOT) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=False, check=False)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode("utf-8", errors="replace").strip() or f"git {' '.join(args)} failed")
    return res.stdout.decode("utf-8", errors="replace")


def _git_z(*args: str) -> list[str]:
    out = _git(*args)
    return [p for p in out.split("\0") if p]


def staged_findings(cfg: dict) -> list[privacy.Finding]:
    rules = privacy.compile_rules(cfg)
    findings: list[privacy.Finding] = []
    for rel in _git_z("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"):
        reason = privacy.path_violation(rel, cfg)
        if reason:
            findings.append(privacy.Finding(rel, 0, "private_path", "block", reason, ""))
        if privacy.is_skipped(rel, cfg):
            continue
        try:
            blob = subprocess.run(["git", "show", f":{rel}"], cwd=ROOT, capture_output=True, check=True).stdout
        except subprocess.CalledProcessError:
            continue  # submodule gitlink or vanished path
        findings.extend(privacy.scan_bytes(blob, rel, cfg, rules))
    return findings


def diff_findings(base: str, cfg: dict) -> list[privacy.Finding]:
    try:
        names = _git_z("diff", "--name-only", "--diff-filter=ACMR", "-z", f"{base}...HEAD")
    except RuntimeError:
        names = _git_z("diff", "--name-only", "--diff-filter=ACMR", "-z", base)
    return privacy.scan_paths(names, ROOT, cfg)


def all_findings(cfg: dict) -> list[privacy.Finding]:
    names = _git_z("ls-files", "-z")
    return privacy.scan_paths(names, ROOT, cfg)


def path_findings(paths: list[str], cfg: dict) -> list[privacy.Finding]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_dir():
            files.extend(x for x in p.rglob("*") if x.is_file() and ".git/" not in str(x).replace("\\", "/") + "/")
        else:
            files.append(p)
    return privacy.scan_paths(files, ROOT, cfg)


def text_findings(text: str, label: str, cfg: dict) -> list[privacy.Finding]:
    return privacy.scan_text(text, label, cfg)


def render(findings: list[privacy.Finding], *, mode: str, as_json: bool, quiet: bool, snippets: bool) -> None:
    summ = privacy.summary(findings)
    if not snippets:
        # Even a redacted line can carry context (clothing, places). Default to location-only.
        for f in findings:
            f.snippet = ""
    if as_json:
        print(json.dumps({"mode": mode, "ok": summ["blocking"] == 0, "summary": summ, "findings": [f.as_dict() for f in findings]}, indent=2))
        return
    status = "PASS" if summ["blocking"] == 0 else "FAIL"
    print(f"pii-guard [{mode}]: {status} — {summ['blocking']} blocking, {summ['warnings']} warning(s)")
    if quiet:
        return
    for f in findings:
        mark = "BLOCK" if f.severity == "block" else "warn "
        loc = f"{f.path}:{f.line}" if f.line else f.path
        print(f"  {mark} {f.rule:<22} {loc}")
        print(f"        {f.label}")
        if f.snippet:
            print(f"        › {f.snippet}")
    if summ["blocking"]:
        print(
            "\n  Personal information or secrets must not enter git. Move the data to private memory\n"
            "  (python3 scripts/private-memory.py put <key> ...), reference it by key, and retry.\n"
            "  Policy: docs/PRIVACY_SAFEGUARDS.md — never bypass with --no-verify for real data."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--diff", metavar="BASE")
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--paths", nargs="+", metavar="P")
    mode.add_argument("--text", metavar="FILE|-", help="scan a text file or stdin (-)")
    ap.add_argument("--config", type=Path, help="alternate pii-guard.json")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--warn-only", action="store_true", help="report but exit 0 (never use in hooks/CI)")
    ap.add_argument("--show-snippets", action="store_true", help="print redacted line context (local use only — keep out of CI logs)")
    args = ap.parse_args()

    try:
        cfg = privacy.load_config(args.config) if args.config else privacy.load_config()
        if args.staged:
            label, findings = "staged", staged_findings(cfg)
        elif args.diff:
            label, findings = f"diff {args.diff}", diff_findings(args.diff, cfg)
        elif args.paths:
            label, findings = "paths", path_findings(args.paths, cfg)
        elif args.text:
            text = sys.stdin.read() if args.text == "-" else Path(args.text).read_text(encoding="utf-8", errors="replace")
            label, findings = "text", text_findings(text, "<text>", cfg)
        else:
            label, findings = "all", all_findings(cfg)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"pii-guard: error — {exc}", file=sys.stderr)
        return 2

    render(findings, mode=label, as_json=args.json, quiet=args.quiet, snippets=args.show_snippets)
    if args.warn_only:
        return 0
    return 1 if privacy.blocking(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
