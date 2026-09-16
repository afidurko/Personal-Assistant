# Continuous QA + billion-sim campaign

## Mandate (persistent)
Aaron authorized continuous QA: detect → dispatch team → fix → rerun, always on.
- `identity/persistence/CONTINUOUS_QA.md`
- `identity/BOUNDARIES.md`
- `mesh/facts.continuous_qa = true`
- Entrypoint: `python3 scripts/qa-loop.py --n 1000000000 --cycles 2`

## What was working (pre-rewrite)
- 100,000,000 sims: **0 failures** (~1.19M sims/s, 4 workers)
- Kill-switch + non-Aaron holds exercised correctly
- Feedback sinks validated on success routes
- Unlimited subagent spawn authority persisted

## What was not working / gaps found
| Issue | Severity | Fix |
|---|---|---|
| Hotspot collision: `sense.chat.aaron` kept only one pathway (docs overwrote research) | high | Multi-option pathway table; pick among hotspots |
| Orphan senses (email, vision, jarvis, vault, mesh) used generic fallback | med | Dedicated hotspots |
| Pathway chained motors without synapse edges (18 missing) | med | Simplified pathways + filled synapses |
| Default path used missing `center.router→center.memory` edge | med | Default now `chief→memory→mesh` |
| Simulator default N still 100M while QA mandate is 1B | low | Default N = 1_000_000_000 |
| No automated detect→dispatch→fix→rerun loop | high | `scripts/qa-loop.py` |

## Rewrite (simulator v2)
- Precompute per-sense pathway tables (no JSON in hot loop beyond worker boot)
- Multi-hotspot support per sense
- One-shot integrity scan + `--strict-edges`
- Dropped unused dataclass / index noise
- Smoke: 5,000,000 @ ~1.28M sims/s, **0 fail**, **0 missing edges**

## Improvement suggestions (next loops)
1. Weight sense sampling by real traffic mix (chat-heavy) instead of uniform
2. Progress heartbeats every 50M sims for long campaigns
3. CI job: `--n 1000000 --strict-edges` on every push
4. Model side_effects as parallel fan-out spikes (not chained motors)
5. Connect viz live counters to sim worker heartbeats

## Campaign log
Results land in `vault/10-Mesh-Distillates/` and `qa-cycles/`.

### Pass 1 (1B) — DONE · green
- File: `connectome-sim-1b-pass1.json`
- Passed 1,000,000,000 / failed 0
- ~1.79M sims/s · ~559s · EXIT 0

### Pass 2 (1B, v2+audit) — RUNNING
- File: `connectome-sim-1b-pass2.json`
- Simulator: v2-simplified with switch gating + feedback synapses
