#!/usr/bin/env python3
"""Export Aaron/Cam persistence bundle for this and future workspaces."""

from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INCLUDE = [
    "identity/ANSWERS_SESSION_01.json",
    "identity/PROFILE.md",
    "identity/BOUNDARIES.md",
    "identity/GOALS.md",
    "identity/persistence/manifest.json",
    "identity/persistence/mesh-seed.json",
    "identity/persistence/UNLIMITED_SUBAGENTS.md",
    "identity/persistence/DAILY_AGI_SCAN.md",
    "identity/persistence/CONTINUOUS_QA.md",
    "identity/persona/cam-face.jpg",
    "config/priority-boot.json",
    "config/connectors.md",
    "config/roles.md",
    "config/roles/careers.md",
    "config/roles/chief.md",
    "config/roles/agi-scout.md",
    "config/roles/capability-broker.md",
    "config/roles/info-retriever.md",
    "config/roles/slm-runtime.md",
    "config/roles/dl-enhance.md",
    "config/teams/agi-research-scan.json",
    "config/teams/capability.json",
    "config/teams/info.json",
    "config/enhancement/slm-dl.json",
    "config/workspaces/registry.json",
    "config/pipelines/daily-agi-scan.json",
    "config/pipelines/cam-enhance-gate.json",
    "config/persona/voice.json",
    "config/persona/vault.json",
    "docs/PERSISTENCE.md",
    "docs/PERSONA.md",
    "docs/CAM_BRAIN.md",
    "docs/AGI_RESEARCH_TEAM.md",
    "docs/WORKSPACES_WORKFLOW.md",
    "vault/Welcome.md",
    "vault/README.md",
    "vault/02-Cam/Brain.md",
    "vault/04-Research/AGI-Daily-Scan.md",
]


def refresh_seed() -> None:
    """Keep mesh-seed assistant/human names aligned with answers if present."""
    answers_path = ROOT / "identity" / "ANSWERS_SESSION_01.json"
    seed_path = ROOT / "identity" / "persistence" / "mesh-seed.json"
    if not answers_path.exists() or not seed_path.exists():
        return
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    prefs = seed.setdefault("mesh/prefs", {})
    prefs["human_name"] = answers.get("human", {}).get("preferred_name", prefs.get("human_name"))
    prefs["assistant_name"] = answers.get("assistant", {}).get("name", prefs.get("assistant_name"))
    prefs["timezone"] = answers.get("human", {}).get("timezone", prefs.get("timezone"))
    seed_path.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bump_manifest() -> None:
    manifest_path = ROOT / "identity" / "persistence" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle_version"] = int(manifest.get("bundle_version", 0)) + 1
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="zip path for portable bundle")
    parser.add_argument("--seed-only", action="store_true", help="only refresh mesh-seed.json")
    args = parser.parse_args()

    refresh_seed()
    if args.seed_only:
        print("refreshed identity/persistence/mesh-seed.json")
        return 0

    bump_manifest()
    refresh_seed()

    out = Path(args.out) if args.out else ROOT / "identity" / "persistence" / "cam-persistence.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in DEFAULT_INCLUDE:
            path = ROOT / rel
            if path.exists():
                zf.write(path, arcname=rel)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
