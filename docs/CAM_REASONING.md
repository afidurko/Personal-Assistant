# Cam Reasoning Logic (plan)

**Status:** plan — not applied  
**Owner:** Aaron (sole task-giver)  
**Depends on:** connectome route, dual-process, HMO/MMP, OCL/CPV, dual-stream, QA, **SGR Agent Core**, **LitServe**  
**SGR source:** [afidurko/sgr-agent-core](https://github.com/afidurko/sgr-agent-core) · `integrations/sgr-agent-core`  
**Inference host:** [afidurko/LitServe](https://github.com/afidurko/LitServe) · `integrations/litserve`  
**Apply gate:** runtime wiring is a Cam functionality change → `switch.cam_enhance` + proposal when ready

This doc unifies Cam’s cognition pieces into one **inspectable reasoning loop**, with **Schema-Guided Reasoning (SGR)** as the slow-path deliberative engine and **LitServe** as the local sLM/DL (and optional OpenAI-compatible) inference host.

## Why this plan

| Layer | Today | Gap |
|---|---|---|
| Route | `scripts/connectome-route.py` → hotspot pathway + motor_plan | No deliberative stages between sense and motor |
| Fast/slow | `config/enhancement/dual-process.json` | Declared only; converse/chief do not escalate |
| Language | `scripts/dual-stream-router.py` | Stream pick is separate from plan/act |
| MAP PFC | `mesh-params.planning_modules_map` | Labels only — no ordered stage runner |
| **Schema reasoner** | **SGR submodule present** | Not yet wrapped as Cam motor / tools |
| **Inference host** | **LitServe submodule present** | No Cam LitAPI wrappers / `cam-litserve` yet |
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

## LitServe as local inference host

[afidurko/LitServe](https://github.com/afidurko/LitServe) (`integrations/litserve`) hosts Cam’s model motors:

```text
fast path  → LitServe sLM classify / compress / route hint
slow path  → SGR ──AsyncOpenAI──► LitServe /v1/chat/completions  (or Aaron-configured cloud)
DL jobs    → LitServe embed / rerank
```

Policy: [`config/integrations/litserve.md`](../config/integrations/litserve.md) · recipe: `config/enhancement/slm-dl.json`  
Kill / `switch.slm_local` / `switch.dl_local` still gate every call.

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
  → 1. FAST     center.slm via **LitServe** classify + route hint + compress   (System-1)
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

## Cut list — slow or does not make sense

Do **not** pull these into the first implementation pass:

| Cut | Why |
|---|---|
| SGR / full reasoner on **every mic turn** | Slow, expensive, breaks soft presence chatter; use intent/length bar |
| TypeScript `server/core` reasoner **before** Python CLI | SGR is Python; dual runtimes double work for no gain |
| Full LitServe **model host** (weights, vLLM, multi-GPU, batching) | Slow to stand up; premature until dry-run loop + escalate rules work |
| LitServe **MCP + batch classify + streaming TTS** in Phase B | Perf/polish; not required for inspectable Reason→Select→Act |
| SGR **Skills / ACP slash commands** as Cam roles | Extra abstraction before Cam toolkit + gates exist |
| First toolkit includes **ClineTool + Scholar + Jarvis** | Wide surface; first pass only MeshRecall / ConnectomeRoute / TrajectoryCheck / FinalAnswer |
| Formal **`motor.sgr` + hotspot** before CLI proves the loop | Config churn; add in apply batch (Phase E) |
| Cortex **MAP HUD** animation of stages | UX polish; distill JSONL traces first |
| Bare **`ToolCallingAgent`** on gated paths | No inspectable reason schema — unsafe for enhance/outbound |
| Upstream **Tavily DeepSearch** as default research | Conflicts with vault → mesh → Scholar → web |

## Thin slice (do this)

1. `scripts/cam-reason.py --dry-run` — accept → fast heuristics → escalate? → stub recall → stub SGR reason schema → trajectory strip → trace JSON  
2. Cam `ReasoningTool` fields: `hotspot_id`, `switch_risks[]`, `stream`  
3. Escalate **bar only** (not every converse turn)  
4. LitServe **deferred** until dry-run green; then thin classify **stub** or OpenAI-compatible **proxy**, not a full local LLM farm  

## Implementation phases

### Phase A — Spec + SGR + LitServe checkout (this PR)

- [x] `docs/CAM_REASONING.md` (this plan)  
- [x] Draft `config/enhancement/reasoning-logic.json` (`status: proposed`)  
- [x] `config/integrations/sgr-agent-core.md` + submodule `integrations/sgr-agent-core`  
- [x] `config/integrations/litserve.md` + submodule `integrations/litserve`  
- [x] Registry + cross-links (brain, chief, Operating Manual)  
- [x] Cut list: slow / nonsensical upgrades deferred  

### Phase B — Thin CLI (no LitServe farm, no converse rewrite)

- [ ] `scripts/cam-reason.py` — **dry-run first**, then optional live  
  - Fast gate (heuristics OK; LitServe classify later)  
  - Escalate bar → stub/real SGR one iteration  
  - Cam tools **only**: MeshRecall, ConnectomeRoute, TrajectoryCheck, FinalAnswer  
  - Emit `reasoning_trace` JSONL under `vault/10-Mesh-Distillates/reasoning/`  
- [ ] Cam `ReasoningTool` subclass with hotspot / switch_risks / stream  
- [ ] Tests: greeting→fast, enhance→slow+strip, kill→empty, weak facts→recall before invent  
- [ ] Explicitly **out of B:** `cam-litserve.py`, converse wire, Cline/Scholar tools, cortex HUD  

### Phase C — Converse (barred only) + LitServe thin host

- [ ] Wrap `camReply` **only** when intent/length bar trips; greetings stay pattern-fast  
- [ ] `scripts/cam-litserve.py` — classify stub + optional `/v1/chat/completions` **proxy** (not vLLM)  
- [ ] Point SGR AgentDefinition `base_url` at LitServe when local switch act  

### Phase D — Mesh polish (after B/C useful)

- [ ] Live-activity `reason:sgr:*` pulses  
- [ ] Optional cortex HUD (last)  

### Phase E — Aaron apply batch

- [ ] Enhancement proposal under `vault/02-Cam/enhancement-proposals/`  
- [ ] Flip `reasoning-logic.json` → `status: applied` only with `switch.cam_enhance`  
- [ ] Then optional `motor.sgr` + hotspot + Cline/Scholar toolkit expansion  
- [ ] Persistence manifest entry  

## Acceptance checks

| Check | Command / signal |
|---|---|
| Submodule present | `integrations/sgr-agent-core/` · `integrations/litserve/` |
| Config validates | load `reasoning-logic.json` in `cam-reason.py` |
| Kill still wins | `--kill` → empty motor_plan |
| Enhance held | plan never includes `motor.enhance` without `--enhance` |
| Personal facts | dry-run shows recall before invent |
| Dual-process | greeting → fast; “propose Cam change” → SGR slow |
| SGR schema | slow path logs Cam `ReasoningTool` fields |
| No mic spam | converse bar skips SGR on greetings / short ack |
| Trace written | distill JSONL line per dry-run |

## Open questions for Aaron (narrowed)

Interim answers locked unless you override:

| # | Question | Interim (locked) |
|---|---|---|
| 1 | Fast→SGR confidence | `0.65` |
| 2 | Every mic turn vs bar | **bar only** (cut every-turn) |
| 3 | Max SGR iterations / burst | inherit ASI ceiling; start **max 4 iterations** dry-run |
| 4 | Agent class | **`SGRToolCallingAgent`**; `SGRAgent` only if local model can't FC |
| 5 | Python CLI vs TS first | **Python CLI first** (cut TS-first) |
| 6 | LitServe bind | `127.0.0.1:8080`; Tailscale later |

Still useful to confirm: whether Phase B may call a **cloud** OpenAI-compatible endpoint for live SGR, or dry-run stubs only until LitServe proxy exists.

## Related

- [CAM_BRAIN.md](CAM_BRAIN.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)  
- [config/integrations/sgr-agent-core.md](../config/integrations/sgr-agent-core.md)  
- [config/integrations/litserve.md](../config/integrations/litserve.md)  
- `config/enhancement/dual-process.json` · `config/enhancement/slm-dl.json` · `config/connectome/mesh-params.json`  
- `config/connectome/trajectory-policies.json` · `config/memory/hmo-tiers.json`  
- Vault: `vault/03-Projects/Cam-Reasoning-Logic.md`  
- Upstream concepts: https://vamplabai.github.io/sgr-agent-core/framework/main-concepts/ · https://lightning.ai/docs/litserve
