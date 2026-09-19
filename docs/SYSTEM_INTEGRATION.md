# Cam system integration

How the pieces compose **one** live Cam for Aaron.

## Bus

```text
Aaron (mic / text / camera)
        │
        ▼
  home UI (Vite)  ←→  server :8787  ←→  WebSocket mesh state
        │                    │
        │                    ├─ CamConverse (reply)
        │                    ├─ SystemBridge ──► connectome-route.py
        │                    │                 └─► live-activity / activity-events
        │                    ├─ ScanOrchestrator (workspaces)
        │                    └─ CamAutonomy (self-improve spawn)
        ▼
  3D cortex (DTI) ← polls /api/runtime/live-activity
```

Inventory: [`config/system/pieces.json`](../config/system/pieces.json)  
Glue: [`server/core/system-bridge.ts`](../server/core/system-bridge.ts)  
CLI: `python3 scripts/cam-system.py` · `python3 scripts/cam-system.py --smoke`

## What “wired together” means

| From | To | Effect |
|---|---|---|
| `/api/turn` | connectome + activity | Chat/mic turns light language tracts and route a motor plan |
| `/api/spike/mic` | `sense.ios.mic` | Mic open spikes auditory columns |
| `/api/spike/camera` | `sense.ios.camera` | Camera spikes visual tracts |
| `/api/system` | piece inventory | Home UI + health see one status surface |
| autonomy tick | live-activity | Background spawn keeps cortex warm |
| health / improve | vault distillates | Ops loop feeds the same activity bus |

Python `cam-converse-server.py` and the TypeScript home server now share the same
activity + connectome contracts so either entrypoint lights the cortex.

## Verify

```bash
python3 scripts/cam-system.py --smoke
python3 scripts/workspace-integration-check.py
python3 scripts/connectome-check.py
python3 scripts/swarm-check.py
npx vitest run server/core/system-bridge.test.ts
npm run dev   # home :5173 · API :8787
curl -s http://127.0.0.1:8787/api/system | jq .overall
```

## Boot order

See `boot_order` in `config/system/pieces.json` and `config/priority-boot.json`
(`system_integration` step). Persistence → connectome → swarm/teams → tools →
mesh server → bridge → converse → home/cortex → health.

## Non-goals

- Standing up live nulltickets/nullclaw in this PR (still listed in architecture build order)
- Merging open VoiceStudio / Aaron-voice / Pupil / MemoryBear branches (separate PRs)
- Filling empty git submodules in cloud checkouts (soft warnings remain OK)
