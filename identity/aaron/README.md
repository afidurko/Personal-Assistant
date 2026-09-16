# Aaron identity media (local)

Private originals stay on Aaron’s devices. This folder holds **refs and enrollment notes only** — do not commit personal photos/videos here.

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

## Manifest shape (`enroll.json`)
```json
{
  "subject": "Aaron",
  "updated_at": "ISO-8601",
  "faces": [{"source": "path/or/phasset", "hash": "...", "embedding_ref": "..."}],
  "voices": [{"source": "path/or/video", "hash": "...", "embedding_ref": "..."}],
  "links": [{"face_id": "...", "voice_id": "...", "video": "...", "same_person": true}]
}
```

See `identity/persistence/AARON_MEDIA_ACCESS.md`.
