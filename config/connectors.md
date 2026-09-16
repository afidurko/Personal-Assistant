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
- Camera / continuous monitor / call-video analysis require human approval

## Bridge later (OpenClaw-inspired external plugins)

- SMS via phone companion
- Voice call / FaceTime via macOS/iOS bridge
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
