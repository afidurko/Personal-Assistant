# Research Brief — Deep learning networks and predictive measures based on experience

**Accessed:** 2026-09-22  
**Question:** Which deep-learning architectures and learning rules let an agent predict outcomes from its *own* past experience, and which measures tell us whether those predictions can be trusted? What transfers to Cam?  
**Method:** Deep dive across four literatures — reinforcement learning / world models, neuroscience-inspired memory, experiential LLM agents, and calibration / uncertainty — using 2024–2026 surveys and primary papers, then mapping each mechanism onto Cam's connectome.  
**Gate:** Distill + advisory instrument. Behaviour changes remain Aaron's (`switch.cam_enhance`).

## Summary

1. **Prediction is the learning signal.** From TD learning (Sutton 1988) and dopamine reward-prediction error (Schultz, Dayan & Montague 1997) to Silver & Sutton's *Era of Experience* (2025), the unifying idea is: predict, observe, update on the *error*. Cam's predictive cortex implements exactly this loop (TD(0) value + `surprise`).
2. **Networks that predict from experience** come in layers of ambition: (a) tabular / Bayesian estimators over context keys; (b) sequence models over trajectories (RNN/LSTM, Transformers, Decision Transformer); (c) **world models** that learn latent dynamics and imagine futures (PlaNet → Dreamer → DreamerV3, JEPA / V-JEPA 2, Genie); (d) LLM agents that turn trajectories into reusable *experiential knowledge* (Reflexion, ExpeL, Early Experience, OEL, MemRL, ExpWeaver). [1][2][3][4][5][6]
3. **Replay is how experience becomes prediction.** Complementary Learning Systems theory — hippocampus replays to a slow neocortical predictor — is now literal engineering: ARROW replays to a DreamerV3 world model with short- and long-term buffers; NeuroSynth separates fast acquisition from slow consolidation; predictive-coding replay improves retention. Human hippocampal recordings (2026) tie replay to updating a **successor representation**. [7][8][9][10][11]
4. **Predictive measures that matter:** Brier score, log loss, ECE (and its trajectory-aware variant TC-ECE), AUROC, Brier skill vs. climatology, interval coverage, and *conformal* guarantees under shift. Agent-specific findings: token log-probs are weak success predictors; trajectory dynamics and internal representations are stronger; step-level calibration does not imply trajectory-level calibration. [12][13][14][15][16]
5. **For Cam:** start with a small-data-honest Bayesian estimator with forgetting and hierarchical backoff (done), score it prequentially, and only escalate to learned sequence models / successor representations once the experience stream is large.

## 1. Foundations — predicting from experience

| Idea | Mechanism | Cam mapping |
|---|---|---|
| TD learning (Sutton 1988) | \(V \leftarrow V + \alpha\,(r - V)\); error drives learning | `td_value`, `surprise` per context key |
| Reward-prediction error (Schultz et al. 1997) | dopamine ≈ TD error | `surprise` → `center.qa` edge (conflict monitor) |
| Successor representation (Dayan 1993; Carvalho et al. 2024 review) | cache expected future state occupancy; fast re-evaluation when rewards change | P4: SR over hotspot sequences ("what follows a failure") [11] |
| Bayesian forgetting (Adams & MacKay 2007) | non-stationary Bernoulli → discount old evidence | `half_life_days` exponential forgetting in the Beta posterior |
| Hierarchical shrinkage | parent posterior becomes child prior | backoff hotspot → pattern → center → sense → global |
| Prequential evaluation (Dawid 1984) | score each forecast before its outcome | `prequential()` in `cam_experience.py` |

## 2. Deep networks that predict from experience

**Sequence models over trajectories.** LSTM / Transformers trained on (state, action, outcome) sequences; Decision Transformer (Chen et al. 2021) conditions on return-to-go. Useful once Cam has thousands of traces; overkill today.

