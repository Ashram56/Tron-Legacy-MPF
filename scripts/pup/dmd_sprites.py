#!/usr/bin/env python3
"""Sprites of the DMD art that no PuP clip replaces: every distinct object (icon, logo, arrow, letter, drawing) of
the effects' frames, cut out as its own picture, for an upscaler.

    python scripts/pup/dmd_sprites.py OUT COMPARE_INDEX.md

COMPARE_INDEX.md (pup_dmd_compare.py's index) lists the effects a clip replaces; they and the text-only effects are
left out. In the others the live text's dots are taken out, the lit dots are joined into objects (dots up to 2 apart
belong together), objects of at least MIN_DOTS lit dots are cut with 2 dots of margin, identical ones (same shape and
shades) are kept once. OUT/sprites/deff_NNN_sKK.png = the object at 8x on black (greys kept); OUT/sprites.md lists
file, effect, size in dots, position and the frames it is in; OUT/sheet_NN.png shows them with their file number.
"""
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import dmd_color  # noqa: E402
from dmd_remaining import ICON_EFFECTS, TEXT_ONLY  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIN_DOTS = 25
GAP = 2
JOIN = 4         # pieces of one letter: boxes overlapping in x and at most this many dots apart in y are one object
# Review round 2: pieces cut out of a frame that are a face or a scene, not an object (the topper's HD icons and the
# PuP clips cover them), a bar, and the repeats of the one frame; "CLEAN" isolates the object in the ones that stay.
DROP_EFFECTS = ICON_EFFECTS
DROP = {(1, 0), (74, 0), (74, 1)} | {(30, k) for k in range(1, 10)}


def clean(n, k, crop):
    """(effect, index) -> the object alone: 30 = the hexagonal frame without the grey backdrop lines."""
    if (n, k) == (30, 0):
        crop = np.where(crop > 100, crop, 0)[:, :36]
    else:
        return crop
    ys, xs = np.nonzero(crop)
    return crop[max(ys.min() - 1, 0):ys.max() + 2, max(xs.min() - 1, 0):xs.max() + 2]


def objects(a):
    """[(y0, y1, x0, x1, mask)] of the lit dots joined into objects."""
    lit = a > 0
    h, w = lit.shape
    seen = np.zeros_like(lit, bool)
    out = []
    for y, x in zip(*np.nonzero(lit)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for dy in range(-GAP, GAP + 1):
                for dx in range(-GAP, GAP + 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and lit[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(pts) >= MIN_DOTS:
            ys, xs = zip(*pts)
            out.append([min(ys), max(ys), min(xs), max(xs), pts])
    merged = True
    while merged:                       # objects whose boxes overlap, or nearly in y, are one object (a letter drawn in two pieces)
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                if a[0] - JOIN <= b[1] and b[0] - JOIN <= a[1] and a[2] <= b[3] and b[2] <= a[3]:
                    out[i] = [min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return [tuple(o) for o in out]


def main():
    out, idx = sys.argv[1], sys.argv[2]
    video = {int(m) for m in re.findall(r"\| [\d.-]+ \| (\d+) \|", open(idx).read())}
    src = os.path.join(ROOT, "game", "media", "dmd")
    info = json.load(open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8"))["deffs"]
    texts = dmd_color.recorded_text(src, {v["slide"] for v in info.values() if v["source"] == "reference"})
    os.makedirs(os.path.join(out, "sprites"), exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    rows, thumbs, seen = [], [], set()
    for d in sorted(glob.glob(os.path.join(src, "deff_*"))):
        n = int(os.path.basename(d).split("_")[1])
        eff = json.load(open(os.path.join(d, "effect.json"), encoding="utf-8"))
        fr = [i for i in eff["items"] if i["type"] == "frames"]
        if not fr or n in video or n in TEXT_ONLY or n in DROP_EFFECTS:
            continue
        k = 0
        names = []
        for pic, _ in fr[0]["frames"]:
            if pic not in names:
                names.append(pic)
        for fi, pic in enumerate(names):
            a = np.array(Image.open(os.path.join(ROOT, "game", pic[len("res://"):])).convert("L"))
            for q in texts.get(os.path.basename(d), {}).get(os.path.basename(pic), {}).get("dots", ()):
                a[q // 128, q % 128] = 0
            for y0, y1, x0, x1, pts in objects(a):
                m = np.zeros_like(a)
                for yy, xx in pts:
                    m[yy, xx] = a[yy, xx]
                crop = m[max(y0 - 2, 0):y1 + 3, max(x0 - 2, 0):x1 + 3]
                key = hashlib.md5(crop.tobytes() + bytes(crop.shape)).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                if (n, k) in DROP:                  # numbered like a kept one, so the files keep their numbers
                    k += 1
                    continue
                crop = clean(n, k, crop)
                fn = "deff_%03d_s%02d.png" % (n, k)
                k += 1
                Image.fromarray(crop).resize((crop.shape[1] * 8, crop.shape[0] * 8), Image.NEAREST).save(
                    os.path.join(out, "sprites", fn))
                rows.append((fn, n, crop.shape[1], crop.shape[0], x0, y0, fi))
                thumbs.append((fn, crop))
    lines = ["# Sprites of the art no clip replaces", "",
             "Each file = one object cut from a frame (8x, greys kept, black background). Joined dots up to %d apart; "
             "at least %d lit dots; identical objects kept once; the live text's dots taken out." % (GAP, MIN_DOTS), "",
             "| file | effect | size (dots) | position x,y | first frame |", "|---|---|---|---|---|"]
    lines += ["| %s | %d | %dx%d | %d,%d | f%d |" % r for r in rows]
    open(os.path.join(out, "sprites.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    per, cell = 40, (190, 100)
    for si in range((len(thumbs) + per - 1) // per):
        ch = thumbs[si * per:(si + 1) * per]
        img = Image.new("RGB", (8 * (cell[0] + 4), ((len(ch) + 7) // 8) * (cell[1] + 18)), (16, 16, 24))
        dr = ImageDraw.Draw(img)
        for i, (fn, crop) in enumerate(ch):
            x, y = (i % 8) * (cell[0] + 4), (i // 8) * (cell[1] + 18)
            t = Image.fromarray(crop)
            s = min(cell[0] / t.width, cell[1] / t.height)
            t = t.resize((max(1, int(t.width * s)), max(1, int(t.height * s))), Image.NEAREST)
            img.paste(t.convert("RGB"), (x, y + 16))
            dr.text((x + 2, y + 1), "%d-%d-%d %s" % (si + 1, i // 8 + 1, i % 8 + 1, fn[5:-4]), font=font, fill=(255, 255, 0))
        img.save(os.path.join(out, "sheet_%02d.png" % (si + 1)))
    print(len(rows), "sprites")


if __name__ == "__main__":
    main()
