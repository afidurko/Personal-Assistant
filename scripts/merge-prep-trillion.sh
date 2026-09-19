#!/usr/bin/env bash
# Merge-prep: static gates + dual three-trillion campaign.
# Usage: bash scripts/merge-prep-trillion.sh [seed] [physical]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SEED="${1:-42}"
PHYSICAL="${2:-10000000}"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, os.cpu_count() or 4))')}"

echo "== merge-prep-trillion: connectome-check =="
python3 scripts/connectome-check.py

echo "== merge-prep-trillion: anatomy + trajectory + memory =="
python3 scripts/connectome-anatomy-check.py
python3 scripts/trajectory-policy-check.py
python3 scripts/memory-tier-check.py

echo "== merge-prep-trillion: workspace units =="
python3 scripts/test_cline_workspaces.py

echo "== merge-prep-trillion: dual 3T campaign =="
WORKERS="$WORKERS" python3 scripts/three-trillion-campaign.py \
  --passes 2 \
  --seed "$SEED" \
  --workers "$WORKERS" \
  --physical "$PHYSICAL"

echo "MERGE-PREP-TRILLION OK"
