#!/usr/bin/env python3
"""Prove Cam's coding effector path can still build when plan usage is tight.

Checks motor.cline wiring, runs a tiny local build (write → exec → assert),
and dry-runs run-cline. No network and no live cline binary required.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_wiring(errors: list[str]) -> dict:
    required = {
        "scripts/run-cline.py": ROOT / "scripts/run-cline.py",
        "scripts/choose-workspace.py": ROOT / "scripts/choose-workspace.py",
        "scripts/cam_workspaces.py": ROOT / "scripts/cam_workspaces.py",
        "config/integrations/cline.md": ROOT / "config/integrations/cline.md",
        ".clinerules": ROOT / ".clinerules",
    }
    for label, path in required.items():
        if not path.is_file():
            errors.append(f"missing {label}")

    motor = load(ROOT / "config/connectome/motor.json")
    motor_ids = {m.get("id") for m in motor.get("effectors") or []}
    if "motor.cline" not in motor_ids:
        errors.append("motor.cline missing from connectome/motor.json")

    reg = load(ROOT / "config/workspaces/registry.json")
    flat_ids = {w.get("id") for w in reg.get("workspaces") or []}
    if "cline" not in flat_ids:
        errors.append("registry flat workspaces missing cline")
    layers = reg.get("layers") or {}
    integ_ids = {i.get("id") for i in layers.get("integrations") or []}
    if "cline" not in integ_ids:
        errors.append("registry integrations missing cline")

    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = {t.get("id") for t in tools.get("tools") or []}
    if "tool.coding.effector_smoke" not in tool_ids:
        errors.append("tools registry missing tool.coding.effector_smoke")

    return {
        "motor_cline": "motor.cline" in motor_ids,
        "registry_cline": "cline" in flat_ids,
        "tool_registered": "tool.coding.effector_smoke" in tool_ids,
    }


def local_build(errors: list[str]) -> dict:
    """Write a tiny module, execute it, and assert the built artifact."""
    with tempfile.TemporaryDirectory(prefix="cam-coding-smoke-") as tmp:
        work = Path(tmp)
        src = work / "probe.py"
        out = work / "artifact.json"
        src.write_text(
            "import json\n"
            "from pathlib import Path\n"
            "payload = {'built': True, 'sum': sum(range(1, 11)), 'effector': 'motor.cline'}\n"
            f"Path({str(out)!r}).write_text(json.dumps(payload) + '\\n', encoding='utf-8')\n"
            "print(json.dumps(payload))\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(src)],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            errors.append(f"local build failed: {proc.stderr.strip() or proc.stdout.strip()}")
            return {"ok": False, "exit": proc.returncode}

        if not out.is_file():
            errors.append("local build did not write artifact.json")
            return {"ok": False}

        artifact = json.loads(out.read_text(encoding="utf-8"))
        if artifact.get("sum") != 55 or artifact.get("built") is not True:
            errors.append(f"local build artifact mismatch: {artifact}")
            return {"ok": False, "artifact": artifact}
        return {"ok": True, "artifact": artifact}


def run_cline_dry(errors: list[str]) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run-cline.py"),
            "--workspace-id",
            "personal-assistant",
            "--dry-run",
            "coding-effector-smoke",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        errors.append(f"run-cline dry-run exit {proc.returncode}: {proc.stderr.strip()}")
        return {"ok": False, "exit": proc.returncode}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        errors.append("run-cline dry-run did not emit JSON")
        return {"ok": False}
    if not data.get("accepted") or not data.get("dry_run"):
        errors.append(f"run-cline dry-run unexpected: {data}")
        return {"ok": False, "result": data}
    return {
        "ok": True,
        "workspace_id": ((data.get("workspace_choice") or {}).get("workspace") or {}).get(
            "id"
        ),
        "dry_run": True,
    }


def main() -> int:
    errors: list[str] = []
    wiring = check_wiring(errors)
    build = local_build(errors)
    dry = run_cline_dry(errors)
    report = {
        "ok": not errors,
        "motor": "motor.cline",
        "wiring": wiring,
        "local_build": build,
        "run_cline_dry": dry,
        "errors": errors,
        "hint": (
            "If Cursor included usage is exhausted, keep coding via cheaper Cursor Models, "
            "enable on-demand with a spend limit, upgrade, or wait for billing reset — "
            "this smoke still validates the local effector path."
        ),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
