# Connectors policy

## Prefer (nullclaw native)

- iMessage, email, Telegram, Discord, Slack, WhatsApp, web, CLI
- Tools: web_search, web_fetch, files, shell (sandboxed), delegate

## Local utilities (Jarvis)

- Submodule: `integrations/jarvis`
- Use for deterministic CLI chores (weather, conversions, file helpers, etc.)
- Invoked by `ops` / subagents — not a second brain
- Memory bridged to `mesh/jarvis` (see `config/integrations/jarvis.md`)

## Vision (PaddleDetection)

- Submodule: `integrations/paddledetection` @ `release/2.9`
- Invoked by `vision` / subagents on media you provide or approve
- Results distilled to `mesh/vision` (see `config/integrations/paddledetection.md`)
- Live iPhone camera is via **iOS companion** (below), not PaddleDetection directly

## iOS companion (Aaron face/voice + camera/mic)

- Scaffold: `companions/ios/` · policy: `config/integrations/ios-companion.md`
- Full design: `docs/IOS_IDENTITY.md`
- **Granted:** Aaron face recognition, Aaron voice recognition, iPhone camera, iPhone mic
- **Granted:** full photos + files access to learn Aaron’s look/sound and photo↔video same-person match (`identity/persistence/AARON_MEDIA_ACCESS.md`)
- Capture mode default: **tasked_only** for live camera/mic
- Status: **scaffolded — native app / enrollment pipeline not built yet**

## Cam face & voice (LLMAvatarTalk)

- Submodule: `integrations/llmavatartalk`
- RIVA ASR/TTS + Audio2Face (+ optional Unreal Metahuman)
- Portrait: `identity/persona/cam-face.jpg`
- Soft airy Argentine voice style in `config/persona/voice.json`
- Brain stays Cam/nullclaw + smart-second-brain

## Knowledge cortex (smart-second-brain)

- Submodule: `integrations/smart-second-brain`
- Obsidian vault search / graph / agents
- See `config/integrations/smart-second-brain.md`
- Set `config/persona/vault.json` → `vault_path`

## Careers boards

- **LinkedIn** — watch matching roles, draft Easy-Apply/outreach; submit only after Aaron approves
- **Indeed** — watch matching roles, draft applications; submit only after Aaron approves
- Credentials stay in local secrets (never commit)
- All opportunities logged to `mesh/careers` + tickets for cross-workspace persistence

## Bridge later (OpenClaw-inspired external plugins)

- SMS via phone companion
- Voice call / FaceTime via macOS/iOS bridge (overlaps iOS companion)
- Rich mobile node actions

Each bridge must:

1. Run as external channel plugin or companion (not core fork)
2. Declare approval requirements in this file
3. Log every outbound attempt to nulltickets events
4. Fail closed if human gate missing

## Lucida

Do not port Lucida services. If we need ASR/vision later, add a small
specialist tool or modern API — not the Java/Thrift stack.

## Enablement checklist (per connector)

- [ ] Credential stored securely
- [ ] Allowlist of peers
- [ ] Quiet hours honored
- [ ] Approval stage wired
- [ ] Test message/call in dry-run mode
- [ ] LinkedIn connected (careers watch)
- [ ] Indeed connected (careers watch)
