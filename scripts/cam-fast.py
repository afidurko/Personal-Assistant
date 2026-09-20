#!/usr/bin/env python3
"""CLI entry for Cam System-1 fast path. See scripts/cam_fast.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cam_fast  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(cam_fast.main())
