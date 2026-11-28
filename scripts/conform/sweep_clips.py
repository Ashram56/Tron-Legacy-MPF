#!/usr/bin/env python3
"""Effects whose film clip the ROM picks with random_below (108: below 4 at 0x10209d8; 111: below 11 at 0x1021be4; the others of dmd_variants.yaml),
run in the ROM code with the draw the game made (its godot log line `DMDPICK deff_NNN_name n k`, dmd_effect.gd), like sweep_arcade.py does for 105.

    TRON_ROM=trn_174h.bin python3 scripts/conform/sweep_clips.py OUT.pkl NAME.godot.log [...]
"""
import os
import pickle
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
from dmd_recipes_c import _Seq  # noqa: E402


def main(out, *logs):
    picks = set()
    for p in logs:
        for line in open(p, errors="replace"):
            m = re.search(r"DMDPICK\s+deff_(\d+)\S*\s+(\d+)\s+(\d+)", line)
            if m:
                picks.add((int(m.group(1)), int(m.group(3))))
    frames = set()
    for eff, k in sorted(picks):
        if eff not in G.RECIPES:
            print("no recipe for", eff)
            continue
        sub = dict(G.RECIPES[eff])
        sub.update(rng=_Seq([k]), max_insns=max(sub.get("max_insns", 0), 8000000))
        n = 0
        for f, _ in G._run(eff, G.recipe(eff, sub)):
            frames.add(f)
            n += 1
        print("effect", eff, "draw", k, n, "frames")
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
