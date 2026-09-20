#!/usr/bin/env python3
"""Confirm Cam home presence is her portrait + Audio2Face, not Speak clips."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    portrait = ROOT / "identity/persona/cam-face.jpg"
    if not portrait.is_file() or portrait.stat().st_size < 1000:
        errors.append("missing identity/persona/cam-face.jpg")

    avatar = load(ROOT / "config/persona/avatar.json").get("avatar") or {}
    if avatar.get("engine") != "audio2face":
        errors.append("avatar.engine must be audio2face")
    if (avatar.get("clips") or {}).get("engine") == "higgsfield":
        errors.append("avatar.clips must not use higgsfield")
    if "cam-face.jpg" not in str(avatar.get("portrait") or ""):
        errors.append("avatar.portrait must be Cam’s identity photo")

    hf = load(ROOT / "config/integrations/higgsfield.json")
    if hf.get("status") != "rejected" or hf.get("presence") is not False:
        errors.append("higgsfield.json must stay rejected / presence=false")

    switches = load(ROOT / "config/connectome/switches.json")
    presence = next((s for s in switches.get("switches") or [] if s.get("id") == "switch.presence"), {})
    act = presence.get("act") or []
    if isinstance(act, str):
        act = [act]
    if "motor.higgsfield" in act:
        errors.append("switch.presence must not act motor.higgsfield")

    for rel in (
        "src/components/CamFace.tsx",
        "src/components/CamStage.tsx",
        "src/styles.css",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for banned in ("cam-face-higgsfield", "Render Speak clip", "Play Speak clip", "clipUrl"):
            if banned in text:
                errors.append(f"{rel} still surfaces {banned}")

    face = (ROOT / "src/components/CamFace.tsx").read_text(encoding="utf-8")
    if "cam-face.jpg" not in face:
        errors.append("CamFace must load Cam’s identity portrait")
    if "composeA2F" not in face:
        errors.append("CamFace must drive A2F weights")

    report = {
        "ok": not errors,
        "engine": avatar.get("engine"),
        "portrait": avatar.get("portrait"),
        "higgsfield_status": hf.get("status"),
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
