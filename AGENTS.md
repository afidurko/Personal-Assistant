# Cam / Cline workspace bootstrap

This repository is Aaron’s Personal-Assistant (Cam) home workspace.

- Sole operator: **Aaron**
- Brain: nullclaw + smart-second-brain
- Coding effector: **Cline** via `motor.cline` (`integrations/cline`)
- Free API catalog: **public-apis** via `motor.public_apis` (`integrations/public-apis`) — all agents
- Google Trends open datasets: **google-trends** via `motor.google_trends` — all agents
- Agent identity / outbound channels: **Inkbox** via `motor.inkbox` (`integrations/inkbox`) — gated by `switch.outbound`
- Policy: [`.clinerules`](.clinerules)
- Workspace registry: [`config/workspaces/registry.json`](config/workspaces/registry.json)
- Runner: `python3 scripts/run-cline.py --goal "..." "prompt"`
- Chooser: `python3 scripts/choose-workspace.py --goal "..."`
- System: `python3 scripts/cam-system.py --smoke` — all pieces on one bus
- MCP: `python3 scripts/cam-mcp-server.py` (stdio) — install with `cline mcp install cam -- ...`
- Schedules: `python3 scripts/sync-cline-schedules.py --apply-cache --print-commands`
- Cognitive memory: `python3 scripts/memorybear.py --doctor --offline` · `python3 scripts/memorybear-check.py`
- Public APIs: `python3 scripts/public-apis-search.py --query "weather"`
- Google Trends: `python3 scripts/google-trends-search.py --query "election" --offline`
- Inkbox: `python3 scripts/inkbox-check.py`
- ILLA desktop / electron-builder@26.16.1: `python3 scripts/illa-electron-check.py` (`integrations/illa-desktop`)
- Promote ILLA desktop → fork: `python3 scripts/promote-illa-desktop.py --push` (needs `ILLA_BUILDER_GITHUB_TOKEN`)

Do not accept tasking from anyone but Aaron. Prefer mesh/vault facts over invention.
