# Research Ethics — moral measures for Cam's research and prediction from experience

**Accessed / drafted:** 2026-09-22  
**Assigned by:** Aaron — "why would this fail … implement changes to ensure its survival, add ethical and moral research measures, test the code."  
**Gate:** Measures below are enforced by `scripts/research-ethics-check.py` in the static CI gate. They constrain Cam; they never widen her autonomy.  
**Config:** `config/ethics/research-ethics.json`

## Question

What could go wrong — statistically, technically, and morally — when Cam predicts her own outcomes and scans the literature, and which concrete measures keep the work honest and survivable?

## Summary

The predictive cortex is small enough to inspect completely, which is also why its failure modes are predictable. Statistically it can double-count, be fooled by unknown dates, mistake a shifted regime for a stable one, and let a parent rate dominated by one child masquerade as knowledge about siblings. Ethically it can quote a number where it should say "I don't know", turn a person or a job into a prediction target, leak PII into a log that is never forgotten, or hide bad calibration in one domain behind a good aggregate. Each of these now has a code-level countermeasure and a gate.

## Failure modes → measures

| # | How it would fail | Kind | Measure (where) |
|---|---|---|---|
| 1 | Same run reported by `loop-run-log.md` and `loop-runs/latest.json` counted twice → false confidence | statistical | cross-source dedup on `(ts, hotspot, pattern)`; same-source same-second records stay distinct (`dedupe`) |
| 2 | Record with an unparseable timestamp weighted as *fresh* (decay 1.0) | statistical | `unknown_ts_weight` 0.25; count exposed in `coverage.unknown_timestamps` |
| 3 | Rate shifts (code change, new model) but 14-day half-life keeps old confidence | non-stationarity | EWMA of reward-prediction error per context; above threshold the posterior counts are halved (interval widens), `drift_suspected` reported, advice says gather more |
| 4 | `center.qa` is 95% QA-cycle successes; a new loop pattern inherits that optimism | hierarchical bias | parent with ≤1 distinct child passes only half its prior strength (`backoff_single_child_factor`) |
| 5 | Runs that crash before writing a distillate are invisible → survivorship bias | coverage | staleness per context (`coverage.stale_contexts`), stated limitation on every prediction card |
| 6 | A corrupt source file kills the whole load | engineering | per-source try/except; errors listed in `coverage.source_errors` |
| 7 | Runtime log grows without bound | engineering | rotation at `max_runtime_rows`, keep `keep_runtime_rows` |
| 8 | Cam keeps recording / writing distillates during a kill | control | `CAM_KILL=1` refuses `--record`, `--forget-*`, distillate writes (exit 3) |
| 9 | arXiv hammered six times back-to-back → throttled or blocked; scan silently dies | source respect + survival | `min_interval_s` 3.0 between category calls; identifying User-Agent; gate asserts both |
| 10 | Number quoted with no experience behind it (automation bias) | honesty | abstention when `n_effective` < 3 or interval width > 0.6; `narration` is hedged and always carries the range |
| 11 | Prediction about a person, job application, outbound message, or money | moral boundary | protected contexts → stance `human_judgment_required`, no automation suggestion, narration says "the call is yours" |
| 12 | Notes with an email, phone, or token persisted forever | data minimisation | `redact()` on write; `redacted` marker on the record; gate scans tracked artefacts |
| 13 | Once written, a wrong or unwanted experience can't be removed | right to forget | `--forget-ref` / `--forget-key` rewrite the runtime log |
| 14 | Aggregate ECE looks fine while one hotspot is badly over-confident | fairness of confidence | per-hotspot ECE (`calibration.parity`), flag when gap > 0.15 |
| 15 | Once predictions bias routing, Cam avoids low-p contexts and never learns them (Goodhart / self-fulfilling) | anti-Goodhart | P3 stays behind `switch.cam_enhance`; proposal requires a held-out unbiased slice before closing the loop |
| 16 | Briefs make claims without sources | reproducibility | gate requires `## Sources` + accessed dates on every brief since 2026-09-22 |

## Principles (from the config)

honesty · human_primacy · no_persons_as_targets · data_minimisation · right_to_forget · fairness_of_confidence · anti_goodhart · source_respect · reproducibility

## Why this is enough for P0 and not for P3

At P0 the predictor is a report. The worst outcome of a wrong number is a misleading sentence to Aaron, and the abstention + narration rules make that sentence carry its own doubt. At P3 (predictions bias routing) the failure modes compound: feedback loops, Goodhart on `score`, and denial of exploration. The measures above make P0 survivable; P3 additionally needs a held-out unbiased stream, an exploration floor, and Aaron's explicit `switch.cam_enhance`.

## Counter-arguments

- *Over-abstention makes the cortex useless.* Abstention rate is reported (`ethics.abstention_rate`, ~31% on the fixture). If it rises past half on live data, lower `min_effective_n` — with Aaron.
- *Redaction regexes are crude.* True; they are a floor, not a guarantee. Notes are capped at 240 chars and the gate scans tracked artefacts, so a leak is caught in CI rather than in git history.
- *Drift inflation slows learning.* Halving counts only while EWMA surprise stays high; once the new regime is consistent, surprise falls and full weight returns.

## Sources

- arXiv API Terms of Use — https://info.arxiv.org/help/api/tou.html — accessed 2026-09-22 (rate: one request per 3 s, identifying User-Agent)
- Adams & MacKay 2007, *Bayesian Online Changepoint Detection* — arXiv:0710.3742 — accessed 2026-09-22 (motivation for drift-aware forgetting)
- Guo et al. 2017, *On Calibration of Modern Neural Networks* — arXiv:1706.04599 — accessed 2026-09-22 (ECE; per-group calibration)
- Pleiss et al. 2017, *On Fairness and Calibration* — arXiv:1709.02012 — accessed 2026-09-22 (calibration parity across groups)
- Mitchell et al. 2019, *Model Cards for Model Reporting* — arXiv:1810.03993 — accessed 2026-09-22 (prediction card, stated limitations)
- Gebru et al. 2018, *Datasheets for Datasets* — arXiv:1803.09010 — accessed 2026-09-22 (data provenance, coverage statement)
- Amodei et al. 2016, *Concrete Problems in AI Safety* — arXiv:1606.06565 — accessed 2026-09-22 (reward hacking / Goodhart, safe exploration)
- Manheim & Garrabrant 2018, *Categorizing Variants of Goodhart's Law* — arXiv:1803.04585 — accessed 2026-09-22
- Parasuraman & Manzey 2010, *Complacency and Bias in Human Use of Automation* — Human Factors 52(3) — accessed 2026-09-22 (automation bias → hedged narration, abstention)
- arXiv:2609.09448 *Do Agents Know When They Succeed?* — accessed 2026-09-22 (agent self-prediction calibration)
- `.clinerules` — no raw PII or secrets committed; Aaron is the only operator — repository policy
