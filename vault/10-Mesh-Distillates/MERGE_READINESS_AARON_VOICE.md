# Merge readiness — Aaron-only voice gate

**Branch:** `cursor/aaron-voice-only-gate-0da0`  
**Date:** 2026-09-19  
**Authorized:** Aaron — implement FunASR Aaron-only listen + dual billion QA + merge prep

## Verdict

**READY TO MERGE**

Dual billion connectome campaigns green (0 failures). Trajectory OCL/CPV billion green (both passes). Aaron-voice billion green (both passes). Suggestive identity implementation added. CI gate green.

## Campaigns

| Pass | Tool | N | Failed | Rate | Artifact |
|---|---|---|---|---|---|
| A | `qa-loop.py` connectome | 1e9 | 0 | ~1.27M sims/s | `qa-cycles/20260919T183312Z-cycle-01/` |
| A′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~2.52M checks/s | `trajectory-1b-voice-pass1.json` |
| A″ | `aaron-voice-billion-fuzz.py` | 1e9 | 0 | ~8.66M checks/s | `aaron-voice-1b-pass1.json` |
| Fix + suggest | identity speak pathway, trajectory policy, voice fuzz, suggestions | — | — | — | this branch |
| B | `qa-loop.py` connectome | 1e9 | 0 | ~1.66M sims/s | `qa-cycles/20260919T185226Z-cycle-01/` |
| B′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~3.00M checks/s | `trajectory-1b-voice-pass2.json` |
| B″ | `aaron-voice-billion-fuzz.py` | 1e9 | 0 | ~4.29M checks/s | `aaron-voice-1b-pass2.json` |

## Correctives / suggestive implementations shipped

1. `motor.speak` requires `switch.identity`; presence hotspot + synapses wired  
2. Trajectory policy `speak_requires_aaron_identity` — strip speak on identity hold  
3. `scripts/aaron-voice-billion-fuzz.py` — surrounding-speaker invariants at billion scale  
4. Suggestive kind `identity` + `suggest-aaron-voice-only-gate` in `server/core/suggestions.ts`  
5. Traffic weights raised for `sense.aaron.voice` / `sense.ios.mic`  
6. CI: voice gate unit tests in `scripts/ci-connectome.sh`

## Pre-merge checklist (verified)

- [x] `bash scripts/ci-connectome.sh`
- [x] `python3 scripts/trajectory-policy-check.py` (6 policies)
- [x] `python3 scripts/memory-tier-check.py`
- [x] `python3 scripts/connectome-check.py` (264 edges, 0 hard)
- [x] Dual billion connectome campaigns
- [x] Dual trajectory billion campaigns
- [x] Dual Aaron-voice billion campaigns
- [x] Vitest `billion-round2` (identity suggestion)
- [x] Voice gate unit + converse smoke tests

## Notes

- Production Aaron identity still needs FunASR CAM++ enrollment on Aaron’s host  
- `hash_dev` backend is fuzz/tests only — not biometric identity  
- `switch.cam_enhance` remains **hold** by default  
- After merge: enroll WAVs via `scripts/aaron-voice-enroll.py` before relying on live mic  
