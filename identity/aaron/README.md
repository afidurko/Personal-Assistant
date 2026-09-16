# Aaron identity media (local)

Private originals stay on Aaron’s devices. This folder holds **refs and enrollment notes only** — do not commit personal photos/videos here.

## Current enrollment (2026-09-16)
- Visual profile: [`VISUAL_PROFILE.md`](VISUAL_PROFILE.md)
- Index: [`enroll-index.json`](enroll-index.json)
- Local copies (gitignored): `local/photos/` — 3 primary Aaron face shots enrolled; gym pair pending label

## Purpose
Build Cam’s understanding of Aaron’s look and sound, including matching a face from a photo to the same person talking in a video.

## Expected local layout (on Aaron’s machine)
```text
identity/aaron/local/          # gitignored
  photos/                      # optional copies Aaron chooses to share
  videos/
  voice/
  embeddings/                  # face/voice vectors (not for public push)
  enroll.json                  # manifest of sources + hashes
```

See `identity/persistence/AARON_MEDIA_ACCESS.md`.
