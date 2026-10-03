#!/usr/bin/env bash
# Boots MPF (the hw_virtual overlay: smart_virtual, trough full) and the Godot media controller on a virtual display
# (Xvfb), captures the DMD in real time and checks that a slide was drawn.
# Output: captures/frames/*.png, captures/dmd_latest.png (128x32) and
# captures/dmd_latest_x8.png (1024x256 preview), plus godot.log and mpf.log.
# Usage: scripts/render_check.sh [seconds] [scenario]   (default 15 s, attract only)
# With a scenario (assets/rules/traces/<name>.txt) MPF plays it in real time on the smart_virtual
# platform (balls move; the overlay already uses it, -X forces it), so the rules drive the display and sounds as in a game.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SECONDS_TO_RUN="${1:-15}"
SCENARIO="${2:-}"
OUT="$ROOT/captures"
rm -rf "$OUT/frames" && mkdir -p "$OUT/frames"
MPF_ARGS=(-c config,hw_virtual -t)
if [ -n "$SCENARIO" ]; then MPF_ARGS=(-c config,hw_virtual -t -X); fi

# Godot is the BCP server, so it starts first; MPF connects to it on localhost:5050.
xvfb-run -a -s "-screen 0 1280x720x24" \
  tools/godot/godot --path game --rendering-driver opengl3 -- \
  --capture-dir="$OUT/frames" --capture-every-ms=250 --capture-for-ms=$((SECONDS_TO_RUN * 1000)) \
  > "$OUT/godot.log" 2>&1 &
GODOT_PID=$!
sleep 3
(cd game && TRON_LIVE_SCENARIO="$SCENARIO" TRON_TRACE="$OUT/live_trace.jsonl" \
  timeout "$((SECONDS_TO_RUN + 5))" ../.venv/bin/mpf game . "${MPF_ARGS[@]}" > "$OUT/mpf.log" 2>&1) &
MPF_PID=$!
wait "$GODOT_PID" || true
wait "$MPF_PID" || true

.venv/bin/python - "$OUT" <<'PY'
import glob, sys
from PIL import Image
out = sys.argv[1]
frames = sorted(glob.glob(f"{out}/frames/*.png"))
if not frames:
    sys.exit("FAIL: no DMD frames captured (see captures/godot.log)")
last = Image.open(frames[-1]).convert("RGB")
last.save(f"{out}/dmd_latest.png")
last.resize((last.width * 8, last.height * 8), Image.NEAREST).save(f"{out}/dmd_latest_x8.png")
lo, hi = last.convert("L").getextrema()
print(f"{len(frames)} frames, last frame {last.size[0]}x{last.size[1]}, brightness {lo}-{hi}")
if lo == hi:
    sys.exit("FAIL: last DMD frame is a single flat colour, no slide was drawn")
print("OK: a slide is on the DMD")
PY
