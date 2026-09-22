# Aaron — visual identity (held in private memory)

**Subject:** Aaron · **Purpose:** face recognition / photo↔video match · **Visibility:** private

The durable description Cam uses to recognize Aaron — source photo names, physical
traits, appearance variations, and any notes about other people who appear in
enrollment media — is **personal information**. It is not published in this
repository and must never be committed here.

## Where it lives

| Item | Location |
|---|---|
| Sealed record | private memory key `identity.aaron.visual_profile` |
| Working copy on Aaron's host | `identity/aaron/local/VISUAL_PROFILE.md` (gitignored) |
| Photos / embeddings | `identity/aaron/local/photos/`, `identity/aaron/local/embeddings/` (gitignored) |

```bash
python3 scripts/private-memory.py get identity.aaron.visual_profile
python3 scripts/private-memory.py doctor
```

See [`docs/PRIVACY_SAFEGUARDS.md`](../../docs/PRIVACY_SAFEGUARDS.md) for the full
data-classification policy and the layers that keep this file redacted.

## What is safe to say publicly

- Face enrollment is complete; matching runs on-device or on Aaron's host
- No photos, embeddings, biometric vectors, or physical descriptions are tracked in git
- `pii-guard` blocks any commit that re-introduces them

## Match policy

- Primary enrolled cluster = Aaron for `sense.aaron.face`
- Reject faces outside the enrolled cluster for `switch.identity`
- Other people who appear in enrollment media are never enrolled or described
