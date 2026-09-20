# Higgsfield — Cam multi-node GPU training

Source: [afidurko/higgsfield](https://github.com/afidurko/higgsfield)  
Upstream: [higgsfield-ai/higgsfield](https://github.com/higgsfield-ai/higgsfield)  
Path: [`integrations/higgsfield`](../../integrations/higgsfield) (git submodule)  
Policy status: **proposed** — training effector, not the brain

## Role in the team

Higgsfield is Cam’s **multi-node GPU training orchestrator** — fault-tolerant
scheduling, ZeRO-3 / FSDP-style sharding, experiment queue, and GitHub Actions
deploy/run for large-model jobs. It is **not** the brain, not tasking, and not
an outbound channel.

| Concern | Owner |
|---|---|
| Aaron tasking / kill / enhance | Cam switches |
| Local inference | LitServe (`integrations/litserve`) · `motor.slm` / `motor.dl` |
| Multi-node train / fine-tune | **Higgsfield** (`motor.higgsfield`) |
| Coding | Cline |
| Memory truth | vault + mesh |

## Why Higgsfield

- Allocates GPU nodes and queues experiments without hand-rolled SSH glue  
- DeepSpeed ZeRO-3 + PyTorch FSDP paths for billion–trillion param models  
- Keeps a normal PyTorch-style loop (`@experiment`) instead of YAML hell  
- CI-friendly: deploy to nodes and launch runs from GitHub Actions  

## Runtime surface

| Piece | Path |
|---|---|
| Submodule | `integrations/higgsfield` |
| Policy | `config/integrations/higgsfield.md` |
| Config | `config/integrations/higgsfield.json` |
| Motor | `motor.higgsfield` (gated) |
| Sense | `sense.train.higgsfield` |
| Hotspot | `hotspot.higgsfield` |
| Check | `python3 scripts/higgsfield-check.py` |
| Dry-run | `python3 scripts/higgsfield-run.py --doctor` |
| Pack | `python3 scripts/pack-higgsfield-result.py --results plan.json` |
| Fixture | `scripts/testdata/sample-higgsfield-experiment.py` |

## Dry-run vs live

```bash
# Default — AST-validate experiment + inventory; no SSH / no GPU
python3 scripts/higgsfield-run.py --doctor
python3 scripts/higgsfield-run.py --experiment path/to/train.py --out /tmp/hf-plan.json
python3 scripts/pack-higgsfield-result.py --results /tmp/hf-plan.json --goal "alpaca" --out /tmp/hf-mesh.json

# Live intent only (still no remote exec in phase-1):
# requires --enhance + CAM_HIGGSFIELD_LIVE=1
CAM_HIGGSFIELD_LIVE=1 python3 scripts/higgsfield-run.py --experiment path/to/train.py --enhance --live
```

Trajectory policies strip `motor.higgsfield` unless `switch.cam_enhance` is act,
and refuse train+jobs / train+inkbox bursts.

## Install

```bash
git submodule update --init integrations/higgsfield
pip install -e integrations/higgsfield
# or: pip install higgsfield==0.0.3
```

Nodes need Ubuntu, SSH, and a non-root sudo user (passwordless). No secrets in repo —
deploy keys and cloud credentials stay in env / host secrets.

## Relation to LitServe / sLM-DL

```text
Train / fine-tune large weights  → Higgsfield (multi-node)
Serve / classify / embed locally → LitServe (motor.slm / motor.dl)
```

Prefer Higgsfield only when Aaron authorizes a training run (enhance / explicit
train goal). Prefer LitServe for day-to-day local inference.

After a successful train, pack emits a **LitServe handoff stub**
(`litserve_handoff`) — adapters are never auto-loaded; Aaron confirms path +
`switch.dl_local`.

## Non-goals

- Not a second orchestrator (nullboiler / connectome stay policy)  
- Not unbounded spend on cloud GPUs without Aaron gate  
- Not replacing Cline, Jarvis, or LitServe  
- Not always-on training farms in this checkout  

## Docs

- Upstream README: https://github.com/higgsfield-ai/higgsfield  
- Fork: https://github.com/afidurko/higgsfield  
- Cam sLM/DL: [config/enhancement/slm-dl.json](../enhancement/slm-dl.json)
