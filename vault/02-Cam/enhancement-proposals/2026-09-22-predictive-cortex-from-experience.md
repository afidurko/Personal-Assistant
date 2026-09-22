# Enhancement proposal — Predictive cortex: outcome prediction from Cam's experience

**Status:** P0 implemented as *advisory* instrument (Aaron request 2026-09-22: "deep dive for deep learning networks and predictive measures based on experiences … enhance Cam"). P3 "close the loop" **awaiting Aaron** (`switch.cam_enhance`).  
**Date:** 2026-09-22  
**Sources:** [[2026-09-22-Deep-Learning-Prediction-From-Experience]] · [[2026-09-22-Research-Tools-For-Cam]] · plan [[2026-09-22-Research-Plan-Predictive-Cam]]  
**Priority:** P0 instrument (done) · P3 behaviour change (proposed)  
**Relevance:** learning from experience · calibration · QA conflict monitoring · MAP `state_prediction` (area.apfc)

## Suggested Cam touchpoints

- `center.dl` / `dl-enhance` (owner) · `center.qa` (surprise → hold advisory) · `center.memory` (episodic store)
- `sense.experience.outcome` → `hotspot.predict_from_experience` → `motor.dl` (+ `motor.mesh`, `motor.vault`)
- `scripts/cam_experience.py` · `scripts/cam-predict.py` · MCP `predict_experience` · `tool.predict.experience`
- `config/enhancement/predictive-cortex.json` (parameters, sources, literature basis)

## Why it enhances Cam

Cam already records what she does (loop runs, QA cycles, reasoning traces) but never asked *"given what happened before, how likely is this to go well?"*. The literature is unanimous that prediction error is the learning signal (TD learning; era of experience; world models), and that agents need **trajectory-aware calibration**, not a single confidence number. Cam now:

1. Normalises every run into an *experience* (context: sense/hotspot/center/pattern/motors; outcome: ok/score/duration).
2. Predicts `p_success` with a Beta-Bernoulli posterior, exponential forgetting (14-day half-life) and hierarchical backoff so unseen hotspots inherit from their center / sense / global rates.
3. Tracks a TD(0) value and a `surprise` (|reward-prediction error|) per context — the plasticity signal.
4. Scores itself **prequentially** (Brier, log loss, ECE, AUROC, Brier skill vs. running base rate, score MAE and 90% interval coverage) so Aaron sees whether the forecasts deserve trust.

## Proposed mapping (config-first)

| Literature | Cam substrate |
|---|---|
| TD(0) / RPE | `td_value`, `surprise` per `hotspot:*`, `pattern:*`, `center:*` |
| Bayesian forgetting | `predictor.half_life_days` |
| Hierarchical shrinkage | `BACKOFF_ORDER` hotspot → pattern → center → sense → global |
| Prequential scoring | `--report` → `vault/10-Mesh-Distillates/predictive-cortex/latest.json` |
| MemRL utility of memories | `evidence[]` weighted by recency; `surprise` marks memories worth replaying |
| TC-ECE | P3: score at route / reflect / motor checkpoints |

## Apply gate

**P0 (this batch, advisory)** — no behaviour change: predictions are reports; `motor.enhance` never appears in the predictive route; kill switch silences it; `predictive-cortex-check` in `ci-static-gate`.

**P3 (needs Aaron)** —
1. Bias `pick_hotspot` by `p_success` when candidates tie.  
2. Let `center.qa` insert a hold when `advice.suggest_qa_hold` is true for motor plans touching `motor.cline`, `motor.jobs`, `motor.outbound`.  
3. Auto-emit experiences from `loop-run.py`, `qa-loop.py`, `cam_reason.py`.  
4. Criteria before asking: ≥ 200 real experiences, `brier_skill > 0`, `ece < 0.1` on the live report.

```bash
python3 scripts/cam-enhance-propose.py --proposal vault/02-Cam/enhancement-proposals/2026-09-22-predictive-cortex-from-experience.md
# Aaron approves P3:
python3 scripts/cam-enhance-propose.py --proposal ... --aaron-approve
```

## Apply record

- **P0 implemented (advisory)** 2026-09-22 — this checkout; verify with `python3 scripts/predictive-cortex-check.py` and `python3 scripts/cam-predict.py --report`.
- P3: pending Aaron.
