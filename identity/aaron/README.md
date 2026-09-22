# Aaron identity media (private)

Everything that describes Aaron as a person — photos, voice samples, embeddings,
physical descriptions, device names, timezone, contact details — is **personal
information**. It stays on Aaron's devices and in Cam's **private memory**. This
folder holds only public stubs that point at where the private data lives.

## What is tracked here (safe)

- [`VISUAL_PROFILE.md`](VISUAL_PROFILE.md) — stub; the real profile is sealed in private memory
- [`enroll-index.json`](enroll-index.json) — stub; the real index is `local/enroll-index.json`
- This README

## What is never tracked (private, gitignored)

```text
identity/aaron/local/            # gitignored — the whole tree
  VISUAL_PROFILE.md              # durable description Cam uses for face matching
  enroll-index.json              # source refs, labels, confidence, voice refs
  private-memory/                # sealed records written by scripts/private-memory.py
  photos/  videos/               # optional copies Aaron chooses to share
  voice/samples/                 # clean Aaron-only WAV clips for enrollment
  voice/embeddings.json          # CAM++ templates + centroid
  embeddings/                    # face/voice vectors
  enroll.json                    # manifest of sources + hashes
```

## Working with private memory

```bash
python3 scripts/private-memory.py doctor                     # store health, cipher, permissions
python3 scripts/private-memory.py list                       # keys only — never values
python3 scripts/private-memory.py get identity.aaron.visual_profile
python3 scripts/private-memory.py put identity.aaron.timezone --value "Region/City"
python3 scripts/private-memory.py import-legacy              # one-time: pull pre-redaction content out of git history
```

Voice gate: record WAVs into `local/voice/samples/` then run
`scripts/aaron-voice-enroll.py` (see `docs/AARON_VOICE_GATE.md`).

## Guardrails

- `.gitignore` excludes `identity/aaron/local/` and every private-memory path
- `scripts/pii-guard.py` (pre-commit, pre-push, CI) blocks descriptions, contact data, secrets, and private paths
- Sentinel denies any motor plan that tries to move private-memory paths off-host
- Policy: [`docs/PRIVACY_SAFEGUARDS.md`](../../docs/PRIVACY_SAFEGUARDS.md) · [`SECURITY.md`](../../SECURITY.md)
