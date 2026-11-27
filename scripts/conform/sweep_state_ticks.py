#!/usr/bin/env python3
"""Effect 19 (score display) with the score move at other ticks of the effect than sweep_state.py's 30 (the scenarios move the score at any moment of a score display).

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_state_ticks.py OUT.pkl "TICKS (comma list)" NAME.jsonl [NAME.jsonl ...]
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
    old, new, ball, tick = job
    r = G.recipe(19)
    ram = S.game(1, 1, ball, (old, 0, 0, 0))
    ram.update(S.credit(2, 0))
    ram[0x372e8] = 1
    r["ram"], r["counters"], r["max_insns"] = ram, (0x21117f4,), 9000000
    r["ram_at"] = ((tick, 0x21109e4, new),)
    return [f for f, _ in G._run(19, r)]


def main(out, ticks, *logs):
    moves = set()
    for p in logs:
        for line in open(p):
            if '"ev": "score"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    moves.add((e["total"] - e["delta"], e["total"]))
    jobs = [(o, n, b, int(t)) for o, n in sorted(moves) if o != n for b in (1,) for t in ticks.split(",")]
    frames = set()
    with Pool(int(os.environ.get("SWEEP_PROCS", 4))) as pool:
        for i, fs in enumerate(pool.imap_unordered(one, jobs)):
            frames.update(fs)
            print(i + 1, len(jobs), len(frames), flush=True)
    pickle.dump(frames, open(out, "wb"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *sys.argv[3:])
