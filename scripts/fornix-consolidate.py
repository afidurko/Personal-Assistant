#!/usr/bin/env python3
"""Fornix consolidation — promote episodic vault notes → semantic distillates.

Scans vault/ for recent notes and writes a semantic summary distillate.
Respects mesh-params defaults (nightly_enabled).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "config" / "connectome" / "mesh-params.json"
VAULT = ROOT / "vault"
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "fornix-consolidation.json"
OUT_MD = ROOT / "vault" / "10-Mesh-Distillates" / "Semantic-From-Episodic.md"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"
MARKER = ROOT / "vault" / "10-Mesh-Distillates" / ".fornix-last-run"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def should_run(force: bool) -> bool:
    if force:
        return True
    params = json.loads(PARAMS.read_text(encoding="utf-8")) if PARAMS.exists() else {}
    if params.get("defaults_applied", {}).get("fornix_consolidation") == "disabled":
        return False
    if not MARKER.exists():
        return True
    # weekly-ish: skip if ran in last 6 days unless forced
    age = datetime.now(timezone.utc).timestamp() - MARKER.stat().st_mtime
    return age > 6 * 86400


def collect_episodic(limit: int = 40) -> list[dict]:
    items = []
    for p in sorted(VAULT.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        if "10-Mesh-Distillates" in p.parts and p.name.startswith("Semantic"):
            continue
        rel = str(p.relative_to(ROOT))
        text = p.read_text(encoding="utf-8", errors="ignore")
        title = text.splitlines()[0].lstrip("# ").strip() if text.strip() else p.stem
        items.append({"path": rel, "title": title[:120], "chars": len(text)})
        if len(items) >= limit:
            break
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not should_run(args.force):
        msg = {"ok": True, "skipped": True, "reason": "recent_or_disabled"}
        print(json.dumps(msg, indent=2) if args.json else "fornix: skipped (recent)")
        return 0

    items = collect_episodic()
    themes = []
    for key, label in [
        ("Health", "system health"),
        ("SwiftGuide", "SwiftGuide cartography"),
        ("Connectome", "connectome / cortex"),
        ("QA", "QA campaigns"),
        ("Persist", "persistence"),
        ("Fasciculus", "white-matter / AGI mesh"),
        ("Open-Questions", "open design questions"),
    ]:
        hits = [i for i in items if key.lower() in i["path"].lower() or key.lower() in i["title"].lower()]
        if hits:
            themes.append({"theme": label, "count": len(hits), "samples": [h["path"] for h in hits[:5]]})

    report = {
        "at": utc(),
        "neuron": "neuron.mesh_sync_loop",
        "bus": "tract.fornix",
        "episodic_scanned": len(items),
        "themes": themes,
        "top": items[:15],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Semantic distillate (fornix consolidation)",
        "",
        f"Promoted from episodic vault scan at `{report['at']}`.",
        "",
        "## Themes",
    ]
    for th in themes:
        md.append(f"- **{th['theme']}** ({th['count']})")
        for s in th["samples"]:
            md.append(f"  - `{s}`")
    md += ["", "## Recent episodic surfaces", ""]
    for i in items[:12]:
        md.append(f"- [{i['title']}]({i['path']})")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    MARKER.write_text(utc() + "\n", encoding="utf-8")

    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": utc(),
                    "neuron": "neuron.mesh_sync_loop",
                    "kind": "loop",
                    "area": "area.mtl",
                    "intensity": 0.85,
                    "tracts": ["tract.fornix", "tract.cingulum", "tract.ilf"],
                    "reason": f"consolidate:{len(themes)}_themes",
                    "source": "fornix_consolidate",
                }
            )
            + "\n"
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"fornix: consolidated {len(items)} notes → {len(themes)} themes")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
