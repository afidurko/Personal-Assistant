#!/usr/bin/env bash
# Serve Cam connectome live visualization
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
cd "$ROOT"
echo "Cam Connectome viz → http://127.0.0.1:${PORT}/visualizations/connectome/"
echo "Ctrl+C to stop"
python3 -m http.server "$PORT" --bind 127.0.0.1
