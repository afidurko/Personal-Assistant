#!/usr/bin/env python3
"""System health scan for Cam workspaces — vitals, architecture, drift, integrations.

Mapped to connectome health neurons (ACC / DLPFC / parietal). Writes a distillate
Cam can scrub on the 3D plasticity tape.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "system-health.json"
CFG = ROOT / "config" / "connectome"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def check_connectome() -> dict:
    code, out = run([sys.executable, str(ROOT / "scripts" / "connectome-check.py"), "--json"])
    try:
        report = json.loads(out.strip().split("\n")[0] if out.strip().startswith("{") else out)
    except json.JSONDecodeError:
        # connectome-check prints JSON only with --json; may include text
        try:
            report = json.loads(out[out.find("{") : out.rfind("}") + 1])
        except Exception:
            report = {"ok": code == 0, "raw": out[:400]}
    report["neuron"] = "neuron.connectome_check"
    report["status"] = "healthy" if report.get("ok") else "critical"
    return report


def check_submodules() -> dict:
    code, out = run(["git", "submodule", "status"])
    lines = [ln for ln in out.splitlines() if ln.strip()]
    uninitialized = [ln for ln in lines if ln.startswith("-")]
    return {
        "neuron": "neuron.submodule_health",
        "count": len(lines),
        "uninitialized": len(uninitialized),
        "status": "warning" if uninitialized else "healthy",
        "sample": lines[:8],
    }


def check_integrations() -> dict:
    expected = [
        "integrations/jarvis",
        "integrations/paddledetection",
        "integrations/llmavatartalk",
        "integrations/smart-second-brain",
        "integrations/swiftguide",
    ]
    present = [p for p in expected if (ROOT / p).exists()]
    missing = [p for p in expected if p not in present]
    return {
        "neuron": "neuron.integration_pulse",
        "present": present,
        "missing": missing,
        "status": "critical" if missing else "healthy",
    }


def check_persist() -> dict:
    manifest = ROOT / "identity" / "persistence" / "manifest.json"
    mesh_seed = ROOT / "identity" / "persistence" / "mesh-seed.json"
    ok = manifest.exists() and mesh_seed.exists()
    return {
        "neuron": "neuron.persist_sync",
        "manifest": manifest.exists(),
        "mesh_seed": mesh_seed.exists(),
        "status": "healthy" if ok else "warning",
    }


def check_secrets_hygiene() -> dict:
    # shallow heuristic — flag obvious secret filenames in tracked tree
    suspects = []
    for pat in ("*.pem", "*.p12", "*credentials*", "*.env"):
        code, out = run(["git", "ls-files", pat])
        for ln in out.splitlines():
            if ln.strip():
                suspects.append(ln.strip())
    return {
        "neuron": "neuron.secret_hygiene",
        "suspects": suspects[:20],
        "status": "warning" if suspects else "healthy",
    }


def check_drift() -> dict:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    arch = (ROOT / "docs" / "CONNECTOME_ARCHITECTURE.md").read_text(encoding="utf-8")
    has_3d = "3D" in readme or "3D" in arch
    has_plasticity = (CFG / "plasticity.json").exists()
    has_areas = (CFG / "areas.json").exists()
    ok = has_3d and has_plasticity and has_areas
    return {
        "neuron": "neuron.drift_scan",
        "readme_mentions_3d": "3D" in readme,
        "plasticity_config": has_plasticity,
        "areas_config": has_areas,
        "status": "healthy" if ok else "warning",
    }


def check_vitals() -> dict:
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    return {
        "neuron": "neuron.vitals_loop",
        "loadavg": load,
        "cwd": str(ROOT),
        "status": "healthy" if load[0] < 16 else "warning",
    }


def check_converse_health() -> dict:
    # best-effort local probe
    code, out = run(["curl", "-s", "-m", "2", "http://127.0.0.1:8787/api/health"])
    ok = code == 0 and ("ok" in out.lower() or "status" in out.lower() or out.strip() == "{}")
    return {
        "neuron": "neuron.converse_health",
        "reachable": code == 0,
        "body": out[:200],
        "status": "healthy" if ok else "idle",
        "notes": "idle if converse server not running — not critical",
    }


def check_arch_scan() -> dict:
    """Layering / coupling signals — no machine-absolute paths in scripts."""
    issues = []
    needle = "/" + "Users" + "/"
    for py in (ROOT / "scripts").glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            issues.append(f"abs_path:{py.name}")
    cfg_ok = (CFG / "areas.json").exists() and (CFG / "tracts.json").exists()
    if not cfg_ok:
        issues.append("missing_connectome_cfg")
    return {
        "neuron": "neuron.arch_scan",
        "issues": issues[:12],
        "status": "warning" if issues else "healthy",
    }


def check_vuln_scan() -> dict:
    """Offline static hygiene — world-writable tracked paths, suspicious names."""
    findings = []
    code, out = run(["git", "ls-files"])
    for rel in out.splitlines():
        p = ROOT / rel.strip()
        if not p.is_file():
            continue
        name = p.name.lower()
        if name in ("id_rsa", "id_ed25519") or name.endswith(".pem"):
            findings.append(f"keyish:{rel}")
        try:
            mode = p.stat().st_mode & 0o777
            if mode & 0o002:
                findings.append(f"world_writable:{rel}")
        except OSError:
            pass
    return {
        "neuron": "neuron.vuln_scan",
        "findings": findings[:20],
        "status": "warning" if findings else "healthy",
    }


def check_priority_boot() -> dict:
    boot = ROOT / "config" / "priority-boot.json"
    if not boot.exists():
        return {"neuron": "neuron.priority_boot", "status": "warning", "present": False}
    try:
        data = json.loads(boot.read_text(encoding="utf-8"))
        steps = data.get("order") or data.get("steps") or data.get("priorities") or []
        return {
            "neuron": "neuron.priority_boot",
            "present": True,
            "step_count": len(steps) if isinstance(steps, list) else 0,
            "status": "healthy",
        }
    except json.JSONDecodeError:
        return {"neuron": "neuron.priority_boot", "status": "critical", "present": True, "parse": "fail"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    checks = [
        check_vitals(),
        check_connectome(),
        check_submodules(),
        check_integrations(),
        check_persist(),
        check_secrets_hygiene(),
        check_drift(),
        check_converse_health(),
        check_arch_scan(),
        check_vuln_scan(),
        check_priority_boot(),
    ]
    severity = {"healthy": 0, "idle": 0, "warning": 1, "critical": 2}
    worst = max(checks, key=lambda c: severity.get(c.get("status", "idle"), 0))
    report = {
        "at": utc(),
        "overall": worst.get("status", "healthy"),
        "checks": checks,
        "neurons_fired": [c["neuron"] for c in checks],
        "workspace": str(ROOT),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Append a compact event onto plasticity timeline for 3D rewind
    timeline_path = ROOT / "vault" / "10-Mesh-Distillates" / "plasticity-timeline.json"
    events = []
    if timeline_path.exists():
        try:
            events = json.loads(timeline_path.read_text(encoding="utf-8")).get("events", [])
        except json.JSONDecodeError:
            events = []
    events.append(
        {
            "t": len(events),
            "ts": utc(),
            "type": "health_scan",
            "status": "ok" if report["overall"] in ("healthy", "idle") else "warn",
            "overall": report["overall"],
            "neurons": report["neurons_fired"],
        }
    )
    timeline_path.write_text(
        json.dumps({"version": 1, "events": events, "rules": "config/connectome/plasticity.json"}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"system-health: {report['overall'].upper()} ({len(checks)} neurons)")
        for c in checks:
            print(f"  {c['status']:8} {c['neuron']}")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0 if report["overall"] != "critical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
