#!/usr/bin/env python3
"""Run a score-dependent effect of the ROM code (assets/tools, Unicorn) for the states a scenario went through, and save the frames.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_state.py OUT.pkl NAME.jsonl [NAME.jsonl ...]

Effect 19 (score display): every score total and every move (old -> new, the new score written at tick 30, ram_at) of the scenarios' `score` events x ball 1-3 x credits record units (-1, 2; the record with units 2
draws CREDITS 0, deff_state.credit), 1 player, 1 M instructions a run. The union of the frames is what code_conform.py adds to the code set.
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
    old, new, ball, units, roll = job
    r = G.recipe(19)
    ram = S.game(1, 1, ball, (old, 0, 0, 0))
    ram.update(S.credit(units, 0))
    r["ram"], r["max_insns"] = ram, 1500000
    if roll:                            # playfield valid (0x372e8) and the tick counter DAT_021117f4: the ROM's score roll (FUN_01023940)
        ram[0x372e8] = 1
        r["counters"], r["max_insns"] = (0x21117f4,), 9000000
    if new != old:                      # the score moves while the effect runs: the ROM's roll-up frames
        r["ram_at"] = ((30, 0x21109e4, new),)
    return [f for f, _ in G._run(19, r)]


def main(argv):
    out, logs = argv[0], argv[1:]
    moves = {(0, 0)}
    for p in logs:
        for line in open(p):
            if '"ev": "score"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    moves.add((e["total"], e["total"]))
                    moves.add((e["total"] - e["delta"], e["total"]))
    jobs = [(o, n, b, u, False) for o, n in sorted(moves) for b in (1, 2, 3) for u in (-1, 2)]
    jobs += [(o, o, b, 2, True) for o, n in sorted(moves) if o == n for b in (1, 2, 3)]       # the roll runs
    frames = set()
    with Pool(4) as pool:
        for i, fs in enumerate(pool.imap_unordered(one, jobs)):
            frames.update(fs)
            print(i + 1, len(jobs), len(frames), flush=True)
    pickle.dump(frames, open(out, "wb"))


if __name__ == "__main__":
    main(sys.argv[1:])
