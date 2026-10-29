#!/usr/bin/env python3
"""Review sheets: the DMD's video-like display effects next to the PuP Pack clip their trigger plays, cropped to the
DMD's 4:1 shape. Nothing is implemented in the game by this; it is for choosing which effects get the clip.

    python scripts/pup/pup_dmd_sheet.py [--pack DIR] [--out DIR] [--rows N] [--min-score X]

Per effect (game/media/dmd/deff_N, frames + their ms in effect.json) the PuP triggers that fire on it come from
game/tron_pup/trigger_map.yaml (D<n> -> tron_deff_N) and the pack's decoded triggers.json (rows on the backglass
top layer, screen 12, with their playlist or file). Each (effect, clip) is one row of a planche:

    columns 1-4  the DMD effect now (colour frames, 256x64) at 0, 33, 66, 100 % of its length
    columns 5-8  the clip at the same relative times, a 4:1 band of the 1920x1080 picture (CROP_Y = the band's
                 centre as a share of the height) on the DMD's size

Every cell is labelled planche-row-column (3-2-6 = planche_03.png, 2nd row, 6th column). index.md lists the
rows (planche-row, effect, trigger, row id, clip) and the effects left out, with their video-likeness score.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CELL = (288, 72)
SIDE = 0.125           # the backglass layout puts the characters in the outer eighths: left out of the DMD crop
CROP_Y = 0.45          # centre of the 4:1 band, share of the clip's height
MOMENTS = (0.0, 0.33, 0.66, 1.0)
LEFT = 330


def video_score(frames):
    """Share of lit dots in the middle shades (2..13) over the effect's frames: line art and text sit on the top
    shade, a film clip is mostly in between."""
    mid = lit = 0
    for p in frames:
        g = np.array(Image.open(p).convert("L"))
        s = np.rint(g / 17).astype(int)
        mid += int(((s >= 2) & (s <= 13)).sum())
        lit += int((s >= 1).sum())
    return mid / lit if lit else 0.0


def effect_frames(folder):
    """[(classic frame path, colour frame path or None, ms)] of the effect's frame item, in play order."""
    with open(os.path.join(folder, "effect.json"), encoding="utf-8") as f:
        eff = json.load(f)
    for it in eff["items"]:
        if it["type"] == "frames":
            out = []
            colour = it.get("color_frames") or []
            for i, (pic, ms) in enumerate(it["frames"]):
                p = os.path.join(ROOT, "game", pic[len("res://"):])
                c = os.path.join(ROOT, "game", colour[i][len("res://"):]) if i < len(colour) else None
                out.append((p, c, ms))
            return out
    return []


def frame_at(frames, share):
    total = sum(ms for _, _, ms in frames) or 1
    t, acc = share * total, 0
    for p, c, ms in frames:
        acc += ms
        if t < acc:
            return c if c and os.path.exists(c) else p
    p, c, _ = frames[-1]
    return c if c and os.path.exists(c) else p


