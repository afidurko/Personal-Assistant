#!/usr/bin/env python3
"""Load hyphenated Cam scripts in-process — no python3 spawn tax."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
_CACHE: dict[str, Any] = {}


def load_script(filename: str):
    name = filename.replace("-", "_").removesuffix(".py")
    if name in _CACHE:
        return _CACHE[name]
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _CACHE[name] = mod
    return mod


def run_main(filename: str, argv: list[str] | None = None) -> int:
    """Call a script's main() with a temporary sys.argv. Returns exit code."""
    mod = load_script(filename)
    old = sys.argv
    sys.argv = [str(SCRIPTS / filename), *(argv or [])]
    try:
        code = mod.main()
        return int(code or 0)
    finally:
        sys.argv = old


def run_main_captured(filename: str, argv: list[str] | None = None) -> tuple[int, str]:
    """Like run_main, but swallow stdout/stderr so JSON hosts stay clean."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run_main(filename, argv)
    return code, ((out.getvalue() or "") + (err.getvalue() or "")).strip()


def route(**kwargs) -> dict:
    """Full connectome-route plan (trajectory + workspace). In-process."""
    return load_script("connectome-route.py").route(**kwargs)
