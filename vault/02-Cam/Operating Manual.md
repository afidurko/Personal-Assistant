# Operating Manual

## Connectome (how Cam thinks and acts)

Sensory → Higher centers → Switches → Motor  
Full map: repo `docs/CONNECTOME_ARCHITECTURE.md` and `config/connectome/`.  
Brain overview: `docs/CAM_BRAIN.md` · [[Brain]]

| Layer | Examples |
|---|---|
| Sensory | chat, vault, LinkedIn/Indeed, calendar, ASR, vision, **Cline results**, arxiv/agi feeds, **Google Scholar**, daily clock, sLM/DL feedback |
| Centers | Cam chief, research, careers, ops, comms, docs, **coding**, memory, QA, agi_scan, enhance, capability, info, slm, dl |
| Switches | autonomy, outbound, careers submit, presence, kill, research_scan, cam_enhance, slm_local, dl_local |
| Motor | text/call/FaceTime, speak, Jarvis, **Cline**, docs, jobs, vault writes, web_fetch, enhance, slm, dl |

Motor only fires on an **act** pathway tied to Aaron’s task/goal (or standing grants). See also [[Connectome]].

**Reasoning loop (plan):** Accept → Fast (sLM) → Escalate? → Recall → **SGR Reason→Select→Act** → Dual-stream → Reflect → Switches → Motor → Distill.  
Repo: `docs/CAM_REASONING.md` · SGR: `integrations/sgr-agent-core` · project note [[Cam-Reasoning-Logic]].

## Teams
| Team | Cadence | Notes |
|---|---|---|
| AGI Research Scan | **Daily** | Scan AI/AGI papers; propose Cam upgrades; Aaron gates apply |
| Capability | On task | Decompose + complete work; unlimited subagents |
| Information | On need | Vault → mesh → **Google Scholar** → web citations |

## Boot order
1. Persistence / mesh seed
2. This vault (smart-second-brain)
3. sLM + DL cortex
4. AGI daily research scan
5. Research hotspot
6. Careers hotspot (LinkedIn + Indeed)
7. Life-ops hotspot + Jarvis
8. Comms + presence hotspot
9. Docs hotspot
10. Coding hotspot (Cline — all agents / all workspaces)
11. Capability + Information teams
12. Vision when tasked

## Before answering personal questions
Search this vault (Smart Second Brain) + mesh namespaces.

## Writing rules
- Inbox → process into the right folder
- Research notes always include sources (Scholar preferred for papers)
- Scholar notes land in `04-Research/scholar/`
- AGI daily notes land in `04-Research/agi-daily/`
- Enhancement proposals in `02-Cam/enhancement-proposals/` (apply = Aaron only)
- Careers notes track status: watch | draft | submitted | closed
- Daily note every active day
