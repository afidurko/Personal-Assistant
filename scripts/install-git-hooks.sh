#!/usr/bin/env bash
# Install Cam's privacy git hooks (idempotent). Points core.hooksPath at
# .githooks so pre-commit / pre-push run scripts/pii-guard.py.
#
#   ./scripts/install-git-hooks.sh          # install for this clone
#   ./scripts/install-git-hooks.sh --check  # exit 1 if not installed
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "install-git-hooks: not a git checkout — skipping"
  exit 0
fi

current="$(git config --get core.hooksPath || true)"
if [ "${1:-}" = "--check" ]; then
  if [ "$current" = ".githooks" ] && [ -x .githooks/pre-commit ] && [ -x .githooks/pre-push ]; then
    echo "install-git-hooks: OK (core.hooksPath=.githooks)"
    exit 0
  fi
  echo "install-git-hooks: NOT installed (core.hooksPath='${current}')" >&2
  exit 1
fi

chmod +x .githooks/pre-commit .githooks/pre-push
if [ "$current" != ".githooks" ]; then
  git config core.hooksPath .githooks
  echo "install-git-hooks: core.hooksPath → .githooks"
else
  echo "install-git-hooks: already installed"
fi
