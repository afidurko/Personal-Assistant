#!/usr/bin/env bash
# purge-git-history.sh — remove personal information from ALL git history.
#
# Redacting HEAD is not enough on a public repository: every old commit, every
# branch, and every PR ref still serves the pre-redaction files. This script
# rewrites history with git-filter-repo. It is DRY-RUN by default and it NEVER
# pushes — Aaron runs the printed force-push himself.
#
#   bash scripts/purge-git-history.sh            # show the plan
#   bash scripts/purge-git-history.sh --execute  # rewrite THIS clone (fresh clone recommended)
#
# Order of operations (docs/PRIVACY_SAFEGUARDS.md → "History purge"):
#   1. python3 scripts/private-memory.py import-legacy   (needs the OLD history — do this first)
#   2. bash scripts/purge-git-history.sh --execute
#   3. git push --force --all origin && git push --force --tags origin
#   4. Ask GitHub Support to purge cached views / unreachable objects (or make the repo private,
#      or delete and re-create it) — force-push alone does not evict refs/pull/*/head.
#   5. Every other clone: re-clone. Do not `git pull` an old clone (it re-introduces old objects).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EXECUTE=0
[ "${1:-}" = "--execute" ] && EXECUTE=1

# Historical files whose every revision is personal information. HEAD holds
# public stubs; they are saved and restored after the rewrite.
PURGE_PATHS=(
  "identity/aaron/VISUAL_PROFILE.md"
  "identity/aaron/enroll-index.json"
  "identity/aaron/voice-profile.json"
  "identity/aaron/enroll.json"
)

# Literal / regex replacements applied to every remaining blob in history.
# The operator timezone itself is personal information, so it is never written in
# this script: it is read from private memory at run time (import-legacy first).
REPLACE_FILE="$(mktemp)"
chmod 600 "$REPLACE_FILE"
cat >"$REPLACE_FILE" <<'EOF'
regex:\bEST / (?:Africa|America|Antarctica|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Z][A-Za-z_]+\b==>operator_local
regex:\b(?:Africa|America|Antarctica|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Z][A-Za-z_]+ \(E[SD]T\)==>operator_local
regex:\(Aaron / E[SD]T\)==>
regex:aaron-\d{2}-[a-z0-9-]+\.(?:jpe?g|png|heic|mov|mp4|m4a|wav)==>[removed]
face_enrollment_complete_4_photos_voice_enrolled==>face_enrollment_complete_voice_enrolled
face_enrollment_complete_4_photos==>face_enrollment_complete
EOF
TZ_NOTE="(not in private memory — only the generic patterns above will apply)"
if tz_value="$(python3 scripts/private-memory.py get identity.aaron.timezone 2>/dev/null)" && [ -n "$tz_value" ]; then
  printf '%s==>operator_local\n' "$tz_value" >>"$REPLACE_FILE"
  TZ_NOTE="(literal value loaded from private memory key identity.aaron.timezone)"
fi

echo "== purge-git-history: plan"
echo "repo:      $ROOT"
echo "remote:    $(git remote get-url origin 2>/dev/null | sed -E 's#//[^@/]+@#//#' || echo '(none)')"
echo "branches:  $(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes | wc -l | tr -d ' ') refs will be rewritten"
echo
echo "paths removed from all history (stubs at HEAD restored afterwards):"
for p in "${PURGE_PATHS[@]}"; do
  n="$(git log --oneline --all -- "$p" 2>/dev/null | wc -l | tr -d ' ')"
  echo "  - $p  ($n historical commits)"
done
echo
echo "text replaced in every historical blob:"
sed 's/^/  - /' "$REPLACE_FILE"
echo

if ! command -v git-filter-repo >/dev/null 2>&1 && ! git filter-repo --version >/dev/null 2>&1; then
  echo "git-filter-repo is not installed."
  echo "  macOS:  brew install git-filter-repo"
  echo "  pip:    python3 -m pip install git-filter-repo"
  echo "  docs:   https://github.com/newren/git-filter-repo"
  [ "$EXECUTE" = 1 ] && exit 1
fi

if [ "$EXECUTE" != 1 ]; then
  cat <<EOF
DRY RUN — nothing changed. To execute (preferably in a fresh clone):

  git clone --mirror <remote-url> purge-work && cd purge-work   # or use this clone with --force
  bash scripts/purge-git-history.sh --execute

Afterwards (Aaron only — this rewrites the public remote):

  git push --force --all origin
  git push --force --tags origin

Then contact GitHub Support (or make the repository private) so cached PR views and
unreachable objects are purged. Old clones must be re-cloned, never pulled.
EOF
  rm -f "$REPLACE_FILE"
  exit 0
fi

echo "== executing rewrite"
STUBS="$(mktemp -d)"
for p in "${PURGE_PATHS[@]}"; do
  if [ -f "$p" ]; then
    mkdir -p "$STUBS/$(dirname "$p")"
    cp "$p" "$STUBS/$p"
  fi
done

ARGS=(--force --replace-text "$REPLACE_FILE" --invert-paths)
for p in "${PURGE_PATHS[@]}"; do ARGS+=(--path "$p"); done
git filter-repo "${ARGS[@]}"

restored=0
for p in "${PURGE_PATHS[@]}"; do
  if [ -f "$STUBS/$p" ]; then
    mkdir -p "$(dirname "$p")"
    cp "$STUBS/$p" "$p"
    git add "$p"
    restored=1
  fi
done
if [ "$restored" = 1 ]; then
  git commit -q -m "Restore public identity stubs after history purge" || true
fi
rm -rf "$STUBS" "$REPLACE_FILE"

echo
echo "== verify"
python3 scripts/pii-guard.py --all
echo "history check (should print nothing):"
git log --all --oneline -- identity/aaron/VISUAL_PROFILE.md | tail -n +2 || true
echo
echo "Rewrite complete in this clone. filter-repo removed the 'origin' remote on purpose."
echo "Re-add it and force-push when ready:"
echo "  git remote add origin <remote-url>"
echo "  git push --force --all origin && git push --force --tags origin"
