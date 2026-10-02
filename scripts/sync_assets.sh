#!/usr/bin/env bash
# Moves the assets submodule to the latest commit of Tron-Legacy-LE-ROM-Decryption
# and writes a summary of what changed to captures/asset_sync.md.
# Exit code 0 = updated, 3 = already up to date.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BRANCH="${ASSETS_BRANCH:-main}"
OUT="$ROOT/captures/asset_sync.md"
mkdir -p captures

GIT_LFS_SKIP_SMUDGE=1 git submodule update --init --depth 1 assets
OLD="$(git -C assets rev-parse HEAD)"
# Enough history to diff the pinned commit against the new one.
GIT_LFS_SKIP_SMUDGE=1 git -C assets fetch --quiet --depth 200 origin "$BRANCH"
NEW="$(git -C assets rev-parse FETCH_HEAD)"

if [ "$OLD" = "$NEW" ]; then
  echo "assets already at ${NEW:0:7}"
  exit 3
fi

GIT_LFS_SKIP_SMUDGE=1 git -C assets -c advice.detachedHead=false checkout --quiet "$NEW"

{
  echo "# Asset sync ${OLD:0:7} -> ${NEW:0:7}"
  echo
  echo "## Commits"
  echo
  git -C assets log --format='- %h %s' "$OLD..$NEW" || echo "- (history too shallow to list)"
  echo
  echo "## Changed files by area (A added, M modified, D deleted, R renamed)"
  for area in mpf_package/config mpf_package/media rules io callouts code docs; do
    changes="$(git -C assets diff --name-status -M "$OLD" "$NEW" -- "$area" || true)"
    [ -z "$changes" ] && continue
    echo
    echo "### $area ($(echo "$changes" | wc -l) files)"
    echo
    echo '```'
    echo "$changes" | head -100
    [ "$(echo "$changes" | wc -l)" -gt 100 ] && echo "... (truncated)"
    echo '```'
  done
  notes="$(git -C assets diff --name-only "$OLD" "$NEW" -- 'mpf_package/UPDATE_*' 'mpf_package/REMOVED_*' || true)"
  if [ -n "$notes" ]; then
    echo
    echo "## Package notes added or changed"
    for n in $notes; do echo; echo "### $n"; echo; echo '```'; git -C assets show "$NEW:$n" | head -60; echo '```'; done
  fi
  deleted="$(git -C assets diff --name-only --diff-filter=DR "$OLD" "$NEW" || true)"
  if [ -n "$deleted" ]; then
    echo
    echo "## Check these: deleted or renamed upstream"
    echo
    echo "$deleted" | sed 's/^/- /' | head -50
  fi
} > "$OUT"

echo "assets moved ${OLD:0:7} -> ${NEW:0:7}; summary in captures/asset_sync.md"
