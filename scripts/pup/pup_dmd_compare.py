#!/usr/bin/env python3
"""Large review sheets: for each video-like DMD effect one cell per moment, the ROM's 128x32 DMD on top and, under
it, the PuP clip chosen for the effect (random, fixed seed), cropped 4:1 and stretched over the effect's length.

    python scripts/pup/pup_dmd_compare.py [--pack DIR] [--out DIR] [--rows 4] [--seed 1] [--crop-y FILE.json]

Cells are 3 per effect (0, 50, 100 % of the effect), 640x160 each, labelled planche-row-column; one cell holds the
128x32 source and the video version, so a reference names both. --crop-y: {"<effect>": share} to move the band
of an effect (centre as a share of the clip's height, default 0.45).
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pup_dmd_sheet as base  # noqa: E402
import pup_clip_crops  # noqa: E402
import yaml  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = base.ROOT
CELL = (992, 248)
# Effects with no PuP trigger of their own (or a text-only DMD capture) that are video sequences too: the clip folder
# that goes with them by name. A proposal to be judged on the sheets, not something the pack's triggers say.
PROPOSED = {
    47: ["DiscBattleMB"], 51: ["DiscBattleMB"], 52: ["DiscBattleMB"], 53: ["DiscBattleMB"], 54: ["DiscBattleMB"],
    55: ["DaftPunk"], 56: ["EndofLineMB"], 57: ["EndofLineMB"], 58: ["EndofLineMB"], 59: ["EndofLineMB"],
    60: ["EndofLineMB"], 139: ["EndofLineMB"],
    65: ["QuorraMB"], 
    73: ["CluJackpot"], 
    
    86: ["LightCycleMB"], 89: ["LightCycleJackpot"], 90: ["LightCycle"], 128: ["LightCycleMB"], 129: ["DiscBattle"],
    95: ["ZuseMode"], 96: ["ZuseMode"], 98: ["ZuseMode"], 100: ["ZEN"],
    104: ["Arcade"], 105: ["Arcade"], 108: ["Recognizer"], 130: ["Recognizer"],
    114: ["SeaofSimulation"], 115: ["SeaofSimulation"], 119: ["SOSJackpot"], 125: ["SOSJackpot"], 126: ["SOSJackpot"],
    143: ["Portal Jackpot"],
}
MOMENTS = (0.0, 0.5, 1.0)
# Clip chosen by hand for an effect (review round 2): the random pick had the wrong meaning.
FORCE = {116: "SOSJackpot/SOSJackpot2.mp4", 120: "SOSJackpot/SOSJackpot2.mp4", 121: "SOSJackpot/SOSJackpot2.mp4",
         118: "SOSJackpot/SOSJackpot2.mp4", 124: "SOSJackpot/SOSJackpot2.mp4",
         119: "SOSJackpot/SOSJackpot2.mp4", 125: "SOSJackpot/SOSJackpot2.mp4",
         65: "QuorraMB/QuorraMB.mp4", 143: "PortalMB/Portal.mp4",
         95: "ZuseMode/ZuseMode.mp4", 98: "ZuseMode/ZuseMode.mp4",      # the backglass' Zuse sequence for every Zuse animation without a clip
         128: "LightCycleMB/LightCycleMB.mp4", 129: "LightCycleMB/LightCycleMB.mp4"}
# Part of a clip kept (share of its length): SOSJackpot2's 2.3-3.0 s is Quorra's face.
WINDOW = {"SOSJackpot/SOSJackpot2.mp4": (0.455, 0.54), "QuorraMB/QuorraMB.mp4": (0.05, 1.0)}
REALTIME = 2.5             # a clip longer than this many times the effect is not stretched: its first seconds play in real time
# Part of the clip an effect plays, by effect (wins over WINDOW): 128 = the rider turning into the wireframe light cycle,
# 129 = the cycles racing.
WINDOW_EFFECT = {128: (0.03, 0.40), 129: (0.45, 0.95)}
PANEL = 41 / 128           # share of the DMD width the score panel takes: left out of column 1


def source_cell(frames, share):
    p = base.frame_at(frames, share)
    # the classic frame (grey), not the colour twin: the 128x32 DMD as the ROM draws it
    classic = [q for q, _, _ in frames if os.path.basename(q) == os.path.basename(p)]
    img = Image.open(classic[0] if classic else p).convert("L")
    return img.resize(CELL, Image.NEAREST).convert("RGB")


def classic_frame_at(frames, share):
    total = sum(ms for _, _, ms in frames) or 1
    t, acc = share * total, 0
    for p, c, ms in frames:
        acc += ms
        if t < acc:
            return p
    return frames[-1][0]


def forced(pick, n, playlists, clips):
    if n in FORCE:
        for pl in playlists.values():
            for f in pl.get("files", []):
                if f["path"].endswith("trn_174h/" + FORCE[n]) or f["path"].endswith("/" + FORCE[n]):
                    clips[f["path"]] = f
                    return f["path"]
    return pick


def plan(pack, seed=1, min_score=0.35):
    """The effects a PuP clip replaces: (rows, skipped effects, variants). A row is (effect, its D triggers, the clip chosen
    (the pack's file record), the effect's frames, number of clips available); variants[effect] = every clip the effect may
    play (the one forced, else all the clips of its triggers), for scripts/pup/gen_dmd_clips.py."""
    tmap = yaml.safe_load(open(os.path.join(ROOT, "game", "tron_pup", "trigger_map.yaml"), encoding="utf-8"))["dmd"]
    dec = json.load(open(os.path.join(pack, "docs", "decoding", "triggers.json"), encoding="utf-8"))
    playlists = {p["folder"]: p for p in dec["playlists"]}
    by_d = {}
    for t in dec["triggers"]:
        for term in t.get("terms", []):
            if term["kind"] == "D" and t["screen"] == 12 and (t["playlist"] or t["file"]):
                by_d.setdefault(term["num"], []).append(t)
    effects = {}
    for d, evs in tmap.items():
        for ev in evs:
            if str(ev).startswith("tron_deff_"):
                effects.setdefault(int(str(ev)[10:].split("{")[0]), []).append(int(d))
    rows, skipped, variants = [], [], {}
    for n in sorted(effects):
        folder = os.path.join(ROOT, "game", "media", "dmd", "deff_%03d" % n)
        fr = base.effect_frames(folder) if os.path.isdir(folder) else []
        uniq = sorted({p for p, _, _ in fr})
        score = base.video_score(uniq) if uniq else 0.0
        clips = {}
        for d in effects[n]:
            for t in by_d.get(d, []):
                files = [f for pl in ([playlists.get(t["playlist"], {})] if t["playlist"] else playlists.values())
                         for f in pl.get("files", []) if f["kind"] == "video" and (not t["file"] or f["file"] == t["file"])]
                for f in files:
                    clips[f["path"]] = f
        if len(uniq) < 6 or score < min_score or not clips:
            skipped.append(n)
            continue
        pick = random.Random(seed * 1000 + n).choice(sorted(clips))
        pick = forced(pick, n, playlists, clips)
        rows.append((n, effects[n], clips[pick], fr, len(clips)))
        variants[n] = [clips[pick]] if n in FORCE else [clips[k] for k in sorted(clips)]
    have = {r[0] for r in rows}
    for n, folders in sorted(PROPOSED.items()):
        folder = os.path.join(ROOT, "game", "media", "dmd", "deff_%03d" % n)
        fr = base.effect_frames(folder) if os.path.isdir(folder) else []
        clips = {f["path"]: f for pl in folders for f in playlists.get(pl, {}).get("files", []) if f["kind"] == "video"}
        if n in have or not fr or not clips:
            continue
        pick = random.Random(seed * 1000 + n).choice(sorted(clips))
        pick = forced(pick, n, playlists, clips)
        rows.append((n, ["by name: " + "/".join(folders)], clips[pick], fr, len(clips)))
        variants[n] = [clips[pick]] if n in FORCE else [clips[k] for k in sorted(clips)]
    return rows, skipped, variants


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=os.path.join(os.path.dirname(ROOT), "tron-le-pup-pack"))
    ap.add_argument("--out", default=os.path.join(ROOT, "captures", "pup_dmd_compare"))
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--min-score", type=float, default=0.35)
    ap.add_argument("--crop-y", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cropy = json.load(open(a.crop_y)) if a.crop_y else {}
    rows, skipped, variants = plan(a.pack, a.seed, a.min_score)
    cropy = json.load(open(a.crop_y)) if a.crop_y else {}
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
    tmp = os.path.join(a.out, "_tmp.png")
    index = ["# DMD 128x32 against the PuP clip, large", "",
             "Column 1 is the DMD without the score panel; the effect's label is above its three rows; the crops are 4 %% tighter "
             "(the curved frame arcs at the edges) and kept between the baked TRON LEGACY logo and the title card (centre 0.33-0.65 of the "
             "height), a few per clip by hand (pup_crop_overrides.json: cy, and cx + w for a narrower band round the subject); a clip more "
             "than %.1f times longer than its effect plays in real time from its start instead of being stretched (the label says so); "
             "a clip can be cut to a part of its length (WINDOW) or replaced for an effect (FORCE): SOSJackpot2 at 2.3-3.0 s (Quorra's face) "
             "for 116-121, 124, 125; QuorraMB.mp4 for 65; Portal.mp4 for 143; ZuseMode.mp4 for 95, 98 (and 96); LightCycleMB.mp4 for 128 (the transformation) and 129." % REALTIME, "",
             "Cell = planche-row-column (2-3-1 = planche_02.png, 3rd row, column 1). Two columns: 1 = the ROM's 128x32 DMD, "
             "2 = the clip chosen for the effect (random among its clips), same moment of the effect; three rows per effect "
             "(0, 50, 100 %: the clip stretched over the effect's length), two effects per planche. Column 1 leaves out the ROM's score panel (the first 41 dots of 128): the DMD art, and what the live text leaves free, lies to its right.", "",
             "| planche-row | effect | D | clip (chosen) | clips available | clip s | DMD s |", "|---|---|---|---|---|---|---|"]
    per = a.rows
    W1 = int(CELL[0] * (1 - PANEL))           # column 1: the DMD without the score panel, same height as column 2
    HEAD = 24
    for pi in range((len(rows) + per - 1) // per):
        chunk = rows[pi * per:(pi + 1) * per]
        rh = CELL[1] + 4
        eh = HEAD + len(MOMENTS) * rh
        img = Image.new("RGB", (W1 + CELL[0] + 8, len(chunk) * eh + (len(chunk) - 1) * 10), (16, 16, 24))
        dr = ImageDraw.Draw(img)
        for ei, (n, ds, clip, fr, navail) in enumerate(chunk):
            rel = clip["path"].replace("trn_174h/", "")
            crop = pup_clip_crops.crop_for(a.pack, rel, clip["seconds"])
            lo, hi = WINDOW_EFFECT.get(n) or WINDOW.get(rel, (0.0, 1.0))
            dms = sum(ms for _, _, ms in fr) / 1000
            if (lo, hi) == (0.0, 1.0) and clip["seconds"] > REALTIME * dms:      # a long loop: played at its speed, from the start
                lo, hi = 0.0, dms / clip["seconds"]
            top = ei * (eh + 10)
            dr.text((4, top + 3), "deff %d   %s   clip %.1fs%s -> effect %.1fs   crop %s" % (
                n, rel, clip["seconds"], (" (first %.1fs, real time)" % (hi * clip["seconds"]) if hi * clip["seconds"] < clip["seconds"] and rel not in WINDOW and n not in WINDOW_EFFECT else " (%d-%d%%)" % (lo * 100, hi * 100)) if (lo, hi) != (0.0, 1.0) else "", dms, crop["how"]),
                font=font, fill=(255, 190, 120))
            for mi, share in enumerate(MOMENTS):
                ri = ei * len(MOMENTS) + mi + 1
                y = top + HEAD + mi * rh
                full = Image.open(classic_frame_at(fr, share)).convert("L")
                px = int(full.width * PANEL)
                src = full.crop((px, 0, full.width, full.height)).resize((W1, CELL[1]), Image.NEAREST).convert("RGB")
                vid = base.clip_frame(os.path.join(a.pack, clip["path"]), clip["seconds"], lo + share * (hi - lo), tmp, crop).resize(CELL, Image.LANCZOS)
                img.paste(src, (0, y))
                img.paste(vid, (W1 + 8, y))
                for col, x in ((1, 0), (2, W1 + 8)):
                    dr.rectangle((x, y, x + 62, y + 18), fill=(0, 0, 0))
                    dr.text((x + 2, y + 1), "%d-%d-%d" % (pi + 1, ri, col), font=font, fill=(255, 255, 0))
            index.append("| %d-%d..%d | %d | %s | %s | %d | %.1f | %.1f |" % (
                pi + 1, ei * len(MOMENTS) + 1, ei * len(MOMENTS) + len(MOMENTS), n, ",".join(map(str, ds)) if isinstance(ds[0], int) else ds[0],
                os.path.relpath(clip["path"], "trn_174h"), navail, clip["seconds"], dms))
        img.save(os.path.join(a.out, "planche_%02d.png" % (pi + 1)))
    if os.path.exists(tmp):
        os.remove(tmp)
    with open(os.path.join(a.out, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print(len(rows), "effects,", (len(rows) + per - 1) // per, "planches; skipped", skipped)


if __name__ == "__main__":
    main()
