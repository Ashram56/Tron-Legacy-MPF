#!/usr/bin/env python3
"""Render GMC display-effect slides in Godot and compare them with the emulator's reference captures.

For each deff the slide (game/slides/deffs, from scripts/gen_media.py) is rendered by
game/tools/slide_capture.tscn (Godot under Xvfb, opengl3) at the start time of every frame of
assets/mpf_package/media/dmd/deff_NNN_*/reference_capture.gif, with the text line values the
reference shows (VALUES, formatted by tron/media_bridge.format_rom_text). Both sequences are
aligned on their first non-black frame and compared dot by dot as DMD levels (0-15: the reference's
grey / 17, the render's red channel / 17, the slide tint keeping red at full scale).

Reported per deff: frames compared, % matching dots (mean / min over frames), frames that match
exactly, and the text check: on the dots of the text lines as the ROM draws them (gen_fonts.render with the
slide's layout), the Godot render against the reference in the best frame pair (100 = pixel-exact).

Usage: .venv/bin/python scripts/render_diff.py [deff ...] [--keep DIR]   (default: DEFAULT_DEFFS)
Exit status 1 when a deff's text is not pixel-exact.
"""
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "game"))
import gen_fonts  # noqa: E402
import rom_layout  # noqa: E402
from tron.media_bridge import format_rom_text  # noqa: E402

PKG = os.path.join(ROOT, "assets", "mpf_package")
GODOT = os.path.join(ROOT, "tools", "godot", "godot")
# Values the reference captures show (read off the GIFs): {deff: [args per line]}
VALUES = {19: [[1], [0]],                   # BALL 1, score 00 (score 0 printed with %,02lu)
          25: [[], [50000]],                # TOTAL BONUS 50,000
          26: [[0], []],                    # PLAYER 0 (the capture had no player number)
          38: [[0]],                        # match number 00
          40: [[0], []],                    # PLAYER 0 / YOU'RE UP
          133: [[], [], None]}              # EXTRA BALL without the score line (None: blank)
DYNAMIC = [19, 25, 26, 133, 38, 40]
CONTROLS = [20, 21, 23, 24, 46]            # static-text effects: slides are the reference capture
DEFAULT_DEFFS = DYNAMIC + CONTROLS


def reference(deff_id):
    from PIL import Image, ImageSequence
    path = glob.glob(os.path.join(PKG, "media", "dmd", "deff_%03d_*" % deff_id, "reference_capture.gif"))[0]
    frames, times, t = [], [], 0
    for f in ImageSequence.Iterator(Image.open(path)):
        px = f.convert("L").load()
        frames.append([[round(px[x, y] / 17) for x in range(128)] for y in range(32)])
        times.append(t)
        t += int(f.info.get("duration", 49)) or 49
    return frames, times


def line_values(deff_id, lines):
    vals = VALUES.get(deff_id, [])
    out = {}
    for i, line in enumerate(lines):
        v = vals[i] if i < len(vals) else []
        out["line%d" % i] = "" if v is None else format_rom_text(line, v)
    return out


def godot_render(jobs):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", GODOT, "--path", os.path.join(ROOT, "game"),
           "--rendering-driver", "opengl3", "res://tools/slide_capture.tscn", "--", "--job=" + f.name]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    os.unlink(f.name)


def load_render(folder, n):
    from PIL import Image
    out = []
    for k in range(n):
        path = os.path.join(folder, "frame_%05d.png" % k)
        if not os.path.exists(path):
            break
        px = Image.open(path).convert("RGB").load()
        out.append([[round(px[x, y][0] / 17) for x in range(128)] for y in range(32)])
    return out


def first_lit(frames):
    return next((k for k, f in enumerate(frames) if any(any(r) for r in f)), 0)


def text_dots(deff_id, lines, values, fonts, get):
    """{(x, y): level} of the slide's text as the ROM draws it (None where nothing is drawn)."""
    canvas = [[None] * 128 for _ in range(32)]
    lays = rom_layout.line_layouts(deff_id, lines, fonts)
    for i, lay in enumerate(lays):
        text = values.get("line%d" % i, "")
        if not lay or not text:
            continue
        font_id, x, y = lay["font"], lay["x"], lay["y"]
        if "alt_when_empty" in lay and not values.get(lay["alt_when_empty"]):
            x, y = lay["alt_x"], lay["alt_y"]
        for k, f in enumerate(lay.get("fit_fonts", [])):
            font_id, y = f, lay["fit_ys"][k]
            if gen_fonts.text_width(fonts[f], text) <= lay["fit_width"]:
                break
        gen_fonts.render(get, fonts[font_id], text, x, y, lay["flags"], canvas)
    return {(x, y): v for y in range(32) for x in range(128) if (v := canvas[y][x]) is not None}


def compare(deff_id, ref, ours, dots):
    a, b = first_lit(ref), first_lit(ours)
    pairs = [(ref[a + k], ours[b + k]) for k in range(min(len(ref) - a, len(ours) - b))]
    scores = [sum(r[y][x] == o[y][x] for y in range(32) for x in range(128)) / 4096 for r, o in pairs]
    # text: the Godot render against the reference on the text's dots, in the best frame pair
    text = max((sum(r[y][x] == o[y][x] for (x, y) in dots) / len(dots) for r, o in pairs), default=0.0) \
        if dots else None
    return {"deff": deff_id, "frames": len(pairs), "offset": b - a,
            "mean": 100 * sum(scores) / len(scores) if scores else 0, "min": 100 * min(scores) if scores else 0,
            "exact_frames": sum(s == 1.0 for s in scores), "text": None if text is None else 100 * text}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    if keep in args:
        args.remove(keep)
    deffs = [int(a) for a in args] or DEFAULT_DEFFS
    rows = {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(PKG, "event_map.csv")))}
    media = json.load(open(os.path.join(ROOT, "game", "tron", "media_data.json")))["deffs"]
    fonts = json.load(open(os.path.join(ROOT, "game", "fonts", "fonts.json")))["fonts"]
    _, get = gen_fonts.load_images()
    work = keep or tempfile.mkdtemp(prefix="render_diff_")
    jobs, refs, info = [], {}, {}
    for d in deffs:
        refs[d] = reference(d)
        lines = media[str(d)]["text"]
        values = line_values(d, lines)
        info[d] = (lines, values)
        jobs.append({"slide": "deff_%03d" % d, "kwargs": values, "times_ms": refs[d][1],
                     "out": os.path.join(work, "deff_%03d" % d)})
    godot_render(jobs)
    failed = False
    print("deff  frames  offset  dots%% mean   min  exact  text%%  values")
    for d in deffs:
        ours = load_render(os.path.join(work, "deff_%03d" % d), len(refs[d][0]))
        if not ours:
            print("%4d  no frames rendered (see Godot)" % d)
            failed = True
            continue
        lines, values = info[d]
        r = compare(d, refs[d][0], ours, text_dots(d, lines, values, fonts, get))
        text = "-" if r["text"] is None else "%.1f" % r["text"]
        failed |= r["text"] is not None and r["text"] < 100
        print("%4d  %6d  %6d  %10.1f %5.1f  %5d  %5s  %s" % (
            d, r["frames"], r["offset"], r["mean"], r["min"], r["exact_frames"], text,
            " / ".join(v for v in values.values() if v)))
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
