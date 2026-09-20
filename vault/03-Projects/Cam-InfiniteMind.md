# Cam + InfiniteMind

Build on [Advanced-logic-reason-idea-and-learning-algorithms](https://github.com/afidurko/Advanced-logic-reason-idea-and-learning-algorithms) (InfiniteMind) as Cam’s formal/meta reasoning substrate.

- Submodule: `integrations/infinitemind`
- Policy: `config/integrations/infinitemind.md`
- Adapter: `python3 scripts/cam-infinitemind.py --goal "…"`
- Wired into slow path: `python3 scripts/cam-reason.py --goal "…" --no-write` (stage `logic`)
- Tests: `python3 scripts/test_cam_infinitemind.py`

## In / out this slice

**In:** LogicEngine, MetaReasoning, EpistemicConfidence, AbductiveHypothesisGenerator  
**Out:** torch RL agent, qiskit override, OpenAI idea generator, virtue-ethics demos

## Next

- Mesh-backed KnowledgeBase experience edges
- LitServe-gated idea generation (no hardcoded API keys)
- Calibrate epistemic threshold against Aaron feedback
