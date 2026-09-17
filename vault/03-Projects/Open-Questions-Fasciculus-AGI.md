# Open questions — fasciculus mesh & AGI stance

Interim defaults applied in `config/connectome/mesh-params.json` so implementation could proceed. Override anytime.

| # | Question | Interim answer |
|---|---|---|
| 1 | Language lateralization | **bilateral_failover** |
| 2 | Max workspaces | **3** (forceps leases) |
| 3 | Fornix consolidation | **nightly_enabled** (`fornix-consolidate.py`) |
| 4 | Dual-stream conflict | **dorsal wins speak / ventral wins docs** |
| 5 | ASI ceiling | **24 neuro columns · myelin ≤ 0.98** |
| 6 | Tailscale as callosum | **forceps_terminals** (peers = commissural ends) |

Edit `mesh-params.json` `open_questions_for_aaron[].answer` (set `interim: false` when confirmed).
