#!/usr/bin/env bash
# Serve Cam connectome live visualization from repo root (vault + config resolve).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
cd "$ROOT"
URL="http://127.0.0.1:${PORT}/visualizations/connectome/"
echo "Cam Connectome viz (repo-root server)"
echo "  open  $URL"
echo "  asset $URL""assets/cam-cortex.glb"
echo "  live  http://127.0.0.1:${PORT}/vault/10-Mesh-Distillates/live-activity.json"
echo "  tip   Glass HUD = near-clear shell; serve MUST be repo root for live feed"
echo "Ctrl+C to stop"
python3 -m http.server "$PORT" --bind 127.0.0.1
