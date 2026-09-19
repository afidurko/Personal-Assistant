# Continuous QA + billion-sim campaign

## Mandate (persistent)
Aaron authorized continuous QA: detect → dispatch team → fix → rerun, always on.
- `identity/persistence/CONTINUOUS_QA.md`
- `identity/BOUNDARIES.md`
- `mesh/facts.continuous_qa = true`
- Entrypoint: `python3 scripts/qa-loop.py --n 1000000000 --cycles 2`
- CI gate: `bash scripts/ci-connectome.sh`

## Campaign results

### Pass 1 (1B) — DONE · green
- File: `connectome-sim-1b-pass1.json`
- 1,000,000,000 / 0 fail · ~1.79M sims/s · ~559s · EXIT 0

### Pass 2 (1B, v2+audit, strict-edges) — DONE · green
- File: `connectome-sim-1b-pass2.json`
- 1,000,000,000 / 0 fail · **0 missing edges** · ~2.64M sims/s · ~379s · EXIT 0

### Pass 3 (1B, Cline workspace runtime, strict-edges) — DONE · green
- File: `connectome-sim-1b-cline-pass1.json`
- 1,000,000,000 / 0 fail · 0 missing edges · ~2.61M sims/s · ~383s · EXIT 0
- Includes `motor.cline` / `center.coding` / `sense.cline.result` pathways
- Unit tests: `scripts/test_cline_workspaces.py` (16) OK

### Pass 4 (1B, simulator v3 weighted+heartbeats) — DONE · green
- File: `connectome-sim-1b-cline-pass2.json`
- QA cycle: `qa-cycles/20260917T013738Z-cycle-01/`
- 1,000,000,000 / 0 fail · 0 missing edges · ~2.22M sims/s · ~451s · EXIT 0
- Simulator: `v3-weighted-heartbeats` (traffic-weighted + 50M heartbeats)
- Mesh mirror: `identity/persistence/qa-mesh-latest.json`

### Pass 5 (1B, VoiceStudio wiring, strict-edges) — DONE · green
- File: `connectome-sim-1b-voicestudio-pass1.json`
- QA cycle: `qa-cycles/20260919T183400Z-cycle-01/`
- 1,000,000,000 / 0 fail · 0 missing edges · ~2.46M sims/s · ~407s · EXIT 0
- Includes `motor.voicestudio` / `sense.voicestudio.*` pathways

### Pass 6 (1B, VoiceStudio + suggestive bridges, strict-edges) — DONE · green
- File: `connectome-sim-1b-voicestudio-pass2.json`
- QA cycle: `qa-cycles/20260919T184117Z-cycle-01/`
- 1,000,000,000 / 0 fail · 0 missing edges · ~1.93M sims/s · ~518s · EXIT 0
- Trajectory: `trajectory-1b-voicestudio-pass2.json` — 1e9 / 0 fail · ~3.96M checks/s
- Merge readiness: `MERGE_READINESS_VOICESTUDIO.md`

## What was fixed this loop
| Issue | Severity | Fix |
|---|---|---|
| Hotspot collision on chat (research vs docs) | high | Multi-option pathways + goal/`--hotspot` router |
| Orphan senses | med | Dedicated hotspots |
| Missing synapse / feedback edges | med | Filled synapses; real motor→memory feedback |
| `side_effects` bypassed holds | high | Route gates via `requires_switch` + kill |
| `motor.mesh` ignored kill | high | Added `switch.kill` |
| Presence/vision/jarvis missing switches | high | Pathways include required switches |
| No continuous QA automation | high | `scripts/qa-loop.py` |
| No Cline workspace runtime tests | high | `scripts/test_cline_workspaces.py` + `ci-connectome.sh` |
| Uniform sense sampling | med | Traffic-weighted sampling in simulator v3 |
| Long campaigns silent | med | 50M heartbeats |
| QA not mirrored to mesh | med | `mirror_mesh_qa` in qa-loop |
| VoiceStudio not in Cam | high | Submodule + connectome + chooser + bridges |
| Audible speak vs file TTS conflation | high | OCL `voicestudio_api_not_outbound_speak` |

## Standing improvements (always watch)
1. CI: `bash scripts/ci-connectome.sh` on push
2. Heartbeats every 50M sims — **done (v3)**
3. Traffic-weighted sense sampling — **done (v3)** + VoiceStudio weights
4. Shared pathway validator module — keep using `build_tables` / connectome-check
5. Mesh-mirror of QA dispatch events — **done**
6. Live nulltickets PUT for Cline tickets when Null stack is up
7. `cline mcp install cam` on each Aaron host after persist-import
8. Start VoiceStudio Electron on Aaron host; bind Cam soft-airy profile; MCP files mode

## Loop status
**Green through VoiceStudio integration.** Continuous QA remains always-on; next failure auto-dispatches a fix team and reruns.
