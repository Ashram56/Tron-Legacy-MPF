#!/usr/bin/env bash
# Installs the pinned toolchain (MPF, Godot, GMC, generated media). Kept for older instructions and
# automation: the work is done by scripts/setup.py, which also runs on Windows and macOS
# (scripts/setup.ps1, scripts/setup.bat). Arguments are passed through (see `--help`).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$(command -v python3 || command -v python)"
exec "$PY" "$ROOT/scripts/setup.py" "$@"
