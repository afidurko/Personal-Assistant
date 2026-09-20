# Converse + in-process route — 3T add-on suggestions

Pass 1 (2026-09-20) was green at N=3,000,000,000,000 (0 hard fails).
Issues found were coverage gaps, not connectome/reason property failures.

## Fixes landed before pass 2

1. Wire `ci-static-gate.py` into the 3T campaign (static checks in one process).
2. Scale `aaron-voice-billion-fuzz.py` with `--physical` / modular_period_scaled.
3. cam-reason 3T workers assert `cam_inproc.route` (coding + enhance-hold) and converse overlays (`hi cam` fast, `can you see me` camera line).
4. Campaign units: reason/fast/InfiniteMind + Aaron voice/converse.
5. `workspace-integration-check` is now inside the static gate.

## Suggested add-ons (next cycle)

| Add-on | Why |
|---|---|
| `config/persona/converse-overlays.json` | Camera/pupil/voice lines live in the server; new presence phrases should not fork `speak_from_trace`. |
| `scripts/converse-billion-fuzz.py` | Modular overlay × intent matrix at 3T, companion to cam-reason fuzz. |
| In-process public-apis / google-trends search | Route smokes are in-process; catalog search still shells out. |
| FunASR enroll checksum in voice 3T | hash_dev covers the contract; live enroll still host-only. |
| dual_stream cache invalidation | mesh-params is cached in `activity_emit`; hook a reload if Aaron edits tracts live. |

## Do not

- Put InfiniteMind on the fast gate.
- Fold 1M fuzz into the static gate.
- Free-spend GPU / outbound from Cline.
