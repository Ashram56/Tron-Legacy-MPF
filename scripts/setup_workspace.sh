#!/usr/bin/env bash
# Installs the pinned toolchain for this repo on Linux x86_64:
#   MPF 0.80.1 (Python venv in .venv/), Godot 4.5.2 (tools/godot/),
#   the GMC 1.0.0 add-on (game/addons/mpf-gmc/) and the assets submodule.
# Safe to re-run: each step is skipped when already in place.
set -euo pipefail

MPF_VERSION="0.80.1"
GODOT_VERSION="4.5.2"
GMC_TAG="v1.0.0"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== assets submodule"
GIT_LFS_SKIP_SMUDGE=1 git submodule update --init --depth 1 assets

echo "== MPF $MPF_VERSION"
if [ ! -x .venv/bin/mpf ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet "mpf==$MPF_VERSION" pillow
fi
.venv/bin/mpf --version

echo "== Godot $GODOT_VERSION (Linux x86_64)"
GODOT_BIN="tools/godot/Godot_v${GODOT_VERSION}-stable_linux.x86_64"
if [ ! -x "$GODOT_BIN" ]; then
  mkdir -p tools/godot
  curl -sSL -o tools/godot/godot.zip \
    "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip"
  unzip -oq tools/godot/godot.zip -d tools/godot
  rm tools/godot/godot.zip
fi
ln -sf "$(basename "$GODOT_BIN")" tools/godot/godot
tools/godot/godot --version

echo "== GMC $GMC_TAG"
if [ ! -f game/addons/mpf-gmc/plugin.cfg ]; then
  tmp="$(mktemp -d)"
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$GMC_TAG" https://github.com/missionpinball/mpf-gmc "$tmp/mpf-gmc"
  mkdir -p game/addons
  cp -r "$tmp/mpf-gmc/addons/mpf-gmc" game/addons/
  rm -rf "$tmp"
fi
grep '^version' game/addons/mpf-gmc/plugin.cfg

echo "== MPF config generated from the asset package"
.venv/bin/python scripts/gen_config.py

echo "== Media (sounds, DMD frames and slides from the asset package)"
.venv/bin/python scripts/gen_media.py

echo "== Godot import (builds game/.godot/)"
# The first import pass can report add-on icon errors; the second is clean.
for _ in 1 2; do tools/godot/godot --headless --path game --import >/dev/null 2>&1 || true; done

echo "Done. Run scripts/render_check.sh to boot MPF + GMC and capture the DMD."
