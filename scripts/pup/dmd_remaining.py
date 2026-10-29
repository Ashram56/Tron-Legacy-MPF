#!/usr/bin/env python3
"""What stays of the ROM's DMD art once the video-like effects take their PuP clip: the effects with no clip chosen
(see pup_dmd_compare.py), as review sheets and as files to send to an image upscaler.

    python scripts/pup/dmd_remaining.py OUT [--replaced 38,46,...]

OUT/sheets/planche_NN.png: one row per remaining effect, up to 4 distinct frames (the live text's dots taken out, as
the HD DMD draws text itself), cells labelled planche-row-column. OUT/sprites/deff_NNN_fKK.png: every distinct frame
of the effects with at most MAX_FRAMES, 8x nearest (1024x256, shades kept as greys), the file names Gemini gets.
OUT/remaining.md: the effects, their frame counts and durations; the long loops are only listed.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import dmd_color  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# The characters' icon effects (face sliding into the hexagonal frame): the topper's HD icons replace them, see pup_icons_sheet.py
ICON_EFFECTS = {62, 63, 70, 74, 75, 79, 99, 131, 136, 137}
TEXT_ONLY = {2, 15, 17, 18, 20, 27, 34, 35, 37}     # text screens and blinking frames: the HD DMD draws them (text, rectangles)
MAX_FRAMES = 12
MIN_LIT = 200           # fewest lit dots (the live text's taken out) for an effect to count as art
PANEL = 41
MAXW = 900             # widest cell; one cell per distinct frame shown (up to 4), so a one-frame effect is one big cell
ROWW = 1800


def main():
    out = sys.argv[1]
    replaced = set()
    if "--replaced" in sys.argv:
        replaced = {int(x) for x in sys.argv[sys.argv.index("--replaced") + 1].split(",")}
    if "--index" in sys.argv:        # pup_dmd_compare.py's index.md: the effects a clip replaces
        replaced |= {int(m) for m in re.findall(r"\| [\d.-]+ \| (\d+) \|", open(sys.argv[sys.argv.index("--index") + 1]).read())}
    src = os.path.join(ROOT, "game", "media", "dmd")
    info = json.load(open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8"))["deffs"]
    recorded = {v["slide"] for v in info.values() if v["source"] == "reference"}
    texts = dmd_color.recorded_text(src, recorded)
    os.makedirs(os.path.join(out, "sheets"), exist_ok=True)
    os.makedirs(os.path.join(out, "sprites"), exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 13)
    rows, empty = [], []
    for d in sorted(glob.glob(os.path.join(src, "deff_*"))):
        n = int(os.path.basename(d).split("_")[1])
        eff = json.load(open(os.path.join(d, "effect.json"), encoding="utf-8"))
        fr = [i for i in eff["items"] if i["type"] == "frames"]
        if not fr or n in replaced or n in TEXT_ONLY or n in ICON_EFFECTS:
            continue
        order, seen = [], set()
        for pic, ms in fr[0]["frames"]:
            if pic not in seen:
                seen.add(pic)
                order.append(pic)
        total = sum(ms for _, ms in fr[0]["frames"])
        lit = 0
        for f in order:
            a = np.array(Image.open(os.path.join(ROOT, "game", f[len("res://"):])).convert("L"))
            for k in texts.get(os.path.basename(d), {}).get(os.path.basename(f), {}).get("dots", ()):
                a[k // 128, k % 128] = 0
            lit = max(lit, int((a > 0).sum()))
        if lit < MIN_LIT:                       # nothing but text and a few dots: HD draws it, nothing to replace
            empty.append((n, lit))
            continue
        rows.append((n, os.path.basename(d), order, total))
    index = ["# What remains of the ROM's DMD art", "",
             "Effects with frames that no PuP clip replaces; the live text's dots are taken out. Frames of the effects with "
             "at most %d distinct frames are in sprites/ (8x). Cell = planche-row-column." % MAX_FRAMES, "",
             "| planche-row | effect | distinct frames | ms | files |", "|---|---|---|---|---|"]
    per = 6
    for pi in range((len(rows) + per - 1) // per):
        chunk = rows[pi * per:(pi + 1) * per]
        img = Image.new("RGB", (110 + ROWW + 16, 0), (16, 16, 24))
        picks = []
        for (n, name, order, total) in chunk:
            lits = []
            for f in order:
                a = np.array(Image.open(os.path.join(ROOT, "game", f[len("res://"):])).convert("L"))
                for k in texts.get(name, {}).get(os.path.basename(f), {}).get("dots", ()):
                    a[k // 128, k % 128] = 0
                lits.append(int((a > 0).sum()))
            good = [f for f, l in zip(order, lits) if l >= max(MIN_LIT // 2, 0.3 * max(lits))] or order
            picks.append([good[int(i * (len(good) - 1) / 3)] for i in range(4)] if len(good) > 3 else good)
        heights = [int(min(MAXW, ROWW // len(p)) * 32 / 87) + 4 for p in picks]
        img = Image.new("RGB", (110 + ROWW + 16, sum(heights)), (16, 16, 24))
        dr = ImageDraw.Draw(img)
        y = 0
        for ri, ((n, name, order, total), pick, rh) in enumerate(zip(chunk, picks, heights), 1):
            cw = min(MAXW, ROWW // len(pick))
            dr.text((4, y + 2), "%d-%d" % (pi + 1, ri), font=font, fill=(255, 255, 0))
            dr.text((4, y + 20), "deff %d" % n, font=font, fill=(255, 255, 255))
            dr.text((4, y + 38), "%d fr" % len(order), font=font, fill=(160, 160, 160))
            files = []
            for ci, f in enumerate(pick, 1):
                a = np.array(Image.open(os.path.join(ROOT, "game", f[len("res://"):])).convert("L"))
                for k in texts.get(name, {}).get(os.path.basename(f), {}).get("dots", ()):
                    a[k // 128, k % 128] = 0
                x = 110 + (ci - 1) * (cw + 4)
                img.paste(Image.fromarray(a[:, PANEL:]).resize((cw, int(cw * 32 / 87)), Image.NEAREST).convert("RGB"), (x, y))   # the score panel (41 dots) left out
                dr.rectangle((x, y, x + 56, y + 14), fill=(0, 0, 0))
                dr.text((x + 2, y), "%d-%d-%d" % (pi + 1, ri, ci), font=font, fill=(255, 255, 0))
            y += rh
            if len(order) <= MAX_FRAMES:
                for k, f in enumerate(order):
                    a = np.array(Image.open(os.path.join(ROOT, "game", f[len("res://"):])).convert("L"))
                    for q in texts.get(name, {}).get(os.path.basename(f), {}).get("dots", ()):
                        a[q // 128, q % 128] = 0
                    fn = "deff_%03d_f%02d.png" % (n, k)
                    Image.fromarray(a).resize((1024, 256), Image.NEAREST).save(os.path.join(out, "sprites", fn))
                    files.append(fn)
            index.append("| %d-%d | %d | %d | %d | %s |" % (pi + 1, ri, n, len(order), total,
                         ("%s .. %s" % (files[0], files[-1])) if files else "(long loop: not exported)"))
        img.save(os.path.join(out, "sheets", "planche_%02d.png" % (pi + 1)))
    index += ["", "## Left out: only text or fewer than %d lit dots once the live text is taken out" % MIN_LIT, "",
              ", ".join("%d (%d)" % e for e in empty)]
    open(os.path.join(out, "remaining.md"), "w", encoding="utf-8").write("\n".join(index) + "\n")
    print(len(rows), "effects remain,", len(os.listdir(os.path.join(out, "sprites"))), "sprite files")


if __name__ == "__main__":
    main()
