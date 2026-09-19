# Cline integration — shared coding effector for every agent & workspace

Source: [afidurko/cline](https://github.com/afidurko/cline)  
Path: [`integrations/cline`](../../integrations/cline) (git submodule)  
Upstream product: [cline.bot](https://cline.bot) (CLI · SDK · VS Code · Desktop · JetBrains)

## Role in the team

Cline is Cam’s **autonomous coding motor** — plan/act edits, shell, multi-agent
teams, schedules, and headless CI. It is **not** the brain.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / persistence | nulltickets |
| Scheduling (team-level) | nullboiler |
| Human override | Aaron via nullhub / kill switch |
| Code edit / repo agent sessions | **Cline** (CLI / SDK / IDE) |
| Workspace path resolution | `config/workspaces/registry.json` + `scripts/choose-workspace.py` |
| Motor fire | `scripts/run-cline.py` |

**All Cam roles and subagents** may invoke `motor.cline` when the work needs
repo edits, tests, or multi-file coding — not only a dedicated coding role.

## Runtime surface (implemented)

| Piece | Path |
|---|---|
| Workspace registry | `config/workspaces/registry.json` |
| Standing schedules | `config/workspaces/schedules.json` |
| Chooser | `scripts/choose-workspace.py` / `scripts/cam_workspaces.py` |
| Motor runner | `scripts/run-cline.py` |
| Rules propagator | `scripts/install-cline-rules.py` |
| MCP bridge | `scripts/cam-mcp-server.py` |
| Schedule sync | `scripts/sync-cline-schedules.py` |
| Ticket export | `scripts/export-cline-tickets.py` |
| Session distillate | `scripts/sync-cline-session.py` |
| Cam policy | `.clinerules` · `AGENTS.md` · `.cursor/rules/cam-cline.mdc` |

## Install (on Aaron’s machine / any workspace)

```bash
git submodule update --init --recursive
npm i -g cline   # or build integrations/cline with Bun
cline auth       # or provider env vars
python3 scripts/install-cline-rules.py --force
python3 scripts/sync-cline-schedules.py --apply-cache --print-commands
# optional MCP
cline mcp install cam -- python3 "$PWD/scripts/cam-mcp-server.py"
python3 scripts/run-cline.py --doctor --dry-run
```

## How every agent uses it

1. Aaron tasks Cam (or a standing goal fires).
2. `connectome-route.py` may select `hotspot.coding` and attach a **workspace** choice.
3. Cam fires `motor.cline` via:

```bash
python3 scripts/run-cline.py --goal "implement feature" --yolo "Implement X and run tests"
# or force a registry id / path
python3 scripts/run-cline.py --workspace-id cline --yolo "bun run cli doctor"
python3 scripts/run-cline.py --path /other/repo --yolo "fix tests"
```

4. Runner sets per-workspace `CLINE_DATA_DIR`, binds a ticket under
   `identity/persistence/tickets/`, streams `--json`, records `mesh/cline`.
5. Curator exports tickets: `python3 scripts/export-cline-tickets.py`.

### CLI flags note

One-shot Cline uses `--cwd` (Cam runner passes it). Cron schedules use
`cline schedule ... --workspace <path>` (see schedule sync).

### Multi-workspace teams

```bash
python3 scripts/run-cline.py \
  --team-name cam-mesh \
  --workspace-id personal-assistant \
  --secondary cline,smart-second-brain \
  --yolo "Coordinate the change; keep Cam policy"
```

## Workspace chooser (task → repo)

| Signal examples | Workspace id |
|---|---|
| connectome, vault, mesh, cam | `personal-assistant` |
| cline sdk/cli, @cline/ | `cline` |
| obsidian plugin, second brain | `smart-second-brain` |
| jarviscli | `jarvis` |
| paddledetection | `paddledetection` |
| audio2face, riva | `llmavatartalk` |
| voicestudio, omnivoice, voice cloning, local tts | `voicestudio` |
| Explicit Aaron path | that path wins |

```bash
python3 scripts/choose-workspace.py --goal "refactor cline cli auth"
python3 scripts/choose-workspace.py --list
```

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/projects` | registry projects (`choose-workspace.py --mesh-projects`) |
| `mesh/cline` | sessions, workspaces, schedules |
| `mesh/cline.schedules` | standing cron mirrors (`sync-cline-schedules.py`) |
| `mesh/runs` | ticket distillates / cline-runs |

## MCP tools (Cam → Cline)

`list_workspaces`, `choose_workspace`, `mesh_search`, `mesh_put`, `vault_search`,
`connectome_route`, `kill_switch_status`, `ticket_list`

## Boundaries

- Only Aaron may assign the original task; Cam/Cline finish under standing autonomy
- Kill switch: `run-cline.py --kill` refuses motor
- No outbound messaging / job submit / spend via Cline
- Provider API keys stay in local secrets / env — never commit
- Prefer Jarvis for trivial deterministic chores; prefer Cline for multi-file code

## Cross-workspace checklist

1. `persist-import` (auto-runs rules install + schedule sync)
2. `git submodule update --init --recursive`
3. Confirm `.clinerules` / `AGENTS.md` / `.cursor/rules/cam-cline.mdc`
4. Re-attach LLM provider credentials (`cline auth`)
5. `python3 scripts/run-cline.py --doctor --dry-run` then a live doctor when ready
6. Optional: pipe `sync-cline-schedules.py --print-commands` into a shell after auth
