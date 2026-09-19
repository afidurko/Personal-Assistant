#!/usr/bin/env bash
# Merge-prep campaign: static gates + two independent 1B strict sims.
# Usage: bash scripts/merge-prep-billion.sh [seed_a] [seed_b]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SEED_A="${1:-601}"
SEED_B="${2:-701}"
OUT_DIR="$ROOT/vault/10-Mesh-Distillates"
CYCLES="$OUT_DIR/qa-cycles"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, os.cpu_count() or 4))')}"

mkdir -p "$CYCLES"

echo "== merge-prep: connectome-check =="
python3 scripts/connectome-check.py

echo "== merge-prep: connectome-anatomy-check =="
python3 scripts/connectome-anatomy-check.py

echo "== merge-prep: unit tests =="
python3 scripts/test_cline_workspaces.py

echo "== merge-prep: 1B pass A (seed=$SEED_A) =="
python3 scripts/connectome-simulate.py \
  --n 1000000000 \
  --strict-edges \
  --seed "$SEED_A" \
  --workers "$WORKERS" \
  --out "$OUT_DIR/connectome-sim-1b-merge-pass-a.json"

echo "== merge-prep: 1B pass B (seed=$SEED_B) =="
python3 scripts/connectome-simulate.py \
  --n 1000000000 \
  --strict-edges \
  --seed "$SEED_B" \
  --workers "$WORKERS" \
  --out "$OUT_DIR/connectome-sim-1b-merge-pass-b.json"

echo "== merge-prep: combine evidence =="
python3 scripts/merge-sim-results.py \
  "$OUT_DIR/connectome-sim-1b-merge-pass-a.json" \
  "$OUT_DIR/connectome-sim-1b-merge-pass-b.json" \
  --out "$CYCLES/connectome-sim-1b-merge-combined.json"

python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timezone
root = Path("$ROOT")
a = json.loads((root / "vault/10-Mesh-Distillates/connectome-sim-1b-merge-pass-a.json").read_text())
b = json.loads((root / "vault/10-Mesh-Distillates/connectome-sim-1b-merge-pass-b.json").read_text())
ok = a.get("failed", 1) == 0 and b.get("failed", 1) == 0
doc = f"""# Merge readiness — billion campaign

**Verdict: {'READY TO MERGE' if ok else 'HOLD'}**

Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
Seeds: A={a.get('n') and '$SEED_A'} / B={'$SEED_B'}

| Gate | Result |
|---|---|
| Pass A | {a['passed']:,} / {a['failed']} fail · {a['sims_per_sec']:,.0f} sims/s |
| Pass B | {b['passed']:,} / {b['failed']} fail · {b['sims_per_sec']:,.0f} sims/s |
| Kill holds A/B | {a['kill_holds']:,} / {b['kill_holds']:,} |
| Non-Aaron holds A/B | {a['non_aaron_holds']:,} / {b['non_aaron_holds']:,} |

Evidence: \`connectome-sim-1b-merge-pass-{{a,b}}.json\` · \`qa-cycles/connectome-sim-1b-merge-combined.json\`
"""
(root / "vault/10-Mesh-Distillates/MERGE_READINESS_BILLION.md").write_text(doc)
print(doc)
raise SystemExit(0 if ok else 1)
PY

echo "MERGE-PREP OK"
