#!/usr/bin/env bash
# Idempotent Cloud Agent install for Personal-Assistant (Cam).
# Must terminate. Do not start servers, watchers, or interactive tools here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Inventory-only: no package-registry egress, no distillate writes.
python3 scripts/cam-system.py --no-write
