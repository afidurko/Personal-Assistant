# Research Plan — Tools, AI studies, and prediction from experience (Cam)

**Accessed / drafted:** 2026-09-22  
**Assigned by:** Aaron — "plan for research; research tools for assistance; research AI studies; deep dive for deep learning networks and predictive measures based on experiences; enhance Cam."  
**Gate:** Scan + distill + implement *advisory* instruments = standing autonomy. Letting predictions change Cam's behaviour (routing bias, QA holds, motor fires) still needs `switch.cam_enhance`.

## Question

How should Cam research, and what should Cam build, so that she predicts outcomes from her own experience with honest, calibrated confidence — and gets steadily better at helping Aaron?

## Summary

Three tracks, one loop:

1. **Tools track** — which research-assistant tools and open literature APIs Cam should route through (brief: [[2026-09-22-Research-Tools-For-Cam]]).
2. **Studies track** — what the 2024–2026 literature says about deep learning networks that *predict from experience*: replay, world models, TD learning, successor representations, experiential LLM agents, and calibration (brief: [[2026-09-22-Deep-Learning-Prediction-From-Experience]]).
3. **Build track** — Cam's **predictive cortex**: an experience stream → predictive measures → prequential calibration, wired as `sense.experience.outcome → center.dl → switch.dl_local → motor.dl` (doc: `docs/PREDICTIVE_CORTEX.md`, config: `config/enhancement/predictive-cortex.json`).

The loop: every run Cam does becomes an experience → the predictor is scored *before* the outcome is known (prequential) → Brier / ECE / surprise tell Cam and Aaron how trustworthy her forecasts are → the daily AGI scan (rubric `enhance_predictive_cortex`) keeps feeding new methods → proposals go through the Aaron gate.

## Phases (technical scope, not calendar)

| Phase | Scope | Touchpoints | Status |
|---|---|---|---|
| P0 Instrument | Experience schema; ingest loop-run-log, QA cycles, reasoning traces, `--record`; Beta-Bernoulli + forgetting + backoff; TD(0) + surprise; prequential Brier/ECE/AUROC; CLI + MCP + check | `scripts/cam_experience.py`, `scripts/cam-predict.py`, `config/connectome/*`, `scripts/predictive-cortex-check.py` | **done (this batch, advisory)** |
| P1 Tools | Add OpenAlex / Semantic Scholar / Crossref lookups beside Scholar (`sense.web.scholar`); consult `public-apis` before inventing endpoints; keep 1 req/3 s etiquette on arXiv | `scripts/scholar-search.py`, `config/integrations/google-scholar.md`, `motor.public_apis` | proposed |
| P2 Signals | Emit experiences from `loop-run.py`, `qa-loop.py`, `cam_reason.py` automatically (writer hook); MemoryBear distillates of high-surprise events | `scripts/loop-run.py`, `scripts/cam_reason.py`, `motor.memorybear` | proposed |
| P3 Close loop | Use `p_success` / `surprise` to bias `pick_hotspot` and insert `center.qa` hold; TC-ECE per trajectory checkpoint | `scripts/connectome-route.py`, `center.qa`, `trajectory-policies.json` | **requires Aaron** (`switch.cam_enhance`) |
| P4 Learned predictor | Successor representation over hotspot sequences; small learned predictor (LoRA / gradient-boosted) once `experience_count` ≫ 1k; conformal intervals (ACI) for non-stationarity | `center.dl`, `config/enhancement/slm-dl.json` | proposed |

## How to run (today)

```bash
python3 scripts/cam-predict.py --report                       # calibration + per-context report
python3 scripts/cam-predict.py --hotspot hotspot.loop_engineering --pattern daily-triage
python3 scripts/cam-predict.py --sense sense.experience.outcome --goal "predict outcome from experience"
python3 scripts/cam-predict.py --record --ok --hotspot hotspot.coding --score 88 --notes "PR green"
python3 scripts/predictive-cortex-check.py                    # wiring + offline smoke
python3 scripts/agi-research-scan.py --dry-run                # scan now scores predictive-cortex papers
```

## Standing research questions (feed the daily scan)

- Step-level calibration ≠ trajectory-level calibration ([2609.07395](https://arxiv.org/abs/2609.07395)) — what checkpoint should Cam score at?
- Internal-state probes beat token log-probs for success prediction ([2609.09448](https://arxiv.org/abs/2609.09448)) — what is Cam's analogue when the "model" is a connectome route, not a transformer?
- Which memories are *worth* reusing (MemRL Q-values, [2601.03192](https://arxiv.org/abs/2601.03192)) vs. merely similar?
- Replay to a world model rather than to a policy (ARROW, [2603.11395](https://arxiv.org/abs/2603.11395)) — Cam's `fornix-consolidate.py` as the replay bus?
- Conformal / adaptive conformal intervals under release-driven shift ([2605.19779](https://arxiv.org/abs/2605.19779)).

## Counter-arguments / risks

- Small-n: with a 14-day half-life and ~1 experience/day per hotspot, `n_effective` is small; report `brier_skill` honestly (negative = not yet skillful). Do not act on thin evidence.
- Keyword scoring in the scan can over-weight video world-model papers that do not help a desktop assistant — prefer L1/L2 "predictor/simulator" methods over pixel generation.
- Prediction is not permission: the OCL / CPV policies remain the boundary; predictions never arm `motor.enhance`.

## Recommendation

Keep P0 advisory and let it accumulate real experiences; run `--report` in the daily triage; bring P3 (closing the loop) to Aaron as a separate proposal once `brier_skill > 0` and `ece < 0.1` hold on ≥ 200 real experiences.

## Sources

- Silver & Sutton, *Welcome to the Era of Experience* (2025) — cited via arXiv:2603.16856 §5 and arXiv:2601.03192 — accessed 2026-09-22  
- https://arxiv.org/abs/2609.07395 — Uncertainty Quantification for LLM Agents (TC-ECE) — accessed 2026-09-22  
- https://arxiv.org/abs/2609.09448 — Do Agents Know When They Succeed? — accessed 2026-09-22  
- https://arxiv.org/abs/2601.03192 — MemRL — accessed 2026-09-22  
- https://arxiv.org/abs/2603.11395 — ARROW — accessed 2026-09-22  
- https://arxiv.org/abs/2605.19779 — Distribution-free UQ for continuous agent evaluation — accessed 2026-09-22  
- Briefs: [[2026-09-22-Research-Tools-For-Cam]] · [[2026-09-22-Deep-Learning-Prediction-From-Experience]]
