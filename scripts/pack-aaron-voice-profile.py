#!/usr/bin/env python3
"""Pack / import Aaron voice-profile for Cam voice-gate add-on.

Export a browser-enrolled spectral profile into identity/aaron/local/voice-profile.json (gitignored),
or import a previously packed profile for device restore.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "identity" / "aaron" / "local" / "voice-profile.json"
GATE_CFG = ROOT / "config" / "identity" / "aaron-voice-gate.json"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_profile(profile: dict) -> list[str]:
    errs: list[str] = []
    if profile.get("version") != 1:
        errs.append("version_must_be_1")
    if profile.get("subject") != "Aaron":
        errs.append("subject_must_be_Aaron")
    bands = profile.get("bands")
    if not isinstance(bands, list) or len(bands) < 8:
        errs.append("bands_missing_or_short")
    elif not all(isinstance(x, (int, float)) for x in bands):
        errs.append("bands_not_numeric")
    if not isinstance(profile.get("pitchHz"), (int, float)):
        errs.append("pitchHz_missing")
    return errs


def pack(profile: dict, *, source: str) -> dict:
    errs = validate_profile(profile)
    if errs:
        raise SystemExit(f"invalid profile: {', '.join(errs)}")
    return {
        "subject": "Aaron",
        "saved_at": utc(),
        "source": source,
        "gate_config": "config/identity/aaron-voice-gate.json",
        "storage_key": "cam.aaron.voice.profile.v1",
        "profile": profile,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--from-json",
        help="path to raw VoiceProfile JSON (version/subject/bands/pitchHz)",
    )
    ap.add_argument(
        "--from-stdin",
        action="store_true",
        help="read raw VoiceProfile JSON from stdin",
    )
    ap.add_argument(
        "--import-pack",
        help="path to a previously packed voice-profile.json (extract profile)",
    )
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="write packed JSON here")
    ap.add_argument("--print-profile", action="store_true", help="print inner profile only")
    ap.add_argument("--json", action="store_true", help="print pack to stdout")
    args = ap.parse_args()

    if not GATE_CFG.exists():
        print("missing config/identity/aaron-voice-gate.json", file=sys.stderr)
        return 1

    if args.import_pack:
        doc = json.loads(Path(args.import_pack).read_text(encoding="utf-8"))
        profile = doc.get("profile") if isinstance(doc.get("profile"), dict) else doc
        packed = pack(profile, source=f"import:{args.import_pack}")
    elif args.from_stdin:
        profile = json.loads(sys.stdin.read())
        packed = pack(profile, source="stdin")
    elif args.from_json:
        profile = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        if "profile" in profile and isinstance(profile["profile"], dict):
            packed = pack(profile["profile"], source=f"file:{args.from_json}")
        else:
            packed = pack(profile, source=f"file:{args.from_json}")
    else:
        print("provide --from-json, --from-stdin, or --import-pack", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(packed, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")

    if args.print_profile:
        print(json.dumps(packed["profile"], indent=2))
    elif args.json:
        print(text, end="")
    else:
        try:
            shown = out.relative_to(ROOT)
        except ValueError:
            shown = out
        print(f"packed Aaron voice profile → {shown}")
        print(f"  bands={len(packed['profile']['bands'])} pitchHz={packed['profile']['pitchHz']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
