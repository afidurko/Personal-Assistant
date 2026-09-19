# Cam Reasoning Logic (plan)

**Status:** plan — not applied  
**Owner:** Aaron (sole task-giver)  
**Depends on:** connectome route, dual-process, HMO/MMP, OCL/CPV, dual-stream, QA  
**Apply gate:** implementing the runtime engine is a Cam functionality change → `switch.cam_enhance` + proposal when ready

This doc unifies Cam’s already-applied cognition pieces into one **inspectable reasoning loop**. Today those pieces exist as configs and side scripts; they are not yet a single turn orchestrator.

## Why this plan

| Layer | Today | Gap |
|---|---|---|
| Route | `scripts/connectome-route.py` → hotspot pathway + motor_plan | No deliberative stages between sense and motor |
| Fast/slow | `config/enhancement/dual-process.json` | Declared only; converse/chief do not escalate |
| Language | `scripts/dual-stream-router.py` | Stream pick is separate from plan/act |
| MAP PFC | `mesh-params.planning_modules_map` | Labels only — no ordered stage runner |
| Memory | HMO tiers + AMM triggers | Not called as a pre-plan gate on every Aaron turn |
| Reflection | QA + trajectory policies | Pre-motor checks exist; not bound into a slow-path SRM step |
| Home converse | `server/core/cam-converse.ts` | Pattern replies — not connectome-backed reasoning |
| Autonomy | `server/core/cam-autonomy.ts` | Background self-tasks — not turn deliberation |

Goal: **one reasoning contract** every Aaron-rooted spike can run, with mesh-logged traces, without inventing goals or bypassing switches.

## Target loop (one turn)

```text
sense spike (Aaron-rooted)
  → 0. ACCEPT   switch.tasking / kill
  → 1. FAST     center.slm classify + route hint + compress   (System-1)
  → 2. GATE     escalate?  (see Escalation)
  → 3. RECALL   HMO primary → secondary → vault (salience-gated)
  → 4. PLAN     MAP stages (slow path only, or light plan on fast)
  → 5. STREAM   dorsal/ventral conflict policy for speak vs docs/research
  → 6. REFLECT  SRM: trajectory policies + mesh claim schema + persona
  → 7. SWITCH   resolve act/hold on required switches
  → 8. MOTOR    fire allowed effectors; log synapse + plasticity
  → 9. DISTILL  mesh/runs + converse distill; Hebbian weight update
```

Fast path may skip full MAP + heavy recall when confidence is high and the act is low-risk. Slow path always runs stages 3–6 before motor.

## Escalation (fast → slow)

Escalate to slow path when **any** of:

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

Config knobs live in proposed `config/enhancement/reasoning-logic.json`.

## MAP stages (slow path)

Aligned to `mesh-params.planning_modules_map`:

| Stage | Area / neuron | Job | Bus |
|---|---|---|---|
| Monitor | `area.cingulate` / `neuron.qa_cycle` | Conflict + prior-error context | `tract.cingulum` |
| Predict | `area.apfc` / `neuron.plan_loop` | Next-state / outcome sketch | `tract.ifof` |
| Evaluate | `area.ofc` / `neuron.boundary` | Risk, Aaron gates, identity | `tract.uncinate` |
| Decompose | `area.dlpfc` / `neuron.delegate_burst` | Subtasks + team spawn | `tract.slf` |
| Coordinate | `area.dlpfc` / `neuron.workspace_orchestrator` | Workspace leases / multi-agent | `tract.forceps_minor` |
| Propose act | `area.premotor` / `neuron.motor_plan` | Candidate motor_plan | `tract.corticospinal` |

Stages are **ordered and abortable**. Evaluate or Reflect may revise the plan (strip motors) without Aaron mid-task interruption when standing autonomy already covers the act.

## Memory gates (stage 3)

Before inventing Aaron facts:

1. HMO **primary** (persona, prefs, open tickets, last directives)  
2. Triggered **secondary** mesh namespaces (facts / projects / research / careers / cline / enhance)  
3. Vault / archive only when secondary is thin or cite-backed research is required  

AMM triggers from dual-process remain: `aaron_question`, `open_ticket`, `persona_check`.

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
  "escalation": ["low_confidence"],
  "stages": ["accept", "fast", "recall", "plan", "stream", "reflect", "switch", "motor"],
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
- Not a second brain — nullclaw / nullboiler remain executors; this is the **policy loop** they share  
- Not replacing Cline plan/act for code; coding still `motor.cline` after Cam’s route + workspace choose  

## Implementation phases

### Phase A — Spec + config (this PR)

- [x] `docs/CAM_REASONING.md` (this plan)  
- [x] Draft `config/enhancement/reasoning-logic.json` (`status: proposed`)  
- [x] Cross-links from `docs/CAM_BRAIN.md`, Operating Manual, chief role  

### Phase B — CLI orchestrator (next coding pass)

- [ ] `scripts/cam-reason.py` — dry-run + live modes  
  - Input: sense id, goal text, optional hotspot  
  - Calls: dual-process escalate → recall stubs → MAP stage list → dual-stream → `trajectory_policy_check` → emit trace JSON  
  - Reuse `connectome-route.py` for pathway / motor_plan baseline  
- [ ] `python3 scripts/cam-reason.py --sense sense.chat.aaron --goal "…" --dry-run`  
- [ ] Unit tests: escalate rules, kill silence, enhance strip, speak→dorsal  

### Phase C — Wire home converse + chief

- [ ] Replace / wrap `camReply` pattern matcher with reason-orchestrator for non-trivial turns  
- [ ] Fast path keeps soft airy short replies; slow path may spawn capability/info teams  
- [ ] Chief role doc: “run reasoning contract before motor” as rule 17  

### Phase D — Mesh + cortex UX

- [ ] Persist traces to `vault/10-Mesh-Distillates/reasoning/`  
- [ ] Live-activity reason strings include `reason:stage:*`  
- [ ] Optional cortex HUD mode: highlight MAP stage columns as a turn advances  

### Phase E — Aaron apply batch

- [ ] Enhancement proposal under `vault/02-Cam/enhancement-proposals/`  
- [ ] Flip `reasoning-logic.json` → `status: applied` only with `switch.cam_enhance`  
- [ ] `scripts/apply-cam-enhancements.py` + persistence manifest entry  

## Acceptance checks

| Check | Command / signal |
|---|---|
| Config validates | JSON schema / load in `cam-reason.py` |
| Kill still wins | `--kill` → empty motor_plan |
| Enhance held | plan never includes `motor.enhance` without `--enhance` |
| Personal facts | dry-run shows recall stage before invent |
| Dual-process | greeting → fast; “propose Cam change” → slow |
| Trace written | distill JSONL line per turn |

## Open questions for Aaron

1. Confidence threshold for fast→slow (default `0.65`)?  
2. Should home converse always run Phase B on every mic turn, or only when text length / intent score exceeds a bar?  
3. Max MAP subagent burst per turn before workspace lease (default inherit ASI ceiling `max_neuro_columns: 24`)?  
4. Prefer Python CLI first (Phase B) or TypeScript in `server/core` next to converse?

Interim defaults ship in the proposed JSON so implementation can proceed once Aaron answers or accepts interim.

## Related

- [CAM_BRAIN.md](CAM_BRAIN.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)  
- `config/enhancement/dual-process.json` · `config/connectome/mesh-params.json`  
- `config/connectome/trajectory-policies.json` · `config/memory/hmo-tiers.json`  
- Vault: `vault/03-Projects/Cam-Reasoning-Logic.md`
