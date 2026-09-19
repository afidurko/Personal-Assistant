#!/usr/bin/env bash
# Regenerate Cam cortical GLB from Brainder DK meshes (CC BY-SA 3.0).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/visualizations/connectome/assets/cam-cortex.glb"
MAP="$ROOT/config/connectome/anatomy-region-map.json"
CACHE="${CAM_BRAIN_CACHE:-/tmp/cam-brain-meshes}"

mkdir -p "$(dirname "$OUT")"
npx --yes freesurfer-to-glb@0.1.0 \
  --region-map "$MAP" \
  --output "$OUT" \
  --cache "$CACHE" \
  --radius 2.4

echo "Wrote $OUT ($(du -h "$OUT" | awk '{print $1}'))"
echo "See visualizations/connectome/assets/NOTICE.md for attribution."

# Mirror into Vite public for React hero
mkdir -p "$ROOT/public/cortex"
cp -f "$OUT" "$ROOT/public/cortex/cam-cortex.glb"
cp -f "$ROOT/config/connectome/anatomy-centroids.json" "$ROOT/public/cortex/anatomy-centroids.json"
cp -f "$ROOT/visualizations/connectome/assets/NOTICE.md" "$ROOT/public/cortex/NOTICE.md"
echo "Mirrored to public/cortex/"
