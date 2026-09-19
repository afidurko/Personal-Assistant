#!/usr/bin/env bash
# Triple-trillion campaign × 2 passes + static gates → merge readiness.
# Default: 3e12 property checks per pass across connectome / trajectory / cam-reason.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CHECKS="${CHECKS:-3000000000000}"
SEED_A="${1:-1001}"
SEED_B="${2:-2003}"
OUT="$ROOT/vault/10-Mesh-Distillates"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, os.cpu_count() or 4))')}"
SAMPLE_EVERY="${SAMPLE_EVERY:-10000000}"

mkdir -p "$OUT/qa-cycles"

echo "== trillion-prep: connectome-check =="
python3 scripts/connectome-check.py

echo "== trillion-prep: trajectory-policy-check =="
python3 scripts/trajectory-policy-check.py

echo "== trillion-prep: cam-reason unit =="
python3 scripts/test_cam_reason.py

echo "== trillion-prep: PASS A ($CHECKS checks, seed=$SEED_A) =="
python3 scripts/cam-trillion-campaign.py \
  --checks "$CHECKS" \
  --seed "$SEED_A" \
  --workers "$WORKERS" \
  --sample-every "$SAMPLE_EVERY" \
  --pass-id A \
  --out "$OUT/cam-trillion-pass-a.json"

echo "== trillion-prep: PASS B ($CHECKS checks, seed=$SEED_B) =="
python3 scripts/cam-trillion-campaign.py \
  --checks "$CHECKS" \
  --seed "$SEED_B" \
  --workers "$WORKERS" \
  --sample-every "$SAMPLE_EVERY" \
  --pass-id B \
  --out "$OUT/cam-trillion-pass-b.json"

python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timezone
root = Path("$ROOT")
out = root / "vault/10-Mesh-Distillates"
a = json.loads((out / "cam-trillion-pass-a.json").read_text())
b = json.loads((out / "cam-trillion-pass-b.json").read_text())
ok = a.get("ok") and b.get("ok")
doc = f"""# Merge readiness — triple-trillion campaign

**Verdict: {'READY TO MERGE' if ok else 'HOLD'}**

Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
Checks/pass: {a.get('checks', 0):,} (3 suites × vectorized properties)  
Seeds: A=$SEED_A / B=$SEED_B

| Pass | Checks | Failed | Rate | Full samples |
|---|---|---|---|---|
| A | {a['checks']:,} | {a['failed']} | {a['checks_per_sec']:,.0f}/s | {a.get('full_samples', 0):,} |
| B | {b['checks']:,} | {b['failed']} | {b['checks_per_sec']:,.0f}/s | {b.get('full_samples', 0):,} |

Suites: connectome holds · trajectory OCL/CPV · cam-reason escalate/bar  
Evidence: \`cam-trillion-pass-{{a,b}}.json\`

## Suggestive next (non-blocking)

- Phase C converse bar-only (never every-mic SGR)
- LitServe thin OpenAI-compatible proxy (no vLLM farm)
- Keep \`cam-trillion-campaign.py\` in nightly merge-prep alongside billion connectome sim
- Aaron-voice + public-apis + inkbox billion fuzz remain standing on main

## Gates

- [x] Dual 3e12 passes
- [x] connectome-check / trajectory-policy-check / test_cam_reason
"""
(out / "MERGE_READINESS_TRILLION.md").write_text(doc)
print(doc)
raise SystemExit(0 if ok else 1)
PY

echo "TRILLION MERGE-PREP OK"
