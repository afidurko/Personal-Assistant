# Google Trends data — open dataset catalog

Source: https://github.com/GoogleTrends/data  
Motor: `motor.google_trends` · Sense: `sense.catalog.google_trends`  
Config: `config/integrations/google-trends.json`  
Scripts: `scripts/google-trends-search.py` · `scripts/pack-google-trends-result.py`

Indexes published CSV/XLSX datasets behind Google Trends graphics via GitHub
git trees API (cached). Does **not** submodule the ~382MB tree. Offline fixture
for CI. No API key; not a live trends.google.com scraper.
