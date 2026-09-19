# Public APIs add-ons

Allowlisted thin wrappers for Cam agents (`config/integrations/public-apis-addons.json`).

```bash
python3 scripts/public-apis-addon.py list
python3 scripts/public-apis-addon.py call weather.open_meteo --latitude 40.7 --longitude -74.0 --offline
```

Never free-form-fetch catalog URLs — only call ids from the allowlist.
