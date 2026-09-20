# InfiniteMind — advanced logic / idea / learning for Cam

Source: [afidurko/Advanced-logic-reason-idea-and-learning-algorithms](https://github.com/afidurko/Advanced-logic-reason-idea-and-learning-algorithms)  
Path: [`integrations/infinitemind`](../../integrations/infinitemind) (git submodule)  
Cam adapter: `scripts/cam_infinitemind.py`  
Policy status: **Phase C thin slice** — dry-run engines only

## Fast vs slow

| Gate | Owner | Speed | Engines |
|---|---|---|---|
| **Fast (System-1)** | `scripts/cam_fast.py` · `center.slm` | Budget ~8ms, LRU, skip heavy stages | Heuristic classify + light route |
| **Slow (System-2)** | InfiniteMind + SGR | Deliberate | Logic / meta / epistemic / abductive + ReasoningTool |

InfiniteMind is **not** on the fast gate. Putting QELR/RMA/QCS on every greeting would hurt Cam’s response speed. Speed enhancements belong in `cam_fast` (+ later LitServe sLM); depth belongs here.

| Engine | InfiniteMind module | Cam use |
|---|---|---|
| Logic (QELR) | `logic_engine.py` | Propositional axioms from switches + mesh; forward-chain motor allowances |
| Meta (RMA) | `meta_reasoning.py` | Strategy pick (analytical / analogical / creative / systematic) |
| Epistemic (QCS) | `epistemic_confidence.py` | Calibrated confidence before motor / FinalAnswer |
| Abductive (QECN) | `abductive_reasoning.py` | Best explanation for escalate vs stay-fast |
| Knowledge graph | `knowledge_base.py` | Later — experience edges into mesh distill (not Phase C) |
| Idea generator | `idea_generator.py` | **Deferred** — needs gated LitServe/OpenAI; no hardcoded keys |
| RL Agent / Quantum COL | `agent.py`, `conscious_override_layer.py` | **Out of scope** — torch/qiskit optional; trajectory OCL already covers override |

InfiniteMind is **not** a second task-giver and does **not** fire motors.

## Mapping onto Cam loop

```text
slow path (after recall):
  → InfiniteMind logic + meta + abductive + epistemic   (Stage: logic)
  → SGR ReasoningTool stub / live                       (Stage: sgr)
  → stream → reflect (trajectory) → switch → motor
```

Cam axioms asserted into `LogicEngine` (truth amplitude 1.0 unless noted):

- `aaron_only_tasking`
- `kill_silences_motors` when kill act
- `enhance_requires_switch` when enhance intent
- `prefer_mesh_before_invent` always
- recall hit notes as soft propositions (0.7–0.9)

## Non-goals (this slice)

- No torch RL training loop
- No qiskit / Cirq backends
- No autonomous idea spam via OpenAI Completion API
- No every-mic InfiniteMind (same bar as SGR)
- No virtue-ethics / solar-grid demos in Cam runtime

## Install

```bash
git submodule update --init integrations/infinitemind
# Core engines import without heavy deps (see OPTIONAL_DEPENDENCIES.md).
# numpy recommended for meta/epistemic scoring (already used by Cam fuzz).
```

## Runtime

```bash
python3 scripts/cam-infinitemind.py --goal "think carefully and make a plan"
python3 scripts/test_cam_infinitemind.py
python3 scripts/cam-reason.py --goal "enhance Cam" --no-write   # includes logic stage
```

Config: `config/enhancement/reasoning-logic.json` → `infinitemind` block.
