#!/usr/bin/env bash
# Serve Cam connectome live visualization (3D DTI cortex by default)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
cd "$ROOT"
echo "Cam 3D Cortex → http://127.0.0.1:${PORT}/visualizations/connectome/"
echo "Flat 2D map  → http://127.0.0.1:${PORT}/visualizations/connectome/flat.html"
echo "Or run the full home (Cam + cortex): npm run dev"
echo "Ctrl+C to stop"
python3 -m http.server "$PORT" --bind 127.0.0.1
