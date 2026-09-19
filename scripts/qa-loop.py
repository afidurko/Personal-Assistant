#!/usr/bin/env python3
"""Continuous QA loop — detect → dispatch team → fix → rerun.

Aaron mandate 2026-09-16. Default campaign N=1_000_000_000.
Never waits for human mid-loop. Logs under vault/10-Mesh-Distillates/qa-cycles/.
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
SIM = ROOT / "scripts" / "connectome-simulate.py"
CHECK = ROOT / "scripts" / "connectome-check.py"
HEALTH = ROOT / "scripts" / "system-health-scan.py"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"
CFG = ROOT / "config" / "connectome"
CYCLES = ROOT / "vault" / "10-Mesh-Distillates" / "qa-cycles"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def emit_activity(reason: str, intensity: float = 0.7) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "neuron": "neuron.qa_cycle",
                    "kind": "loop",
                    "area": "area.cingulate",
                    "intensity": intensity,
                    "tracts": ["tract.cingulum", "tract.slf", "tract.fornix"],
                    "reason": reason,
                    "source": "qa_loop",
                }
            )
            + "\n"
        )


def run_static_check() -> dict:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        report = {"ok": False, "parse_error": proc.stdout[:500]}
    report["exit_code"] = proc.returncode
    return report


def run_health_scan() -> dict:
    """Fire health_conductor — workspace vitals / drift / integrations."""
    proc = subprocess.run(
        [sys.executable, str(HEALTH), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        report = {"overall": "critical", "parse_error": (proc.stdout or "")[:500]}
    report["exit_code"] = proc.returncode
    return report


def run_sim(n: int, workers: int, seed: int, out: Path, strict_edges: bool = True) -> dict:
    cmd = [
        sys.executable,
        str(SIM),
        "--n",
        str(n),
        "--workers",
        str(workers),
        "--seed",
        str(seed),
        "--out",
        str(out),
    ]
    if strict_edges:
        cmd.append("--strict-edges")
    print(f"[qa] sim: n={n:,} workers={workers} seed={seed} strict={strict_edges}", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT))
    wall = time.perf_counter() - t0
    summary: dict = {}
    if out.exists():
        summary = json.loads(out.read_text(encoding="utf-8"))
    summary["qa_exit_code"] = proc.returncode
    summary["qa_wall_s"] = wall
    return summary


def log_issue(cycle_dir: Path, issue: str, detail: dict) -> None:
    (cycle_dir / "issue.json").write_text(
        json.dumps({"at": utc_now(), "issue": issue, "detail": detail}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"[qa] issue logged: {issue}", flush=True)


def dispatch_team(cycle_dir: Path, issue: str) -> dict:
    """Record diagnosis/fix team event — unlimited subagents, no human gate."""
    team = {
        "event": "team_dispatch",
        "dispatched_at": utc_now(),
        "issue": issue,
        "roles": [
            "pathway-auditor",
            "synapse-mapper",
            "simulator-simplifier",
            "regression-runner",
        ],
        "authority": "unlimited_subagents",
        "human_gate": False,
        "await_human": False,
    }
    (cycle_dir / "team-dispatch.json").write_text(
        json.dumps(team, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[qa] team dispatched: {issue}", flush=True)
    return team


def diagnose(summary: dict) -> list[dict]:
    findings: list[dict] = []
    code = summary.get("qa_exit_code", 1)

    if not summary.get("n") and code != 0:
        findings.append(
            {
                "severity": "high",
                "kind": "sim_crash_or_no_output",
                "detail": {"exit_code": code},
            }
        )
        return findings

    if summary.get("failed", 0) > 0:
        findings.append(
            {
                "severity": "high",
                "kind": "sim_failures",
                "detail": {
                    "failed": summary["failed"],
                    "first_errors": summary.get("first_errors", []),
                },
            }
        )

    if summary.get("missing_edges_count", 0) > 0:
        findings.append(
            {
                "severity": "medium",
                "kind": "missing_synapses",
                "detail": {
                    "count": summary["missing_edges_count"],
                    "sample": summary.get("missing_edges_sample") or [],
                },
                "fix": "add_missing_edges",
            }
        )

    if code == 2:
        findings.append(
            {
                "severity": "high",
                "kind": "integrity_fail",
                "detail": "connectome build_tables hard errors",
            }
        )

    return findings


def apply_simplify_fixes(findings: list[dict], cycle_dir: Path) -> list[str]:
    """Apply detectable structural fixes only. Prefer simplify."""
    applied: list[str] = []
    if not any(f.get("fix") == "add_missing_edges" for f in findings):
        (cycle_dir / "fixes-applied.json").write_text(
            json.dumps({"applied": applied, "note": "no_detectable_auto_fix"})
            + "\n",
            encoding="utf-8",
        )
        return applied

    synapses_path = CFG / "synapses.json"
    hotspots = json.loads((CFG / "hotspots.json").read_text(encoding="utf-8"))
    data = json.loads(synapses_path.read_text(encoding="utf-8"))
    existing = {(e["from"], e["to"]) for e in data["edges"]}
    added = 0

    for h in hotspots["hotspots"]:
        path = h["pathway"]
        for a, b in zip(path, path[1:]):
            if (a, b) in existing:
                continue
            data["edges"].append(
                {
                    "from": a,
                    "to": b,
                    "weight": 1.0,
                    "source": "qa-loop-simplify",
                }
            )
            existing.add((a, b))
            added += 1

    if added:
        synapses_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        applied.append(f"filled_{added}_hotspot_edges")
        (cycle_dir / "fix-synapses.json").write_text(
            json.dumps({"added": added}, indent=2) + "\n", encoding="utf-8"
        )

    (cycle_dir / "fixes-applied.json").write_text(
        json.dumps({"applied": applied}, indent=2) + "\n", encoding="utf-8"
    )
    return applied


def metrics_from(summary: dict) -> dict:
    return {
        "n": summary.get("n"),
        "passed": summary.get("passed"),
        "failed": summary.get("failed"),
        "kill_holds": summary.get("kill_holds"),
        "non_aaron_holds": summary.get("non_aaron_holds"),
        "feedback_ok": summary.get("feedback_ok"),
        "missing_edges_count": summary.get("missing_edges_count"),
        "sims_per_sec": summary.get("sims_per_sec"),
        "elapsed_s": summary.get("elapsed_s"),
        "qa_wall_s": summary.get("qa_wall_s"),
        "workers": summary.get("workers"),
        "first_errors": summary.get("first_errors", []),
        "exit_code": summary.get("qa_exit_code"),
    }


def mirror_mesh_qa(cycle_dir: Path, record: dict) -> None:
    """Mirror QA cycle distillate into persistence for cross-workspace recall."""
    mesh_dir = ROOT / "identity" / "persistence"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    path = mesh_dir / "qa-mesh-latest.json"
    doc = {
        "namespace": "mesh/runs",
        "kind": "qa_cycle",
        "cycle_dir": str(cycle_dir.relative_to(ROOT)),
        "at": utc_now(),
        "status": record.get("status"),
        "metrics": record.get("metrics"),
        "findings": record.get("findings"),
        "await_human": False,
        "continuous_qa": True,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    # Also drop under vault distillates
    out = (
        ROOT
        / "vault"
        / "10-Mesh-Distillates"
        / "qa-cycles"
        / "mesh-mirror-latest.json"
    )
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def write_suggestions(
    cycle_dir: Path, summary: dict, findings: list[dict], green: bool
) -> None:
    lines = [
        "# QA cycle suggestions",
        "",
        f"- status: {'green' if green else 'needs_work'}",
        f"- sims: {summary.get('n')}",
        f"- passed/failed: {summary.get('passed')}/{summary.get('failed')}",
        f"- throughput: {summary.get('sims_per_sec')} sims/s",
        f"- missing_edges: {summary.get('missing_edges_count')}",
        "",
        "## Findings",
    ]
    if not findings:
        lines.append("- none")
    for f in findings:
        lines.append(f"- [{f['severity']}] {f['kind']}: {f.get('detail')}")
    lines += [
        "",
        "## After green (standing improvements)",
        "- CI: `bash scripts/ci-connectome.sh` (check + workspace unit tests + 1M strict)",
        "- Standing: `python3 scripts/system-health-scan.py` (health_conductor)",
        "- Nightly billion fuzz via `qa-loop.py --n 1000000000 --cycles 1`",
        "- Aaron **test** protocol (3T→fix→suggest→3T→merge): `python3 scripts/three-trillion-campaign.py --passes 2`",
        "- Trajectory OCL/CPV billion: `python3 scripts/trajectory-billion-fuzz.py --n 1000000000`",
        "- Cam reason billion: `python3 scripts/cam-reason-billion-fuzz.py --n 1000000000`",
        "- Triple-trillion campaign: `bash scripts/merge-prep-trillion.sh`",
        "- Aaron-only voice gate billion: `python3 scripts/aaron-voice-billion-fuzz.py --n 1000000000`",
        "- Progress heartbeats every 50M sims for long campaigns (simulator v3)",
        "- Traffic-weighted sense sampling (chat/vault/cline/scholar/arxiv/aaron.voice/public-apis/inkbox-heavy)",
        "- Mirror QA cycle events into `identity/persistence/qa-mesh-latest.json`",
        "- Cline workspace runtime: `python3 scripts/test_cline_workspaces.py`",
        "- Cam reason dry-run: `python3 scripts/test_cam_reason.py`",
        "- Public APIs catalog: `python3 scripts/public-apis-check.py` + `test_public_apis.py`",
        "- Joshinator embodiment: `unittest backend.test_embodiment` + `embodiment-billion-fuzz.py`",
        "- Inkbox identity: `python3 scripts/inkbox-check.py` (outbound gated via motor.inkbox)",
        "- When Mac is available: flip Tailscale preferred host to aaron-mac",
        "- Suggest: bind `run-cline.py` tickets into live nulltickets when stack is up",
        "- Suggest: `cline mcp install cam` on each Aaron machine after persist-import",
        "- Suggest: pack research mesh writes with `scripts/pack-mesh-claim.py` (MMP)",
        "- Suggest: keep HMO primary lean — persona/prefs only; archive vault distillates",
        "- Suggest: before merge run `trajectory-policy-check` + dual three-trillion "
        "(`merge-prep-trillion.sh`) + cam-reason billion",
        "- Suggest: Phase C converse bar-only — never every-mic SGR",
        "- Suggest: LitServe thin proxy after dry-run green; no vLLM farm yet",
        "- Suggest: expand Cam toolkit (Cline/Scholar) only after Phase B merge",
        "- Suggest: before inventing HTTP helpers, run `scripts/public-apis-search.py`",
        "- Suggest: Inkbox live send only under switch.outbound — never free-send from Cline",
        "- Suggest: keep card 3D spawns procedural — never load franchise GLTF/character packs",
        "- Suggest: push joshinator embodiment upstream when Cursor has write access",
        "- Suggest: Aaron-only voice — `python3 scripts/aaron-voice-gate-check.py` + enroll in Cam UI",
        "- Suggest: voice-gate add-ons — adaptive noise, `pack-aaron-voice-profile.py`, `/api/voice/gate/reject`",
        "- Suggest: bump traffic weight on `sense.aaron.voice` / `sense.ios.mic` for noisy-room campaigns",
        "- Suggest: after converse/addon edits, vitest `aaron-voice-gate*` + dual billion connectome",
        "- Suggest: confirm `neuron.aaron_voice_gate` healthy in system-health before merge",
        "- Suggest: VoiceStudio local speech — `python3 scripts/voicestudio-health.py` + MCP files mode (`config/mcp/voicestudio.json`)",
        "- Suggest: pack voice jobs with `scripts/pack-voicestudio-result.py` (no raw WAV in git)",
        "- Suggest: `voicestudio-speak.py` for motor.voicestudio file renders; audible still uses motor.speak gates",
        "- Suggest: enroll Aaron voice (`aaron-voice-enroll.py`) before live mic; keep fail-closed",
        "- Suggest: `speak_requires_aaron_identity` — motor.speak stripped when switch.identity holds",
        "",
    ]
    (cycle_dir / "suggestions.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--cycles", type=int, default=2)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-strict-edges", action="store_true")
    args = p.parse_args()

    CYCLES.mkdir(parents=True, exist_ok=True)
    stamp = utc_now()
    overall_exit = 0
    strict = not args.no_strict_edges

    for c in range(1, args.cycles + 1):
        cycle_dir = CYCLES / f"{stamp}-cycle-{c:02d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        print(f"[qa] === cycle {c}/{args.cycles} ===", flush=True)
        emit_activity(f"cycle_start:{c}", 0.85)

        check = run_static_check()
        (cycle_dir / "static-check.json").write_text(
            json.dumps(check, indent=2) + "\n", encoding="utf-8"
        )
        health = run_health_scan()
        (cycle_dir / "system-health.json").write_text(
            json.dumps(health, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"[qa] health_conductor: {health.get('overall', '?')} "
            f"({len(health.get('checks') or [])} neurons)",
            flush=True,
        )
        if not check.get("ok"):
            print("[qa] static check FAIL — dispatching fix team", flush=True)
            dispatch_team(cycle_dir, "static_graph_fail")
            findings = [
                {
                    "severity": "high",
                    "kind": "static_graph_fail",
                    "detail": check,
                    "fix": "add_missing_edges",
                }
            ]
            applied = apply_simplify_fixes(findings, cycle_dir)
            check = run_static_check()
            if not check.get("ok"):
                overall_exit = 1
                write_suggestions(cycle_dir, {"n": 0}, findings, False)
                (cycle_dir / "cycle.json").write_text(
                    json.dumps(
                        {
                            "cycle": c,
                            "status": "failed",
                            "static_check": check,
                            "fixes_applied": applied,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                continue

        summary = run_sim(
            args.n,
            args.workers,
            args.seed + c,
            cycle_dir / "sim-results.json",
            strict_edges=strict,
        )
        findings = diagnose(summary)
        green = not findings and summary.get("qa_exit_code", 1) == 0
        write_suggestions(cycle_dir, summary, findings, green)

        record = {
            "cycle": c,
            "of": args.cycles,
            "at": utc_now(),
            "await_human": False,
            "static_check": {"ok": check.get("ok"), "missing": check.get("missing_edges")},
            "metrics": metrics_from(summary),
            "findings": findings,
            "status": "green" if green else "failed",
        }

        if green:
            print(f"[qa] cycle {c} green", flush=True)
        else:
            issue = "; ".join(f["kind"] for f in findings) or "unknown_failure"
            log_issue(
                cycle_dir,
                issue,
                {"metrics": record["metrics"], "findings": findings},
            )
            dispatch_team(cycle_dir, issue)
            applied = apply_simplify_fixes(findings, cycle_dir)
            record["fixes_applied"] = applied

            if applied:
                rerun = run_sim(
                    args.n,
                    args.workers,
                    args.seed + c + 100,
                    cycle_dir / "sim-results-rerun.json",
                    strict_edges=strict,
                )
                rerun_findings = diagnose(rerun)
                record["rerun"] = {
                    "metrics": metrics_from(rerun),
                    "findings": rerun_findings,
                    "status": (
                        "green"
                        if not rerun_findings and rerun.get("qa_exit_code") == 0
                        else "failed"
                    ),
                }
                if record["rerun"]["status"] != "green":
                    overall_exit = 1
                else:
                    print(f"[qa] cycle {c} green after fix+rerun", flush=True)
            else:
                overall_exit = 1
                print(
                    f"[qa] cycle {c} no auto-fix; continuing next cycle",
                    flush=True,
                )

        (cycle_dir / "cycle.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        mirror_mesh_qa(cycle_dir, record)

    print(f"[qa] done overall_exit={overall_exit}", flush=True)
    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
