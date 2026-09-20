#!/usr/bin/env python3
"""CLI entry for Cam ↔ InfiniteMind adapter. See scripts/cam_infinitemind.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cam_infinitemind  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(cam_infinitemind.main())
