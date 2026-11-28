#!/usr/bin/env python3
"""Effect 77 (Gem hurry-up, text FOLLOW GEM / seconds left / value) of the ROM code for every timer value (gem_timer RAM 0x3b12c) and score.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_gem.py OUT.pkl NAME.jsonl [NAME.jsonl ...]    (scores from the `score` events)
"""
import json
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402


def one(job):
    timer, score = job
    sub = dict(G.RECIPES.get(77, {}))
    sub.update(ram={**S.game(1, 1, 1, (score, 0, 0, 0)), 0x3b12c: timer}, max_insns=3000000)
    return [f for f, _ in G._run(77, G.recipe(77, sub))]


def main(out, *logs):
    scores = {0}
    for p in logs:
        for line in open(p):
            if '"ev": "score"' in line:
                scores.add(json.loads(line)["total"])
    jobs = [(t, s) for t in range(0, 26) for s in sorted(scores)]
    frames = set()
    with Pool(4) as pool:
        for n, fs in enumerate(pool.imap_unordered(one, jobs)):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(jobs), len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
