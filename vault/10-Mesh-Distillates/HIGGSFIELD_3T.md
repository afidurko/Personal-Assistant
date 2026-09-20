# Higgsfield — Cam function + 3T findings (2026-09-20)

## Function for Cam

Higgsfield is Cam’s **Aaron-gated multi-node GPU training effector** — not the brain.

| Layer | ID |
|---|---|
| Submodule | `integrations/higgsfield` |
| Motor | `motor.higgsfield` |
| Sense | `sense.train.higgsfield` |
| Hotspot | `hotspot.higgsfield` |
| Gate | `switch.cam_enhance` + `switch.kill` |
| Check | `scripts/higgsfield-check.py` |

Split with LitServe:

```text
Train / fine-tune large weights  → Higgsfield (multi-node, spend risk)
Serve / classify / embed locally → LitServe (motor.slm / motor.dl)
```

Cam uses it when Aaron authorizes a train/fine-tune: allocate nodes, queue
experiments, ZeRO-3/FSDP shard, deploy via GitHub Actions. Cline may *code*
against the workspace; Cline must **not** free-spend cloud GPUs.

## Three-trillion campaign

Protocol: 3T → fix/suggest → 3T → merge if green

| Gate | Result |
|---|---|
| Pass A (pre-fix audit) | green · `20260920T011734Z-3t-pass-1` |
| Pass B (pre-fix audit) | green · `20260920T011757Z-3t-pass-2` |
| Pass A (post-wire) | green · `20260920T011922Z-3t-pass-1` |
| Pass B (post-wire) | green · `20260920T011943Z-3t-pass-2` |
| Verdict | **READY TO MERGE** |

N = 3,000,000,000,000 (exhaustive/modular + 10M physical). All harnesses exit 0
including `higgsfield-check` on the post-wire dual pass.

## Issues found (soft — 3T hard gates were already green)

1. Motor existed without sense/hotspot/synapses → dead pathway  
2. Not in `ci-connectome.sh` / HARD_PATHS / system-health expected list  
3. 3T campaign did not run `higgsfield-check`  
4. Policy still said check “when added”  
5. No live train runner yet (`status: proposed`) — intentional until Aaron arms spend  

## Fixes applied this cycle

- Wired `sense.train.higgsfield` → centers → `switch.cam_enhance` → `motor.higgsfield` + feedback synapses  
- Added `hotspot.higgsfield`  
- CI + HARD_PATHS + system-health + 3T campaign include `higgsfield-check`  
- Policy/config/registry updated with sense/hotspot/script  

## Improve next (not blocking merge)

1. **Dry-run runner** — `scripts/higgsfield-run.py --dry-run` that validates `@experiment` + node inventory without SSH/GPU spend  
2. **Motor executor** — keep dry-run by default; only arm when enhance switch flipped + explicit Aaron goal  
3. **Cost envelope** — trajectory policy deny if cloud GPU spend not in flight envelope  
4. **Mesh distill** — pack train job status into `mesh/runs` / `mesh/tools`  
5. **LitServe handoff** — after train, optional path to load adapters into LitServe  
6. **Unit test** — `test_higgsfield.py` mirroring public-apis/trends check patterns  
