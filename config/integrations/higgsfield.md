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

## Runtime surface (planned)

| Piece | Path |
|---|---|
| Submodule | `integrations/higgsfield` |
| Policy | `config/integrations/higgsfield.md` |
| Config | `config/integrations/higgsfield.json` |
| Motor | `motor.higgsfield` (gated) |
| Check | `python3 scripts/higgsfield-check.py` (when added) |

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

## Non-goals

- Not a second orchestrator (nullboiler / connectome stay policy)  
- Not unbounded spend on cloud GPUs without Aaron gate  
- Not replacing Cline, Jarvis, or LitServe  
- Not always-on training farms in this checkout  

## Docs

- Upstream README: https://github.com/higgsfield-ai/higgsfield  
- Fork: https://github.com/afidurko/higgsfield  
- Cam sLM/DL: [config/enhancement/slm-dl.json](../enhancement/slm-dl.json)
