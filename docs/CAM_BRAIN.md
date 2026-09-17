# Cam Brain (reimagined)

Cam’s brain is a **connectome** plus three standing **agent teams**, a **DL + sLM cortex**, and unlimited subagent recruitment. Aaron remains the only root task-giver and has ultimate say over functionality changes.

## Layers

```text
Aaron
  └─ sensory periphery (chat, vault, web/arxiv, clock, ASR, vision, sLM/DL feedback)
       └─ higher centers (chief, router, specialists, AGI scan, enhance, info, capability, slm, dl)
            └─ circuit switches (autonomy, research_scan, cam_enhance, slm_local, dl_local, kill, …)
                 └─ motor (vault, mesh, web_fetch, enhance, slm, dl, speak, jobs, …)
```

## Teams (all may spawn subagents)

| Team | Lead center | Job |
|---|---|---|
| **AGI Research Scan** | `center.agi_scan` | Everyday internet scan for AI/AGI papers/findings that can enhance Cam |
| **Capability** | `center.capability` / `center.enhance` | Complete tasks; broker specialists + models; gate Cam upgrades |
| **Information** | `center.info` | Vault → mesh → web cited answers |

Configs: `config/teams/*.json`

## Deep learning + sLMs

Local helpers, not a second brain:

- **sLM runtime** (`center.slm` → `motor.slm`) — classify, route hints, compress, draft assists
- **DL enhance** (`center.dl` → `motor.dl`) — embeddings, rerank, identity/paper vectors

Recipe book: `config/enhancement/slm-dl.json`

## Human ultimate say

| Action | Autonomy |
|---|---|
| Daily scan + distill + propose | Standing ON (`switch.research_scan`) |
| Apply Cam functionality changes | **Aaron only** (`switch.cam_enhance`, default hold) |
| Kill / pause all | Aaron anytime |

## Daily scan

```bash
python3 scripts/agi-research-scan.py           # live arXiv pull + vault/mesh notes
python3 scripts/agi-research-scan.py --dry-run # plan only
python3 scripts/cam-enhance-propose.py --proposal path.md
python3 scripts/cam-enhance-propose.py --proposal path.md --aaron-approve
```

Pipeline: `config/pipelines/daily-agi-scan.json`  
Docs: [AGI_RESEARCH_TEAM.md](AGI_RESEARCH_TEAM.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)
