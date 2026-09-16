#!/usr/bin/env python3
"""Continuous QA loop — detect → dispatch team → fix → rerun.

Always-on mandate (Aaron 2026-09-16). Default campaign: 1_000_000_000 sims.
Never waits for human mid-loop. Logs every cycle under qa-cycles/.
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
CFG = ROOT / "config" / "connectome"
CYCLES = ROOT / "vault" / "10-Mesh-Distillates" / "qa-cycles"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_sim(n: int, workers: int, seed: int, out: Path) -> dict:
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
    print(f"[qa] dispatch sim: {' '.join(cmd)}", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
    elapsed = time.perf_counter() - t0
    summary = {}
    if out.exists():
        summary = json.loads(out.read_text(encoding="utf-8"))
    summary["qa_exit_code"] = proc.returncode
    summary["qa_wall_s"] = elapsed
    return summary


def dispatch_team(issue: str, cycle_dir: Path) -> dict:
    """Record a virtual diagnosis team (unlimited subagents, no human gate)."""
    team = {
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
    }
    (cycle_dir / "team-dispatch.json").write_text(
        json.dumps(team, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[qa] team dispatched for: {issue}", flush=True)
    return team


def diagnose(summary: dict) -> list[dict]:
    """Produce concrete findings from a sim summary + static config scan."""
    findings: list[dict] = []
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
    missing = summary.get("missing_edges_sample") or []
    if summary.get("missing_edges_count", 0) > 0:
        findings.append(
            {
                "severity": "medium",
                "kind": "missing_synapses",
                "detail": {
                    "count": summary["missing_edges_count"],
                    "sample": missing,
                },
                "fix": "add_missing_edges",
            }
        )
    if summary.get("qa_exit_code", 0) == 2:
        findings.append(
            {
                "severity": "high",
                "kind": "integrity_fail",
                "detail": "build_tables hard errors",
            }
        )
    return findings


def apply_fixes(findings: list[dict], cycle_dir: Path) -> list[str]:
    """Auto-apply safe structural fixes. Prefer simplify."""
    applied: list[str] = []
    synapses_path = CFG / "synapses.json"
    for f in findings:
        if f.get("fix") != "add_missing_edges":
            continue
        sample = f["detail"].get("sample") or []
        data = json.loads(synapses_path.read_text(encoding="utf-8"))
        existing = {(e["from"], e["to"]) for e in data["edges"]}
        added = 0
        for item in sample:
            # format: missing_edge:a->b
            if not item.startswith("missing_edge:"):
                continue
            pair = item[len("missing_edge:") :]
            if "->" not in pair:
                continue
            a, b = pair.split("->", 1)
            if (a, b) in existing:
                continue
            data["edges"].append(
                {
                    "from": a,
                    "to": b,
                    "weight": 1.0,
                    "source": "qa-loop-auto",
                }
            )
            existing.add((a, b))
            added += 1
        if added:
            synapses_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            applied.append(f"added_{added}_synapse_edges")
            (cycle_dir / "fix-synapses.json").write_text(
                json.dumps({"added": added, "sample": sample}, indent=2) + "\n",
                encoding="utf-8",
            )
    # Also scan all hotspot pathways for any missing edges not in sample.
    if any(f.get("fix") == "add_missing_edges" for f in findings):
        hotspots = json.loads((CFG / "hotspots.json").read_text(encoding="utf-8"))
        data = json.loads(synapses_path.read_text(encoding="utf-8"))
        existing = {(e["from"], e["to"]) for e in data["edges"]}
        added = 0
        for h in hotspots["hotspots"]:
            path = h["pathway"]
            for a, b in zip(path, path[1:]):
                if (a, b) not in existing:
                    data["edges"].append(
                        {
                            "from": a,
                            "to": b,
                            "weight": 1.0,
                            "source": "qa-loop-hotspot-fill",
                        }
                    )
                    existing.add((a, b))
                    added += 1
        if added:
            synapses_path.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            applied.append(f"filled_{added}_hotspot_edges")
    (cycle_dir / "fixes-applied.json").write_text(
        json.dumps({"applied": applied}, indent=2) + "\n", encoding="utf-8"
    )
    return applied


def write_suggestions(cycle_dir: Path, summary: dict, findings: list[dict]) -> None:
    lines = [
        "# QA cycle suggestions",
        "",
        f"- sims: {summary.get('n')}",
        f"- passed: {summary.get('passed')} failed: {summary.get('failed')}",
        f"- throughput: {summary.get('sims_per_sec')} sims/s",
        f"- missing_edges: {summary.get('missing_edges_count')}",
        "",
        "## Findings",
    ]
    if not findings:
        lines.append("- none — campaign green")
    for f in findings:
        lines.append(f"- [{f['severity']}] {f['kind']}: {f.get('detail')}")
    lines += [
        "",
        "## Improvement ideas",
        "- Cover orphan senses (email, vision, jarvis, mesh, vault) with real hotspots",
        "- Validate synapse edges in the hot loop under a --strict-edges mode for CI",
        "- Add progress heartbeats every N million sims for long campaigns",
        "- Weight sense sampling by real traffic mix instead of uniform",
        "- Keep simulator v2 path tables; avoid re-parsing JSON inside workers",
        "",
    ]
    (cycle_dir / "suggestions.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--cycles", type=int, default=2)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    CYCLES.mkdir(parents=True, exist_ok=True)
    overall_exit = 0
    stamp = utc_now()

    for c in range(1, args.cycles + 1):
        cycle_dir = CYCLES / f"{stamp}-cycle-{c:02d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        out = cycle_dir / "sim-results.json"
        print(f"[qa] === cycle {c}/{args.cycles} ===", flush=True)

        summary = run_sim(args.n, args.workers, args.seed + c, out)
        findings = diagnose(summary)
        write_suggestions(cycle_dir, summary, findings)

        record = {
            "cycle": c,
            "n": args.n,
            "failed": summary.get("failed"),
            "passed": summary.get("passed"),
            "sims_per_sec": summary.get("sims_per_sec"),
            "findings": findings,
            "exit_code": summary.get("qa_exit_code"),
        }

        if findings:
            dispatch_team(
                "; ".join(f["kind"] for f in findings),
                cycle_dir,
            )
            applied = apply_fixes(findings, cycle_dir)
            record["fixes_applied"] = applied
            # Immediate rerun after fix inside the same cycle slot.
            if applied:
                rerun_out = cycle_dir / "sim-results-rerun.json"
                rerun = run_sim(args.n, args.workers, args.seed + c + 100, rerun_out)
                record["rerun"] = {
                    "failed": rerun.get("failed"),
                    "passed": rerun.get("passed"),
                    "missing_edges_count": rerun.get("missing_edges_count"),
                    "exit_code": rerun.get("qa_exit_code"),
                }
                if rerun.get("failed", 1) != 0:
                    overall_exit = 1
            else:
                overall_exit = 1
        else:
            record["status"] = "green"
            print(f"[qa] cycle {c} green", flush=True)

        (cycle_dir / "cycle.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )

    print(f"[qa] done overall_exit={overall_exit}", flush=True)
    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
