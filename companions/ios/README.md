# Cam iOS companion — iPhone & iPad (no Mac required for on-device talk)

## Your gear
- **iPhone** + **iPad** · Tailscale on · **no Mac**
- Config: `config/network/ios-devices.json` · `docs/IOS_DEVICES.md`

## Use Cam now (Safari on-device)
1. Get the `companions/web/` files onto the device (Files app / repo sync / host URL)
2. Open `index.html` in **Safari**, or open Cam URL if a host is running
3. Share → **Add to Home Screen**
4. Open **Cam** → **Enable mic & talk**

On-device mode replies locally when no Cam server is reachable.

## Tailscale names (edit to match Tailscale app)
- iPhone: `aaron-iphone`
- iPad (preferred host later): `aaron-ipad`

## Optional shared server on iPad
Use **a-Shell** on iPad to run `scripts/cam-converse-server.py`, then open `http://aaron-ipad:8787` on iPhone.

## Native Xcode app
Still needs a Mac — scaffold/API only for now (`CamAPI` talks to same `/api/turn`).

Aaron-only voice gate contract: `companions/ios/CamVoiceGate.swift`
- Same fields as web: `aaron_voice_score`, `enrolled`, `multi_speaker_hint`
- Adaptive noise threshold bump mirrors `addons.adaptive_noise`
- Native SpeakerRecognition can replace spectral scoring later without changing `/api/turn`

Stack guidance distilled from SwiftGuide: `vault/03-Projects/iOS-Companion-SwiftGuide-Stack.md`
and `config/connectome/mindmap.json` (`ios_companion_stack_picks`). Prefer SwiftUI + TCA,
local-first (SwiftData/GRDB), minimal deps.

See `docs/CAM_CONVERSE.md`, `docs/TAILSCALE.md`, `docs/IOS_DEVICES.md`.
