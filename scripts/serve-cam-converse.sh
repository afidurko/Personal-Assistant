#!/usr/bin/env bash
# Start Cam listen/speak companion on this machine.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8787}"
exec python3 "$ROOT/scripts/cam-converse-server.py" --host 0.0.0.0 --port "$PORT"
