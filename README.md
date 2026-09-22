# Personal-Assistant — Cam for Aaron

Cam is Aaron’s always-on Argentine assistant (32, blue eyes, brown hair, soft airy voice)
for life automation, source-backed research, documents, LinkedIn/Indeed jobs, and
talking presence — with a smart second brain, **agent teams**, and a **sLM/DL cortex**.

## Home (Cam + live 3D cortex)

```bash
npm install
npm run dev
# → http://127.0.0.1:5173  — Cam listens/speaks; 3D DTI cortex mounts in-process (vendored three)
# API/mesh  → http://127.0.0.1:8787
# Standalone viz → http://127.0.0.1:8787/viz/connectome/
```

Cam stays on in the background spawning self-improve tasks (spawn bay on the home page).
Runtime distillates live under `data/runtime/` (gitignored). Scan delta cache skips tree walks when sources are unchanged.

## Design

- **Brain:** nullclaw + [smart-second-brain](https://github.com/afidurko/smart-second-brain) + [MemoryBear](https://github.com/afidurko/MemoryBear) + [SwiftGuide](https://github.com/afidurko/SwiftGuide) cartography + sLM/DL cortex — [docs/CAM_BRAIN.md](docs/CAM_BRAIN.md) · **predictive cortex** (outcomes from experience, calibrated) — [docs/PREDICTIVE_CORTEX.md](docs/PREDICTIVE_CORTEX.md)
- **Teams:** AGI Research Scan (daily) · Capability · Information · Tooling — [docs/AGI_RESEARCH_TEAM.md](docs/AGI_RESEARCH_TEAM.md)
- **Swarm patterns:** privilege inheritance + boss/worker bus from [HAAS](https://github.com/afidurko/OpenAI_Agent_Swarm) — wired into the neural mesh + memory for all workspaces/agents — [docs/HAAS_CAM_PATTERNS.md](docs/HAAS_CAM_PATTERNS.md)
- **Vault:** [`vault/`](vault/) starter Obsidian vault (open this folder in Obsidian)
- **Tasks/mesh:** nulltickets · **Orchestration:** nullboiler · **Control:** Aaron only
- **Presence:** [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) (RIVA + Audio2Face)
- **Tools:** Jarvis · Cline · PaddleDetection · Pupil (gaze) · LinkedIn/Indeed · **Google Scholar** · **Google Trends data** · **public-apis** · **Inkbox** · **loop-engineering** · `config/tools/registry.json`
- **Autonomy:** Aaron assigns; Cam finishes without mid-task interference; 24/7 available; teams spawn unlimited subagents (privilege inheritance, no escalation)

Face: [`identity/persona/cam-face.jpg`](identity/persona/cam-face.jpg)  
Persona: [docs/PERSONA.md](docs/PERSONA.md) · Persistence: [docs/PERSISTENCE.md](docs/PERSISTENCE.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Workspaces: [docs/WORKSPACES_WORKFLOW.md](docs/WORKSPACES_WORKFLOW.md)

## Connectome architecture (brain map)

Cam is a **Brodmann cortex** — see [docs/CONNECTOME_ARCHITECTURE.md](docs/CONNECTOME_ARCHITECTURE.md):

```text
Aaron → sensory → Brodmann areas (columns=agents/loops) → switches → motor
                 ↘ association tracts = neural mesh ↗
```

Lenses: **3D cortex** (spin + rewind) · **2D flat** · plasticity tape for tract errors.

```bash
# Example: route a careers spike to motor plan
python3 scripts/connectome-route.py --sense sense.careers.listing --goal "watch roles"
# QA conflict-monitoring loop through ACC
python3 scripts/connectome-route.py --sense sense.chat.aaron --goal "qa loop"
# SwiftGuide → iOS companion stack brief
python3 scripts/connectome-route.py --sense sense.swiftguide.map --goal "ios companion stack"
# Plasticity / neurogenesis tape
python3 scripts/connectome-plasticity.py --neurogenesis
# Daily AGI research scan pathway
python3 scripts/connectome-route.py --sense sense.clock.daily --goal "daily agi scan"
# Google Scholar literature search (fixture / live)
python3 scripts/connectome-route.py --sense sense.web.scholar --goal "scholar search"
python3 scripts/scholar-search.py --query "connectome mapping" --offline
# Google Trends open datasets (fixture / live GitHub index)
python3 scripts/connectome-route.py --sense sense.catalog.google_trends --goal "google trends election dataset"
python3 scripts/google-trends-search.py --query election --offline
# Run the daily scan (arXiv → vault/mesh proposals)
python3 scripts/agi-research-scan.py
# Confirm workspace + integration wiring
python3 scripts/workspace-integration-check.py
# Loop Engineering (L1 standing triage / audit)
python3 scripts/connectome-route.py --sense sense.loop.tick --goal "daily triage loop engineering"
python3 scripts/loop-check.py
python3 scripts/loop-run.py --pattern daily-triage --level L1
# MemoryBear cognitive memory (offline doctor)
python3 scripts/memorybear.py --doctor --offline
python3 scripts/memorybear-check.py
# Predictive cortex — outcome prediction from Cam's own experience (advisory)
python3 scripts/cam-predict.py --report
python3 scripts/cam-predict.py --hotspot hotspot.loop_engineering --pattern daily-triage --sense sense.loop.tick
python3 scripts/cam-predict.py --narrate --hotspot hotspot.coding      # the hedged sentence Cam would say
python3 scripts/predictive-cortex-check.py
python3 scripts/research-ethics-check.py                               # ethics gate: redaction, protected contexts, abstention, parity
# Overall system pulse (all pieces on one bus)
python3 scripts/cam-system.py --smoke
# HAAS→Cam privilege + boss/worker contracts
python3 scripts/swarm-check.py
# Kill switch silences motors
python3 scripts/connectome-route.py --sense sense.chat.aaron --kill
# Live 3D cortex
bash scripts/serve-connectome-viz.sh
# open http://127.0.0.1:8765/visualizations/connectome/
```

## Open the vault (2 minutes)

1. Install [Obsidian](https://obsidian.md)
2. **Open folder as vault** → choose `vault/` in this repo
3. Community plugins → install **Smart Second Brain** → Enable
4. Start at [[Welcome]] (`vault/Welcome.md`)

Cam is already pointed at `vault` via `config/persona/vault.json`.

## Submodules

```bash
git submodule update --init --recursive
bash scripts/cam-avatar-hint.sh
python3 scripts/persist-export.py --seed-only
```

## Neural mesh health scanner (TypeScript)

Live workspace scanners visualized as an interactive brain map with persistent memory
and Swift Guide concept tour. See also the connectome docs above — these stacks coexist
and may need a deliberate product wiring decision.

| Workspace | Role |
| --- | --- |
| **System Health** | Vitals: resources, readiness, process health |
| **Architecture Map** | Structural topology and layering |
| **Vulnerability Scan** | Threat surface and insecure patterns |
| **Updates & Drift** | Freshness and tooling drift |
| **Improvement Engine** | Cross-workspace actionable suggestions |

```bash
npm install
npm run dev
```

- UI: http://localhost:5173
- API / WS: http://localhost:8787 (`/api/state`, `/ws`)
- One-shot: `npm run scan`

```
shared/          Domain types & color palette
server/
  workspaces/    Parallel health / arch / vuln / updates / improvements scanners
  core/          Neural mesh, persistent memory, scan orchestrator
  index.ts       Express + WebSocket fan-out
src/             React brain map UI
data/            Persisted mesh + memory (gitignored runtime state)
```

## Status

Persona locked. Starter vault created. Always-on autonomy set.
Brain reimagined with AGI scan / capability / info teams + sLM/DL cortex.
Cline wired as shared coding effector for all agents and future workspaces
(registry, runner, MCP, schedules, tickets).
MemoryBear wired as shared cognitive memory effector for all agents/workspaces
(sense/motor/hotspots, mesh/memorybear, MCP read/write, HMO secondary tier).
Public-apis wired as shared free-API catalog for all agents
(`motor.public_apis`, MCP `public_apis_search`, tooling/info/capability/AGI teams).
**Overall system bridge** ties home converse → connectome → live cortex activity
(`server/core/system-bridge.ts`, `GET /api/system`, `python3 scripts/cam-system.py`).
Next: enable Smart Second Brain in Obsidian + RIVA/Audio2Face studio + live Null stack.
Neural-mesh scanner stack and Cam connectome share one activity bus via the system bridge.
