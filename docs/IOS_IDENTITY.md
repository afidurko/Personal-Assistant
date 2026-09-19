# iOS identity + camera / microphone

**Status:** requested by Aaron 2026-09-16 · **not shipping yet** · scaffolded

## Direct answer

| Capability | Have it today? | Notes |
|---|---|---|
| Recognize **Aaron’s** face | **Enrollment started** | Photos enrolled; live matcher still companion-side |
| Recognize **Aaron’s** voice | **Gate implemented** | Enroll WAVs on host (`scripts/aaron-voice-enroll.py`); FunASR CAM++ for production |
| iPhone **camera** access | **Yes via web companion** | Native iOS app still scaffold; browser camera works on device |
| iPhone **microphone** access | **Yes via web companion** | Open `docs/CAM_CONVERSE.md` — run server on Aaron’s Mac/phone browser |
| Live converse with Cam | **Yes via web companion** | Mic → transcript → Cam reply → soft TTS |
| Cam’s face / soft voice (assistant persona) | Yes | Portrait + browser TTS / RIVA plan |
| Speech-to-text (ASR) | Browser Speech API now; FunASR/RIVA later | Runs **after** Aaron voice gate on server |
| Object/person detection | PaddleDetection on media | Plus Aaron photo enrollment |

**Important:** Cloud Agent VMs have no mic. Live talk requires running `cam-converse-server.py` on Aaron’s machine.

## What Aaron asked for

1. Voice recognition of **Aaron**
2. Facial recognition of **Aaron**
3. Access to iPhone camera
4. Access to iPhone microphone
5. **Full access to photos and files** to learn Aaron’s look/sound, including matching a face in a photo to the same person talking in a video

These are granted as standing capabilities (Aaron-only enrollment + use).

## Photo / file enrollment (granted 2026-09-16)

```text
Photos library + files
  ├─ still faces     → face embeddings
  ├─ video faces     → face track + match to stills
  └─ video/audio     → speaker embedding
           │
           ▼
  Aaron identity engram (photo ↔ video ↔ voice linked)
           │
           ▼
  switch.identity / sense.aaron.face / sense.aaron.voice
```

Details: `identity/persistence/AARON_MEDIA_ACCESS.md` · local refs: `identity/aaron/`

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

1. **Web companion (ready)** — `companions/web/` + `scripts/cam-converse-server.py` — mic/camera/converse in browser
2. **Aaron-only voice gate (ready scaffold)** — `docs/AARON_VOICE_GATE.md` · FunASR CAM++ enroll on host
3. **iOS companion app** (`companions/ios/`) — SwiftUI + AVFoundation; same `/api/*` as web
4. **Enrollment flow** — Aaron face (done from photos) + **voice samples on-device/host**
5. **Match APIs** — `POST /api/spike/aaron.face` · `POST /api/spike/aaron.voice` · `POST /api/voice/gate`
6. **RIVA studio** — TTS/Audio2Face for full presence; hearing can stay on FunASR gate

## Repo pointers
- Voice gate: `docs/AARON_VOICE_GATE.md` · `config/integrations/funasr.md`
- Live converse: `docs/CAM_CONVERSE.md`
- Companion scaffold: `companions/ios/README.md` · `companions/web/`
- Integration policy: `config/integrations/ios-companion.md`
- Persistence: `mesh/facts.ios_aaron_identity = true`
