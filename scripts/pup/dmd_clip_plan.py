#!/usr/bin/env python3
"""The plan of the PuP clips on the DMD, as data: scripts/pup/dmd_clip_plan.json (committed; needs the decoded pack,
docs/decoding/triggers.json of the private pup_pack, and OpenCV for the face crops, so it is made here and read by
scripts/pup/gen_dmd_clips.py, which only needs the pack's videos and ffmpeg).

    python scripts/pup/dmd_clip_plan.py [--pack DIR]

The plan is the one of the review sheets (pup_dmd_compare.py plan(): which clip each video-like effect plays, FORCE and
WINDOW there, the crops pup_clip_crops.py with pup_crop_overrides.json), per effect:
  "64": {"ms": 3790, "loop": false, "variants": [{"clip": "QuorraMB/QuorraMB.mp4", "seconds": 10.1, "lo": 0.05, "hi": 1.0,
          "crop": [x0, y0, w, h]}]}     the game plays one of the variants at random; the part lo..hi of the clip is
                                         stretched over ms (a clip more than REALTIME times longer is played at its speed)
and the characters' icon effects (the face sliding into the hexagonal frame), whose picture the topper's HD icon replaces:
  "icons": {"62": "quorra", ...}, "icon_sources": {"quorra": {"clip", "t", "box"}}
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pup_clip_crops  # noqa: E402
import pup_dmd_compare as C  # noqa: E402
import pup_icons_sheet  # noqa: E402

PLAN = os.path.join(HERE, "dmd_clip_plan.json")
# the clips carry the pack's baked "JACKPOT" lettering: a clip it covers is left out, and the title wipes that start
# some clips are skipped by starting later (the lettering at the bottom of the others is cropped away: pup_crop_overrides.json)
LOOP_SECONDS = 15          # a looping effect plays this much of its clip, at its own speed, before the clip loops
SKIP = {"LightCycleJackpot/LightCycleJackpot5.mp4"}
START_AFTER = {"DiscBattleJackpot/DiscWarsJackpot1.mp4": 0.26, "LightCycleJackpot/LightCycleJackpot1.mp4": 0.26,
               "QuorraJackpot/QuorraJackpot1.mp4": 0.26}
ICON_EFFECTS = {62: "quorra", 63: "quorra", 70: "quorra", 74: "clu", 131: "clu", 75: "gem", 79: "gem", 99: "zuse",
                136: "flynn", 137: "flynn"}


def main():
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else os.path.join(os.path.dirname(C.ROOT), "tron-le-pup-pack")
    rows, skipped, variants = C.plan(pack)
    effects = {}
    for n, _ds, _clip, fr, _navail in rows:
        dms = sum(ms for _, _, ms in fr)
        vs = []
        loop = any(i["type"] == "frames" and i.get("loop") for i in json.load(open(
            os.path.join(C.ROOT, "game", "media", "dmd", "deff_%03d" % n, "effect.json"), encoding="utf-8"))["items"])
        for v in variants[n]:
            rel = v["path"].replace("trn_174h/", "")
            if rel in SKIP and len(variants[n]) > 1:
                continue
            lo, hi = C.WINDOW_EFFECT.get(n) or C.WINDOW.get(rel, (0.0, 1.0))
            lo = max(lo, START_AFTER.get(rel, 0.0))
            top = hi                    # the end of the clip's window (before the effect's length cuts it)
            if (lo, hi) == (0.0, 1.0) and v["seconds"] > C.REALTIME * dms / 1000:
                hi = dms / 1000 / v["seconds"]
            c = pup_clip_crops.crop_for(pack, rel, v["seconds"])
            row = {"clip": rel, "seconds": v["seconds"], "lo": round(lo, 4), "hi": round(hi, 4),
                   "crop": [c["x0"], c["y0"], c["x1"] - c["x0"], c["h"]]}
            if loop:       # the ROM loops its short animation until the game ends the effect: the clip plays in real time
                row["hi"] = round(min(top, lo + LOOP_SECONDS / v["seconds"]), 4)
                row["ms"] = round((row["hi"] - lo) * v["seconds"] * 1000)
            vs.append(row)
        effects[str(n)] = {"ms": dms, "loop": loop, "variants": vs}
    icons = {}
    for name, (clip, t, _effs, box) in pup_icons_sheet.ICONS.items():
        icons[name] = {"clip": clip, "t": t, "box": list(box)}
    out = {"effects": effects, "icons": {str(k): v for k, v in ICON_EFFECTS.items()}, "icon_sources": icons}
    with open(PLAN, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(len(effects), "effects,", sum(len(e["variants"]) for e in effects.values()), "clips,", len(icons), "icons ->", PLAN)


if __name__ == "__main__":
    main()
