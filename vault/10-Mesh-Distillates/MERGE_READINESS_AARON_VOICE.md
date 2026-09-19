# Merge readiness — Aaron-only voice (noisy environments)

**Branch:** `cursor/aaron-voice-only-noise-b9c5`  
**Date:** 2026-09-19  
**Authorized:** Aaron — voice-only in noise + dual billion QA + merge prep

## Verdict

**READY TO MERGE**

Both billion connectome campaigns green (0 failures). Trajectory OCL/CPV billion green. Vitest billion R1+R2 green. Suggestive implementations added. CI gate green.

## Campaigns

| Pass | Tool | N | Failed | Rate | Artifact |
|---|---|---|---|---|---|
| A | `qa-loop.py` connectome | 1e9 | 0 | ~2.46M sims/s | `qa-cycles/20260919T183344Z-cycle-01/` · `connectome-sim-1b-pass1-aaron-voice.json` |
| Fix + suggest | traffic weights, identity-voice suggestions, CI voice gate | — | — | — | commit on this branch |
| B | `qa-loop.py` connectome | 1e9 | 0 | ~1.78M sims/s | `qa-cycles/20260919T184125Z-cycle-01/` · `connectome-sim-1b-pass2-aaron-voice.json` |
| B′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~4.0M checks/s | `trajectory-1b-pass2-aaron-voice.json` |
| B″ | vitest stress billion R1+R2 | 1e9×2 | 0 | — | `server/stress/billion-round*.test.ts` |

## Correctives / suggestive implementations shipped

1. Aaron-only voice gate (client spectral + server `/api/turn`) for noisy rooms  
2. Traffic weights: `sense.aaron.voice` 3.0 · `sense.ios.mic` 2.5 · face 1.5  
3. SuggestionKind `identity-voice` + enroll / noisy-gate suggestions in `suggestions.ts`  
4. CI: `scripts/aaron-voice-gate-check.py` in `ci-connectome.sh`  
5. QA standing suggestions document Aaron-only merge steps  
6. Connectome `hotspot.aaron_voice_noise` + switch.identity aaron-only notes  

## Pre-merge checklist (verified)

- [x] Pass-1 billion connectome (0 failures)
- [x] Pass-2 billion connectome (0 failures)
- [x] Trajectory billion (0 failures)
- [x] Vitest billion R1+R2 (0 failures)
- [x] `bash scripts/ci-connectome.sh`
- [x] `python3 scripts/aaron-voice-gate-check.py`
- [x] `python3 scripts/connectome-check.py`
- [x] Voice unit tests (aaron-voice-gate / cam-converse / aaronVoiceGate)

## Notes

- Health “warning” = empty integration submodules (expected in cloud checkout)  
- `switch.cam_enhance` remains hold  
- Typing still bypasses voice gate (`text_bypass`)
