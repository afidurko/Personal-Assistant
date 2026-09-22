# Converse + in-process route — 3T add-on suggestions

Pass 1 (2026-09-20) was green at N=3,000,000,000,000 (0 hard fails).
Issues found were coverage gaps, not connectome/reason property failures.

## Fixes landed before pass 2

1. Wire `ci-static-gate.py` into the 3T campaign (static checks in one process).
2. Scale `aaron-voice-billion-fuzz.py` with `--physical` / modular_period_scaled.
3. cam-reason 3T workers assert `cam_inproc.route` (coding + enhance-hold) and converse overlays (`hi cam` fast, `can you see me` camera line).
4. Campaign units: reason/fast/InfiniteMind + Aaron voice/converse.
5. `workspace-integration-check` is now inside the static gate.

## Landed add-ons

| Add-on | Status |
|---|---|
| `config/persona/converse-overlays.json` | Landed — `speak_from_trace` reads persona config. |
| `scripts/converse-billion-fuzz.py` | Landed — overlay × intent matrix + catalog smoke. |
| In-process public-apis / google-trends search | Landed — `cam_inproc.public_apis_search` / `google_trends_search`. |
| FunASR enroll checksum in voice 3T | Landed — `VoiceStore.enroll_checksum` + reload verify. |
| dual_stream cache invalidation | Landed — mtime reload + `invalidate_dual_stream_cache()`. |

## Suggested add-ons (next cycle)

| Add-on | Why |
|---|---|
| Turn-history phrasing | `speak_from_trace(..., history=)` is reserved; use last Aaron line for echo variety. |
| Live FunASR CAM++ enroll | Checksum covers the store; host enroll still replaces hash_dev. |
| `quotes.quotable` / `exchange.open_er_api` | Allowlisted add-ons when ops asks. |

## Do not

- Put InfiniteMind on the fast gate.
- Fold 1M fuzz into the static gate.
- Free-spend GPU / outbound from Cline.
