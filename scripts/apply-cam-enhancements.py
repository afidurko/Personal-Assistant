#!/usr/bin/env python3
"""Apply Aaron-approved Cam enhancement proposals (batch).

Records approvals, marks proposal markdown Applied, updates mesh-seed enhance
state, and runs verification scripts. Does not flip switch.cam_enhance default
for future proposals — future changes still need Aaron.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "vault" / "02-Cam" / "enhancement-proposals"
SEED = ROOT / "identity" / "persistence" / "mesh-seed.json"
BATCH_LOG = ROOT / "identity" / "persistence" / "CAM_ENHANCE_BATCH_2026-09-17.md"


def mark_proposal(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "**Status:** applied" in text:
        return False
    text = re.sub(
        r"\*\*Status:\*\*[^\n]+",
        "**Status:** applied (Aaron approved 2026-09-17 · `switch.cam_enhance` for this batch)",
        text,
        count=1,
    )
    if "## Apply gate" in text and "BATCH APPLIED" not in text:
        text += (
            "\n\n## Apply record\n\n"
            "- **BATCH APPLIED** by Aaron 2026-09-17 via `scripts/apply-cam-enhancements.py`\n"
            "- Implementer: Cam capability-broker (this checkout)\n"
        )
    path.write_text(text, encoding="utf-8")
    return True


def run(cmd: list[str]) -> dict:
    try:
        out = subprocess.check_output(cmd, text=True, cwd=ROOT)
        return {"ok": True, "out": out.strip()}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "out": (exc.output or "") + str(exc)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aaron-approve", action="store_true", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.aaron_approve:
        print("refusing without --aaron-approve", file=sys.stderr)
        return 2

    proposals = sorted(PROPOSALS.glob("*.md"))
    changed = []
    if not args.dry_run:
        for path in proposals:
            if mark_proposal(path):
                changed.append(str(path.relative_to(ROOT)))

        seed = json.loads(SEED.read_text(encoding="utf-8"))
        enhance = seed.setdefault("mesh/enhance", {})
        enhance["switch_cam_enhance"] = "hold"
        enhance["last_batch_approved_by"] = "Aaron"
        enhance["last_batch_approved_at"] = "2026-09-17"
        enhance["last_batch"] = "cam-function-papers-2026-09-17"
        enhance["applied_configs"] = [
            "config/memory/hmo-tiers.json",
            "config/memory/mesh-claim-schema.json",
            "config/connectome/trajectory-policies.json",
            "config/enhancement/dual-process.json",
            "config/persona/consistency-checks.json",
            "config/enhancement/social-harness.json",
            "config/enhancement/vision-grounding.json",
            "config/enhancement/science-agent-env.json",
        ]
        enhance["note"] = (
            "Batch applied; future functionality changes still require Aaron "
            "(switch.cam_enhance defaults to hold)."
        )
        research = seed.setdefault("mesh/research", {})
        research["cam_function_batch_applied"] = True
        research["cam_function_batch_at"] = "2026-09-17"
        SEED.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        BATCH_LOG.write_text(
            "# Cam enhance batch — 2026-09-17\n\n"
            "**Aaron approved all** Cam-function / AGI proposals and ordered implement-all.\n\n"
            f"- Applied at: {datetime.now(timezone.utc).isoformat()}\n"
            f"- Proposals touched: {len(proposals)}\n"
            "- Future `switch.cam_enhance` default remains **hold**\n"
            "- Verify: `python3 scripts/connectome-check.py` · "
            "`python3 scripts/memory-tier-check.py` · "
            "`python3 scripts/trajectory-policy-check.py`\n",
            encoding="utf-8",
        )

    checks = {
        "connectome": run([sys.executable, str(ROOT / "scripts/connectome-check.py"), "--json"]),
        "memory_tiers": run([sys.executable, str(ROOT / "scripts/memory-tier-check.py"), "--json"]),
        "trajectory": run(
            [sys.executable, str(ROOT / "scripts/trajectory-policy-check.py"), "--json"]
        ),
        "enhance_gate_armed": run(
            [
                sys.executable,
                str(ROOT / "scripts/cam-enhance-propose.py"),
                "--aaron-approve",
                "--apply",
                "--proposal",
                "vault/02-Cam/enhancement-proposals/2026-09-17-hmo-hierarchical-memory-for-cam.md",
            ]
        ),
    }
    report = {
        "ok": all(c.get("ok") for c in checks.values()),
        "dry_run": args.dry_run,
        "proposals_total": len(proposals),
        "proposals_marked": changed,
        "checks": {k: {"ok": v["ok"]} for k, v in checks.items()},
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
