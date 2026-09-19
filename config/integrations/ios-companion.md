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

Match threshold default: **0.85** (`config/identity/aaron-voice.json` · `switch.identity`).

Mic converse turns must pass the Aaron voice gate (`docs/AARON_VOICE_GATE.md`) so surrounding speakers do not create Cam turns.

## Security
- TLS to Aaron’s Cam host only
- Enrollment samples never leave device unless Aaron opts in
- Pairing requires Aaron confirmation once (QR / setup code)
- Revoke from nullhub / kill switch clears session tokens
