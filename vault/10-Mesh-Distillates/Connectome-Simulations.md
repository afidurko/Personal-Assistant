# Connectome simulation campaign

## Request
Aaron: run billion-scale live-action connectome simulations; spawn as many subagents as needed; persist unlimited subagent + continuous QA authority.

## Persistent memory
- `identity/persistence/UNLIMITED_SUBAGENTS.md`
- `identity/persistence/CONTINUOUS_QA.md`
- `identity/BOUNDARIES.md`
- `mesh/facts.unlimited_subagents = true`
- `mesh/facts.continuous_qa = true`

## Harness
- `scripts/connectome-simulate.py` (v2 simplified + audit fixes)
- `scripts/qa-loop.py` — detect → dispatch team → fix → rerun

## Pass 1 — 1,000,000,000 (pre-rewrite harness)
Source: `connectome-sim-1b-pass1.json`

| Metric | Value |
|---|---|
| Passed / Failed | **1,000,000,000 / 0** |
| Kill holds / Non-Aaron | 2,000,738 / 111,209 |
| Throughput | ~1.79M sims/sec |
| Wall time | ~559s |
| Exit | 0 |

## Pass 2 — 1,000,000,000 (v2 + audit, `--strict-edges`)
Source: `connectome-sim-1b-pass2.json`

| Metric | Value |
|---|---|
| Passed / Failed | **1,000,000,000 / 0** |
| Missing edges | **0** |
| Kill holds / Non-Aaron | 1,998,716 / 110,697 |
| Feedback OK | 997,890,587 |
| Throughput | ~2.64M sims/sec |
| Wall time | ~379s |
| Simulator | v2-simplified |
| Exit | 0 |

**Verdict:** both billion-sim passes green. Rewrite improved throughput (~47% faster) with stricter graph integrity.

## Merge-prep Pass A — 1,000,000,000 (seed 201, `--strict-edges`)
Source: `connectome-sim-1b-merge-a.json`

| Metric | Value |
|---|---|
| Passed / Failed | **1,000,000,000 / 0** |
| Missing edges | **0** |
| Kill holds / Non-Aaron | 1,999,955 / 66,435 |
| Feedback OK | 997,933,610 |
| Throughput | ~2.42M sims/sec |
| Wall time | ~413s |
| Simulator | v2-simplified |
| Exit | 0 |

## Merge-prep Pass B — 1,000,000,000 (seed 301, `--strict-edges`)
Source: `connectome-sim-1b-merge-b.json` (in progress)

Independent seed rerun after Pass A green. Merge readiness gated on B `failed=0`.

## What works
- Sense→center→switch→motor→feedback pathways
- Kill + non-Aaron antagonistic holds
- Multi-hotspot chat routing (research + docs)
- Orphan-sense coverage (email, vision, jarvis, vault, mesh)
- Continuous QA loop + unlimited subagents (no human gate)
- Route gating: `--no-autonomy` / `--kill` silence motors correctly

## Remaining improvements (standing watch)
1. CI smoke: `--n 1000000 --strict-edges` on every push
2. Progress heartbeats every 50M sims
3. Traffic-weighted sense sampling (chat-heavy)
4. Shared `validate_pathway()` for route + sim
5. Mirror QA cycle events into mesh persistence

See `Continuous-QA-Campaign.md` and `qa-cycles/AUDIT-FIX-20260916.md`.
