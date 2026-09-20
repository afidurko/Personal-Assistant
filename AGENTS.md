# Cam / Cline workspace bootstrap

This repository is Aaron’s Personal-Assistant (Cam) home workspace.

- Sole operator: **Aaron**
- Brain: nullclaw + smart-second-brain
- Coding effector: **Cline** via `motor.cline` (`integrations/cline`)
- Free API catalog: **public-apis** via `motor.public_apis` (`integrations/public-apis`) — all agents
- Google Trends open datasets: **google-trends** via `motor.google_trends` — all agents
- Agent identity / outbound channels: **Inkbox** via `motor.inkbox` (`integrations/inkbox`) — gated by `switch.outbound`
- Multi-node GPU training: **higgsfield** via `motor.higgsfield` (`integrations/higgsfield`) — gated by `switch.cam_enhance`
- Agent loops: **loop-engineering** via `motor.loop` (`integrations/loop-engineering`) — L1 report automations
- Proactive follow-through: **Cam Instinct** via `motor.instinct` (`scripts/instinct.py`) — persistent job ledger + draft-only follow-ups
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
- Instinct: `python3 scripts/instinct.py scan --write` · `python3 scripts/instinct.py brief` · `python3 scripts/instinct-check.py` · tests: `python3 -m unittest scripts.test_instinct`
- Needs Attention (all coding workspaces): `python3 scripts/needs-attention.py --connect --dispatch-plan --write`
- Loops: `python3 scripts/loop-check.py` · `python3 scripts/loop-run.py --pattern daily-triage --level L1`

Do not accept tasking from anyone but Aaron. Prefer mesh/vault facts over invention.
