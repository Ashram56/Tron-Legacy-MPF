#!/usr/bin/env python3
"""Run one effect of the ROM code with several first arguments (task + 0x30; e.g. the "N MORE TO START" counts of effect 75) and save the frames.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_args.py OUT.pkl EFFECT MAX_INSNS ARG [ARG ...]
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402


def one(job):
    e, mi, a = job
    sub = dict(G.RECIPES.get(e, {}))
    sub.update(args=[a, 0, 0, 0], max_insns=mi)
    return [f for f, _ in G._run(e, G.recipe(e, sub))]


def main(out, e, mi, *args):
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, [(int(e), int(mi), int(a)) for a in args]):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
