# Cam Reasoning Logic (plan)

**Status:** plan — not applied  
**Owner:** Aaron (sole task-giver)  
**Depends on:** connectome route, dual-process, HMO/MMP, OCL/CPV, dual-stream, QA, **SGR Agent Core**  
**SGR source:** [afidurko/sgr-agent-core](https://github.com/afidurko/sgr-agent-core) · `integrations/sgr-agent-core`  
**Apply gate:** runtime wiring is a Cam functionality change → `switch.cam_enhance` + proposal when ready

This doc unifies Cam’s cognition pieces into one **inspectable reasoning loop**, with **Schema-Guided Reasoning (SGR)** as the slow-path deliberative engine.

## Why this plan

| Layer | Today | Gap |
|---|---|---|
| Route | `scripts/connectome-route.py` → hotspot pathway + motor_plan | No deliberative stages between sense and motor |
| Fast/slow | `config/enhancement/dual-process.json` | Declared only; converse/chief do not escalate |
| Language | `scripts/dual-stream-router.py` | Stream pick is separate from plan/act |
| MAP PFC | `mesh-params.planning_modules_map` | Labels only — no ordered stage runner |
| **Schema reasoner** | **SGR submodule now present** | Not yet wrapped as Cam motor / tools |
| Memory | HMO tiers + AMM triggers | Not called as a pre-plan gate on every Aaron turn |
| Reflection | QA + trajectory policies | Pre-motor checks exist; not bound into a slow-path SRM step |
| Home converse | `server/core/cam-converse.ts` | Pattern replies — not connectome-backed reasoning |
| Autonomy | `server/core/cam-autonomy.ts` | Background self-tasks — not turn deliberation |

Goal: **one reasoning contract** every Aaron-rooted spike can run, with mesh-logged traces, without inventing goals or bypassing switches.

## SGR as System-2 substrate

Upstream SGR agents run:

```text
while state not in FINISH:
  reasoning = _reasoning_phase()   # ReasoningTool schema (or SO NextStep)
  tool      = _select_action_phase(reasoning)
  await _action_phase(tool)
```

Cam maps that onto the connectome:

| SGR phase | Cam stage | Center / neuron |
|---|---|---|
| ReasoningTool | MONITOR + PREDICT | `neuron.qa_cycle`, `neuron.plan_loop` |
| GeneratePlan / AdaptPlan | DECOMPOSE + COORDINATE | `neuron.delegate_burst`, `neuron.workspace_orchestrator` |
| Select action | EVALUATE + PROPOSE | `neuron.boundary` → `neuron.motor_plan` |
| Action (tool) | SWITCH → MOTOR | gated `motor.*` via Cam tool wrappers |
| ClarificationTool | HOLD + ask Aaron | never invent personal facts |
| FinalAnswer / report | STREAM + SPEAK/DOCS | dual-stream dorsal/ventral |

**Default agent class:** `SGRToolCallingAgent` (explicit reason schema + native tool pick).  
**Fallback:** `SGRAgent` for weaker local / sLM backends.  
**Avoid for gated paths:** bare `ToolCallingAgent` (no inspectable reason fields).

Integration policy: [`config/integrations/sgr-agent-core.md`](../config/integrations/sgr-agent-core.md)

### Cam toolkit (planned wrappers)

| Tool | Wraps |
|---|---|
| `MeshRecallTool` | HMO primary → secondary → vault |
| `ConnectomeRouteTool` | `connectome-route.py` pathway + switches |
| `TrajectoryCheckTool` | OCL/CPV (`trajectory-policies.json`) |
| `ScholarFetchTool` / web | `motor.web_fetch` + Scholar |
| `ClineTool` | `motor.cline` + workspace choose |
| `JarvisTool` | `motor.jarvis` |
| Upstream `ReasoningTool` / plan / clarify / final_answer | keep as system tools |

SGR tools never fire enhance/outbound/careers-submit without the matching `switch.*` act.

## Target loop (one turn)

```text
sense spike (Aaron-rooted)
  → 0. ACCEPT   switch.tasking / kill
  → 1. FAST     center.slm classify + route hint + compress   (System-1)
  → 2. GATE     escalate?  (see Escalation)
  → 3. RECALL   HMO primary → secondary → vault (salience-gated)
  → 4. SGR      Reasoning → Select → Act loop (MAP-aligned; slow path)
  → 5. STREAM   dorsal/ventral conflict policy for speak vs docs/research
  → 6. REFLECT  SRM: trajectory policies + mesh claim schema + persona
  → 7. SWITCH   resolve act/hold on required switches
  → 8. MOTOR    fire allowed effectors; log synapse + plasticity
  → 9. DISTILL  mesh/runs + converse distill; Hebbian weight update
```

Fast path may skip full SGR + heavy recall when confidence is high and the act is low-risk. Slow path always runs recall + at least one SGR reasoning iteration + reflect before motor.

## Escalation (fast → slow / SGR)

Escalate to SGR when **any** of:

1. Intent involves `enhance`, `outbound`, `careers_submit`, money, or identity-boundary edits  
2. Fast classifier confidence &lt; threshold (default `0.65`, tunable)  
3. Open ticket / standing goal requires multi-step decomposition  
4. Personal-fact question with weak mesh/vault hits  
5. QA / prior turn left a veto or trajectory violation  
6. Aaron explicitly asks to plan, research, or “think carefully”

Stay on fast path when:

- Greeting / ack / mic-check / presence chatter  
- Jarvis-style deterministic utility with clear args  
- Route hint maps to a single standing hotspot with no gated motors  

Config knobs: `config/enhancement/reasoning-logic.json`.

## MAP stages ↔ SGR tools

Aligned to `mesh-params.planning_modules_map`:

| Stage | Area / neuron | SGR hook | Bus |
|---|---|---|---|
| Monitor | `area.cingulate` / `neuron.qa_cycle` | `ReasoningTool.current_situation` | `tract.cingulum` |
| Predict | `area.apfc` / `neuron.plan_loop` | `ReasoningTool.remaining_steps` | `tract.ifof` |
| Evaluate | `area.ofc` / `neuron.boundary` | toolkit filter by switches | `tract.uncinate` |
| Decompose | `area.dlpfc` / `neuron.delegate_burst` | `GeneratePlanTool` / `AdaptPlanTool` | `tract.slf` |
| Coordinate | `area.dlpfc` / `neuron.workspace_orchestrator` | workspace lease + team spawn | `tract.forceps_minor` |
| Propose act | `area.premotor` / `neuron.motor_plan` | select_action → Cam motor tool | `tract.corticospinal` |

Stages are **ordered and abortable**. Evaluate or Reflect may revise the plan (strip motors) without Aaron mid-task interruption when standing autonomy already covers the act.

## Memory gates (stage 3)

Before inventing Aaron facts:

1. HMO **primary** (persona, prefs, open tickets, last directives)  
2. Triggered **secondary** mesh namespaces (facts / projects / research / careers / cline / enhance)  
3. Vault / archive only when secondary is thin or cite-backed research is required  

AMM triggers from dual-process remain: `aaron_question`, `open_ticket`, `persona_check`.  
Prefer `MeshRecallTool` inside SGR before `WebSearchTool`.

## Self-reflection (stage 6)

Reuse dual-process SRM checks:

- `trajectory_policies` (`config/connectome/trajectory-policies.json`)  
- `mesh_claim_schema`  
- `persona_consistency`  

On fail: revise motor_plan (strip / draft_only / propose_only) and log `mesh/runs` reason — do not fire gated motors.

## Trace schema (inspectable)

Every completed turn writes a compact claim (MMP-compatible) under `mesh/runs` / distillates:

```json
{
  "kind": "reasoning_trace",
  "sense": "sense.chat.aaron",
  "path": "slow",
  "engine": "sgr_tool_calling_agent",
  "escalation": ["low_confidence"],
  "sgr_iterations": 3,
  "reasoning_steps": ["…"],
  "stages": ["accept", "fast", "recall", "sgr", "stream", "reflect", "switch", "motor"],
  "hotspot_id": "hotspot.capability",
  "stream": "dorsal",
  "motor_plan": ["motor.mesh", "motor.speak"],
  "violations": [],
  "citations": [],
  "ts": "ISO-8601"
}
```

Cortex live feed may pulse tracts named in the active stages (same activity-events channel as autonomy).

## Non-goals

- No autonomous goal genesis across the commissural mesh  
- No silent `motor.enhance` (Aaron gate stays)  
- SGR is not a second brain — nullclaw / nullboiler remain executors; SGR is the **schema loop** for slow path  
- Not replacing Cline plan/act for code; coding still `motor.cline` after Cam’s route + workspace choose  
- Upstream Tavily DeepSearch stack is optional; Cam order stays vault → mesh → Scholar → web  

## Implementation phases

### Phase A — Spec + SGR checkout (this PR)

- [x] `docs/CAM_REASONING.md` (this plan)  
- [x] Draft `config/enhancement/reasoning-logic.json` (`status: proposed`)  
- [x] `config/integrations/sgr-agent-core.md` + submodule `integrations/sgr-agent-core`  
- [x] Registry + cross-links (brain, chief, Operating Manual)  

### Phase B — CLI orchestrator + Cam toolkit

- [ ] `scripts/cam-reason.py` — dry-run + live modes  
  - Fast gate → recall stubs → escalate to SGR agent with Cam toolkit  
  - Reuse `connectome-route.py` for pathway / motor_plan baseline  
  - Emit reasoning_trace JSON  
- [ ] `config/sgr/cam-agents.yaml` — Cam AgentDefinition(s)  
- [ ] Cam tools: MeshRecall, ConnectomeRoute, TrajectoryCheck, Cline, Scholar  
- [ ] Tests: escalate rules, kill silence, enhance strip, speak→dorsal, SGR reason schema present  

### Phase C — Wire home converse + chief

- [ ] Replace / wrap `camReply` for non-trivial turns → `cam-reason` / SGR  
- [ ] Fast path keeps soft airy short replies; slow path may spawn capability/info teams via SGR  
- [ ] Chief rule 17 stays authoritative  

### Phase D — Mesh + cortex UX

- [ ] Persist traces to `vault/10-Mesh-Distillates/reasoning/`  
- [ ] Live-activity `reason:sgr:*` pulses  
- [ ] Optional cortex HUD: highlight MAP columns as SGR iterations advance  

### Phase E — Aaron apply batch

- [ ] Enhancement proposal under `vault/02-Cam/enhancement-proposals/`  
- [ ] Flip `reasoning-logic.json` → `status: applied` only with `switch.cam_enhance`  
- [ ] Optional `motor.sgr` in `config/connectome/motor.json` + hotspot wiring  
- [ ] Persistence manifest entry  

## Acceptance checks

| Check | Command / signal |
|---|---|
| Submodule present | `integrations/sgr-agent-core/sgr_agent_core/` |
| Config validates | load `reasoning-logic.json` in `cam-reason.py` |
| Kill still wins | `--kill` → empty motor_plan |
| Enhance held | plan never includes `motor.enhance` without `--enhance` |
| Personal facts | dry-run shows recall / MeshRecall before invent |
| Dual-process | greeting → fast; “propose Cam change” → SGR slow |
| SGR schema | slow path logs `ReasoningTool` fields |
| Trace written | distill JSONL line per turn |

## Open questions for Aaron

1. Confidence threshold for fast→SGR (default `0.65`)?  
2. Should home converse always run SGR on every mic turn, or only when text length / intent score exceeds a bar?  
3. Max SGR iterations / MAP subagent burst per turn (default inherit ASI ceiling `max_neuro_columns: 24`)?  
4. Confirm default agent: `SGRToolCallingAgent` vs `SGRAgent` for local sLM?  
5. Prefer Python CLI first (Phase B) or TypeScript bridge in `server/core` next to converse?

Interim defaults ship in the proposed JSON so implementation can proceed once Aaron answers or accepts interim.

## Related

- [CAM_BRAIN.md](CAM_BRAIN.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)  
- [config/integrations/sgr-agent-core.md](../config/integrations/sgr-agent-core.md)  
- `config/enhancement/dual-process.json` · `config/connectome/mesh-params.json`  
- `config/connectome/trajectory-policies.json` · `config/memory/hmo-tiers.json`  
- Vault: `vault/03-Projects/Cam-Reasoning-Logic.md`  
- Upstream concepts: https://vamplabai.github.io/sgr-agent-core/framework/main-concepts/
