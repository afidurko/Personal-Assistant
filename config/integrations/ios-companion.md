# iOS companion — Aaron identity + camera/mic

## Purpose
Native iPhone / web bridge so Cam can:
- Capture camera / microphone when Aaron tasks it **or opens the converse UI**
- Hold a live conversation (ASR → Cam reply → TTS)
- Verify **Aaron’s** face and voice (speaker + face match)
- Feed spikes into the connectome sensory layer

Web companion (ready now): `companions/web/` + `docs/CAM_CONVERSE.md`  
Native iOS: same `/api/*` contract once Xcode app is created.

## Not this
- Not Cam’s avatar face/voice (that’s LLMAvatarTalk)
- Not always-on surveillance
- Not cloud face search of strangers

## Permissions (Info.plist)
- `NSCameraUsageDescription` — “Cam uses the camera so Aaron can be recognized and so tasked vision works.”
- `NSMicrophoneUsageDescription` — “Cam uses the microphone so Aaron’s voice can be recognized and so tasked listening works.”
- Optional: Speech Recognition / Face ID usage strings if using Apple frameworks

## Endpoints (companion → Cam host)
| Spike | Payload |
|---|---|
| `sense.ios.camera` | frame ref / thumbnail hash, purpose, aaron_face_score? |
| `sense.ios.mic` | audio ref / duration, purpose, aaron_voice_score? |
| `sense.aaron.face` | score ∈ [0,1], device_id, enrolled=true |
| `sense.aaron.voice` | score ∈ [0,1], device_id, enrolled=true · or WAV via `/api/voice/gate` |

Match threshold default: **0.85** quiet / **0.88** noisy (configurable in `config/identity/aaron-voice-gate.json`). Server FunASR CAM++ gate also uses **0.85** (`config/identity/aaron-voice.json` · `switch.identity`).

## Aaron-only in noisy rooms

Cam must recognize **Aaron’s voice only**. Surrounding conversation is filtered via complementary layers:

1. Enroll Aaron once (~10s quiet speech) in the companion / home UI (spectral browser gate)
2. On each mic utterance, on-device spectral voiceprint scores vs enrollment
3. Below threshold (or multi-speaker hint) → **ignore** — no Cam reply
4. Server `/api/turn` also rejects mic turns without a passing `aaron_voice_score`; FunASR CAM++ gate (`docs/AARON_VOICE_GATE.md`) covers host-side WAV enrollment
5. Typing still works (`text_bypass`)

Config: `config/identity/aaron-voice-gate.json` · `config/identity/aaron-voice.json`  
Hotspot: `hotspot.aaron_voice_noise` · Sense: `sense.aaron.voice` · Switch: `switch.identity`

## Security
- TLS to Aaron’s Cam host only
- Enrollment samples never leave device unless Aaron opts in
- Pairing requires Aaron confirmation once (QR / setup code)
- Revoke from nullhub / kill switch clears session tokens
- Voiceprints stay in on-device storage by default (`localStorage`)
