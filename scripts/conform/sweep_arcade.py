#!/usr/bin/env python3
"""Effect 105 (arcade award slot machine) of the ROM code with the draws the game made: the trace's `deff_args` (award, cabinets, icons, slot) are turned back into the
random_below (0xc6b4) draws the ROM routine makes: per slot a cabinet (below 4) then an icon seed (below 13; icon = seed + 1, 13 -> 1), then the slot (below 3).

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_arcade.py OUT.pkl NAME.jsonl [NAME.jsonl ...]
"""
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
from dmd_recipes_c import _Seq  # noqa: E402


def main(out, *logs):
    frames = set()
    for p in logs:
        for line in open(p):
            if '"deff_args"' not in line:
                continue
            e = json.loads(line)
            if e["id"] != 105:
                continue
            a = e["args"]
            draws = []
            for k in range(3):
                icon = a["icon%d" % k]
                draws += [a["cab%d" % k], icon - 1 if icon > 1 else 12]
            draws.append(a["slot"])
            sub = dict(G.RECIPES[105])
            sub.update(args=[a["award"], 0, 0, 0], rng=_Seq(draws), max_insns=8000000)
            frames.update(f for f, _ in G._run(105, G.recipe(105, sub)))
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
