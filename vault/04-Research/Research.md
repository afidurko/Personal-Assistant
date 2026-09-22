# Research

Source-backed briefs. Use [[Research Brief]] template.

Standing: [[AGI-Daily-Scan]] — everyday AI/AGI papers that may enhance Cam.

**Latest Cam-function brief:** [[2026-09-17-Cam-Function-Papers]] — prioritized papers for memory, mesh, switches, persona (propose-only).

**Research plan (2026-09-22):** [[2026-09-22-Research-Plan-Predictive-Cam]] — tools · AI studies · deep learning + prediction from experience → Cam predictive cortex (`docs/PREDICTIVE_CORTEX.md`).  
Briefs: [[2026-09-22-Research-Tools-For-Cam]] · [[2026-09-22-Deep-Learning-Prediction-From-Experience]] · [[2026-09-22-Research-Ethics-Measures]] (failure modes → survival + moral measures, gated in CI)

```bash
python3 scripts/cam-predict.py --report            # how well Cam predicts her own outcomes
python3 scripts/research-ethics-check.py           # ethics gate — redaction, protected contexts, abstention, parity, source etiquette
```

**Google Scholar** connected — literature + citations via SerpAPI  
(`config/integrations/google-scholar.md`). Notes land in `04-Research/scholar/`.

**Public APIs** connected — curated free/public HTTP API catalog for all agents  
(`config/integrations/public-apis.md`). Notes land in `04-Research/public-apis/`.

```bash
python3 scripts/scholar-search.py --query "your topic" --offline   # fixture
python3 scripts/scholar-search.py --query "your topic"             # live (needs SERPAPI_API_KEY)
python3 scripts/public-apis-search.py --query "weather"            # local catalog
python3 scripts/public-apis-search.py --query "weather" --offline  # fixture
```
