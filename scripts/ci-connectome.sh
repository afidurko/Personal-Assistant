#!/usr/bin/env bash
# CI gate for Cam connectome + Cline workspace runtime
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== cam system integration =="
python3 scripts/cam-system.py --smoke
python3 scripts/test_cam_system.py
python3 scripts/flight-envelope.py --offline-only

echo "== connectome-check =="
python3 scripts/connectome-check.py

echo "== connectome-anatomy-check (glass cortex asset) =="
python3 scripts/connectome-anatomy-check.py

echo "== trajectory-policy-check =="
python3 scripts/trajectory-policy-check.py

echo "== memory-tier-check =="
python3 scripts/memory-tier-check.py

echo "== aaron-voice-gate-check =="
python3 scripts/aaron-voice-gate-check.py

echo "== cline workspace unit tests =="
python3 scripts/test_cline_workspaces.py

echo "== cam-reason unit tests =="
python3 scripts/test_cam_reason.py

echo "== aaron voice gate unit tests =="
AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_aaron_voice_gate.py
AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_cam_converse_voice_gate.py

echo "== public-apis unit + wiring =="
python3 scripts/test_public_apis.py
python3 scripts/test_public_apis_addons.py
python3 scripts/public-apis-check.py
python3 scripts/public-apis-addon.py doctor

echo "== google-trends unit + wiring =="
python3 scripts/test_google_trends.py
python3 scripts/test_google_trends_addons.py
python3 scripts/google-trends-check.py
python3 scripts/google-trends-addon.py doctor

echo "== joshinator IP-safe embodiment =="
python3 -m pip install -q -r integrations/joshinator-analyzer/backend/requirements-ci.txt
PYTHONPATH=integrations/joshinator-analyzer/backend \
  python3 -m unittest discover -s integrations/joshinator-analyzer/backend -p 'test_embodiment.py' -v
python3 scripts/embodiment-billion-fuzz.py --n 1000000 --seed 11 \
  --out vault/10-Mesh-Distillates/qa-cycles/ci-embodiment-1m.json

echo "== inkbox wiring =="
python3 scripts/inkbox-check.py

echo "== loop-engineering wiring =="
python3 scripts/loop-check.py
python3 scripts/loop-run.py --pattern daily-triage --level L1 --dry-run

echo "== connectome fuzz (1M strict) =="
python3 scripts/connectome-simulate.py \
  --n 1000000 \
  --strict-edges \
  --seed 7 \
  --out vault/10-Mesh-Distillates/qa-cycles/ci-sim-1m.json

echo "== cam-reason fuzz (1M modular) =="
python3 scripts/cam-reason-billion-fuzz.py \
  --n 1000000 \
  --seed 11 \
  --out vault/10-Mesh-Distillates/qa-cycles/ci-cam-reason-1m.json

echo "CI OK"
