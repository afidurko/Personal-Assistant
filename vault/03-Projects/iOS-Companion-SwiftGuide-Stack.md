# Cam iOS companion — stack from SwiftGuide

Distilled from `integrations/swiftguide` (2026 ecosystem report + architecture maps).
Full picks: `config/connectome/mindmap.json` → `ios_companion_stack_picks`.

## Prefer (2026)

- **UI / state:** SwiftUI + TCA (`swift-composable-architecture`)
- **Local-first:** SwiftData and/or GRDB; KeychainAccess for secrets
- **Knowledge text:** Down / Splash / native Markdown attributed strings
- **Talk to Cam:** URLSession over Tailscale; optional Starscream if converse needs WS
- **Hygiene:** SwiftLint + snapshot testing

## Avoid for new code

RxSwift, PromiseKit, ReSwift, SwiftyUserDefaults wrappers, heavy UIKit-form kits

## Connectome path

`sense.swiftguide.map` → `center.cartography` → `center.docs` / `center.research` → `motor.docs` + `motor.vault`

Related: [[2026-09-16-SwiftGuide-brain-map]] · `companions/ios/README.md`
