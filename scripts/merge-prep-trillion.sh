#!/usr/bin/env bash
# Merge-prep: static gates + dual three-trillion campaigns.
# 1) connectome/embodiment/trajectory modular 3T (three-trillion-campaign.py)
# 2) connectome/trajectory/cam-reason property 3T × 2 (cam-trillion-campaign.py)
# Usage: bash scripts/merge-prep-trillion.sh [seed] [physical]
#        CAM_TRILLION_SEED_A / CAM_TRILLION_SEED_B override property-pass seeds.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SEED="${1:-42}"
PHYSICAL="${2:-10000000}"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, os.cpu_count() or 4))')}"
CHECKS="${CHECKS:-3000000000000}"
SEED_A="${CAM_TRILLION_SEED_A:-1001}"
SEED_B="${CAM_TRILLION_SEED_B:-2003}"
OUT="$ROOT/vault/10-Mesh-Distillates"
SAMPLE_EVERY="${SAMPLE_EVERY:-10000000}"

mkdir -p "$OUT/qa-cycles"

echo "== merge-prep-trillion: connectome-check =="
python3 scripts/connectome-check.py

echo "== merge-prep-trillion: anatomy + trajectory + memory =="
python3 scripts/connectome-anatomy-check.py
python3 scripts/trajectory-policy-check.py
python3 scripts/memory-tier-check.py

echo "== merge-prep-trillion: cam-reason unit =="
python3 scripts/test_cam_reason.py

echo "== merge-prep-trillion: workspace units =="
python3 scripts/test_cline_workspaces.py

echo "== merge-prep-trillion: dual 3T modular campaign =="
WORKERS="$WORKERS" python3 scripts/three-trillion-campaign.py \
  --passes 2 \
  --seed "$SEED" \
  --workers "$WORKERS" \
  --physical "$PHYSICAL"

echo "== merge-prep-trillion: cam property PASS A ($CHECKS checks, seed=$SEED_A) =="
python3 scripts/cam-trillion-campaign.py \
  --checks "$CHECKS" \
  --seed "$SEED_A" \
  --workers "$WORKERS" \
  --sample-every "$SAMPLE_EVERY" \
  --pass-id A \
  --out "$OUT/cam-trillion-pass-a.json"

echo "== merge-prep-trillion: cam property PASS B ($CHECKS checks, seed=$SEED_B) =="
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
doc = f"""# Merge readiness — triple-trillion campaign (cam property)

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
Companion modular campaign: \`MERGE_READINESS_THREE_TRILLION.md\`

## Suggestive next (non-blocking)

- Phase C converse bar-only (never every-mic SGR)
- LitServe thin OpenAI-compatible proxy (no vLLM farm)
- Keep both \`three-trillion-campaign.py\` and \`cam-trillion-campaign.py\` in nightly merge-prep
- Aaron-voice + public-apis + inkbox billion fuzz remain standing on main

## Gates

- [x] Dual 3e12 cam-property passes
- [x] connectome-check / anatomy / trajectory-policy / memory-tier / test_cam_reason / workspaces
"""
(out / "MERGE_READINESS_TRILLION.md").write_text(doc)
print(doc)
raise SystemExit(0 if ok else 1)
PY

echo "MERGE-PREP-TRILLION OK"
