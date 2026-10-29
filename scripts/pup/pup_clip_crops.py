#!/usr/bin/env python3
"""Per-clip 4:1 crop of the PuP Pack's 1920x1080 clips for the DMD: which columns to keep (the static character
panels at both sides out) and where the band sits vertically (on the faces when OpenCV finds some, else on the
busiest part of the picture), the same for the whole clip so the picture does not wander.

    python scripts/pup/pup_clip_crops.py PACK CLIP.mp4 ...        # print the crops
    crop_for(pack, relpath, seconds) -> {"x0", "x1", "y0", "h"} in pixels

Overrides, by clip path inside trn_174h (e.g. "Gem/Gem1.mp4"), in scripts/pup/pup_crop_overrides.json:
{"Gem/Gem1.mp4": {"cy": 0.40}}  (band centre as a share of the height) and/or {"x0": 262, "x1": 1684}, or {"cx": 700, "w": 900} (a narrower band centred on x = 700).
Analyses are cached in .cache/pup_crops.json.
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CACHE = os.path.join(ROOT, ".cache", "pup_crops.json")
OVERRIDES = os.path.join(HERE, "pup_crop_overrides.json")
HAAR = os.path.join(ROOT, ".cache", "models", "haar.xml")
DEFAULT_X = (302, 1646)          # the panels' edge, measured on the pack's clips
SAMPLES = 8
DEFAULT_CY = 0.40
CY_RANGE = (0.33, 0.65)    # where the pack's clips show the scene itself, between the baked logo and title bands
FRAME_X = (250, 1700)      # the neon frame round the picture: nothing of the character panels outside it
ZOOM = 0.96              # share of the width kept after the panels: the curved frame arcs at the edges out


def frames(path, seconds):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(SAMPLES):
            t = max(0.0, min(seconds - 0.05, (i + 0.5) / SAMPLES * seconds))
            p = os.path.join(tmp, "f.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", path, "-frames:v", "1", p], check=True)
            out.append(np.array(Image.open(p).convert("RGB")))
    return out


def columns(fr):
    """Static columns (the panels) are the same in every sampled frame; keep the run between the panels."""
    g = np.stack([f.mean(axis=2) for f in fr])
    moving = g.std(axis=0).mean(axis=0) > 4
    w = g.shape[2]
    x0 = next((i for i in range(0, 700) if moving[i:i + 40].all()), DEFAULT_X[0])
    x1 = next((i for i in range(w - 1, 1200, -1) if moving[i - 40:i].all()), DEFAULT_X[1])
    if not (200 <= x0 <= 330 and 1620 <= x1 <= 1720):       # no panel found (a full-screen overlay): the default
        return DEFAULT_X
    return x0, x1


def band_centre(fr, x0, x1, bh):
    import cv2
    h = fr[0].shape[0]
    centres, weights = [], []
    cascade = cv2.CascadeClassifier(HAAR) if os.path.exists(HAAR) else None
    for f in fr:
        crop = f[:, x0:x1]
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        if cascade is not None and not cascade.empty():
            for (x, y, w, hh) in cascade.detectMultiScale(gray, 1.1, 4, minSize=(70, 70)):
                if (y + hh / 2) / h < 0.62:       # a face in the lower part is the title card's, not the scene's
                    centres.append(y + hh / 2)
                    weights.append(w * hh)
    if len(centres) >= 2:
        order = np.argsort(centres)
        cs = np.cumsum(np.array(weights)[order])
        cy = float(np.array(centres)[order][np.searchsorted(cs, cs[-1] / 2)])
        return cy / h, "faces"
    return DEFAULT_CY, "default"      # no face: the action sits at 0.35-0.45 of the height; the title card below it is not it


def analyse(path, seconds):
    fr = frames(path, seconds)
    x0, x1 = columns(fr)
    bh = (x1 - x0) // 4
    cy, how = band_centre(fr, x0, x1, bh)
    return {"x0": int(x0), "x1": int(x1), "cy": round(cy, 3), "how": how}


def crop_for(pack, rel, seconds):
    """{"x0","x1","y0","h"} of the clip's crop (rel: path under trn_174h, e.g. Gem/Gem1.mp4)."""
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if rel not in cache:
        cache[rel] = analyse(os.path.join(pack, "trn_174h", rel), seconds)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w"), indent=0, sort_keys=True)
    c = dict(cache[rel])
    c["cy"] = min(max(c["cy"], CY_RANGE[0]), CY_RANGE[1])       # above: the TRON LEGACY logo, below: the title card
    c["x0"], c["x1"] = max(c["x0"], DEFAULT_X[0]), min(c["x1"], DEFAULT_X[1])      # never a sliver of the panels
    if os.path.exists(OVERRIDES):
        c.update(json.load(open(OVERRIDES)).get(rel, {}))
    if "w" in c:        # override: a narrower band round the subject, "cx" its centre (pixels), kept inside the picture frame
        half = c["w"] / 2
        mid = min(max(c.get("cx", (c["x0"] + c["x1"]) / 2), FRAME_X[0] + half), FRAME_X[1] - half)
    else:
        mid, half = (c["x0"] + c["x1"]) / 2, (c["x1"] - c["x0"]) / 2 * ZOOM      # the panels' dark arcs at the edges
    c["x0"], c["x1"] = int(mid - half), int(mid + half)
    bh = (c["x1"] - c["x0"]) // 4
    y0 = int(min(max(c["cy"] * 1080 - bh / 2, 0), 1080 - bh))
    return {"x0": c["x0"], "x1": c["x1"], "y0": y0, "h": bh, "how": c.get("how", "override")}


if __name__ == "__main__":
    pack = sys.argv[1]
    for rel in sys.argv[2:]:
        print(rel, analyse(os.path.join(pack, "trn_174h", rel), 3.0))