def clip_frame(path, seconds, share, tmp, crop=None):
    t = max(0.0, min(seconds - 0.05, share * seconds))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", path, "-frames:v", "1", tmp], check=True)
    im = Image.open(tmp).convert("RGB")
    if crop:
        return im.crop((crop["x0"], crop["y0"], crop["x1"], crop["y0"] + crop["h"]))
    w, h = im.size
    x0, x1 = int(SIDE * w), int((1 - SIDE) * w)
    bh = (x1 - x0) // 4
    y0 = int(min(max(CROP_Y * h - bh / 2, 0), h - bh))
    return im.crop((x0, y0, x1, y0 + bh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=os.path.join(os.path.dirname(ROOT), "tron-le-pup-pack"))
    ap.add_argument("--out", default=os.path.join(ROOT, "captures", "pup_dmd_sheets"))
    ap.add_argument("--rows", type=int, default=9)
    ap.add_argument("--min-score", type=float, default=0.35)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(ROOT, "game", "tron_pup", "trigger_map.yaml"), encoding="utf-8") as f:
        tmap = yaml.safe_load(f)["dmd"]
    with open(os.path.join(a.pack, "docs", "decoding", "triggers.json"), encoding="utf-8") as f:
        dec = json.load(f)
    playlists = {p["folder"]: p for p in dec["playlists"]}
    by_d = {}
    for t in dec["triggers"]:
        for term in t.get("terms", []):
            if term["kind"] == "D" and t["screen"] == 12 and (t["playlist"] or t["file"]):
                by_d.setdefault(term["num"], []).append(t)
    effects = {}                                   # deff -> [D]
    for d, evs in tmap.items():
        for ev in evs:
            if str(ev).startswith("tron_deff_"):
                n = int(str(ev)[len("tron_deff_"):].split("{")[0])
                effects.setdefault(n, []).append(int(d))
    rows, left_out = [], []
    for n in sorted(effects):
        folder = os.path.join(ROOT, "game", "media", "dmd", "deff_%03d" % n)
        fr = effect_frames(folder) if os.path.isdir(folder) else []
        uniq = sorted({p for p, _, _ in fr})
        score = video_score(uniq) if uniq else 0.0
        clips = []
        for d in effects[n]:
            for t in by_d.get(d, []):
                if t["playlist"]:
                    pl = playlists.get(t["playlist"], {})
                    files = [(f["path"], f["seconds"], "%s/%s" % (t["playlist"], f["file"])) for f in pl.get("files", [])
                             if f["kind"] == "video"]
                else:
                    files = []
                    for pl in playlists.values():
                        for f in pl.get("files", []):
                            if f["file"] == t["file"] and f["kind"] == "video":
                                files.append((f["path"], f["seconds"], "%s/%s" % (pl["folder"], f["file"])))
                for c in files:
                    clips.append((d, t["id"], c))
        merged = {}                                # one row per clip: the D triggers and rows that play it
        for d, tid, c in clips:
            m = merged.setdefault(c[2], [c, [], []])
            if d not in m[1]:
                m[1].append(d)
            if tid not in m[2]:
                m[2].append(tid)
        clips = [(m[1], m[2], m[0]) for m in merged.values()]
        if len(uniq) < 6 or score < a.min_score or not clips:
            left_out.append((n, len(uniq), score, bool(clips)))
            continue
        for d, tid, (path, secs, label) in clips:
            rows.append((n, d, tid, os.path.join(a.pack, path), secs, label, fr, score))
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    tmp = os.path.join(a.out, "_tmp.png")
    index = ["# PuP clips on the DMD: review sheets", "",
             "Cell = planche-row-column (3-2-6 = planche_03.png, 2nd row, 6th column). Columns 1-4: the DMD effect now; "
             "5-8: the clip's 4:1 crop at the same relative times (0, 33, 66, 100 %).", "",
             "| planche-row | effect | D | trigger row | clip | clip s | DMD s | video score |", "|---|---|---|---|---|---|---|---|"]
    for pi in range((len(rows) + a.rows - 1) // a.rows):
        chunk = rows[pi * a.rows:(pi + 1) * a.rows]
        img = Image.new("RGB", (LEFT + 8 * (CELL[0] + 4), len(chunk) * (CELL[1] + 6)), (16, 16, 24))
        dr = ImageDraw.Draw(img)
        for ri, (n, d, tid, path, secs, label, fr, score) in enumerate(chunk, 1):
            y = (ri - 1) * (CELL[1] + 6)
            dms = sum(ms for _, _, ms in fr) / 1000
            dr.text((4, y + 2), "%d-%d  deff %d" % (pi + 1, ri, n), font=font, fill=(255, 255, 255))
            dr.text((4, y + 18), "D%s  row %s" % (",".join(map(str, d)), ",".join(map(str, tid)))[:40], font=small, fill=(180, 200, 255))
            dr.text((4, y + 32), label[:38], font=small, fill=(255, 190, 120))
            dr.text((4, y + 46), "clip %.1fs  dmd %.1fs" % (secs, dms), font=small, fill=(160, 160, 160))
            for ci, share in enumerate(MOMENTS):
                cell = Image.open(frame_at(fr, share)).convert("RGB").resize(CELL, Image.NEAREST)
                cell2 = clip_frame(path, secs, share, tmp).resize(CELL, Image.LANCZOS)
                for col, c in ((ci + 1, cell), (ci + 5, cell2)):
                    x = LEFT + (col - 1) * (CELL[0] + 4)
                    img.paste(c, (x, y))
                    d2 = ImageDraw.Draw(img)
                    d2.rectangle((x, y, x + 52, y + 13), fill=(0, 0, 0))
                    d2.text((x + 2, y), "%d-%d-%d" % (pi + 1, ri, col), font=small, fill=(255, 255, 0))
            index.append("| %d-%d | %d | D%s | %s | %s | %.1f | %.1f | %.2f |" % (pi + 1, ri, n, ",".join(map(str, d)), ",".join(map(str, tid)), label, secs, dms, score))
        img.save(os.path.join(a.out, "planche_%02d.png" % (pi + 1)))
    if os.path.exists(tmp):
        os.remove(tmp)
    index += ["", "## Effects with a PuP trigger left out", "", "| effect | distinct frames | video score | has a clip |", "|---|---|---|---|"]
    for n, k, s, c in left_out:
        index.append("| %d | %d | %.2f | %s |" % (n, k, s, "yes" if c else "no"))
    with open(os.path.join(a.out, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print("%d rows, %d planches, %d effects left out" % (len(rows), (len(rows) + a.rows - 1) // a.rows, len(left_out)))


if __name__ == "__main__":
    sys.exit(main())
