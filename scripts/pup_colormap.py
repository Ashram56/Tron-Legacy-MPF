#!/usr/bin/env python3
"""Derives the colour map of the HD colour DMD (game/tools/dmd_colormap.json) from the videos of Terry Red's
"End of Line" PuP-Pack for Tron Legacy (https://github.com/Ashram56/Tron-LE-PuP-Pack, a separate download;
nothing of it is copied into this repository: only the hues measured here end up in the colour map).

How a display effect finds its videos: the pack's docs/decoding/triggers.json lists each PuP DMD capture
D<n> (the dots the pack waits for on the DMD) with the display effect it matches (mpf_events tron_deff_N),
and the PuP triggers that play a video on D<n>. Videos of the event layer (screen 12, the pop-up video the
pack plays for that moment) come first; the backglass underlay (screen 2) and the topper (13, 14) only
when the event layer has none; the pack's generic backglass loop is ignored. Effects the pack has no
capture for take the videos of their feature (FAMILY: the running screen of a mode takes its intro's).

For each effect, the videos are sampled (ffmpeg, 2 frames a second, inside the film window: CROP) and the
hues of the coloured pixels are counted (weight saturation^2 x value, 10 degree bins). The two strongest
hues at least 45 degrees apart are snapped to the Tron hues (dmd_color.HUES: cyan and blue light lines,
orange CLU / Rinzler, amber, red, violet, green) and make the effect's 16-shade palette (dmd_color.ramp):
dim shades in the main hue, bright shades in the second hue, the top shade a white highlight. A warm hue
(red, orange, amber) marks the subject of the pack's videos against the cyan world (CLU, Rinzler, the
light cycles, the Recognizer), so it takes the body shades and the cool hue the light lines.

    .venv/bin/python scripts/pup_colormap.py PATH/TO/Tron-LE-PuP-Pack    # rewrites game/tools/dmd_colormap.json
"""
import colorsys
import csv
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dmd_color  # noqa: E402

TRON_HUES = dmd_color.HUES                # the hues (degrees) the measured ones snap to: the film's palette
WARM = {"red", "orange", "amber"}
GENERIC = {"TronLegacyBG.mp4"}            # the pack's backglass loop: plays under everything
CROP = "crop=iw*0.72:ih*0.64:iw*0.14:ih*0.11"   # the film window inside the pack's frame
SCREENS = (12, 2, 14, 13)                 # event layer first, then underlay, topper
# effects without a capture of their own -> the effect whose videos they share (same feature, same moment)
FAMILY = {47: 46, 50: 49, 52: 51, 53: 51, 54: 51, 57: 56, 58: 56, 59: 56, 60: 56, 139: 56, 65: 64, 66: 64,
          67: 64, 72: 71, 131: 71, 77: 76, 86: 85, 89: 88, 95: 94, 93: 94, 96: 97, 98: 94, 114: 113, 115: 113,
          125: 113, 141: 140, 143: 142, 144: 142, 110: 108, 130: 108, 112: 101, 105: 104, 135: 106, 134: 106}
ARCADE = {104: ("Arcade", "ArcadeMystery.mp4")}   # triggered by a switch and a lamp, not a DMD capture


def deff_names():
    path = os.path.join(ROOT, "assets", "mpf_package", "event_map.csv")
    return {int(r["deff"]): r["name"] for r in csv.DictReader(open(path, encoding="utf-8"))}


def matches(pack):
    """{deff: [(capture D, screen, playlist, video file), ...]} from the pack's triggers.json."""
    d = json.load(open(os.path.join(pack, "docs", "decoding", "triggers.json"), encoding="utf-8"))
    playlists = {p["folder"]: p for p in d["playlists"]}
    by_capture = {}
    for t in d["triggers"]:
        for term in t["terms"]:
            if term["kind"] == "D" and t["screen"] in SCREENS:
                by_capture.setdefault(term["num"], []).append(t)
    out = {}
    for c in d["captures"]:
        deffs = {int(m.group(1)) for e in c.get("mpf_events", []) for m in [re.fullmatch(r"tron_deff_(\d+)(\{.*\})?", e)]
                 if m}
        for t in by_capture.get(c["d"], []):
            files = [t["file"]] if t["file"] else [f["file"] for f in playlists.get(t["playlist"], {}).get("files", [])
                                                  if f["kind"] == "video"]
            for f in files:
                if f.endswith(".mp4") and f not in GENERIC:
                    for deff in deffs:
                        out.setdefault(deff, []).append((c["d"], t["screen"], t["playlist"], f))
    for deff, (pl, f) in ARCADE.items():
        out.setdefault(deff, []).append((None, 12, pl, f))
    for deff, rows in out.items():                     # the best screen only
        best = min(SCREENS.index(r[1]) for r in rows)
        out[deff] = sorted({r for r in rows if SCREENS.index(r[1]) == best}, key=lambda r: (r[2], r[3]))
    return out


