#!/usr/bin/env bash
# Hint script: how to bring up Cam's LLMAvatarTalk presence studio.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AV="$ROOT/integrations/llmavatartalk"

echo "Cam presence (LLMAvatarTalk)"
echo "Brain: Cam/nullclaw — not AvatarTalk's embedded LLM in production"
echo
if [[ ! -d "$AV" ]]; then
  echo "Missing submodule. Run: git submodule update --init --recursive"
  exit 1
fi

echo "1) On your GPU/studio machine:"
echo "   - Start NVIDIA Riva (see $AV/docs/RIVA)"
echo "   - Start Audio2Face (see $AV/docs/Audio2Face)"
echo "   - Optional Metahuman (see $AV/docs/UE)"
echo "2) cp $AV/.env.sample $AV/.env  # set NVIDIA_API_KEY locally"
echo "3) Set Riva URI in $AV/config.py"
echo "4) Voice id for Cam: config/persona/voice.json (default English-US.Female-1)"
echo "5) Demo only: cd $AV && pip install -r requirements.txt && python main.py"
echo "6) Production: route ASR text -> Cam, Cam reply -> TTS -> Audio2Face"
echo
echo "Docs: docs/PERSONA.md and config/integrations/llmavatartalk.md"
