# iOS identity + camera / microphone

**Status:** requested by Aaron 2026-09-16 · **not shipping yet** · scaffolded

## Direct answer

| Capability | Have it today? | Notes |
|---|---|---|
| Recognize **Aaron’s** face | **No** | Need enrolled face print + iOS/Vision (or on-device model) |
| Recognize **Aaron’s** voice | **No** | Need enrolled voice print + speaker-ID (not just ASR transcript) |
| iPhone **camera** access | **No** | Needs native iOS companion with Camera permission |
| iPhone **microphone** access | **No** | Needs native iOS companion with Mic permission |
| Cam’s face / soft voice (assistant persona) | Yes (assets + LLMAvatarTalk plan) | That is Cam speaking/looking — not Aaron biometrics |
| Speech-to-text (ASR) | Planned via RIVA | Transcribes words; does **not** prove it’s Aaron |
| Object/person detection | PaddleDetection on **attached** media | Not live iPhone camera; not Aaron-ID |

## What Aaron asked for

1. Voice recognition of **Aaron**
2. Facial recognition of **Aaron**
3. Access to iPhone camera
4. Access to iPhone microphone

These are granted as standing capabilities (Aaron-only enrollment + use).

## Design (Null stack + iOS companion)

```text
iPhone (companion app)
  ├─ AVFoundation camera  → frames / FaceTime preview
  ├─ AVAudioEngine mic    → audio buffers
  ├─ Local face match     → aaron_face_score
  └─ Local speaker-ID     → aaron_voice_score
           │
           ▼  encrypted channel
Cam sensory periphery
  sense.ios.camera / sense.ios.mic / sense.aaron.face / sense.aaron.voice
           │
           ▼
switch.tasking + switch.identity  → only Aaron biometrics unlock tasking when remote
           │
           ▼
centers → motors (unchanged)
```

### Rules
- Biometrics enroll **Aaron only**; never clone Aaron’s voice/face for outbound impersonation unless Aaron asks
- Camera/mic are **tasked** sensors (not always-on surveillance) unless Aaron explicitly enables a monitoring task
- Face/voice match strengthens `switch.tasking` (reject non-Aaron)
- Fail closed if companion offline or match score below threshold
- All captures logged to mesh/tickets (path + purpose); raw media stays on device by default

## Build plan

1. **iOS companion app** (`companions/ios/`) — SwiftUI + AVFoundation; Info.plist `NSCameraUsageDescription` / `NSMicrophoneUsageDescription`
2. **Enrollment flow** — Aaron records face + voice samples on-device; store embeddings in Keychain / Secure Enclave–backed store
3. **Match APIs** — `POST /spike/aaron.face` · `POST /spike/aaron.voice` with score + device id
4. **Connectome wiring** — senses + `switch.identity` (already scaffolded in config)
5. **Optional** — Apple Speech framework for on-device ASR fallback when RIVA studio is down

## Repo pointers
- Companion scaffold: `companions/ios/README.md`
- Integration policy: `config/integrations/ios-companion.md`
- Persistence: `mesh/facts.ios_aaron_identity = true`
