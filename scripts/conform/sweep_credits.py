#!/usr/bin/env python3
"""Effect 10 (the credits screens, deff_010 0x01000000) of the ROM code for every credits record. Its argument (task + 0x30) is the credit
record number passed to FUN_00004ff4 (FUN_000047b0 accepts only 1: 0x040e0bb0 + 1 * 0x28), units 0.. 8 and 0.. 3 whole credits (record 0x2111008).

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_credits.py OUT.pkl
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402


def one(job):
    units, credits = job
    sub = dict(G.RECIPES.get(10, {}))
    sub.update(args=[1, 0, 0, 0], ram={**S.game(), **S.credit(units, credits)}, max_insns=3000000)
    return [f for f, _ in G._run(10, G.recipe(10, sub))]


def main(out):
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, [(u, c) for u in range(0, 9) for c in range(0, 4)]):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(sys.argv[1])
