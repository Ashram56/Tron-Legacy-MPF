#!/usr/bin/env python3
"""Boot Godot (GMC) and MPF (hw_virtual), capture the 128x32 DMD in real time and check that a slide was drawn.

    python scripts/render_check.py [seconds] [scenario]     (default 15 s, attract only)

Output in captures/: frames/*.png, dmd_latest.png (128x32), dmd_latest_x8.png (1024x256 preview), godot.log,
mpf.log and live_trace.jsonl. With a scenario (assets/rules/traces/<name>.txt) MPF plays it in real time on the
smart_virtual platform, so the rules drive the display and sounds as in a game.

Godot's --headless mode uses a dummy renderer that draws nothing, so Godot gets a real window: under Xvfb on
Linux without a display, a normal (small) window elsewhere. The renderer is OpenGL (Mesa llvmpipe on Xvfb).
"""
import glob
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402
import toolchain as tc  # noqa: E402

OUT = os.path.join(tc.ROOT, "captures")


def check(out=OUT):
    from PIL import Image
    frames = sorted(glob.glob(os.path.join(out, "frames", "*.png")))
    if not frames:
        return "FAIL: no DMD frames captured (see captures/godot.log)"
    last = Image.open(frames[-1]).convert("RGB")
    last.save(os.path.join(out, "dmd_latest.png"))
    last.resize((last.width * 8, last.height * 8), Image.NEAREST).save(os.path.join(out, "dmd_latest_x8.png"))
    lo, hi = last.convert("L").getextrema()
    print("{} frames, last frame {}x{}, brightness {}-{}".format(len(frames), last.size[0], last.size[1], lo, hi))
    if lo == hi:
        return "FAIL: last DMD frame is a single flat colour, no slide was drawn"
    print("OK: a slide is on the DMD")
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    seconds = int(argv[0]) if argv else 15
    scenario = argv[1] if len(argv) > 1 else None
    frames = os.path.join(OUT, "frames")
    shutil.rmtree(frames, ignore_errors=True)
    os.makedirs(frames)
    godot_args = ["--rendering-driver", "opengl3", "--",
                  "--capture-dir=" + frames, "--capture-every-ms=250",
                  "--capture-for-ms={}".format(seconds * 1000)]
    run.run("virtual", scenario=scenario, seconds=seconds + 5, godot_args=godot_args,
            godot_log=os.path.join(OUT, "godot.log"), mpf_log=os.path.join(OUT, "mpf.log"),
            trace=os.path.join(OUT, "live_trace.jsonl"), wait_godot_exit=True)
    # the PIL check runs in the venv's Python when this one has no Pillow
    try:
        import PIL  # noqa: F401
    except ImportError:
        import subprocess
        return subprocess.call([tc.python(), "-c", "import sys; sys.path.insert(0, {!r}); import render_check; "
                                "sys.exit(render_check.check())".format(os.path.dirname(os.path.abspath(__file__)))])
    error = check()
    if error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
