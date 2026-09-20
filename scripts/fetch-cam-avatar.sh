#!/usr/bin/env bash
# Fetch Cam's browser TalkingHead GLB into public/avatars/cam.glb
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/public/avatars/cam.glb"
URL="${CAM_AVATAR_GLB_URL:-https://raw.githubusercontent.com/met4citizen/TalkingHead/main/avatars/brunette.glb}"
mkdir -p "$(dirname "$OUT")"
if [[ -f "$OUT" && "${1:-}" != "--force" ]]; then
  echo "Exists: $OUT ($(wc -c < "$OUT") bytes)"
  exit 0
fi
echo "Downloading $URL"
curl -L --fail --retry 4 -o "$OUT" "$URL"
echo "Wrote $OUT ($(wc -c < "$OUT") bytes)"