def hue_histogram(path, fps=2, w=96, h=54):
    """36 bins of 10 degrees: sum of saturation^2 x value of the coloured pixels of the sampled frames, in
    the video's window (CROP): the pack frames every video with the same cyan border and characters."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", CROP + ",fps=%g,scale=%d:%d" % (fps, w, h),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    hist = [0.0] * 36
    for i in range(0, len(raw) - 2, 3):
        r, g, b = raw[i] / 255, raw[i + 1] / 255, raw[i + 2] / 255
        hh, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s > 0.3 and v > 0.2:
            hist[int(hh * 36) % 36] += s * s * v
    return hist


def snap(hue):
    name = min(TRON_HUES, key=lambda k: min(abs(TRON_HUES[k] - hue), 360 - abs(TRON_HUES[k] - hue)))
    return name


def two_hues(hist):
    """The strongest hue, and the strongest one at least 45 degrees away (if it has a fifth of the weight)."""
    smooth = [hist[i - 1] * 0.5 + hist[i] + hist[(i + 1) % 36] * 0.5 for i in range(36)]
    total = sum(smooth) or 1
    first = max(range(36), key=lambda i: smooth[i])
    far = [i for i in range(36) if min(abs(i - first), 36 - abs(i - first)) >= 5]
    second = max(far, key=lambda i: smooth[i])
    h1 = first * 10 + 5
    h2 = second * 10 + 5 if smooth[second] >= 0.2 * smooth[first] else None
    return h1, h2, round(smooth[first] / total, 3)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    pack = argv[0]
    names = deff_names()
    found = matches(pack)
    cache = {}
    deffs = {}
    for deff in sorted(names):
        src = deff if deff in found else FAMILY.get(deff)
        if src not in found:
            continue
        hist = [0.0] * 36
        videos = found[src]
        for _, _, playlist, f in videos:
            key = (playlist, f)
            if key not in cache:
                path = os.path.join(pack, "trn_174h", playlist, f)
                cache[key] = hue_histogram(path) if os.path.exists(path) else [0.0] * 36
            hist = [a + b for a, b in zip(hist, cache[key])]
        if not any(hist):
            continue
        h1, h2, share = two_hues(hist)
        main_hue, accent = snap(h1), snap(h2) if h2 is not None else None
        if accent == main_hue:
            accent = None
        if accent in WARM and main_hue not in WARM or main_hue in WARM and accent and accent not in WARM:
            # the warm hue marks the subject (CLU, Rinzler, the light cycles, the Recognizer) against the
            # cyan world: it takes the body shades (1-7: faces, vehicles, film clips), the cool one the
            # bright shades (12-15: the light lines, to the white highlight)
            cool = accent if main_hue in WARM else main_hue
            warm = main_hue if main_hue in WARM else accent
            main_hue, accent = warm, cool
        entry = {"name": names[deff][len("deff_000_"):], "hues": [main_hue] + ([accent] if accent else []),
                 "measured": [h1] + ([h2] if h2 is not None else []), "share": share,
                 "videos": sorted({"%s/%s" % (p, f) for _, _, p, f in videos})}
        if src != deff:
            entry["via"] = src
        else:
            entry["captures"] = sorted({d for d, _, _, _ in videos if d is not None})
        deffs[str(deff)] = entry
        print("deff %3d %-32s %-10s %-10s %s" % (deff, entry["name"], main_hue, accent or "-", ", ".join(entry["videos"])[:70]))
    data = dmd_color.load_colormap()
    data["deffs"] = deffs
    dmd_color.save_colormap(data)
    print("%d effects with PuP colours (%d by their own capture), the others the default palette"
          % (len(deffs), sum(1 for e in deffs.values() if "via" not in e)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
