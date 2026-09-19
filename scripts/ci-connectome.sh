#!/usr/bin/env bash
# CI gate for Cam connectome + Cline workspace runtime
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== connectome-check =="
python3 scripts/connectome-check.py

echo "== trajectory-policy-check =="
python3 scripts/trajectory-policy-check.py

echo "== memory-tier-check =="
python3 scripts/memory-tier-check.py

echo "== cline workspace unit tests =="
python3 scripts/test_cline_workspaces.py

echo "== aaron voice gate unit tests =="
AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_aaron_voice_gate.py
AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_cam_converse_voice_gate.py

echo "== public-apis unit + wiring =="
python3 scripts/test_public_apis.py
python3 scripts/test_public_apis_addons.py
python3 scripts/public-apis-check.py
python3 scripts/public-apis-addon.py doctor

echo "== connectome fuzz (1M strict) =="
python3 scripts/connectome-simulate.py \
  --n 1000000 \
  --strict-edges \
  --seed 7 \
  --out vault/10-Mesh-Distillates/qa-cycles/ci-sim-1m.json

echo "CI OK"
