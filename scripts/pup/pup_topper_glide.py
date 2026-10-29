#!/usr/bin/env python3
"""Where do the characters' faces slide into the hexagonal frame? Contact sheets of the topper info clips over their
first seconds (the whole 1920x562 frame, one every STEP seconds), plus the clip's motion in the icon area, so the
glide can be found (or ruled out) instead of guessed from the first second.

    python scripts/pup/pup_topper_glide.py OUTDIR [--pack DIR] [--seconds 6]

OUTDIR/glide_<name>.png: cells labelled <sheet>-<row>-<col> with the time; OUTDIR/glide.md: per clip the times where
the icon area (left quarter) changes most. Clips with no change there (Zuse, Flynn, Portal ...) have a static icon.
"""
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLIPS = {"clu": "CluModeInfo/CLU_Mode_Info.mp4", "gem": "GemModeInfo/Gem_Mode_Info.mp4",
         "quorra": "QuorraMBInfo/Quorra_MB_INFO.mp4", "zuse": "ZuseModeInfo/ZuseInfo.mp4",
         "flynn": "FindFlynnInfo/FindFlynnInfo.mp4", "sos": "SoSModeInfo/SoS_Mode_Info.mp4",
         "discwars": "DiscWarsMBInfo/DiscWarsMB_Info.mp4", "lightcycle": "LightCycleMBInfo/LightCycle_MB_INFO.mp4",
         "portal": "PortalModeInfo/Portal_Mode_Info.mp4"}
STEP, COLS, CELL = 0.25, 4, (480, 140)


def main():
    out = sys.argv[1]
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else os.path.join(os.path.dirname(ROOT), "tron-le-pup-pack")
    secs = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 6.0
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 13)
    md = ["# Topper info clips: motion in the icon area", "", "| sheet | clip | times (s) where the icon area changes | max change |", "|---|---|---|---|"]
    for si, (name, rel) in enumerate(CLIPS.items(), 1):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(pack, "trn_174h", rel), "-vf", "fps=10,scale=480:-1",
                            os.path.join(tmp, "%04d.png")], check=True)
            fs = sorted(glob.glob(os.path.join(tmp, "*.png")))
            im = [Image.open(f).convert("RGB") for f in fs]
        g = [np.array(i.convert("L"))[:, :120].astype(float) for i in im]
        d = [float(np.abs(g[i] - g[i - 1]).mean()) for i in range(1, len(g))]
        moving = [round(i / 10, 1) for i, v in enumerate(d, 1) if v > 6]
        md.append("| %d | %s | %s | %.1f |" % (si, rel, ", ".join(map(str, moving[:24])) or "none: static", max(d)))
        n = int(secs / STEP)
        rows = (n + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * (CELL[0] + 4), rows * (CELL[1] + 4)), (16, 16, 24))
        dr = ImageDraw.Draw(sheet)
        for k in range(n):
            t = k * STEP
            fr = im[min(int(round(t * 10)), len(im) - 1)].resize(CELL, Image.LANCZOS)
            x, y = (k % COLS) * (CELL[0] + 4), (k // COLS) * (CELL[1] + 4)
            sheet.paste(fr, (x, y))
            dr.rectangle((x, y, x + 120, y + 15), fill=(0, 0, 0))
            dr.text((x + 2, y), "%d-%d-%d t=%.2f" % (si, k // COLS + 1, k % COLS + 1, t), font=font, fill=(255, 255, 0))
        sheet.save(os.path.join(out, "glide_%02d_%s.png" % (si, name)))
    open(os.path.join(out, "glide.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
