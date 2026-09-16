#!/usr/bin/env python3
"""Build / update Aaron identity enrollment manifest from local media paths.

Does not upload originals. Writes identity/aaron/local/enroll.json (gitignored).
Requires Aaron media access grant — see identity/persistence/AARON_MEDIA_ACCESS.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "identity" / "aaron" / "local"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
AUDIO_EXT = {".m4a", ".wav", ".mp3", ".aac", ".caf"}


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def collect(paths: list[Path]) -> dict:
    faces, voices, videos = [], [], []
    for root in paths:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            rel = str(p)
            entry = {"source": rel, "hash": file_hash(p)}
            if ext in IMAGE_EXT:
                faces.append(entry)
            elif ext in VIDEO_EXT:
                videos.append(entry)
                voices.append({**entry, "from_video": True})
            elif ext in AUDIO_EXT:
                voices.append(entry)
    links = []
    # Heuristic placeholder: same stem across photo+video suggests same session/person
    stems = {}
    for f in faces:
        stems.setdefault(Path(f["source"]).stem.lower(), []).append(("face", f))
    for v in videos:
        stems.setdefault(Path(v["source"]).stem.lower(), []).append(("video", v))
    for stem, items in stems.items():
        kinds = {k for k, _ in items}
        if "face" in kinds and "video" in kinds:
            links.append(
                {
                    "stem": stem,
                    "same_person_candidate": True,
                    "note": "same filename stem — confirm with face+voice match model",
                    "items": items,
                }
            )
    return {
        "subject": "Aaron",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "understand_aaron_look_and_sound",
        "photo_to_video_match": True,
        "faces": faces,
        "voices": voices,
        "videos": videos,
        "links": links,
        "counts": {
            "faces": len(faces),
            "voices": len(voices),
            "videos": len(videos),
            "link_candidates": len(links),
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[OUT_DIR / "photos", OUT_DIR / "videos", OUT_DIR / "voice"],
        help="folders of Aaron media (default identity/aaron/local/{photos,videos,voice})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR / "enroll.json",
    )
    args = p.parse_args()
    manifest = collect(args.paths)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
