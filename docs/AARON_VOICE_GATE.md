# Aaron-only voice gate

**Status:** implemented scaffold (2026-09-19) · **production identity requires FunASR CAM++ enroll on Aaron’s machine**

## Goal

Cam must recognize **Aaron’s voice only**. In a noisy room or group conversation, surrounding speakers are ignored — they must not create Cam turns.

## Pipeline

```text
mic
 → energy VAD (segments)
 → speaker embedding (FunASR CAM++ in production)
 → cosine vs enrolled Aaron templates / centroid
 → threshold (default 0.85, switch.identity)
 → accept Aaron segments only
 → sense.aaron.voice + optional ASR / converse turn
```

Anonymous diarization (`spk=0`) is **not** identity. Face enrollment is separate (`sense.aaron.face`).

## Repo pieces

| Piece | Path |
|---|---|
| Policy config | `config/identity/aaron-voice.json` |
| Core library | `scripts/aaron_voice_gate.py` |
| Enroll CLI | `scripts/aaron-voice-enroll.py` |
| Verify CLI | `scripts/aaron-voice-verify.py` |
| Tests | `scripts/test_aaron_voice_gate.py` |
| Converse gate | `scripts/cam-converse-server.py` |
| Web capture | `companions/web/app.js` |
| Integration note | `config/integrations/funasr.md` |

## Bring-up on Aaron’s host

1. Install FunASR + torch (CPU OK for enroll/verify; GPU optional).
2. Capture 3–5 clean Aaron-only WAVs → `identity/aaron/local/voice/samples/`.
3. `python3 scripts/aaron-voice-enroll.py samples/*.wav`
4. Probe with a second Aaron clip and a non-Aaron clip via `aaron-voice-verify.py`.
5. Calibrate `threshold` in `config/identity/aaron-voice.json` if needed.
6. Run `python3 scripts/cam-converse-server.py` — mic turns require gate pass.

## Fail-closed rules

- Not enrolled → mic turns **rejected** (text still works)
- Backend unavailable → reject when `fail_closed: true`
- Score &lt; threshold → reject (`non_aaron_or_below_threshold`)
- Mixed audio → Aaron segments kept; others dropped (`aaron_match_with_surrounding_dropped`)

## Limits

- Heavy overlap (simultaneous talk) is harder than turn-taking; gate helps, does not perfectly separate.
- Very short particles (“yeah”) may score low — prefer longer enrollment phrases.
- `hash_dev` backend is for unit tests only — never treat it as biometric identity.
