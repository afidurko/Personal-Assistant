#!/usr/bin/env python3
"""Bridge Jarvis local memory.json <-> mesh/jarvis document.

Jarvis memory is a cache. Shared truth lives in nulltickets mesh namespaces.
This script only reads/writes local files — no network required.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMORY = (
    ROOT
    / "integrations"
    / "jarvis"
    / "jarviscli"
    / "packages"
    / "memory"
    / "memory.json"
)


def load_memory(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def export_mesh_doc(memory: dict) -> dict:
    return {
        "namespace": "mesh/jarvis",
        "source": "integrations/jarvis",
        "sensitivity": "team",
        "entries": memory,
    }


def cmd_export(args: argparse.Namespace) -> int:
    memory = load_memory(Path(args.memory))
    doc = export_mesh_doc(memory)
    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    src = Path(args.from_path)
    if not src.exists():
        print(f"missing import file: {src}", file=sys.stderr)
        return 1
    raw = json.loads(src.read_text(encoding="utf-8"))
    entries = raw.get("entries", raw)
    if not isinstance(entries, dict):
        print("import payload must be an object or {entries: object}", file=sys.stderr)
        return 1

    dest = Path(args.memory)
    current = load_memory(dest)
    merged = dict(current)
    merged.update(entries)

    if args.dry_run:
        print(json.dumps({"would_write": dest.as_posix(), "keys": sorted(merged)}, indent=2))
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(merged)} keys → {dest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--memory",
        default=str(DEFAULT_MEMORY),
        help="path to Jarvis memory.json",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    export_p = sub.add_parser("export", help="print mesh/jarvis document")
    export_p.add_argument("--out", help="write to file instead of stdout")
    export_p.set_defaults(func=cmd_export)

    import_p = sub.add_parser("import", help="merge mesh dump into Jarvis memory")
    import_p.add_argument("--from", dest="from_path", required=True)
    import_p.add_argument("--dry-run", action="store_true")
    import_p.set_defaults(func=cmd_import)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
