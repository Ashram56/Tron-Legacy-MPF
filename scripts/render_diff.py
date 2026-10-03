#!/usr/bin/env python3
"""Render GMC display-effect slides in Godot and compare them with the emulator's reference captures.

For each deff the slide (game/slides/deffs, from scripts/gen_media.py) is rendered by
game/tools/slide_capture.tscn (Godot under Xvfb, opengl3) at the start time of every frame of
assets/mpf_package/media/dmd/deff_NNN_*/reference_capture.gif, with the text line values the
reference shows (VALUES, formatted by tron/media_bridge.format_rom_text). Both sequences are
aligned on their first non-black frame and compared dot by dot as DMD levels (0-15: the reference's
grey / 17, the render's red channel / 17, the slide tint keeping red at full scale).

Reported per deff: frames compared, % matching dots (mean / min over frames), frames that match
exactly, and the text check: on the dots of every text the slide can show, as the ROM draws it
(gen_fonts.render with the slide's layouts), the Godot render against the reference in every frame,
so text timing (rotation, blink, show/hide) counts too: mean % and frames with all text dots equal.
Slides built from the graphics frames are rendered on their own timeline when the capture has one frame
per ROM frame (deff 38); otherwise at the capture's frame times.

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
import run  # noqa: E402
import rom_layout  # noqa: E402
from tron.media_bridge import format_rom_text  # noqa: E402

PKG = os.path.join(ROOT, "assets", "mpf_package")
# Values the reference captures show (read off the GIFs): {deff: [args per line]}
VALUES = {19: [[1], [0]],                   # BALL 1, score 00 (score 0 printed with %,02lu)
          25: [[], [50000]],                # TOTAL BONUS 50,000
          26: [[0], []],                    # PLAYER 0 (the capture had no player number)
          38: [[], [0], None],              # MATCH, match number 00
          40: [[0], []],                    # PLAYER 0 / YOU'RE UP
          114: [[], [], ["SHOOT"], ["FLYNNS ARCADE"]],   # SOS stage 0 (deff 114's stage messages)
          115: [["FLYNN"], ["BONUS"], [1000000]],         # stage 0 skipped: FLYNN BONUS 1,000,000
          133: [[], [], None]}              # EXTRA BALL without the score line (None: blank)
# Other event args of the score display (tron/score_display.gd) as the deff 19 capture shows them:
# credits 1 coin of 3, replay level 20,000,000, one player with 00, playfield not yet valid and the
# blink counter where the capture's blink phase is (score shown at 0 ms, blanked 110 ms later).
EXTRA = {19: {"credits": "CREDITS 1/3", "replay": "REPLAY AT " + format_rom_text("%,02lu", [20000000]),
              "p1": "00", "p2": "", "p3": "", "p4": "", "players": 1, "player": 1, "valid": False,
              "award": "", "award_age": 99, "blink_age": 70}}
# The status panel of the other effects: one player with 00 (all captures are on ball 1 with no score);
# its blink phase comes from a counter outside the effect, so it is read off each capture (panel_phase).
PANEL = {"p1": "00", "p2": "", "p3": "", "p4": "", "players": 1, "player": 1, "valid": False,
         "award": "", "award_age": 99}
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


def graphics_frames(deff_id):
    path = glob.glob(os.path.join(PKG, "media", "dmd", "deff_%03d_*" % deff_id, "timing.json"))
    return json.load(open(path[0], encoding="utf-8")).get("graphics_frames", []) if path else []


def panel_phase(ref, times):
    """blink_age (ticks) at the slide start that best puts the panel score's blink (blank 7 of every 14
    ticks) where the capture has it, judged on the player 1 score (x 32-38, rows 1-5) in every frame;
    None when it never blinks."""
    lit = [any(f[y][x] for y in range(1, 6) for x in range(32, 39)) for f in ref]
    if all(lit):
        return None

    def agree(b0):
        return sum(lit[k] == ((b0 + round(t / rom_layout.TICK_MS) - 62) % 14 > 6) for k, t in enumerate(times))
    return max(range(63, 77), key=agree)


def line_values(deff_id, lines):
    vals = VALUES.get(deff_id, [])
    out = {}
    for i, line in enumerate(lines):
        v = vals[i] if i < len(vals) else []
        out["line%d" % i] = "" if v is None else format_rom_text(line, v)
    out.update(EXTRA.get(deff_id, {}))
    return out


def godot_render(jobs):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    cmd = run.godot_command(["--rendering-driver", "opengl3", "res://tools/slide_capture.tscn", "--",
                             "--job=" + f.name])      # under Xvfb on Linux without a display
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


def text_region(deff_id, lines, values, fonts, get):
    """Dots of the slide's text as the ROM draws it (gen_fonts.render with the slide's layouts and
    values, every text the slide can show: alternate rows, fit fonts, deff 19's panel and lines)."""
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
    if "p1" in values:
        for _, var, x, y, flags in rom_layout.SCORE_PANEL:
            if values.get(var):
                gen_fonts.render(get, fonts[0], values[var], x, y, flags, canvas)
    return {(x, y) for y in range(32) for x in range(128) if canvas[y][x] is not None}


