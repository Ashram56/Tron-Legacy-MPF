"""deff_138 (0x01003c30, "N WAY COMBO"): the Light Cycle combo award.

Task: +0x30 the points ("%,02lu"), +0x34 a table entry whose message (u16 at +8) names the combo (0: none), +0x38 the count ("%u", font 42 / 43 swapped every
2 flips, right edge at x 0x53, row 0x13). 41 flips of 3 ticks (FUN_010241a0(3, 0)); each: "WAY" 0x6a1 (font 33, flags 1, x 0x55, row 6), "COMBO" 0x6a2 (row 0xc), the
points (row 0x12), the named combo (font 0, centred on 0x54, row 0x18), "JACKPOT=%,02lu" 0x6a3 (font 0, row 0x1e) with the player's jackpot (RAM 0x2111608 + 4 *
(player - 1)); FUN_01024460(10, 0x20) ends it.
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

FLIPS = 0x29
TICKS = 3


def pages(points, count, jackpot, named=""):
    out = []
    for k in range(FLIPS):
        p = E.Page()
        p.text("%u" % count, 0x2b if k & 2 else 0x2a, 0x53, 0x13, 4)
        p.text("WAY", 33, 0x55, 6, 1)
        p.text("COMBO", 33, 0x55, 0xc, 1)
        p.text(fmt(points), 33, 0x55, 0x12, 1)
        if named:
            p.text(named, 0, 0x54, 0x18, 2)
        p.text("JACKPOT=%s" % fmt(jackpot), 0, 0x54, 0x1e, 2)
        out.append((k * TICKS, p))
    out.append((FLIPS * TICKS, E.Page()))
    return out


def frames(points, count, jackpot, named=""):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(points, count, jackpot, named)]


def draws(points, count, jackpot, named=""):
    return [(t, p.items) for t, p in pages(points, count, jackpot, named)]
