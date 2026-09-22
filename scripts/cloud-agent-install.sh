#!/usr/bin/env bash
# Idempotent Cloud Agent install for Personal-Assistant (Cam).
# Must terminate. Do not start servers, watchers, or interactive tools here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Privacy guard hooks (layer 2): every commit/push from this pod is scanned for
# personal information before it can leave. Idempotent, no network.
bash scripts/install-git-hooks.sh

# Inventory-only: no package-registry egress, no distillate writes.
python3 scripts/cam-system.py --no-write
