#!/usr/bin/env python3
"""The status panel (deff_draw_status_panel 0x010230ec, columns 0-40) of the ROM code with the last award it shows under the score: DAT_021117f8 (the
points of the last score, FUN_01022fdc) fading by DAT_021117fc (its age: palette level (0x1a - age) >> 1 while age < 0x1a), run inside effect 19.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_panel.py OUT.pkl NAME.jsonl [NAME.jsonl ...]    (the `score` events: delta, total)
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
    delta, total, age = job[:3]
    r = G.recipe(19)
    ram = S.game(1, 1, 1, (total, 0, 0, 0))
    ram.update(S.credit(2, 0))
    ram.update({0x21117f8: delta, 0x21117fc: age})
    r["ram"], r["max_insns"] = ram, 1000000
    if len(job) == 5:                   # a timer bar of the panel (x = 40, FUN_00027174): zfs 0x3b58c, clu 0x3b57c, gem 0x3b584 (u16), rows from its value
        ram[job[3]] = job[4]
    elif len(job) == 4:                   # the points just scored: the fade age DAT_021117fc and the roll counter DAT_021117f4 both count from 0
        ram[0x372e8] = 1
        r["counters"], r["max_insns"] = (0x21117f4, 0x21117fc), 9000000
    return [f for f, _ in G._run(19, r)]


def main(out, *logs):
    moves = set()
    for p in logs:
        adds = []                       # the score_adds of one score event: FUN_010238ac keeps the larger points within 16 ticks, so the
        for line in open(p):            # panel's last award is the sum or any one of them (the game's score_added), with the total so far
            if '"ev": "score_add"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    adds.append(e["points"])
            elif '"ev": "score"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    moves.add((e["delta"], e["total"]))
                    before, run = e["total"] - e["delta"], 0
                    for a in adds:
                        run += a
                        moves.add((a, before + run))
                        moves.add((max(adds[:adds.index(a) + 1]), before + run))
                    adds = []
    jobs = [(d, t, a) for d, t in sorted(moves) for a in range(0, 28)]
    jobs += [(d, t, a, bar, v) for d, t in sorted(moves) for a in (0, 26) for bar in (0x3b58c, 0x3b57c, 0x3b584) for v in range(1, 11)]
    jobs += [(d, t, 0, True) for d, t in sorted(moves)]       # just scored, playfield valid: fade and roll run together
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, jobs):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(jobs), len(frames))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
