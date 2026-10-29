#!/usr/bin/env python3
"""Where is the subject of a clip, and where does its current 4:1 crop sit? Eight frames over the clip (or over
FROM-TO seconds), the whole 1920x1080 picture, the crop of pup_clip_crops.py drawn on them in red.

    python scripts/pup/pup_clip_probe.py OUT.png CLIP_UNDER_trn_174h.mp4 [FROM TO]
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pup_clip_crops  # noqa: E402

PACK = os.path.join(os.path.dirname(pup_clip_crops.ROOT), "tron-le-pup-pack")


def secs(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout)


def main():
    out, rel = sys.argv[1], sys.argv[2]
    path = os.path.join(PACK, "trn_174h", rel)
    total = secs(path)
    a, b = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (0.0, total)
    c = pup_clip_crops.crop_for(PACK, rel, total)
    sheet = Image.new("RGB", (4 * 484, 2 * 274))
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(8):
            t = a + (i + 0.5) / 8 * (b - a)
            f = os.path.join(tmp, "f.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % t, "-i", path, "-frames:v", "1", f], check=True)
            im = Image.open(f).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle((c["x0"], c["y0"], c["x1"], c["y0"] + c["h"]), outline=(255, 0, 0), width=5)
            d.text((10, 10), "t=%.2f" % t, fill=(255, 255, 0))
            sheet.paste(im.resize((480, 270)), ((i % 4) * 484, (i // 4) * 274))
    sheet.save(out)


if __name__ == "__main__":
    main()
