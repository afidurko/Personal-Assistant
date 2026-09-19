#!/usr/bin/env python3
"""Shared trillion-scale helpers for Cam fuzz campaigns.

Finite modular / pathway spaces: verify a physical stress subset, then scale
the remainder when N ≥ 1e11 (Aaron three-trillion protocol).
"""

from __future__ import annotations

SCALE_THRESHOLD = 100_000_000_000  # 1e11
PHYSICAL_DEFAULT = 10_000_000
THREE_TRILLION = 3_000_000_000_000


def resolve_scale(n: int, physical: int | None = None) -> tuple[int, int, str]:
    """Return (physical_n, scaled_n, sampler_tag)."""
    if n < SCALE_THRESHOLD:
        return n, 0, "literal_loop"
    phys = PHYSICAL_DEFAULT if physical is None else physical
    phys = max(0, min(n, phys))
    return phys, n - phys, "modular_period_scaled"
