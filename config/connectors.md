# Connectors policy

## System integration (all pieces on one bus)

- Inventory: `config/system/pieces.json`
- Bridge: `server/core/system-bridge.ts` — home `/api/turn` + mic/camera spikes
  route through connectome and light DTI live-activity
- Status: `GET /api/system` · CLI `python3 scripts/cam-system.py --smoke`
- Docs: `docs/SYSTEM_INTEGRATION.md`
- Home UI: System pulse panel lists every piece

## Prefer (nullclaw native)

- iMessage, email, Telegram, Discord, Slack, WhatsApp, web, CLI
- Tools: web_search, web_fetch, files, shell (sandboxed), delegate

## Local utilities (Jarvis)

- Submodule: `integrations/jarvis`
- Use for deterministic CLI chores (weather, conversions, file helpers, etc.)
- Invoked by `ops` / subagents — not a second brain
- Memory bridged to `mesh/jarvis` (see `config/integrations/jarvis.md`)

## Coding agent (Cline) — all agents & workspaces

- Submodule: `integrations/cline` ← [afidurko/cline](https://github.com/afidurko/cline)
- Shared coding effector (`motor.cline`): CLI / SDK / IDE / headless
- **Every** Cam role and subagent may invoke it for multi-file code work
- Registry: `config/workspaces/registry.json`
- Runner: `scripts/run-cline.py` (sandboxes, tickets, `--cwd`)
- Chooser: `scripts/choose-workspace.py`
- Rules install: `scripts/install-cline-rules.py`
- MCP: `scripts/cam-mcp-server.py`
- Schedules: `config/workspaces/schedules.json` + `scripts/sync-cline-schedules.py`
- Policy: `.clinerules` · `AGENTS.md` · `.cursor/rules/cam-cline.mdc`
- Mesh: `mesh/cline`, `mesh/projects`, `mesh/runs`
- Details: `config/integrations/cline.md`
- Not the brain — nullclaw remains executive; Cline executes code

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
- **Live converse:** **ENABLED** by Aaron — `identity/persistence/CAM_CONVERSE_ENABLED.md`
- Network: **Tailscale** — `docs/TAILSCALE.md`
- Capture mode: **standing_on** (`switch.ios_capture`)
- UI: `docs/CAM_CONVERSE.md` (`companions/web/` + `scripts/cam-converse-server.py`)
- Status: **feature on**; iPhone reaches Cam host over Tailscale

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

## Knowledge cartography (SwiftGuide)

- Submodule: `integrations/swiftguide`
- Hierarchical mind maps + 2026 Swift ecosystem report
- Dual-lens brain map: CNS anatomy ↔ mind-map trees
- iOS companion stack picks in `config/connectome/mindmap.json`
- See `config/integrations/swiftguide.md`
- Spikes: `sense.swiftguide.map` → `area.apfc` (cartography columns)

## Careers boards

- **LinkedIn** — watch matching roles, draft Easy-Apply/outreach; submit only after Aaron approves
- **Indeed** — watch matching roles, draft applications; submit only after Aaron approves
- Credentials stay in local secrets (never commit)
- All opportunities logged to `mesh/careers` + tickets for cross-workspace persistence

## Google Scholar (literature + citations)

- Policy: `config/integrations/google-scholar.md`
- Config: `config/integrations/google-scholar.json`
- Sense: `sense.web.scholar` · Hotspot: `hotspot.google_scholar`
- Bridge: **SerpAPI** (`SERPAPI_API_KEY` in local `.env` — never commit)
- Used by Information + Research (+ AGI scout when AI/AGI-relevant)
- Scripts: `scripts/scholar-search.py`, `scripts/pack-scholar-result.py`
- Distills to `mesh/research` + `vault/04-Research/scholar/`

## Public APIs (free API catalog — all agents)

- Source: [afidurko/public-apis](https://github.com/afidurko/public-apis)
- Policy: `config/integrations/public-apis.md`
- Config: `config/integrations/public-apis.json`
- Path: `integrations/public-apis` (git submodule)
- Sense: `sense.catalog.public_apis` · Hotspot: `hotspot.public_apis` · Motor: `motor.public_apis`
- **Available to all roles and subagents** — discover free/public HTTP APIs before inventing endpoints
- Scripts: `scripts/public-apis-search.py`, `scripts/pack-public-apis-result.py`, `scripts/public-apis-check.py`, `scripts/public-apis-addon.py`
- MCP: `public_apis_search` · `public_apis_addon` via `scripts/cam-mcp-server.py`
- Add-ons: `config/integrations/public-apis-addons.json` (allowlisted thin wrappers)
- Distills to `mesh/tools` + `vault/04-Research/public-apis/`
- No catalog API key; individual listed APIs may need their own local secrets
- Free-form URL fetch from catalog hits is forbidden — only allowlisted add-ons may call HTTP

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
- [ ] Google Scholar connected (SerpAPI key in local `.env`)
- [ ] Optional: Scholar `profile.author_id` set for Aaron citation watch
