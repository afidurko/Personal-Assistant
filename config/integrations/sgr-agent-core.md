# SGR Agent Core — Schema-Guided Reasoning for Cam

Source: [afidurko/sgr-agent-core](https://github.com/afidurko/sgr-agent-core)  
Upstream concept: [Schema-Guided Reasoning / neuraldeep](https://vamplabai.github.io/sgr-agent-core/)  
Path: [`integrations/sgr-agent-core`](../../integrations/sgr-agent-core) (git submodule — planned)  
Policy status: **proposed** with Cam reasoning plan (`docs/CAM_REASONING.md`)

## Role in the team

SGR is Cam’s **slow-path deliberative cortex** — structured Reasoning → Select → Act
cycles with Pydantic tool schemas. It is **not** the sole brain and **not** a
second task-giver.

| Concern | Owner |
|---|---|
| Aaron tasking / kill / enhance gate | Cam switches + nullhub |
| Connectome route / hotspots | `scripts/connectome-route.py` |
| Fast path (System-1) | `center.slm` / dual-process |
| Slow path plan + tool loop (System-2) | **SGR** (`SGRToolCallingAgent` default) |
| Coding effector | Cline (`motor.cline`) |
| Memory truth | vault + mesh (HMO/MMP) |

## Why SGR (not ad-hoc ReAct)

Cam already declared MAP stages and dual-process; SGR supplies the **executable
schema** those stages were missing:

```text
while not finished:
  reasoning = ReasoningTool   # structured situation + remaining_steps
  tool      = select_action   # from toolkit (or from SO function field)
  result    = action(tool)
```

Preferred Cam agent class: **`SGRToolCallingAgent`** (explicit ReasoningTool +
native function calling). Fall back to `SGRAgent` for weaker local models;
avoid bare `ToolCallingAgent` for enhance/outbound paths (no inspectable reason
schema).

## Tool map → Cam motors / centers

| SGR tool | Cam mapping | Gate |
|---|---|---|
| `ReasoningTool` | MAP monitor + predict (`neuron.qa_cycle`, `neuron.plan_loop`) | always on slow path |
| `GeneratePlanTool` / `AdaptPlanTool` | `area.apfc` / `neuron.delegate_burst` decompose | slow path |
| `ClarificationTool` | hold + ask Aaron (never invent facts) | autonomy / tasking |
| `WebSearchTool` / `ExtractPageContentTool` | `motor.web_fetch` + Scholar | research_scan / info |
| `CreateReportTool` / `FinalAnswerTool` | `motor.docs` / `motor.speak` after switches | outbound / dual-stream |
| `RunCommandTool` | Jarvis / shell chores only — not free root | tooling + QA |
| *(Cam)* `MeshRecallTool` | HMO primary→secondary→vault | always before invent |
| *(Cam)* `ConnectomeRouteTool` | hotspot pathway + switch resolve | per turn |
| *(Cam)* `TrajectoryCheckTool` | OCL/CPV policies | pre-motor |
| *(Cam)* `ClineTool` | `motor.cline` + workspace choose | autonomy |

Cam-specific tools wrap motors; they do **not** bypass `switch.*`.

## Runtime surface (planned)

| Piece | Path |
|---|---|
| Submodule | `integrations/sgr-agent-core` |
| Reasoning plan | `docs/CAM_REASONING.md` |
| Proposed config | `config/enhancement/reasoning-logic.json` |
| CLI orchestrator | `scripts/cam-reason.py` (Phase B — calls SGR) |
| Agent definition YAML | `config/sgr/cam-agents.yaml` (Phase B) |
| Motor | proposed `motor.sgr` under `center.capability` |

## Install (Aaron machine / cloud)

```bash
git submodule update --init integrations/sgr-agent-core
# or clone: https://github.com/afidurko/sgr-agent-core
pip install -e "integrations/sgr-agent-core[all]"   # or pip install "sgr-agent-core[all]"
```

Secrets stay in env (`SGR__*` / OpenAI-compatible key) — never commit.

## Non-goals

- SGR does not assign root tasks (Aaron only)
- SGR does not apply Cam enhance without `switch.cam_enhance`
- SGR does not replace Cline for multi-file coding
- Upstream DeepSearch Tavily stack is optional; Cam prefers vault → mesh → Scholar → web

## Docs

- Framework: https://vamplabai.github.io/sgr-agent-core/framework/main-concepts/
- Cam plan: [docs/CAM_REASONING.md](../../docs/CAM_REASONING.md)
