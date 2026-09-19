# Research

Source-backed briefs. Use [[Research Brief]] template.

Standing: [[AGI-Daily-Scan]] — everyday AI/AGI papers that may enhance Cam.

**Latest Cam-function brief:** [[2026-09-17-Cam-Function-Papers]] — prioritized papers for memory, mesh, switches, persona (propose-only).

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
