#!/usr/bin/env python3
"""Effect 75 ("N MORE TO START", FOLLOW GEM) of the ROM code with the panel state of the game: the player's score, the last points (DAT_021117f8) fading by
their age (DAT_021117fc, counted per tick), for N = 1..3 (task + 0x30).

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_more.py OUT.pkl NAME.jsonl [NAME.jsonl ...]
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
    delta, total, more = job
    sub = dict(G.RECIPES.get(75, {}))
    ram = S.game(1, 1, 1, (total, 0, 0, 0))
    ram.update({0x21117f8: delta, 0x21117fc: 0})
    sub.update(args=[more, 0, 0, 0], ram=ram, counters=(0x21117fc,), max_insns=20000000)
    return [f for f, _ in G._run(75, G.recipe(75, sub))]


def main(out, *logs):
    moves = set()
    for p in logs:
        for line in open(p):
            if '"ev": "score"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    moves.add((e["delta"], e["total"]))
    jobs = [(d, t, m) for d, t in sorted(moves) for m in (1, 2, 3)]
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, jobs):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(jobs), len(frames))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
