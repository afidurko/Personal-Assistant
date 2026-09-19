# Cam system integration (organism bus)

How the pieces compose **one** live Cam for Aaron — upgraded beyond glue.

## Bus (priority build)

```text
Aaron (text | mic+voice_score | camera)
        │
        ▼
  identity gate ──reject──► ACC pulse (no ticket, no memory)
        │ pass
        ▼
  HMO primary recall (vault/persona lean hits)
        │
        ▼
  ConnectomeKernel (in-process TypeScript)
        ├─ hotspot + switches
        ├─ dual-stream winner (dorsal/ventral)
        ├─ MAP PFC stages
        ├─ OCL/CPV trajectory physics
        └─ circadian intensity
        │
        ▼
  activity → live-activity + /ws activity_update → 3D cortex
        │
        ▼
  MotorExecutor (causal deltas)
        ├─ live: mesh, vault, public_apis(offline), slm/dl stubs
        ├─ dry-run: outbound / jobs / enhance / cline / speak
        └─ plasticity LTP/LTD + workspace lease broadcast
```

Inventory: [`config/system/pieces.json`](../config/system/pieces.json)  
Kernel: [`server/core/connectome-kernel.ts`](../server/core/connectome-kernel.ts)  
Motors: [`server/core/motor-executor.ts`](../server/core/motor-executor.ts)  
Bridge: [`server/core/system-bridge.ts`](../server/core/system-bridge.ts)  
Envelope: `python3 scripts/flight-envelope.py` · `POST /api/system/rehearse`

## Shipped upgrades (this branch)

| # | Upgrade | Status |
|---|---|---|
| 1 | In-process connectome kernel | **shipped** |
| 2 | Causal motor executor + plasticity | **shipped** (safe motors live; gated dry-run) |
| 3 | Aaron identity gate on mic | **shipped** (score required; FunASR weights blocked) |
| 4 | HMO primary recall on turn | **shipped** (path/vault; MemoryBear API blocked) |
| 5 | Cortex WS push (`activity_update`) | **shipped** |
| 6 | Piece SLOs + Tailscale probe | **shipped** (cheap probes) |
| 7 | Nulltickets synaptic body | **blocked** — no live null stack in checkout |
| 8 | Dual-stream personality physics | **shipped** |
| 9 | Foveated world (Pupil) | **blocked** — PR #18 |
| 10 | Flight envelope rehearsal | **shipped** |
| 11 | sLM/DL live cortex | **stub shipped** — heuristic until weights |
| 12 | MAP planner visible on routes | **shipped** |
| 13 | Fornix dream cycle | **script exists** — `scripts/fornix-consolidate.py` |
| 14 | Neurogenesis of capability | **partial** — plasticity tape / improve engine |
| 15 | Global workspace leases | **shipped** (max 3 packets) |
| 16 | Tailscale callosum status | **shipped** (config probe; live net blocked) |
| 17 | AGI scan rewires routing | **blocked** — needs enhance-gate + draft applicator |
| 18 | Trajectory physics live | **shipped** |
| 19 | Embodiment theater | **blocked** — PRs #19/#20/#21 |
| 20 | Circadian quiet hours | **shipped** |

## Absolute blockers (need Aaron / other PRs)

1. **FunASR + VoiceStudio models** — real voiceprint enroll/speak (PRs #14/#17)
2. **MemoryBear live API** — cognitive memory on critical path (PR #12)
3. **Pupil Capture** — gaze/world stream (PR #18)
4. **nulltickets/nullclaw** — durable synapses across process death
5. **Local sLM/DL weights** — replace heuristic stubs
6. **Card/Joshinator/Inkbox** — embodiment theater PRs

## Verify

```bash
python3 scripts/cam-system.py --smoke
python3 scripts/flight-envelope.py --offline-only
npx vitest run server/core/system-bridge.test.ts
npm run lint
npm run dev
curl -s -X POST http://127.0.0.1:8787/api/turn \
  -H 'content-type: application/json' \
  -d '{"text":"hi","source":"text"}' | jq .bridge.route.kernel
python3 scripts/flight-envelope.py   # with server up
```
