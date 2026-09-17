#!/usr/bin/env python3
"""Prepare Cline tickets for nulltickets PUT / mesh export.

Reads identity/persistence/tickets/{pending,done} and writes a mesh bundle
under vault/10-Mesh-Distillates/cline-tickets/ for curator upload.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", choices=["pending", "done", "all"], default="all")
    p.add_argument("--out", help="output JSON path")
    p.add_argument("--mark-exported", action="store_true")
    args = p.parse_args()

    paths: list[Path] = []
    if args.status in {"pending", "all"}:
        paths.extend(sorted((cw.TICKETS_DIR / "pending").glob("*.json")))
    if args.status in {"done", "all"}:
        paths.extend(sorted((cw.TICKETS_DIR / "done").glob("*.json")))

    tickets = []
    for path in paths:
        doc = cw.load_json(path)
        if not doc:
            continue
        tickets.append(doc)

    bundle = {
        "namespace": "mesh/runs",
        "kind": "cline_ticket_export",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(tickets),
        "tickets": tickets,
        "nulltickets": {
            "suggested_puts": [
                f"tickets/cline/{t.get('id')}" for t in tickets if t.get("id")
            ]
            + ["mesh/cline", "mesh/runs"]
        },
    }

    out = (
        Path(args.out)
        if args.out
        else ROOT
        / "vault"
        / "10-Mesh-Distillates"
        / "cline-tickets"
        / f"export-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    cw.write_json(out, bundle)
    print(f"wrote {out} ({len(tickets)} tickets)")

    if args.mark_exported:
        for path in paths:
            doc = cw.load_json(path)
            doc["exported_at"] = bundle["exported_at"]
            cw.write_json(path, doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
