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

Calibration (`--report`) is **prequential** — each experience is predicted before it is revealed: Brier, log loss, ECE (10 bins) with a reliability table, AUROC, Brier skill against a Laplace running base rate, score MAE and 90% interval coverage, mean surprise, abstention rate, per-hotspot calibration parity, and a verdict (`insufficient_sample` / `not_yet_skillful` / `skillful_but_miscalibrated` / `skillful_and_calibrated`).

## Failure modes and survival measures

Each of these would have made the first draft wrong or dead; each has a countermeasure in `cam_experience.py` and a unit test in `SurvivalTests`.

| Failure | Measure |
|---|---|
| Same run in `loop-run-log.md` **and** `loop-runs/latest.json` counted twice | cross-source `dedupe` on `(ts, hotspot, pattern)`; same-source same-second records stay distinct (two QA cycles really did share a second) |
| Unparseable timestamp weighted as fresh (decay 1.0) | `unknown_ts_weight` 0.25; `coverage.unknown_timestamps` |
| Regime shift hidden by a 14-day half-life | EWMA of reward-prediction error per context → `drift_suspected`; posterior counts scaled by `drift_inflation` (interval widens) until surprise settles |
| Parent rate dominated by one child leaks to siblings (`center.qa` ≈ QA cycles) | parent with ≤1 distinct child passes `backoff_single_child_factor` of its prior strength |
| Crashed runs write no distillate → survivorship bias | `coverage.stale_contexts` (no record for `stale_after_days`), limitation stated on every card |
| One corrupt source file kills the load | per-source isolation → `coverage.source_errors` |
| Runtime log grows forever | rotation at `max_runtime_rows`, keep `keep_runtime_rows` |
| Writes continue during a kill | `CAM_KILL=1` refuses `--record`, `--forget-*`, distillates (exit 3); reads stay allowed |
| arXiv scan hammers six categories back-to-back → throttled | `min_interval_s` 3.0 in `agi-research-scan.py`, asserted by the ethics gate |
| Verdict trusted on 59 records with 2 failures | `insufficient_sample` until `min_n_for_verdict` and `min_outcomes_each_class` |

## Ethics

Config: `config/ethics/research-ethics.json` · gate: `scripts/research-ethics-check.py` (in `ci-static-gate`) · brief: `vault/04-Research/2026-09-22-Research-Ethics-Measures.md`.

- **Honesty / abstention** — below `abstention.min_effective_n` or above `max_interval_width`, `advice.stance = abstain`; `narration` is a hedged sentence that always carries the range, never a bare number.
- **Human primacy / protected contexts** — careers, outbound, Inkbox, money, identity, voice → `human_judgment_required`; no `suggest_qa_hold`; narration ends "the call is yours".
- **No persons as targets** — contexts are Cam's own hotspots/patterns; protected list blocks people-facing motors.
- **Data minimisation** — `redact()` strips emails, phones, tokens, bearer strings, SSNs on write; `redacted` marks the record; the gate scans tracked artefacts.
- **Right to forget** — `--forget-ref` / `--forget-key` rewrite the runtime log.
- **Fairness of confidence** — `calibration.parity` reports ECE per hotspot and flags gaps > 0.15.
- **Anti-Goodhart** — scores are reported, never optimised; P3 needs a held-out unbiased slice and `switch.cam_enhance`.
- **Source respect / reproducibility** — arXiv etiquette, identifying User-Agent, `## Sources` with accessed dates on every brief since 2026-09-22, versioned schema, prequential protocol.

## Run

```bash
python3 scripts/cam-predict.py --report                                   # live report → vault/10-Mesh-Distillates/predictive-cortex/latest.json
python3 scripts/cam-predict.py --report --offline                         # fixture only
python3 scripts/cam-predict.py --hotspot hotspot.loop_engineering --pattern daily-triage --sense sense.loop.tick
python3 scripts/cam-predict.py --sense sense.experience.outcome --goal "predict outcome from experience"
python3 scripts/cam-predict.py --narrate --hotspot hotspot.coding         # only the hedged sentence
python3 scripts/cam-predict.py --record --ok --hotspot hotspot.coding --score 88 --notes "PR green"
python3 scripts/cam-predict.py --forget-ref "run-42"                      # right to forget
CAM_KILL=1 python3 scripts/cam-predict.py --record --ok --hotspot x       # exit 3, nothing written
python3 scripts/predictive-cortex-check.py                                # wiring + offline smoke (in ci-static-gate)
python3 scripts/research-ethics-check.py                                  # ethics gate (in ci-static-gate)
```

MCP: `predict_experience {goal|hotspot|pattern, sense, report, offline}` in `scripts/cam-mcp-server.py`. Tool registry: `tool.predict.experience` (all roles and subagents, `switch.dl_local`).

## Boundaries

- Predictions never plan `motor.enhance`; `switch.kill` silences the route (checked).
- Small `n_effective` is reported, not hidden — `brier_skill ≤ 0` means "not yet better than the base rate".
- Closing the loop (P3 in the research plan) is a separate Aaron-gated proposal: `vault/02-Cam/enhancement-proposals/2026-09-22-predictive-cortex-from-experience.md`.

## Literature basis (short)

TD learning (Sutton 1988) · reward-prediction error (Schultz, Dayan & Montague 1997) · successor representations (Dayan 1993; Carvalho et al. 2024) · Bayesian forgetting (Adams & MacKay 2007) · calibration (Brier 1950; Guo et al. 2017) · agent calibration ([2609.09448](https://arxiv.org/abs/2609.09448), [2609.07395](https://arxiv.org/abs/2609.07395)) · experiential agents (ExpeL, Early Experience [2510.08558](https://arxiv.org/abs/2510.08558), OEL [2603.16856](https://arxiv.org/abs/2603.16856), MemRL [2601.03192](https://arxiv.org/abs/2601.03192)) · world models and replay (DreamerV3, ARROW [2603.11395](https://arxiv.org/abs/2603.11395), Agentic World Modeling [2604.22748](https://arxiv.org/abs/2604.22748)).
