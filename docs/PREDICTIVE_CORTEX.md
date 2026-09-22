# Cam Predictive Cortex — outcome prediction from experience

Cam predicts how her own work will go, from how it went before — and says how much to trust the number.

**Status:** implemented as an *advisory* instrument (Aaron, 2026-09-22). Using predictions to change routing, insert QA holds, or fire motors remains behind `switch.cam_enhance`.

Config: [`config/enhancement/predictive-cortex.json`](../config/enhancement/predictive-cortex.json) · Library: `scripts/cam_experience.py` · CLI: `scripts/cam-predict.py` · Check: `scripts/predictive-cortex-check.py` · Tests: `scripts/test_cam_experience.py`
Research: [`vault/04-Research/2026-09-22-Research-Plan-Predictive-Cam.md`](../vault/04-Research/2026-09-22-Research-Plan-Predictive-Cam.md) · briefs on [tools](../vault/04-Research/2026-09-22-Research-Tools-For-Cam.md) and [deep learning / prediction from experience](../vault/04-Research/2026-09-22-Deep-Learning-Prediction-From-Experience.md)

## Pathway

```text
sense.experience.outcome ─► center.dl (area.apfc · MAP state_prediction) ─► switch.dl_local ─► motor.dl
          │                        │                                         side effects: motor.mesh, motor.vault
          ├─► center.memory (episodic store, HMO secondary)
          └─► center.qa    (high surprise → conflict monitor may advise a hold)
```

Hotspot `hotspot.predict_from_experience` · neuron `neuron.predict_experience` · tracts `tract.ifof`, `tract.fornix`.

## Experience stream

Every source is read in place — nothing else in Cam had to change:

| Source | File | Outcome |
|---|---|---|
| loop runs | `loop-run-log.md`, `vault/10-Mesh-Distillates/loop-runs/latest.json` | `status == ok`, score |
| QA cycles | `vault/10-Mesh-Distillates/qa-cycles/*/cycle.json` | `status == green`, pass ratio, wall time |
| reasoning traces | `vault/10-Mesh-Distillates/reasoning/*.jsonl` | no trajectory violations |
| recorded | `data/runtime/experiences.jsonl` (`cam-predict.py --record`) | as recorded |

Schema (`make_experience`): `ts`, `source`, `context{sense, hotspot, center, pattern, motors}`, `outcome{ok, score, duration_s}`, `notes`, `ref`.

## Predictive measures

| Field | Method |
|---|---|
| `p_success`, `credible_interval` | Beta-Bernoulli posterior; exponential forgetting (`half_life_days` = 14); hierarchical backoff hotspot → pattern → center → sense → global (parent mean becomes child prior, strength 2) |
| `expected_score`, `expected_duration_s` | recency-weighted mean / std at the finest context with evidence |
| `td_value`, `last_surprise` | TD(0): `V ← V + α (r − V)`, α = 0.2; surprise = |reward-prediction error| |
| `surprise_if_ok`, `surprise_if_fail` | −log p of each possible outcome |
| `confidence` | 1 − credible-interval width |
| `advice` | `expect_success` · `expect_friction` · `thin_evidence` · `no_experience_yet`; `suggest_qa_hold`, `suggest_gather_more` (advisory) |

Calibration (`--report`) is **prequential** — each experience is predicted before it is revealed: Brier, log loss, ECE (10 bins) with a reliability table, AUROC, Brier skill against a Laplace running base rate, score MAE and 90% interval coverage, mean surprise, and a verdict (`not_yet_skillful` / `skillful_but_miscalibrated` / `skillful_and_calibrated`).

## Run

```bash
python3 scripts/cam-predict.py --report                                   # live report → vault/10-Mesh-Distillates/predictive-cortex/latest.json
python3 scripts/cam-predict.py --report --offline                         # fixture only
python3 scripts/cam-predict.py --hotspot hotspot.loop_engineering --pattern daily-triage --sense sense.loop.tick
python3 scripts/cam-predict.py --sense sense.experience.outcome --goal "predict outcome from experience"
python3 scripts/cam-predict.py --record --ok --hotspot hotspot.coding --score 88 --notes "PR green"
python3 scripts/predictive-cortex-check.py                                # wiring + offline smoke (in ci-static-gate)
```

MCP: `predict_experience {goal|hotspot|pattern, sense, report, offline}` in `scripts/cam-mcp-server.py`. Tool registry: `tool.predict.experience` (all roles and subagents, `switch.dl_local`).

## Boundaries

- Predictions never plan `motor.enhance`; `switch.kill` silences the route (checked).
- Small `n_effective` is reported, not hidden — `brier_skill ≤ 0` means "not yet better than the base rate".
- Closing the loop (P3 in the research plan) is a separate Aaron-gated proposal: `vault/02-Cam/enhancement-proposals/2026-09-22-predictive-cortex-from-experience.md`.

## Literature basis (short)

TD learning (Sutton 1988) · reward-prediction error (Schultz, Dayan & Montague 1997) · successor representations (Dayan 1993; Carvalho et al. 2024) · Bayesian forgetting (Adams & MacKay 2007) · calibration (Brier 1950; Guo et al. 2017) · agent calibration ([2609.09448](https://arxiv.org/abs/2609.09448), [2609.07395](https://arxiv.org/abs/2609.07395)) · experiential agents (ExpeL, Early Experience [2510.08558](https://arxiv.org/abs/2510.08558), OEL [2603.16856](https://arxiv.org/abs/2603.16856), MemRL [2601.03192](https://arxiv.org/abs/2601.03192)) · world models and replay (DreamerV3, ARROW [2603.11395](https://arxiv.org/abs/2603.11395), Agentic World Modeling [2604.22748](https://arxiv.org/abs/2604.22748)).
