#!/usr/bin/env bash
# CI gate for Cam connectome + Cline workspace runtime
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== static gate (one process) =="
# ci-static-gate covers connectome-check, workspace-integration, anatomy,
# trajectory, sentinel, voice, public-apis, trends, inkbox, higgsfield, loop, envelope.
python3 scripts/ci-static-gate.py

echo "== unit tests (one process) =="
(
  cd scripts && python3 -m unittest \
    test_cam_system \
    test_cloud_agent_install \
    test_cam_reason \
    test_cam_sentinel \
    test_cam_fast \
    test_cam_infinitemind \
    test_cline_workspaces \
    test_public_apis \
    test_public_apis_addons \
    test_google_trends \
    test_google_trends_addons \
    test_higgsfield \
    test_embodiment_lite
)

echo "== aaron voice gate unit tests =="
(
  cd scripts && AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 \
    python3 -m unittest test_aaron_voice_gate test_cam_converse_voice_gate
)

echo "== joshinator IP-safe embodiment =="
if python3 -c "import pydantic" 2>/dev/null; then
  echo "pydantic already present"
elif python3 -m pip install -q -r integrations/joshinator-analyzer/backend/requirements-ci.txt; then
  echo "installed requirements-ci.txt"
else
  echo "pydantic unavailable (offline); catalog-only embodiment fuzz"
fi
if python3 -c "import pydantic" 2>/dev/null; then
  PYTHONPATH=integrations/joshinator-analyzer/backend \
    python3 -m unittest discover -s integrations/joshinator-analyzer/backend -p 'test_embodiment.py' -v
else
  echo "skip embodiment unit tests (no pydantic)"
fi

echo "== embodiment fuzz (1M strict) =="
python3 scripts/embodiment-billion-fuzz.py --n 1000000 --seed 11 \
  --out vault/10-Mesh-Distillates/qa-cycles/ci-embodiment-1m.json

echo "== presence portrait (no Speak clips) =="
python3 scripts/presence-check.py

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
