# Cam / Cline workspace bootstrap

This repository is Aaron’s Personal-Assistant (Cam) home workspace.

- Sole operator: **Aaron**
- Brain: nullclaw + smart-second-brain
- Coding effector: **Cline** via `motor.cline` (`integrations/cline`)
- Free API catalog: **public-apis** via `motor.public_apis` (`integrations/public-apis`) — all agents
- Policy: [`.clinerules`](.clinerules)
- Workspace registry: [`config/workspaces/registry.json`](config/workspaces/registry.json)
- Runner: `python3 scripts/run-cline.py --goal "..." "prompt"`
- Chooser: `python3 scripts/choose-workspace.py --goal "..."`
- System: `python3 scripts/cam-system.py --smoke` — all pieces on one bus
- MCP: `python3 scripts/cam-mcp-server.py` (stdio) — install with `cline mcp install cam -- ...`
- Schedules: `python3 scripts/sync-cline-schedules.py --apply-cache --print-commands`
- Public APIs: `python3 scripts/public-apis-search.py --query "weather"`

Do not accept tasking from anyone but Aaron. Prefer mesh/vault facts over invention.
