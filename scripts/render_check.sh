#!/usr/bin/env bash
# Boots Godot + MPF (hw_virtual), captures the DMD and checks a slide was drawn.
# Usage: scripts/render_check.sh [seconds] [scenario]. The work is done by scripts/render_check.py.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
exec "$PY" "$ROOT/scripts/render_check.py" "$@"