**World models (latent dynamics + imagination).** The 2026 surveys agree on the framing: a world model is a predictive latent-dynamics system that supports planning and closed-loop evaluation, not pixel realism. [1][2][3]
- *Dreamer family* (PlaNet → DreamerV3 → Dreamer 4): RSSM latent state, symlog targets, imagination rollouts; DreamerV3 (Nature 2025) is the reference single-config agent. [2][3]
- *JEPA / V-JEPA 2*: predict future **representations**, not pixels — the right granularity for Cam, whose "observations" are mesh/vault states, not video. [1][2]
- *Agentic World Modeling* taxonomy: **L1 Predictor** (one-step transitions) → **L2 Simulator** (multi-step action-conditioned) → **L3 Evolver** (revises itself when predictions fail); four law regimes (physical, digital, social, scientific). Cam's predictive cortex is an L1 predictor in the *digital/social* regime; the `surprise` channel is the seed of L3. [2]
- *World Action Models* ("dream less, act more") and *embodied WM* ("plausible → controllable → actionable") both argue evaluation should measure improved behaviour, not fidelity — matching Cam's advisory-first stance. [3][17]
- Open problems named across surveys: compounding errors, weak action conditioning, **uncertainty calibration**, long-horizon consistency. [1][2][17]

**Replay and continual learning (brain-inspired).**
- ARROW: replay experiences to the *world model* (not the policy) with a short-term FIFO plus a long-term distribution-matching buffer; less forgetting at equal memory. [7]
- NeuroSynth: dual pathways — fast hippocampal-like acquisition, slow cortical consolidation, replay + distillation. [8]
- Predictive-coding generative replay: ~15% better retention than backprop replay in the reported study. [9]
- Human single-neuron evidence (2026): replay at rest supports future structure learning; replay during decisions supports immediate judgments — both modelled as SR updates. [10]
- Cam analogue: `fornix-consolidate.py` + MemoryBear as the replay bus; experiences with high `surprise` are the ones worth replaying.

## 3. LLM agents as experiential learners

| Work | Mechanism | Weight updates? | Transfer to Cam |
|---|---|---|---|
| Reflexion (2023) | verbal self-reflection stored in episodic memory | no | reasoning trace notes |
| ExpeL (AAAI 2024) | extract insights from trajectories into external memory | no | vault `Research Brief` distillates |
| Early Experience (arXiv:2510.08558) | implicit world modelling + self-reflection from the agent's own future states, reward-free | yes | seed for P4 learned predictor |
| OEL (arXiv:2603.16856) | extract experiential knowledge from deployment trajectories, consolidate by on-policy context distillation | yes | daily distill → sLM candidates |
| MemRL (arXiv:2601.03192) | runtime RL learns Q-values for *which* episodic memories to reuse; backbone frozen | no (memory utility only) | `td_value` per experience key |
| ExpWeaver (arXiv:2605.07164) | reasoning → optional experience use → action; learnable with GRPO | optional | make `predict_experience` an optional MCP step in Cam's SGR loop |
| ForecastCompass (arXiv:2605.30858) | factor memory + calibration memory, revised via retrospective analysis | no | store calibration lessons next to predictions |

## 4. Predictive measures — how to know a prediction is trustworthy

| Measure | What it tells you | In Cam |
|---|---|---|
| Brier score (Brier 1950) | mean squared error of probabilities | `calibration.brier` |
| Brier skill vs. running base rate | are we better than "always predict the average"? | `brier_skill` (negative = not yet) |
| Log loss | penalises confident misses | `log_loss` |
| ECE (Naeini 2015; Guo 2017) | confidence vs. accuracy gap across bins | `ece`, `reliability` table |
| TC-ECE (arXiv:2609.07395) | calibration at trajectory checkpoints; step-OK ≠ trajectory-OK | P3 — score at route, reflect, and motor stages |
| AUROC | discrimination of ok vs. fail | `auroc` |
| Credible / conformal intervals | honest width; ACI adapts under shift (arXiv:2605.19779) | Beta 90% interval today; ACI proposed |
| Surprise (−log p of what happened) | prediction error as plasticity signal | `surprise_if_ok`, `surprise_if_fail`, `last_surprise` |

Agent-specific evidence: internal-representation probes (LTD, ARP) beat calibrated log-probs and trajectory-confidence baselines on AUROC/Brier across Bash/SQL/Python agents [12]; averaging over trajectories hides late-stage overconfidence [13]; conformal search (CAS) uses APS + ACI to guarantee coverage in agentic retrieval [14]; forecasting agents improve Brier/ECE with explicit calibration memory [15]; Brier-trained reward gives best Brier while log-trained can yield better ECE [16].

## What Cam now does (P0, advisory)

