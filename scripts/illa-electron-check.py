#!/usr/bin/env python3
"""Confirm ILLA + electron-builder@26.16.1 wiring for Cam.

No network required. Verifies config, desktop pin, registry, and mesh seed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "26.16.1"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    for rel in (
        "config/integrations/electron-builder.json",
        "config/integrations/electron-builder.md",
        "config/integrations/illa-builder.json",
        "config/integrations/illa-builder.md",
        "integrations/illa-desktop/package.json",
        "integrations/illa-desktop/src/main.js",
        "integrations/illa-desktop/src/preload.js",
        "integrations/illa-desktop/src/url-contract.js",
        "integrations/illa-desktop/scripts/assert-builder-pin.mjs",
        "integrations/illa-desktop/scripts/contract-selftest.js",
        "integrations/illa-desktop/build/icon.png",
        "scripts/promote-illa-desktop.py",
        "scripts/illa-desktop-billion-fuzz.py",
        "scripts/test_illa_desktop.py",
        "patches/illa-builder-desktop/README.md",
        "vault/03-Projects/ILLA-Electron-Desktop.md",
    ):
        if not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")

    # packaging author contract (required for .deb)
    pkg_path = ROOT / "integrations/illa-desktop/package.json"
    if pkg_path.exists():
        pkg = load(pkg_path)
        author = pkg.get("author") or {}
        email = author.get("email") if isinstance(author, dict) else ""
        if "@" not in str(email):
            errors.append("illa-desktop package.json missing author.email")
        maint = ((pkg.get("build") or {}).get("linux") or {}).get("maintainer")
        if "@" not in str(maint or ""):
            errors.append("illa-desktop package.json missing build.linux.maintainer")

    # node contract selftest
    selftest = ROOT / "integrations/illa-desktop/scripts/contract-selftest.js"
    if selftest.exists():
        import subprocess

        proc = subprocess.run(
            ["node", str(selftest)],
            cwd=str(ROOT / "integrations/illa-desktop"),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"contract-selftest:{proc.stderr or proc.stdout}")

    eb = load(ROOT / "config/integrations/electron-builder.json") if (ROOT / "config/integrations/electron-builder.json").exists() else {}
    pin = ((eb.get("pin") or {}).get("version")) or ""
    if pin != PIN:
        errors.append(f"electron-builder.json pin={pin!r} expected {PIN}")

    illa = load(ROOT / "config/integrations/illa-builder.json") if (ROOT / "config/integrations/illa-builder.json").exists() else {}
    pack_ver = ((illa.get("packager") or {}).get("version")) or ""
    if pack_ver != PIN:
        errors.append(f"illa-builder.json packager.version={pack_ver!r} expected {PIN}")

    pkg_path = ROOT / "integrations/illa-desktop/package.json"
    if pkg_path.exists():
        pkg = load(pkg_path)
        dep = (pkg.get("devDependencies") or {}).get("electron-builder")
        if dep != PIN:
            errors.append(f"illa-desktop package.json electron-builder={dep!r} expected {PIN}")

    reg = load(ROOT / "config/workspaces/registry.json")
    layers = reg.get("layers") or {}
    integ_ids = [i.get("id") for i in layers.get("integrations") or []]
    for need in ("electron-builder", "illa-builder", "illa-desktop"):
        if need not in integ_ids:
            errors.append(f"registry layers.integrations missing {need}")

    coding_ids = [w.get("id") for w in layers.get("coding_workspaces") or []]
    for need in ("electron-builder", "illa-builder", "illa-desktop"):
        if need not in coding_ids:
            errors.append(f"registry layers.coding_workspaces missing {need}")

    flat_ids = [w.get("id") for w in reg.get("workspaces") or []]
    for need in ("electron-builder", "illa-builder", "illa-desktop"):
        if need not in flat_ids:
            errors.append(f"registry flat workspaces missing {need}")

    seed = load(ROOT / "identity/persistence/mesh-seed.json")
    tools = seed.get("mesh/tools") or {}
    prefs = seed.get("mesh/prefs") or {}
    projects = seed.get("mesh/projects") or {}
    if not (tools.get("electron_builder") or prefs.get("electron_builder") or projects.get("illa_desktop")):
        errors.append("mesh-seed missing electron_builder / illa_desktop flags")

    workflow = reg.get("workflow") or {}
    if workflow.get("illa_electron_check") != "scripts/illa-electron-check.py":
        soft.append("workflow.illa_electron_check not registered")

    illa = load(ROOT / "config/integrations/illa-builder.json") if (ROOT / "config/integrations/illa-builder.json").exists() else {}
    promote = illa.get("desktop_promote") or {}
    if promote.get("status") == "ready_blocked_on_push":
        soft.append("promotion ready; needs ILLA_BUILDER_GITHUB_TOKEN or fork write to --push")

    default_url = ((illa.get("defaults") or {}).get("illa_url_default")) or ""
    if default_url and "3000" not in default_url:
        soft.append(f"unexpected default URL {default_url!r} (expected :3000 for Vite dev)")

    report = {
        "ok": not errors,
        "errors": errors,
        "soft_warnings": soft,
        "pin": PIN,
        "release": "https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1",
        "illa_fork": "https://github.com/afidurko/illa-builder/tree/beta",
        "electron_builder_fork": "https://github.com/afidurko/electron-builder",
        "desktop_shell": "integrations/illa-desktop",
        "promote": promote,
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
