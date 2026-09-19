# Overall system integration

**Authorized by:** Aaron  
**Date:** 2026-09-19  
**Status:** enabled

Cam’s home converse, Brodmann connectome, neural-mesh scanners, autonomy spawn,
and motors share one bus via `server/core/system-bridge.ts` and
`config/system/pieces.json`.

Verify: `python3 scripts/cam-system.py --smoke` · `GET /api/system`
Docs: `docs/SYSTEM_INTEGRATION.md`