```text
sense.experience.outcome → center.dl → switch.dl_local → motor.dl   (+ motor.mesh, motor.vault)
experiences: loop-run-log.md · qa-cycles/*/cycle.json · reasoning/*.jsonl · data/runtime/experiences.jsonl
measures:    p_success + 90% CI · expected score/duration · td_value · surprise · Brier/ECE/AUROC/skill
```

## Counter-arguments / risks

- Small data: Bayesian + forgetting is the right first estimator; learned networks would overfit Cam's dozens of experiences.
- Video-centric world models are a distraction for a desktop assistant; keep the L1/L2 *digital regime* framing.
- Calibration on stationary benchmarks does not survive release shifts — plan ACI, report by horizon.
- Prediction ≠ permission: OCL / CPV policies still bound motors; `motor.enhance` is never in the predictive route.

## Recommendation

Adopt the loop *predict → observe → surprise → replay → re-predict* as Cam's learning contract; keep the estimator small and honest; add SR / learned predictors and conformal intervals only after the experience stream shows positive Brier skill on real runs; bring "closing the loop" to Aaron as its own proposal.

## Sources

- [1] https://arxiv.org/abs/2606.00133 — World Models: A Comprehensive Survey — accessed 2026-09-22  
- [2] https://arxiv.org/abs/2604.22748 — Agentic World Modeling: Foundations, Capabilities, Laws — accessed 2026-09-22  
- [3] https://arxiv.org/abs/2606.20781 — World Action Models: A Survey — accessed 2026-09-22  
- [4] https://arxiv.org/abs/2510.08558 — Agent Learning via Early Experience — accessed 2026-09-22  
- [5] https://arxiv.org/abs/2603.16856 — Online Experiential Learning for Language Models — accessed 2026-09-22  
- [6] https://arxiv.org/abs/2605.07164 — Rethinking Experience Utilization (ExpWeaver) — accessed 2026-09-22  
- [7] https://arxiv.org/abs/2603.11395 — ARROW: Augmented Replay for Robust World Models — accessed 2026-09-22  
- [8] https://arxiv.org/abs/2607.28663 — NeuroSynth continual RL — accessed 2026-09-22  
- [9] https://arxiv.org/abs/2512.00619 — Neuroscience-inspired memory replay (predictive coding) — accessed 2026-09-22  
- [10] https://aaron.bornstein.org/cv/pubs/2026_gbkfsb_ccn_2pg.pdf — Replay updates a successor representation (CCN 2026) — accessed 2026-09-22  
- [11] Carvalho, Tomov, de Cothi, Barry & Gershman (2024) *Predictive Representations: Building Blocks of Intelligence*, Annual Review of Psychology — accessed 2026-09-22  
- [12] https://arxiv.org/abs/2609.09448 — Do Agents Know When They Succeed? — accessed 2026-09-22  
- [13] https://arxiv.org/abs/2609.07395 — Uncertainty Quantification for LLM Agents (TC-ECE) — accessed 2026-09-22  
- [14] https://arxiv.org/abs/2608.20771 — CAS: Conformalized Agentic Search — accessed 2026-09-22  
- [15] https://arxiv.org/abs/2605.30858 — ForecastCompass — accessed 2026-09-22  
- [16] https://arxiv.org/abs/2605.19779 — Distribution-Free UQ for Continuous AI Agent Evaluation — accessed 2026-09-22  
- [17] https://arxiv.org/abs/2609.16697 — World Models for Embodied Intelligence: Plausible → Controllable → Actionable — accessed 2026-09-22  
- MemRL https://arxiv.org/abs/2601.03192 · ExpeL https://arxiv.org/abs/2308.10144 · Reflexion https://arxiv.org/abs/2303.11366 · DreamerV3 https://arxiv.org/abs/2301.04104 · Decision Transformer https://arxiv.org/abs/2106.01345 · Guo et al. 2017 https://arxiv.org/abs/1706.04599 · Adams & MacKay 2007 https://arxiv.org/abs/0710.3742 · Sutton 1988 *Machine Learning* 3:9–44 · Schultz, Dayan & Montague 1997 *Science* 275:1593 · Dayan 1993 *Neural Computation* 5:613 · Dawid 1984 *J. R. Statist. Soc. A* 147:278 · Brier 1950 *Monthly Weather Review* 78:1
