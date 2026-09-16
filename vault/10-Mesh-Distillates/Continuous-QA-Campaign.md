# Continuous QA + billion-sim campaign

## Mandate (persistent)
Aaron authorized continuous QA: detect → dispatch team → fix → rerun, always on.
- `identity/persistence/CONTINUOUS_QA.md`
- `identity/BOUNDARIES.md`
- `mesh/facts.continuous_qa = true`
- Entrypoint: `python3 scripts/qa-loop.py --n 1000000000 --cycles 2`

## Campaign results

### Pass 1 (1B) — DONE · green
- File: `connectome-sim-1b-pass1.json`
- 1,000,000,000 / 0 fail · ~1.79M sims/s · ~559s · EXIT 0

### Pass 2 (1B, v2+audit, strict-edges) — DONE · green
- File: `connectome-sim-1b-pass2.json`
- 1,000,000,000 / 0 fail · **0 missing edges** · ~2.64M sims/s · ~379s · EXIT 0
- Throughput up ~47% vs pass 1 after rewrite/simplify

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

## Standing improvements (always watch)
1. CI: `--n 1000000 --strict-edges` on push
2. Heartbeats every 50M sims
3. Traffic-weighted sense sampling
4. Shared pathway validator module
5. Mesh-mirror of QA dispatch events

## Loop status
**Green.** Continuous QA remains always-on; next failure auto-dispatches a fix team and reruns.
