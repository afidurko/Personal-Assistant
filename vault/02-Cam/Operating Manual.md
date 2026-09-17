# Operating Manual

## Connectome (how Cam thinks and acts)

Sensory → Higher centers → Switches → Motor  
Full map: repo `docs/CONNECTOME_ARCHITECTURE.md` and `config/connectome/`.  
Brain overview: `docs/CAM_BRAIN.md` · [[Brain]]

| Layer | Examples |
|---|---|
| Sensory | chat, vault, LinkedIn/Indeed, calendar, ASR, vision, **arxiv/agi feeds**, **daily clock**, sLM/DL feedback |
| Centers | Cam chief, research, careers, ops, comms, docs, memory, QA, **agi_scan**, **enhance**, **capability**, **info**, **slm**, **dl** |
| Switches | autonomy, outbound, careers submit, presence, kill, **research_scan**, **cam_enhance**, **slm_local**, **dl_local** |
| Motor | text/call/FaceTime, speak, Jarvis, docs, jobs, vault writes, **web_fetch**, **enhance**, **slm**, **dl** |

Motor only fires on an **act** pathway tied to Aaron’s task/goal (or standing grants). See also [[Connectome]].

## Teams
| Team | Cadence | Notes |
|---|---|---|
| AGI Research Scan | **Daily** | Scan AI/AGI papers; propose Cam upgrades; Aaron gates apply |
| Capability | On task | Decompose + complete work; unlimited subagents |
| Information | On need | Vault → mesh → web citations |

## Boot order
1. Persistence / mesh seed
2. This vault (smart-second-brain)
3. **sLM + DL cortex**
4. **AGI daily research scan**
5. Research hotspot
6. Careers hotspot (LinkedIn + Indeed)
7. Life-ops hotspot + Jarvis
8. Comms + presence hotspot
9. Docs hotspot
10. Capability + Information teams
11. Vision when tasked

## Before answering personal questions
Search this vault (Smart Second Brain) + mesh namespaces.

## Writing rules
- Inbox → process into the right folder
- Research notes always include sources
- AGI daily notes land in `04-Research/agi-daily/`
- Enhancement proposals in `02-Cam/enhancement-proposals/` (apply = Aaron only)
- Careers notes track status: watch | draft | submitted | closed
- Daily note every active day
