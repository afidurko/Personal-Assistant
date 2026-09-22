## Summary

<!-- What changed and why. Keep it about the code — no personal details about Aaron. -->

## Privacy checklist (required — `privacy-guard` CI must be green)

- [ ] No personal information about Aaron or anyone else in code, config, docs, fixtures, distillates, or this PR text (names beyond the first name, contact details, timezone/location, device names, physical descriptions, photos, voice/face data, health, finances, employment specifics)
- [ ] No secrets, tokens, keys, or `.env` values
- [ ] Anything personal that the runtime needs was stored with `scripts/private-memory.py put …` and is referenced by key
- [ ] `python3 scripts/pii-guard.py --all` passes locally
- [ ] Guardrail files (`config/privacy/`, `.githooks/`, `.github/`, `.clinerules`, `AGENTS.md`, `config/connectome/*policy*.json`) are unchanged, or Aaron granted this change

## Testing

<!-- Commands run and results. -->

Policy: `docs/PRIVACY_SAFEGUARDS.md` · `SECURITY.md`
