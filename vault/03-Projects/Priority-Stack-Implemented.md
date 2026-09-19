# Priority stack — implemented

| Priority | Item | Status | Artifact |
|---|---|---|---|
| 0 | Open-question defaults | done (interim) | `mesh-params.json` |
| 1 | `tailscale_reach` | done (idle if no CLI) | `system-health-scan.py` |
| 2 | `improve_engine` | done | `scripts/improve-engine.py` → Improve-Engine-Tasks.md |
| 3 | `persist_sync` weekly | done | health hook after green |
| 4 | Submodule init | done | jarvis/paddle/avatar/ssb checked out |
| 5 | Real activity feed | done | `activity-events.jsonl` + live-activity merge |
| 6 | Camera presets | done | Cor / Ax / Sag buttons |
| 7 | Fiber LOD | done | LOD toggle + mobile default low |
| 8 | Grouped Fire buttons | done | Tasks / Systems / Utility |
| 9 | `workspace_orchestrator` | done | `scripts/workspace-lease.py` |
| 10 | Fornix consolidation | done | `scripts/fornix-consolidate.py` |
| 11 | Dual-stream router | done | `scripts/dual-stream-router.py` |
| polish | Favicon + myelination persist | done | SVG data-URI · localStorage |
| opt | Converse → live mesh | done | `/api/turn` + mic/camera → `activity-events.jsonl` |

## Run
```bash
python3 scripts/system-health-scan.py          # + improve + persist + fornix + live-activity
python3 scripts/improve-engine.py
python3 scripts/workspace-lease.py acquire --workspace demo
python3 scripts/dual-stream-router.py speak
python3 scripts/fornix-consolidate.py --force
python3 scripts/cam-converse-server.py
# other terminal:
curl -s -X POST http://127.0.0.1:8787/api/turn -H 'content-type: application/json' \
  -d '{"text":"hi cam","source":"text"}'
bash scripts/serve-connectome-viz.sh
```
