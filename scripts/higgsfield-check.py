#!/usr/bin/env python3
"""Smoke-check Higgsfield integration wiring (no GPU / no network required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    policy = ROOT / "config/integrations/higgsfield.md"
    cfg = ROOT / "config/integrations/higgsfield.json"
    sub = ROOT / "integrations/higgsfield"
    reg = ROOT / "config/workspaces/registry.json"
    motor = ROOT / "config/connectome/motor.json"

    for p in (policy, cfg, reg, motor):
        if not p.is_file() or p.stat().st_size == 0:
            errors.append(f"missing: {p.relative_to(ROOT)}")

    if cfg.is_file():
        data = json.loads(cfg.read_text(encoding="utf-8"))
        if data.get("id") != "higgsfield":
            errors.append("higgsfield.json id mismatch")
        if data.get("motor") != "motor.higgsfield":
            errors.append("higgsfield.json motor mismatch")

    if reg.is_file():
        r = json.loads(reg.read_text(encoding="utf-8"))
        ids = {i.get("id") for i in r.get("layers", {}).get("integrations", [])}
        if "higgsfield" not in ids:
            errors.append("registry missing integrations.higgsfield")
        ws = {w.get("id") for w in r.get("workspaces", [])}
        if "higgsfield" not in ws:
            errors.append("registry missing workspace higgsfield")

    if motor.is_file():
        m = json.loads(motor.read_text(encoding="utf-8"))
        mids = {e.get("id") for e in m.get("effectors", [])}
        if "motor.higgsfield" not in mids:
            errors.append("motor.json missing motor.higgsfield")

    entries = []
    if sub.exists():
        entries = [p for p in sub.iterdir() if p.name != ".git"]
    checkout = "ok" if entries else "empty_or_missing"

    out = {
        "ok": not errors,
        "integration": "higgsfield",
        "checkout": checkout,
        "errors": errors,
    }
    print(json.dumps(out, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
