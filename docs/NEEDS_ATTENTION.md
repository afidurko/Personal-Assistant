# Needs Attention agents — all coding workspaces

Aaron asked Cam to automate the **Needs Attention** tab and connect every coding workspace.

## What it is

Cursor’s Agents Window groups agents that need you (approvals, questions, unfinished review) under **Needs Attention**. Cam mirrors that intent inside the mesh:

| Piece | Role |
|---|---|
| `team.needs-attention` | Triage · workspace-connector · dispatcher · Aaron-escalator |
| `scan.needs_attention` | Scan workspace synthesizing urgent findings + registry connectivity |
| Attention mesh layer | `attention-triage`, `workspace-connector`, `attention-dispatcher` |
| UI panel | Cam home **Needs Attention** tab |
| `scripts/needs-attention.py` | Connect survey + dispatch plan across `config/workspaces/registry.json` |
| Schedule | `cam-daily-needs-attention` |
| MCP | `needs_attention` |

## Commands

```bash
python3 scripts/needs-attention-check.py
python3 scripts/needs-attention.py --connect
python3 scripts/needs-attention.py --dispatch-plan --write
python3 scripts/needs-attention.py --execute --write   # workspace-connector clears connectivity
python3 scripts/needs-attention.py --json
```

## Gates (never auto-cleared from Cline)

- `switch.cam_enhance` — functionality changes to Cam
- `switch.outbound` / Inkbox send
- Kill switch / money movement

Auto-clearable items are routed with `choose-workspace` → `run-cline` / issue-loop / swarm assign.

## Registry

- Team: `layers.agent_teams` → `team.needs-attention`
- Scan: `layers.scan_workspaces` → `scan.needs_attention`
- Coding targets: `layers.coding_workspaces` (all connected by workspace-connector)
