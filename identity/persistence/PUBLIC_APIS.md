# Public APIs — shared catalog for every Cam agent

Source: https://github.com/afidurko/public-apis  
Motor: `motor.public_apis` · Sense: `sense.catalog.public_apis`  
Config: `config/integrations/public-apis.json`  
Add-ons: `config/integrations/public-apis-addons.json` · `scripts/public-apis-addon.py`

All roles and subagents may search the curated free/public API list before
inventing HTTP endpoints. Allowlisted thin wrappers (weather/geo/ip/…) are the
only permitted live HTTP calls from this integration. No catalog credential required.