def compare(deff_id, ref, ours, dots):
    a, b = first_lit(ref), first_lit(ours)
    pairs = [(ref[a + k], ours[b + k]) for k in range(min(len(ref) - a, len(ours) - b))]
    scores = [sum(r[y][x] == o[y][x] for y in range(32) for x in range(128)) / 4096 for r, o in pairs]
    # text: the Godot render against the reference on the text's dots, every frame (shown or not)
    tscores = [sum(r[y][x] == o[y][x] for (x, y) in dots) / len(dots) for r, o in pairs] if dots else []
    return {"deff": deff_id, "frames": len(pairs), "offset": b - a,
            "mean": 100 * sum(scores) / len(scores) if scores else 0, "min": 100 * min(scores) if scores else 0,
            "exact_frames": sum(s == 1.0 for s in scores),
            "text": 100 * sum(tscores) / len(tscores) if tscores else None,
            "text_exact": sum(t == 1.0 for t in tscores)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    if keep in args:
        args.remove(keep)
    deffs = [int(a) for a in args] or DEFAULT_DEFFS
    rows = {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(PKG, "event_map.csv"), encoding="utf-8"))}
    media = json.load(open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8"))["deffs"]
    fonts = json.load(open(os.path.join(ROOT, "game", "fonts", "fonts.json"), encoding="utf-8"))["fonts"]
    _, get = gen_fonts.load_images()
    work = keep or tempfile.mkdtemp(prefix="render_diff_")
    jobs, refs, info = [], {}, {}
    for d in deffs:
        refs[d] = reference(d)
        lines = media[str(d)]["text"]
        values = line_values(d, lines)
        if media[str(d)].get("panel") and d not in EXTRA:
            phase = panel_phase(*refs[d])
            values.update(PANEL, valid=phase is None, blink_age=phase or 0)
        info[d] = (lines, values)
        times = refs[d][1]
        if media[str(d)]["source"] == "graphics" and abs(len(times) - len(graphics_frames(d))) <= 1:
            times = [rom_layout.frame_ms(d, k) for k in range(len(times))]   # one capture frame per ROM frame
        jobs.append({"slide": "deff_%03d" % d, "kwargs": values, "times_ms": times,
                     "out": os.path.join(work, "deff_%03d" % d)})
    godot_render(jobs)
    failed = False
    print("deff  frames  offset  dots%% mean   min  exact  text%%/exact  lines")
    for d in deffs:
        ours = load_render(os.path.join(work, "deff_%03d" % d), len(refs[d][0]))
        if not ours:
            print("%4d  no frames rendered (see Godot)" % d)
            failed = True
            continue
        lines, values = info[d]
        r = compare(d, refs[d][0], ours, text_region(d, lines, values, fonts, get))
        text = "-" if r["text"] is None else "%.1f %3d" % (r["text"], r["text_exact"])
        failed |= r["text"] is not None and r["text"] < 100
        print("%4d  %6d  %6d  %10.1f %5.1f  %5d  %9s  %s" % (
            d, r["frames"], r["offset"], r["mean"], r["min"], r["exact_frames"], text,
            " / ".join(str(values[k]) for k in sorted(values) if k.startswith("line") and values[k])))
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
