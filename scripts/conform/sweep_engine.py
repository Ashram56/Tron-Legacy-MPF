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
from tron import rom_deff55, rom_deff58, rom_deff60, rom_deff83, rom_deff138  # noqa: E402


def main(out, *logs):
    frames = set()
    for p in logs:
        for line in open(p):
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
            elif i == 138:
                fs = rom_deff138.frames(n("points"), n("count"), n("jackpot"), str(a.get("named", "") or ""))
            elif i in (58, 59):
                fs = rom_deff58.frames(i, [n("value")])
            elif i == 60:
                fs = rom_deff60.frames([n("value"), n("more")])
            else:
                continue
            frames.update(f for _, f in fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(*sys.argv[1:])
