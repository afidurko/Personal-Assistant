# Cam iOS companion (scaffold)

Native iPhone app for **Aaron face/voice recognition** and **camera/microphone** access.

## Status
Scaffold only — no Xcode project checked in yet. Create with:

```bash
# on a Mac with Xcode
mkdir -p companions/ios
# File → New → App (SwiftUI, iOS 17+)
# Bundle id suggestion: com.aaron.cam.companion
```

## Required capabilities
- Camera (AVCaptureSession)
- Microphone (AVAudioEngine)
- On-device face enrollment + match (Vision / custom embedding)
- On-device voice enrollment + speaker-ID
- Secure pairing to Cam host

## First screens
1. Pair with Cam (setup code)
2. Enroll Aaron face (guided)
3. Enroll Aaron voice (guided phrases)
4. Permissions: Camera + Microphone
5. Live: match indicator + “task Cam” button

## Privacy copy (required by App Store)
Camera and mic are used so Cam can recognize Aaron and run vision/listening **only when Aaron tasks it** (or when Aaron enables a standing monitor task).

See `docs/IOS_IDENTITY.md` and `config/integrations/ios-companion.md`.
