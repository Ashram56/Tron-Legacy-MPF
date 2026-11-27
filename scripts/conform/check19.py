#!/usr/bin/env python3
"""rom_deff19 (the score display program) against the ROM code in Unicorn: every flip, columns 41-127.

    TRON_ROM=trn_174h.bin python3 scripts/conform/check19.py SCORE BALL VALID [TICKS]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "assets", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "game"))
import deff_frames as F  # noqa: E402
import deff_state as S  # noqa: E402
import gen_code_dmd as G  # noqa: E402
from tron import dmd_engine as E, rom_deff19  # noqa: E402


def oracle(score, ball, valid, insns):
    r = G.recipe(19)
    ram = S.game(1, 1, ball, (score, 0, 0, 0))
    ram.update(S.credit(2, 0))
    if valid:
        ram[0x372e8] = 1
    snaps, ticks = F.frames(19, args=r["args"], ram=ram, init=r["init"], max_insns=insns, counters=(0x21117f4,))
    return [(t, E.mix(fg, bg)) for (r0, r1, fg, bg), t in zip(snaps, ticks)]


REPLAY = os.environ.get("REPLAY", "")


def main(score, ball, valid, insns=3000000):
    ora = oracle(score, ball, valid, insns)
    ok = bad = 0
    first = None
    for t, f in ora:
        mine = E.mix(bytes([0xff]) * (E.W * E.H), rom_deff19.page(score, ball, "CREDITS 0", valid, t, t, replay=REPLAY).b)
        a = bytes(f[y * E.W + x] for y in range(E.H) for x in range(41, E.W))
        b = bytes(mine[y * E.W + x] for y in range(E.H) for x in range(41, E.W))
        if a == b:
            ok += 1
        else:
            bad += 1
            first = first or t
    print("score", score, "ball", ball, "valid", valid, "->", ok, "of", ok + bad, "first mismatch tick", first, "ticks", [t for t, _ in ora][:6])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]), int(a[1]), int(a[2]), int(a[3]) if len(a) > 3 else 3000000)
