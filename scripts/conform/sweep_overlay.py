#!/usr/bin/env python3
"""Effects that draw over the screen already on display (the film of effect 57) run in the ROM code on top of each frame of that film.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_overlay.py OUT.pkl EFFECT UNDER VALUE [ARG ...]

The picture under EFFECT is frame k of effect UNDER (57: the SWITCHES= film, its counter RAM 0x3ae00 = VALUE) for every k of its loop; the effect's task
arguments are ARG... (task + 0x30, + 0x34, ...). Effects 58 and 59 (Daft Punk / End of Line awards) print their value over that film.
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import deff_frames as F  # noqa: E402
import gen_code_dmd as G  # noqa: E402


_PAIRS = {}


def pairs_of(under, value):
    if (under, value) not in _PAIRS:
        r = G.recipe(under, dict(G.RECIPES.get(under, {}), ram={0x3ae00: value}, max_insns=12000000))
        ps, _ = F.frames(under, args=r["args"], ram=r["ram"], init=r["init"], counters=r["counters"], max_insns=r["max_insns"])
        pairs = []
        for _, _, a, b in ps:
            if not pairs or pairs[-1] != (a, b):
                pairs.append((a, b))
        _PAIRS[(under, value)] = pairs
    return _PAIRS[(under, value)]


def one(job):
    eff, under, value, args, k = job
    pairs = pairs_of(under, value)
    if k >= len(pairs):
        return None
    sub = dict(G.RECIPES.get(eff, {}), args=args, prev={"deff": under, "frame": k})
    rr = G.recipe(eff, sub)
    ram = dict(rr["ram"])
    G.seed_previous_screen(ram, *pairs[k])
    rr["ram"], rr["prev"] = ram, None
    return [f for f, _ in G._run(eff, rr)]


def main(argv):
    out, eff, under, value = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
    args = [int(a) for a in argv[4:]] + [0, 0, 0, 0]
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, [(eff, under, value, args[:4], k) for k in range(70)]):
            if fs:
                frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print(len(frames), "frames")


if __name__ == "__main__":
    main(sys.argv[1:])
