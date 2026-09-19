# LitServe — Cam local inference host

Source: [afidurko/LitServe](https://github.com/afidurko/LitServe)  
Upstream: [Lightning-AI/LitServe](https://github.com/Lightning-AI/LitServe) · [docs](https://lightning.ai/docs/litserve)  
Path: [`integrations/litserve`](../../integrations/litserve) (git submodule)  
Policy status: **proposed** with Cam reasoning / sLM-DL plan

## Role in the team

LitServe is Cam’s **local inference server** — custom Python `LitAPI` endpoints for
sLM classify/route/compress, DL embed/rerank, and (optionally) an OpenAI-compatible
backend that **SGR** calls on the slow path. It is **not** the brain and does not
assign tasks.

| Concern | Owner |
|---|---|
| Aaron tasking / kill / enhance | Cam switches |
| Schema-Guided Reasoning loop | SGR (`integrations/sgr-agent-core`) |
| Fast-path jobs | `center.slm` → `motor.slm` → **LitServe** |
| Embed / rerank / identity vectors | `center.dl` → `motor.dl` → **LitServe** |
| Coding | Cline |
| Memory truth | vault + mesh |

## Why LitServe

- Custom inference logic in pure Python (batching, streaming, multi-model) without MLOps glue  
- Fits Cam’s “smallest model that works” rule — host 1B–8B sLMs + embedders locally  
- OpenAI-compatible surface lets SGR keep its `AsyncOpenAI` client pointed at localhost  
- Streaming supports converse / presence without a second stack  

## Endpoint map (planned)

| LitAPI | Cam job | Switch |
|---|---|---|
| `/v1/slm/classify` | intent + hotspot route hint | `switch.slm_local` |
| `/v1/slm/compress` | brief / mesh distill compress | `switch.slm_local` |
| `/v1/dl/embed` | vault/mesh embeddings | `switch.dl_local` |
| `/v1/dl/rerank` | retrieval rerank | `switch.dl_local` |
| `/v1/chat/completions` | OpenAI-compatible for SGR / converse assist | slm_local (+ kill) |

All endpoints refuse work when `switch.kill` is act. Enhance/outbound never bypass connectome via LitServe.

## Runtime surface (planned)

| Piece | Path |
|---|---|
| Submodule | `integrations/litserve` |
| Cam server wrapper | `scripts/cam-litserve.py` (Phase B+) |
| API definitions | `config/litserve/` (Phase B) |
| sLM-DL recipe | `config/enhancement/slm-dl.json` |
| Reasoning plan | `docs/CAM_REASONING.md` |
| Motors | `motor.slm`, `motor.dl` (existing) |

## Install

```bash
git submodule update --init integrations/litserve
pip install -e integrations/litserve
# or: pip install litserve
```

Model weights stay outside git; point configs at local paths / env. No secrets in repo.

## Relation to SGR

```text
Aaron spike → Cam gate
  ├─ fast → LitServe sLM classify/compress
  └─ slow → SGR (Reason→Select→Act) ──LLM──► LitServe /v1/chat/completions
                                              (or cloud OpenAI-compatible)
```

Prefer local LitServe when `switch.slm_local` is act; cloud only as Aaron-configured fallback.

## Non-goals

- Not a second orchestrator (nullboiler / connectome stay policy)  
- Not unbounded model training in this repo  
- Not replacing Cline or Jarvis  
- Not hosting always-on camera / raw Aaron media without existing privacy gates  

## Docs

- LitServe: https://lightning.ai/docs/litserve  
- Cam reasoning: [docs/CAM_REASONING.md](../../docs/CAM_REASONING.md)  
- sLM/DL: [config/enhancement/slm-dl.json](../enhancement/slm-dl.json)
