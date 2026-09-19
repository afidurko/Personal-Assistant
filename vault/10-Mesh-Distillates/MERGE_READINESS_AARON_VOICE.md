# Merge readiness — Aaron-only voice + add-ons

**Branch:** `cursor/aaron-voice-only-noise-b9c5`  
**Date:** 2026-09-19  
**Authorized:** Aaron — voice-only in noise + voice-gate add-ons + dual billion QA + merge prep

## Verdict

**READY TO MERGE**

Both billion connectome campaigns green (0 failures) after voice-gate add-ons. Trajectory OCL/CPV billion green. Vitest billion R1+R2 green (incl. add-on suggestion assertion). Suggestive implementations added. CI gate green. `neuron.aaron_voice_gate` healthy.

## Campaigns

| Pass | Tool | N | Failed | Rate | Artifact |
|---|---|---|---|---|---|
| A | `qa-loop.py` connectome | 1e9 | 0 | ~2.28M sims/s | `qa-cycles/20260919T194658Z-cycle-01/` · `connectome-sim-1b-pass1-voice-addons.json` |
| Fix + suggest | traffic weights · add-on suggestions · mesh-seed facts · QA standing docs | — | — | — | commit on this branch |
| B | `qa-loop.py` connectome | 1e9 | 0 | ~1.81M sims/s | `qa-cycles/20260919T195522Z-cycle-01/` · `connectome-sim-1b-pass2-voice-addons.json` |
| B′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~4.0M checks/s | `trajectory-1b-pass2-voice-addons.json` |
| B″ | vitest stress billion R1+R2 | 1e9×2 | 0 | — | `server/stress/billion-round*.test.ts` |

## Correctives / suggestive implementations shipped

1. Aaron-only voice gate (client spectral + server `/api/turn`) for noisy rooms  
2. **Add-ons:** adaptive noise · profile export/import · reject stats · health pulse · iOS `CamVoiceGate.swift`  
3. Traffic weights: `sense.aaron.voice` **3.5** · `sense.ios.mic` **2.75** · face 1.5  
4. SuggestionKind `identity-voice` + enroll / noisy-gate / **addons** suggestions  
5. Mesh-seed facts: `aaron_voice_gate_addons`, `aaron_voice_adaptive_noise`, identity addon fields  
6. CI: `scripts/aaron-voice-gate-check.py` (addons + iOS contract + neuron)  
7. QA standing suggestions document voice-addon merge steps  

## Pre-merge checklist (verified)

- [x] Pass-1 billion connectome (0 failures)
- [x] Pass-2 billion connectome (0 failures)
- [x] Trajectory billion (0 failures)
- [x] Vitest billion R1+R2 (0 failures)
- [x] `bash scripts/ci-connectome.sh`
- [x] `python3 scripts/aaron-voice-gate-check.py`
- [x] `python3 scripts/connectome-check.py`
- [x] Voice unit tests (aaron-voice-gate / addons / cam-converse / aaronVoiceGate)
- [x] `neuron.aaron_voice_gate` healthy in system-health

## Notes

- Health “warning” = empty integration submodules (expected in cloud checkout)  
- `switch.cam_enhance` remains hold  
- Typing still bypasses voice gate (`text_bypass`)  
- Adaptive threshold (0.91) engages after multi-speaker reject streaks
