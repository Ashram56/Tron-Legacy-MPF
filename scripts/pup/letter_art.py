#!/usr/bin/env python3
"""The ZUSE and TRON letters of the topper as HD pictures for the DMD's letter effects (deff 91, 92, 94, 107).

    python scripts/pup/letter_art.py [PACK] [--force]     # -> game/hd_art/letters/<L>_on.png and <L>_off.png

The pack's ZUSE/ZUSE_<L>.mp4 and TRON/TRON_<L>.mp4 show the whole word in blue with letter <L> turning red. The first
frame is the word with no letter collected, the last one has <L> red: the pixels that differ mark <L>, so each letter is
cut out (alpha from the brightness, black = transparent) twice: red (on, collected) and blue (off, still to get).
The game draws them in place of the ROM's dots when the HD DMD is on (tron/dmd_effect.gd _letters); no file: the ROM's
letters, upscaled. TRON_LETTER_ART=0 turns them off.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DST = os.path.join(ROOT, "game", "hd_art", "letters")
WORDS = (("ZUSE", "ZUSE"), ("TRON", "TRON"))
MARGIN = 14          # pixels kept round the letter (its glow)


def frame(ffmpeg, mp4, t, out):
    cmd = [ffmpeg, "-v", "error", "-y"] + (["-sseof", "-0.1"] if t < 0 else ["-ss", str(t)]) + \
        ["-i", mp4, "-frames:v", "1", out]
    subprocess.run(cmd, check=True)
    return np.asarray(Image.open(out).convert("RGB"), dtype=np.float32)


def cut(rgb, mask):
    """RGBA of the picture where mask is set: colour kept, alpha from the brightness."""
    alpha = rgb.max(axis=2) * mask
    a = np.clip(alpha, 0, 255)
    colour = np.where(a[..., None] > 0, np.clip(rgb * 255.0 / np.maximum(rgb.max(axis=2), 1)[..., None], 0, 255), 0)
    return np.dstack([colour, a]).astype(np.uint8)


def clu_letters():
    """The C, L, U of the CLU hurry-up (deff 80), drawn smooth in the ROM's colours (bold, yellow with an orange edge):
    the ROM's blocky letters upscaled looked smeared. No pack needed. -> game/hd_art/letters/CLU_<L>_on.png"""
    from PIL import ImageDraw
    import math
    S = 800                                   # drawing size; the picture is 400 px with 14 % margin
    paths = {
        "C": [(1.0, 0.1), (0.5, 0.1)] + [(0.5 + 0.4 * math.cos(math.radians(a)), 0.5 + 0.4 * math.sin(math.radians(a)))
                                         for a in range(270, 89, -6)] + [(0.5, 0.9), (1.0, 0.9)],
        "L": [(0.2, 0.0), (0.2, 0.9), (1.0, 0.9)],
        "U": [(0.15, 0.0), (0.15, 0.55)] + [(0.5 + 0.35 * math.cos(math.radians(a)), 0.55 + 0.35 * math.sin(math.radians(a)))
                                           for a in range(180, -1, -6)] + [(0.85, 0.55), (0.85, 0.0)],
    }
    os.makedirs(DST, exist_ok=True)
    pad = 0.14

    def stroke(points, width, colour):
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        pts = [(round((pad + (1 - 2 * pad) * x) * S), round((pad + (1 - 2 * pad) * y) * S)) for x, y in points]
        d.line(pts, fill=colour, width=width, joint="curve")
        r = width // 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=colour)
        return img

    for letter, pts in paths.items():
        glow = stroke(pts, 150, (255, 138, 0, 255)).filter(ImageFilter.GaussianBlur(26))
        glow.putalpha(glow.getchannel("A").point(lambda v: int(v * 0.6)))
        img = Image.alpha_composite(glow, stroke(pts, 112, (255, 138, 0, 255)))
        img = Image.alpha_composite(img, stroke(pts, 76, (255, 238, 0, 255)))
        img.resize((400, 400), Image.LANCZOS).save(os.path.join(DST, "CLU_%s_on.png" % letter))


def make(pack, force=False):
    clu_letters()
    sys.path.insert(0, HERE)
    try:
        from gen_dmd_clips import find_ffmpeg      # FFMPEG, the PATH, or imageio-ffmpeg in the venv (macOS has no ffmpeg of its own)
        ffmpeg = find_ffmpeg()
    except SystemExit as e:
        print("   letter art (ZUSE, TRON): {}".format(e))
        return 1
    os.makedirs(DST, exist_ok=True)
    made = 0
    with tempfile.TemporaryDirectory() as tmp:
        for folder, word in WORDS:
            found, frames = {}, {}
            for letter in word:
                on, off = (os.path.join(DST, "%s_%s.png" % (letter, k)) for k in ("on", "off"))
                mp4 = os.path.join(pack, folder, "%s_%s.mp4" % (word, letter))
                if not os.path.exists(mp4) or (os.path.exists(on) and os.path.exists(off) and not force):
                    continue
                first = frame(ffmpeg, mp4, 0, os.path.join(tmp, "a.png"))
                last = frame(ffmpeg, mp4, -1, os.path.join(tmp, "b.png"))
                # the letter is the red of the last frame (its neighbours stay blue, and so does their glow)
                diff = (last[..., 0] - last[..., 2] > 25) & (np.abs(first - last).max(axis=2) > 25)
                ys, xs = np.nonzero(diff)
                if not len(xs):
                    continue
                # the letter's own pixels and their glow, not the neighbours': the differing area, widened and feathered
                grow = Image.fromarray((diff * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.MinFilter(11)).filter(ImageFilter.MaxFilter(5))
                mask = np.asarray(grow.filter(ImageFilter.GaussianBlur(2)), dtype=np.float32) / 255.0
                found[letter] = (xs.min() - MARGIN, xs.max() + MARGIN + 1, ys.min() - MARGIN, ys.max() + MARGIN + 1)
                frames[letter] = (cut(last, mask), cut(first, mask))
            # one canvas for the word's letters (its height, the widest letter): they keep their sizes among each other
            if found:
                top = max(0, min(b[2] for b in found.values()))
                bottom = min(first.shape[0], max(b[3] for b in found.values()))
                width = max(b[1] - b[0] for b in found.values())
                for letter, (x0, x1, _, _) in found.items():
                    for path, rgba in zip((os.path.join(DST, "%s_on.png" % letter), os.path.join(DST, "%s_off.png" % letter)),
                                          frames[letter]):
                        canvas = Image.new("RGBA", (width, bottom - top), (0, 0, 0, 0))
                        crop = Image.fromarray(rgba).crop((max(x0, 0), top, min(x1, rgba.shape[1]), bottom))
                        canvas.paste(crop, ((width - crop.width) // 2, 0))
                        canvas.save(path)
                    made += 1
    print("   letter art: %d letters -> game/hd_art/letters/" % made)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--clu" in sys.argv:
        clu_letters()
        sys.exit(0)
    sys.exit(make(args[0] if args else os.path.join(ROOT, "pup_pack", "trn_174h"), "--force" in sys.argv))
