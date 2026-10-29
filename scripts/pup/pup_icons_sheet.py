#!/usr/bin/env python3
"""The characters' HD icons (face in a hexagonal frame) the topper info clips carry, cut out as PNGs, next to the
DMD effects that show the same character's icon. One row per character: cell 1 = the topper's icon (frame of the
clip at ICON_AT seconds, the hexagon cut at ICON_BOX), cells 2-5 = the DMD effects' middle frames.

    python scripts/pup/pup_icons_sheet.py OUTDIR [--pack DIR]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pup_dmd_sheet as base  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = base.ROOT
ICON_BOX = (30, 10, 530, 552)          # the hexagon of the 1920x562 topper clips
# character -> (topper clip, seconds, DMD effects that show the character)
ICONS = {
    "quorra": ("QuorraMBInfo/Quorra_MB_INFO.mp4", 3.0, (62, 63, 70), ICON_BOX),
    "clu": ("CluModeInfo/CLU_Mode_Info.mp4", 3.0, (73, 74, 131), ICON_BOX),
    "gem": ("GemModeInfo/Gem_Mode_Info.mp4", 3.0, (75, 79), ICON_BOX),
    "zuse": ("ZuseModeInfo/ZuseInfo.mp4", 3.0, (99,), ICON_BOX),
    "flynn": ("FindFlynnInfo/FindFlynnInfo.mp4", 1.5, (136, 137), (235, 0, 705, 562)),   # this clip's hexagon sits further right
}


def main():
    out = sys.argv[1]
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else os.path.join(os.path.dirname(ROOT), "tron-le-pup-pack")
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
    tmp = os.path.join(out, "_tmp.png")
    cw, ch = 512, 128
    sheet = Image.new("RGB", (300 + 4 * (cw + 4), len(ICONS) * 310), (16, 16, 24))
    dr = ImageDraw.Draw(sheet)
    for ri, (name, (clip, t, effs, box)) in enumerate(ICONS.items(), 1):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", os.path.join(pack, "trn_174h", clip),
                        "-frames:v", "1", tmp], check=True)
        icon = Image.open(tmp).convert("RGB").crop(box)
        icon.save(os.path.join(out, "icon_%s_hd.png" % name))
        y = (ri - 1) * 310
        sheet.paste(icon.resize((290, int(290 * icon.height / icon.width))), (4, y + 4))
        dr.text((6, y + 6), "1-%d-1 %s" % (ri, name), font=font, fill=(255, 255, 0))
        best = []                       # the frame with most lit dots of each effect: the icon, not a blank moment
        for n in effs:
            fr = base.effect_frames(os.path.join(ROOT, "game", "media", "dmd", "deff_%03d" % n))
            top = max(((int((np.array(Image.open(p).convert("L")) > 0).sum()), p) for p, _, _ in fr), default=(0, None))
            if top[1]:
                best.append((top[0], n, top[1]))
        for ci, (lit, n, path) in enumerate(sorted(best, reverse=True)[:4], 2):
            x = 300 + (ci - 2) * (cw + 4)
            im = Image.open(path).convert("L").resize((cw, ch), Image.NEAREST).convert("RGB")
            sheet.paste(im, (x, y + 4))
            dr.text((x + 2, y + 6), "1-%d-%d deff %d" % (ri, ci, n), font=font, fill=(255, 255, 0))
    os.remove(tmp)
    sheet.save(os.path.join(out, "icons_planche.png"))


if __name__ == "__main__":
    main()
