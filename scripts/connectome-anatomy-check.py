#!/usr/bin/env python3
"""Static check — Cam anatomical cortex map covers Brodmann areas + GLB asset.

Suggestive gate after human-brain UI: every `area.*` in areas.json must appear
in anatomy-region-map.json; centroids must exist; cam-cortex.glb must be present.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
ASSET = ROOT / "visualizations" / "connectome" / "assets" / "cam-cortex.glb"
NOTICE = ROOT / "visualizations" / "connectome" / "assets" / "NOTICE.md"
PUBLIC_GLB = ROOT / "public" / "cortex" / "cam-cortex.glb"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    areas = json.loads((CFG / "areas.json").read_text(encoding="utf-8"))
    region_map = json.loads((CFG / "anatomy-region-map.json").read_text(encoding="utf-8"))
    centroids = json.loads((CFG / "anatomy-centroids.json").read_text(encoding="utf-8"))

    area_ids = {a["id"] for a in areas["areas"]}
    mapped = set()
    empty_parcels = []
    for entry in region_map:
        name = entry.get("name") or ""
        if name.startswith("area.") and not name.endswith(".hippocampus"):
            # area.mtl.hippocampus folds into area.mtl
            mapped.add(name)
        parcels = entry.get("parcels") or []
        if not parcels:
            empty_parcels.append(name)

    missing_map = sorted(area_ids - mapped)
    extra_map = sorted(mapped - area_ids)
    centroid_ids = {
        k for k in (centroids.get("centroids") or {}) if k.startswith("area.")
    }
    missing_centroids = sorted(area_ids - centroid_ids)

    glb_ok = ASSET.is_file() and ASSET.stat().st_size > 100_000
    notice_ok = NOTICE.is_file()
    public_ok = PUBLIC_GLB.is_file() and PUBLIC_GLB.stat().st_size > 100_000

    errors: list[str] = []
    if missing_map:
        errors.append(f"unmapped_areas:{','.join(missing_map)}")
    if empty_parcels:
        errors.append(f"empty_parcels:{','.join(empty_parcels)}")
    if missing_centroids:
        errors.append(f"missing_centroids:{','.join(missing_centroids)}")
    if not glb_ok:
        errors.append("missing_or_tiny_cam_cortex_glb")
    if not notice_ok:
        errors.append("missing_asset_notice")
    if not public_ok:
        errors.append("missing_public_cortex_glb_mirror")

    report = {
        "areas": len(area_ids),
        "mapped_areas": len(mapped),
        "region_entries": len(region_map),
        "missing_map": missing_map,
        "extra_map": extra_map,
        "missing_centroids": missing_centroids,
        "glb_bytes": ASSET.stat().st_size if ASSET.is_file() else 0,
        "public_glb_bytes": PUBLIC_GLB.stat().st_size if PUBLIC_GLB.is_file() else 0,
        "notice": notice_ok,
        "ok": not errors,
        "errors": errors,
        "suggestions": [
            "Keep anatomy-region-map.json in lockstep with areas.json when adding Brodmann hubs",
            "Regenerate cam-cortex.glb via scripts/build-cam-cortex-glb.sh after map edits",
            "Serve viz from repo root so live-activity.json resolves beside the glass shell",
            "React hero loads /cortex/cam-cortex.glb — keep public/cortex mirrored",
        ],
    }

    out = (
        ROOT
        / "vault"
        / "10-Mesh-Distillates"
        / "qa-cycles"
        / "connectome-anatomy-check-latest.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"connectome-anatomy-check: {status}")
        print(
            f"  areas={report['areas']} mapped={report['mapped_areas']} "
            f"glb={report['glb_bytes']:,}B errors={len(errors)}"
        )
        for e in errors:
            print(f"  ERR {e}")
        for s in report["suggestions"]:
            print(f"  SUGGEST {s}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
