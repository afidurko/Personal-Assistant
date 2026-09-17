# Cam Brain (reimagined)

Cam’s brain is a **connectome** plus standing **agent teams**, a **DL + sLM cortex**, **HAAS-pattern swarm contracts** (privileges + boss/worker bus), and unlimited subagent recruitment. Aaron remains the only root task-giver and has ultimate say over functionality changes.

## Layers

```text
Aaron
  └─ sensory periphery (chat, vault, web/arxiv, clock, ASR, vision, sLM/DL feedback, swarm bus)
       └─ higher centers (chief, router, specialists, AGI scan, enhance, info, capability, tooling, slm, dl)
            └─ circuit switches (autonomy, research_scan, cam_enhance, tooling, slm_local, dl_local, kill, …)
                 └─ motor (vault, mesh, web_fetch, enhance, tool, swarm, slm, dl, speak, jobs, …)
```

## Teams (all may spawn subagents)

| Team | Lead center | Job |
|---|---|---|
| **AGI Research Scan** | `center.agi_scan` | Everyday internet scan for AI/AGI papers/findings that can enhance Cam |
| **Capability** | `center.capability` / `center.enhance` | Complete tasks; broker specialists + models; gate Cam upgrades |
| **Information** | `center.info` | Vault → mesh → web cited answers |
| **Tooling** | `center.tooling` | Tool-creator → tool-user; boss/worker synapse ops |

Configs: `config/teams/*.json` · Swarm: `config/swarm/` · Runtime: `server/core/swarm-runtime.ts` · Docs: [HAAS_CAM_PATTERNS.md](HAAS_CAM_PATTERNS.md)

Neural mesh layer **swarm** (privilege-broker, lineage-guardian, boss-router, tool-broker) runs on every scan cycle and writes shared memory namespaces for **all agents and workspaces**.

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
| Tool create/run under registry | Standing ON (`switch.tooling`) — enhance apply still Aaron-gated |
| Kill / pause all | Aaron anytime |

## Daily scan

```bash
python3 scripts/agi-research-scan.py           # live arXiv pull + vault/mesh notes
python3 scripts/agi-research-scan.py --dry-run # plan only
python3 scripts/cam-enhance-propose.py --proposal path.md
python3 scripts/cam-enhance-propose.py --proposal path.md --aaron-approve
python3 scripts/swarm-check.py                 # privilege + primitive contracts
```

Pipeline: `config/pipelines/daily-agi-scan.json`  
Docs: [AGI_RESEARCH_TEAM.md](AGI_RESEARCH_TEAM.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md) · [HAAS_CAM_PATTERNS.md](HAAS_CAM_PATTERNS.md)
