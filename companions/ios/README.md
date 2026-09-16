# Cam iOS companion

Native iPhone app for **Aaron face/voice recognition**, **camera**, **microphone**, and **live converse with Cam**.

## Status
- Capabilities **granted** in mesh/boundaries
- Web companion works now: `companions/web/` + `docs/CAM_CONVERSE.md`
- Native Xcode project: create on Mac (scaffold below)

## Create project (Mac + Xcode)
```bash
# File → New → App (SwiftUI, iOS 17+)
# Bundle id: com.aaron.cam.companion
# Add to this folder as companions/ios/CamCompanion/
```

## Info.plist usage strings
- `NSCameraUsageDescription` — Cam uses the camera to recognize Aaron and for tasked vision.
- `NSMicrophoneUsageDescription` — Cam uses the microphone to recognize Aaron’s voice and converse.
- `NSSpeechRecognitionUsageDescription` — Cam turns your speech into text for conversation.
- `NSPhotoLibraryUsageDescription` — Cam reads your photos to learn your look (Aaron grant).

## Pair to Cam host
Prefer **Tailscale MagicDNS** (Aaron’s tailnet). Set host in `config/network/tailscale.json`, then:

```text
http://<cam-host-magicdns>:8787
```

See `docs/TAILSCALE.md`. Same `/api/*` contract as the web companion.

## First screens
1. Pair with Cam (host URL / setup code)
2. Enroll Aaron face
3. Enroll Aaron voice
4. Permissions: Camera + Microphone + Speech + Photos
5. Live converse (same loop as web companion)

## Swift stub (drop into project)

```swift
// CamAPI.swift
import Foundation

struct CamTurn: Codable {
  let cam: String
  let speak: Speak?
  struct Speak: Codable { let rate: Double?; let pitch: Double?; let lang: String? }
}

enum CamAPI {
  static var base = URL(string: "http://127.0.0.1:8787")!

  static func turn(text: String, source: String = "mic") async throws -> CamTurn {
    var req = URLRequest(url: base.appendingPathComponent("api/turn"))
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = try JSONEncoder().encode(["text": text, "transcript": text, "source": source])
    let (data, _) = try await URLSession.shared.data(for: req)
    return try JSONDecoder().decode(CamTurn.self, from: data)
  }
}
```

See `docs/CAM_CONVERSE.md`, `docs/IOS_IDENTITY.md`, `config/integrations/ios-companion.md`.
