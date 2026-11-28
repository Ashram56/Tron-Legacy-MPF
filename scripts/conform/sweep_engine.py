#!/usr/bin/env python3
"""The frames of the ported effect programs (tron/rom_deff*.py, each checked against the ROM code) for the arguments a scenario's `deff_args` events carry,
as a set for code_conform.py --extra.

    python3 scripts/conform/sweep_engine.py OUT.pkl NAME.jsonl [...]
"""
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game"))
from tron import rom_deff2, rom_deff38, rom_deff55, rom_deff57, rom_deff58, rom_deff60, rom_deff83, rom_deff94, rom_deff95, rom_deff96, rom_deff108, rom_deff138, rom_deff139  # noqa: E402


def main(out, *logs):
    frames = set()
    for p in logs:
        for line in open(p):
            if '"deff_live"' in line:                  # the values a live effect printed (RAM): effect 57's switch count
                e = json.loads(line)
                if e["id"] == 57:
                    frames.update(f for _, f in rom_deff57.frames(int(e["args"].get("value", 0) or 0), flips=116))
                elif e["id"] == 42:                    # deff_42 (0x01029fd8): rspin_last / rspin_total, the first page of the 0x5d-tick cycle
                    frames.add(rom_deff83.frames42(int(e["args"].get("last", 0) or 0), int(e["args"].get("total", 0) or 0))[0][1])
                elif e["id"] == 95:
                    frames.update(f for _, f in rom_deff95.frames(int(e["args"].get("timer", 0) or 0), int(e["args"].get("value", 0) or 0)))
                continue
            if '"deff_args"' not in line:
                continue
            e = json.loads(line)
            a, i = e["args"], e["id"]
            n = lambda k: int(a.get(k, 0) or 0)  # noqa: E731
            if i == 55:
                b, af = a.get("before", (0, 0)), a.get("after", (0, 0))
                fs = rom_deff55.frames([b[0], b[1], af[0], af[1], n("flags"), n("more")])
            elif i == 83:
                fs = rom_deff83.frames83([n("more"), n("mask")])
            elif i == 139:
                fs = rom_deff139.frames(n("value"))
            elif i == 138:
                fs = rom_deff138.frames(n("points"), n("count"), n("jackpot"), str(a.get("named", "") or ""))
            elif i in (58, 59):
                fs = rom_deff58.frames(i, [n("value")])
            elif i == 60:
                fs = rom_deff60.frames([n("value"), n("more")])
            elif i == 94:
                fs = rom_deff94.frames(n("value"))
            elif i == 108:
                fs = rom_deff108.frames(int(a.get("clip", a.get("variant", 0)) or 0) % 4, n("left"))
            elif i == 38:
                fs = rom_deff38.frames(n("winners"), n("number"))
            elif i == 2:
                fs = rom_deff2.frames(int(a.get("volume", 0x28) or 0))
            elif i == 96:
                fs = [f for c in range(rom_deff96.PICTURES)       # the background picture counter (RAM 0x3b92c) goes on from the last run: every start value
                      for f in rom_deff96.frames(n("timer"), n("value"), [(n("k") * 1000, tuple(a.get("rnd", (0, 0, 0))), 0)], c)]
            elif i == 42:
                fs = rom_deff83.frames42(n("last"), n("total"))[:1]
            else:
                continue
            frames.update(f for _, f in fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
