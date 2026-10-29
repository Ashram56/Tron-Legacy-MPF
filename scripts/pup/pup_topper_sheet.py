#!/usr/bin/env python3
"""Review sheet of the PuP Pack's topper clips (screens 13/14, 1920x562) cropped 4:1, with the trigger that plays
each (switch W<n> for the TRON/ZUSE letters, D<n> for the modes) and the DMD effect it goes with, so the ones that
stand for a DMD animation (TRON/ZUSE letters, the mode frames) can be picked. Cells: planche-row-column, column 1 =
the effect's 128x32 frame (when the trigger is a DMD one), 2-4 = the clip at 0, 50, 100 %.

    python scripts/pup/pup_topper_sheet.py [--pack DIR] [--out DIR]
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pup_dmd_sheet as base  # noqa: E402
import yaml  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = base.ROOT
CELL = (640, 160)


def crop(path, secs, share, tmp):
    t = max(0.0, min(secs - 0.05, share * secs))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", path, "-frames:v", "1", tmp], check=True)
    im = Image.open(tmp).convert("RGB")
    w, h = im.size
    bh = w // 4
    y0 = (h - bh) // 2
    return im.crop((0, y0, w, y0 + bh)).resize(CELL, Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=os.path.join(os.path.dirname(ROOT), "tron-le-pup-pack"))
    ap.add_argument("--out", default=os.path.join(ROOT, "captures", "pup_topper_sheet"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dec = json.load(open(os.path.join(a.pack, "docs", "decoding", "triggers.json"), encoding="utf-8"))
    tm = yaml.safe_load(open(os.path.join(ROOT, "game", "tron_pup", "trigger_map.yaml"), encoding="utf-8"))["dmd"]
    sw = {int(k): v for k, v in yaml.safe_load(open(os.path.join(ROOT, "game", "tron_pup", "trigger_map.yaml"),
                                                    encoding="utf-8"))["switches"].items()}
    playlists = {p["folder"]: p for p in dec["playlists"]}
    rows, seen = [], set()
    for t in dec["triggers"]:
        if t["screen"] not in (13, 14) or not (t["playlist"] or t["file"]):
            continue
        what, deffs = [], []
        for term in t["terms"]:
            if term["kind"] == "D":
                for ev in tm.get(term["num"], []):
                    what.append(str(ev))
                    if str(ev).startswith("tron_deff_"):
                        deffs.append(int(str(ev)[10:].split("{")[0]))
            elif term["kind"] == "W":
                what.append("W%d %s" % (term["num"], sw.get(term["num"], "")))
        for f in playlists.get(t["playlist"], {}).get("files", []):
            if f["kind"] != "video" or (t["file"] and f["file"] != t["file"]):
                continue
            key = (f["path"], tuple(what))
            if key in seen:
                continue
            seen.add(key)
            rows.append((t["id"], t["screen"], t["description"], what, deffs, f))
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
    tmp = os.path.join(a.out, "_tmp.png")
    index = ["# PuP topper clips", "", "Cell = planche-row-column; column 1 = the DMD effect's 128x32 frame (when a DMD trigger), "
             "columns 2-4 = the clip cropped 4:1 at 0, 50, 100 %.", "",
             "| planche-row | trigger row | screen | description | fires on | clip | s |", "|---|---|---|---|---|---|---|"]
    per = 6
    for pi in range((len(rows) + per - 1) // per):
        chunk = rows[pi * per:(pi + 1) * per]
        img = Image.new("RGB", (4 * (CELL[0] + 6) + 4, len(chunk) * (CELL[1] + 6)), (16, 16, 24))
        dr = ImageDraw.Draw(img)
        for ri, (tid, scr, desc, what, deffs, f) in enumerate(chunk, 1):
            y = (ri - 1) * (CELL[1] + 6)
            if deffs:
                folder = os.path.join(ROOT, "game", "media", "dmd", "deff_%03d" % deffs[0])
                fr = base.effect_frames(folder) if os.path.isdir(folder) else []
                if fr:
                    src = Image.open(base.frame_at(fr, 0.5)).convert("L").resize(CELL, Image.NEAREST).convert("RGB")
                    img.paste(src, (0, y))
            for ci, share in enumerate((0.0, 0.5, 1.0), 2):
                x = (ci - 1) * (CELL[0] + 6)
                img.paste(crop(os.path.join(a.pack, f["path"]), f["seconds"], share, tmp), (x, y))
            for ci in range(1, 5):
                x = (ci - 1) * (CELL[0] + 6)
                dr.rectangle((x, y, x + 56, y + 17), fill=(0, 0, 0))
                dr.text((x + 2, y), "%d-%d-%d" % (pi + 1, ri, ci), font=font, fill=(255, 255, 0))
            index.append("| %d-%d | %d | %d | %s | %s | %s | %.1f |" % (pi + 1, ri, tid, scr, desc, ", ".join(what), f["path"].replace("trn_174h/", ""), f["seconds"]))
        img.save(os.path.join(a.out, "planche_%02d.png" % (pi + 1)))
    if os.path.exists(tmp):
        os.remove(tmp)
    open(os.path.join(a.out, "index.md"), "w", encoding="utf-8").write("\n".join(index) + "\n")
    print(len(rows), "rows")


if __name__ == "__main__":
    main()
