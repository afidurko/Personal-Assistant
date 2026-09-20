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
- Policy: [`.clinerules`](.clinerules)
- Workspace registry: [`config/workspaces/registry.json`](config/workspaces/registry.json)
- Runner: `python3 scripts/run-cline.py --goal "..." "prompt"`
- Chooser: `python3 scripts/choose-workspace.py --goal "..."`
- System: `python3 scripts/cam-system.py --smoke` — all pieces on one bus
- Home build plan (priorities · avatar tiers · auto-update): [`docs/CAM_HOME_BUILD.md`](docs/CAM_HOME_BUILD.md) — `python3 scripts/build-plan-check.py`
- MCP: `python3 scripts/cam-mcp-server.py` (stdio) — install with `cline mcp install cam -- ...`
- Schedules: `python3 scripts/sync-cline-schedules.py --apply-cache --print-commands`
- Cognitive memory: `python3 scripts/memorybear.py --doctor --offline` · `python3 scripts/memorybear-check.py`
- Public APIs: `python3 scripts/public-apis-search.py --query "weather"`
- Google Trends: `python3 scripts/google-trends-search.py --query "election" --offline`
- Inkbox: `python3 scripts/inkbox-check.py`
- ILLA desktop / electron-builder@26.16.1: `python3 scripts/illa-electron-check.py` (`integrations/illa-desktop`)
- Promote ILLA desktop → fork: `python3 scripts/promote-illa-desktop.py --push` (needs `ILLA_BUILDER_GITHUB_TOKEN`)
- Needs Attention (all coding workspaces): `python3 scripts/needs-attention.py --connect --dispatch-plan --write`
- Loops: `python3 scripts/loop-check.py` · `python3 scripts/loop-run.py --pattern daily-triage --level L1`

Do not accept tasking from anyone but Aaron. Prefer mesh/vault facts over invention.

## Cursor Cloud specific instructions

Cloud Agent `install` and `start` fields must be real shell commands that exist on PATH or in this repo. Do not put dashboard UI words such as `build` or `promote` in those fields.

- Config: [`.cursor/environment.json`](.cursor/environment.json)
- Install (idempotent, terminates): `./scripts/cloud-agent-install.sh` — runs `python3 scripts/cam-system.py --no-write`
- Start: omit unless a per-pod daemon is required (dev servers belong in `terminals`)
- Restricted egress: do not run `npm ci` / `npm install` during install until `registry.npmjs.org` is on the environment allowlist
- Higgsfield dry-run / `higgsfield-check` stay green when `integrations/higgsfield` is an empty submodule; live train still needs `git submodule update --init`
- Embodiment 3T uses pydantic-free `embodiment_lite` when `pypi.org` is blocked; full resolve needs `requirements-ci.txt`
