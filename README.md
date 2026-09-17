# Personal-Assistant — Cam for Aaron

Cam is Aaron’s always-on Argentine assistant (32, blue eyes, brown hair, soft airy voice)
for life automation, source-backed research, documents, LinkedIn/Indeed jobs, and
talking presence — with a smart second brain, **agent teams**, and a **sLM/DL cortex**.

## Design

- **Brain:** nullclaw + [smart-second-brain](https://github.com/afidurko/smart-second-brain) + sLM/DL cortex — [docs/CAM_BRAIN.md](docs/CAM_BRAIN.md)
- **Teams:** AGI Research Scan (daily) · Capability · Information — [docs/AGI_RESEARCH_TEAM.md](docs/AGI_RESEARCH_TEAM.md)
- **Vault:** [`vault/`](vault/) starter Obsidian vault (open this folder in Obsidian)
- **Tasks/mesh:** nulltickets · **Orchestration:** nullboiler · **Control:** Aaron only
- **Presence:** [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) (RIVA + Audio2Face)
- **Tools:** Jarvis · PaddleDetection · LinkedIn/Indeed
- **Autonomy:** Aaron assigns; Cam finishes without mid-task interference; 24/7 available; teams spawn unlimited subagents

Face: [`identity/persona/cam-face.jpg`](identity/persona/cam-face.jpg)  
Persona: [docs/PERSONA.md](docs/PERSONA.md) · Persistence: [docs/PERSISTENCE.md](docs/PERSISTENCE.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Workspaces: [docs/WORKSPACES_WORKFLOW.md](docs/WORKSPACES_WORKFLOW.md)

## Connectome architecture (brain map)

Cam is wired like a nervous system — see [docs/CONNECTOME_ARCHITECTURE.md](docs/CONNECTOME_ARCHITECTURE.md):

```text
Aaron → sensory → higher centers → circuit switches → motor effectors
```

```bash
# Example: route a careers spike to motor plan
python3 scripts/connectome-route.py --sense sense.careers.listing --goal "watch roles"
# Daily AGI research scan pathway
python3 scripts/connectome-route.py --sense sense.clock.daily --goal "daily agi scan"
# Run the daily scan (arXiv → vault/mesh proposals)
python3 scripts/agi-research-scan.py
# Confirm workspace + integration wiring
python3 scripts/workspace-integration-check.py
# Kill switch silences motors
python3 scripts/connectome-route.py --sense sense.chat.aaron --kill
# Live brain + spinal cord visualization (all repos)
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
Next: enable Smart Second Brain in Obsidian + RIVA/Audio2Face studio + live Null stack.
Neural-mesh scanner stack is present alongside the Cam connectome foundation.
