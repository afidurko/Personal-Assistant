#!/usr/bin/env python3
"""Static check: converse overlays config is loadable and probes match."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import converse_overlays as co  # noqa: E402


def main() -> int:
    report = co.check_overlays()
    report["config"] = "config/persona/converse-overlays.json"
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
