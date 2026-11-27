#!/usr/bin/env python3
"""Effects that read RAM the game changes while they run (deff_live events of the wall-clock trace) run in the ROM code with those values.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_live.py OUT.pkl EFFECT NAME.jsonl [NAME.jsonl ...]

Effect 141 (Portal Multiball, deff_141 0x0102ffa0): pm_phase 0x3b878 (screen), pm_super_value 0x3b854 (super), the next award
FUN_0102f5f4 = min(500000 + 50000 * sum of the seven shot counters 0x3b85c + 4 i, 1,500,000) (next).
"""
import json
import os
import pickle
import struct
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402


def ram_141(a):
    ram = {0x3b878: a["screen"], 0x3b854: a["super"]}
    ram.update({0x3b85c + 4 * i: 0 for i in range(7)})
    ram[0x3b85c] = max(0, (a["next"] - 500000) // 50000)
    return ram


def ram_47(a, discs=6, recogs=3):
    """Disc Multiball status (deff_47 0x01007f34): dmb_phase 0x3af04, disc count 0x3af10 (shots left = adj 68 - count, FUN_01007074; not drawn once the
    count passed it), recognizer count 0x3af14 (adj 69, FUN_010070b8), jackpot 0x3af18, super 0x3af1c. 6 and 3 are the factory values INSTALL FACTORY sets."""
    dl, rl = a.get("disc_left"), a.get("recog_left")
    return {0x3af04: a["screen"], 0x3af10: discs + 1 if dl is None else discs - dl, 0x3af14: recogs + 1 if rl is None else recogs - rl,
            0x3af18: a["jackpot"], 0x3af1c: a["super"]}


RAMS = {141: ram_141, 47: ram_47}
# Effects whose values are the task arguments (task + 0x30, +0x34, ...): the deff_args events. 140 (0x0102faec): total, sos_bonus (task + 0x34 != 0 prints
# SEA OF SIMULATION BONUS and the value).
TASK_ARGS = {140: lambda a: [a["total"], a["sos_bonus"], 0, 0],
             142: lambda a: [a["value"], a["count"], int(a["ball_added"]), 0],         # Portal awards: value in task + 0x30
             143: lambda a: [a["value"], 0, 0, 0], 144: lambda a: [a["value"], 0, 0, 0],
             145: lambda a: [a["total"], 0, 0, 0],
             103: lambda a: [a["value"], 0, 0, 0],
             # Multiball effects: the points/total are task + 0x30 (48 49 50 51 58 59 61 90 139) or + 0x38 (87 88 89); 60 has two rows; 83 and 26 read a byte
             48: lambda a: [a["points"], 0, 0, 0], 49: lambda a: [a["points"], 0, 0, 0], 50: lambda a: [a["points"], 0, 0, 0],
             51: lambda a: [a["total"], 0, 0, 0], 90: lambda a: [a["total"], 0, 0, 0],
             58: lambda a: [a["value"], 0, 0, 0], 59: lambda a: [a["value"], 0, 0, 0], 61: lambda a: [a["value"], 0, 0, 0],
             139: lambda a: [a["value"], 0, 0, 0], 60: lambda a: [a["value"], a["more"], 0, 0],
             83: lambda a: [a["more"], 0, 0, 0], 26: lambda a: [a["player"], 0, 0, 0], 112: lambda a: [a["award"], 0, 0, 0]}              # SKILL SHOT value


def clip_args(e, a):
    """Light Cycle jackpot films (deff_87 0x01019e74, 88, 89): task + 0x3c = the clip level (< 6), task + 0x40 = the clip, kept when it lies in the
    level's [first, last] (table 0x040d2ffc, 8 bytes a level) else the first; 88 and 89 take the clip of the level's table entry +4 and +6
    (jump table 0x040d3084). Points are task + 0x38. Every level and every clip of the level, as the ROM's caller may pick any."""
    rom = open(os.environ["TRON_ROM"], "rb").read()
    out = []
    for level in range(6):
        first, last = struct.unpack_from("<HH", rom, 0x40d2ffc - 0x4000000 + 8 * level)
        for clip in (range(first, last + 1) if e == 87 else (first,)):
            out.append([0, 0, a["points"], level, clip])
    return out


def count_args(e, a):
    """Effects that print a count the game does not log (deff_62 0x0101d3d8: "%d TO LIGHT QUORRA MULTIBALL", task + 0x30): 1 to 10."""
    return [[n, 0, 0, 0] for n in range(1, 11)]


EXPAND = {87: clip_args, 88: clip_args, 89: clip_args, 62: count_args}
ALWAYS = (62,)


def one(job):
    e, a = job
    sub = dict(G.RECIPES.get(e, {}))
    sub.setdefault("max_insns", 60000000)
    base = sub["ram"]() if callable(sub.get("ram")) else dict(sub.get("ram") or S.game())
    if e in RAMS:
        base.update(RAMS[e](dict(a)))
    sub.update(ram=base)
    if e in EXPAND:
        sub["args"] = list(dict(a)["args"])
    elif e in TASK_ARGS:
        sub["args"] = TASK_ARGS[e](dict(a))
    return [f for f, _ in G._run(e, G.recipe(e, sub))]


def main(out, e, *logs):
    e = int(e)
    states = set()
    for p in logs:
        for line in open(p):
            if '"ev": "deff_live"' in line or ('"ev": "deff_args"' in line and (e in TASK_ARGS or e in EXPAND)):
                ev = json.loads(line)
                if ev["id"] == e:
                    states.add(tuple(sorted(ev["args"].items())))
    if e in EXPAND:
        jobs = [(e, (("args", tuple(x)),)) for s in (sorted(states) or [()]) for x in EXPAND[e](e, dict(s))]
        jobs = sorted(set(jobs))
    else:
        jobs = [(e, s) for s in sorted(states)]
    frames = set()
    with Pool(int(os.environ.get("SWEEP_PROCS", 4))) as pool:
        for fs in pool.imap_unordered(one, jobs):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(jobs), len(frames))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
