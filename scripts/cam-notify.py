#!/usr/bin/env python3
"""Drop a message into Aaron's Cam Live inbox from any script or loop.

    python3 scripts/cam-notify.py --subject "Nightly triage" --body "3 findings…"
    echo "long body" | python3 scripts/cam-notify.py --subject "Report" --stdin

The message appears in the Messages panel of Cam Live (and pushes to the
phone when Aaron has enabled switch.outbound channels). This is the glue
that lets loop-engineering reports, needs-attention runs, and any cron
job reach Aaron instead of dying in a JSONL nobody reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cam_messages import MessageCenter  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="")
    ap.add_argument("--stdin", action="store_true", help="read body from stdin")
    ap.add_argument("--kind", default="report",
                    help="message kind (report, reminder, task_done, note, …)")
    ap.add_argument("--priority", default="normal", choices=["normal", "high"])
    ap.add_argument("--no-outbound", action="store_true",
                    help="inbox only — skip push channels even if enabled")
    args = ap.parse_args(argv)

    body = sys.stdin.read() if args.stdin else args.body
    mc = MessageCenter()
    msg = mc.send(args.subject, body, kind=args.kind, priority=args.priority,
                  allow_outbound=not args.no_outbound)
    print(json.dumps({"ok": True, "id": msg["id"], "at": msg["at"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
