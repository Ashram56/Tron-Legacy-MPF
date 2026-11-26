#!/usr/bin/env python3
"""The bonus count screens (effect 25, child task bonus_count_task 0x01000e7c) of the ROM code for every item and running total.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_bonus.py OUT.pkl [NAME.jsonl ...]   (the jsonl's deff_args give the totals shown)

A screen shows one item (items_table 0x02111690 + player*4 + item*16: byte 0 = 50,000, byte 1 = 250,000 per bonus_item_value 0x01015f7c, ROM
values at 0x040d2ddc / 0x040d2de0) and the running sum, which only depends on the base (bonus_base 0x021115e0) plus what was counted before: each run
sets one item and the base that gives the sum, for sums 0 .. 3,000,000 by 50,000.
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402


def one(job):
    item, level, base = job[:3]
    ram = {**S.game(), 0x21115e0: base, 0x21115d4: 1}
    if item >= 0:
        ram[0x2111690 + 4 + 16 * item] = 0x100 if level else 1
    elif item == -1:                    # Sea of Simulation: sos_count_get 0x01026390 (byte 0x2111800 for player 1) x 450,000
        ram[0x2111800] = level
    elif item == -2:                    # Portal: portal_count_get 0x0102f3e8 (byte 0x21118b8) x 0x225510
        ram[0x21118b8] = level
    else:                               # the multiplier screens "%dX": DAT_021115d3[player] (0x21115d4), total x 2 .. x level
        ram[0x21115d4] = level
    sub = dict(G.RECIPES[25])
    if len(job) == 4:                   # the whole effect (child then TOTAL BONUS screens) for a total the game showed
        sub.update(ram=ram, max_insns=20000000)
        sub["extra_runs"] = [dict(fn_addr=0x1000e7c, max_insns=6000000, ram=ram)]
        return [f for f, _ in _whole(sub)]
    sub.update(fn_addr=0x1000e7c, max_insns=6000000 if item == -3 else 1000000, extra_runs=(), ram=ram)
    return [f for f, _ in G._run(25, G.recipe(25, sub))]


def _whole(sub):
    r = G.recipe(25, sub)
    frames = G._run(25, r)
    for extra in r["extra_runs"]:
        s2 = dict(sub)
        s2.update(extra)
        s2["extra_runs"] = ()
        frames = G._run(25, G.recipe(25, s2)) + frames
    return frames


def main(out, *logs):
    jobs = [(i, lv, b) for i in range(9) for lv in (0, 1) for b in range(0, 3000001, 50000)]
    jobs += [(-1, n, b) for n in (1, 2, 3, 4) for b in range(0, 3000001, 50000)]
    jobs += [(-2, n, b) for n in (1, 2) for b in range(0, 6000001, 50000)]
    jobs += [(-3, 5, b) for b in range(0, 9000001, 50000)]
    import json
    totals = {json.loads(l)["args"]["total"] for p in logs for l in open(p) if '"deff_args"' in l and json.loads(l)["id"] == 25}
    for t in sorted(totals):            # a total shown: base T with multiplier m (T x m = total), no items
        for m in (1, 2, 3, 4, 5):
            if t % m == 0 and (t // m) % 50000 == 0:
                jobs.append((-3, m, t // m, "whole"))
    frames = set()
    with Pool(4) as pool:
        for n, fs in enumerate(pool.imap_unordered(one, jobs)):
            frames.update(fs)
            if n % 100 == 0:
                print(n, len(jobs), len(frames), flush=True)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
