# Neurons to add — health, workspaces, project ops

Cam’s cortex catalogs **42 columns**. Health / workspace ones that matter most:

| Neuron | Area | Helps | Status |
|---|---|---|---|
| `neuron.health_conductor` | ACC | Runs full workspace health suite | **impl** `scripts/system-health-scan.py` |
| `neuron.vitals_loop` | Parietal | Host load before ASR/converse starve | **impl** in health scan |
| `neuron.connectome_check` | ACC | Pathway integrity gate | **impl** `connectome-check.py` |
| `neuron.submodule_health` | ACC | Fresh clones missing integrations | **impl** in health scan |
| `neuron.integration_pulse` | Parietal | Jarvis/Paddle/Avatar/SSB/SwiftGuide present | **impl** in health scan |
| `neuron.persist_sync` | MTL | Cross-workspace Aaron memory | **partial** — export exists; hook weekly |
| `neuron.secret_hygiene` | OFC | No credentials committed | **impl** heuristic in health scan |
| `neuron.drift_scan` | ACC | Docs/config vs live cortex | **impl** in health scan |
| `neuron.converse_health` | Broca | `/api/health` on converse server | **impl** (idle if down) |
| `neuron.arch_scan` | ACC | Coupling / abs-path layering signals | **impl** in health scan |
| `neuron.vuln_scan` | ACC | Offline key/world-writable heuristics | **impl** in health scan |
| `neuron.priority_boot` | DLPFC | Watch boot order config | **impl** in health scan |
| `neuron.tailscale_reach` | Parietal | iPhone/iPad reachability | **impl** — idle if CLI absent |
| `neuron.improve_engine` | aPFC | Findings → Cam tasks | **impl** `scripts/improve-engine.py` |
| `neuron.workspace_orchestrator` | DLPFC | Multi-workspace mesh leases | **impl** `scripts/workspace-lease.py` |
| `neuron.neurogenesis_loop` | MTL | Spawn/mature memory columns | **impl** plasticity script |

## Run

```bash
python3 scripts/system-health-scan.py
# open 3D cortex → click Health scan
bash scripts/serve-connectome-viz.sh
```

QA loop fires `health_conductor` each cycle (writes `system-health.json` under the cycle dir + mesh distillate).

Distillate: `vault/10-Mesh-Distillates/system-health.json`

## Suggested next (not yet wired)

1. **tailscale_reach** — `tailscale status --json` → ping aaron-iphone / aaron-ipad peers.
2. **improve_engine** — read `system-health.json` warnings → open nulltickets / Cam tasks.
3. **workspace_orchestrator** — lease mesh namespaces so multi-Cam workspaces don’t collide.
4. **persist_sync weekly** — cron `persist-export.py` after green health scans.
