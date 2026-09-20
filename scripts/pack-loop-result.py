#!/usr/bin/env python3
"""Pack a loop-run JSON document into mesh/loops + vault distillate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "identity/persistence/loop-mesh-latest.json"
MESH_OUT = ROOT / "identity/persistence/loop-mesh-latest.json"
VAULT_OUT = ROOT / "vault/10-Mesh-Distillates/loop-runs/latest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from", dest="src", help="path to loop run JSON")
    p.add_argument("--from-latest", action="store_true", help="re-pack loop-mesh-latest.json")
    p.add_argument("--pattern", default="", help="annotate pattern id")
    p.add_argument("--stdin", action="store_true", help="read JSON from stdin")
    args = p.parse_args()

    if args.stdin:
        raw = sys.stdin.read()
        doc = json.loads(raw or "{}")
    elif args.from_latest or not args.src:
        path = Path(args.src) if args.src else DEFAULT_IN
        if not path.exists():
            print(json.dumps({"ok": False, "error": f"missing {path}"}))
            return 1
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        path = Path(args.src)
        doc = json.loads(path.read_text(encoding="utf-8"))

    out = {
        "namespace": "mesh/loops",
        "kind": "loop_run",
        "at": utc_now(),
        "source": "scripts/pack-loop-result.py",
        "pattern": args.pattern or doc.get("pattern"),
        "payload": doc,
    }
    MESH_OUT.parent.mkdir(parents=True, exist_ok=True)
    VAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    MESH_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    VAULT_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "mesh": str(MESH_OUT.relative_to(ROOT)),
                "vault": str(VAULT_OUT.relative_to(ROOT)),
                "pattern": out.get("pattern"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
