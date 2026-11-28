"""deff_60 (0x01005d44): an award on the Daft Punk / End of Line film (the value, and the balls still to earn).

Task: +0x30 the value (printed "%,02lu", font 18), +0x34 the balls still needed (0: "BALL ADDED"). 21 flips of 6 ticks (FUN_010241a0(6, 0)); each: the page
cleared, image 0x1fd7 at (0x29, 0) through palette A (levels 2-15 -> 1: FUN_0002b378 with a palette, FUN_000298b8), the value on row 0x12 (row 0xf
when balls are still needed) in plain levels on even flips and through palette B (levels 1-15 -> 0) on odd ones, then message 0x6e2 (font 33, row 0x1a)
or "%u MORE FOR" 0x6e0 (row 0x16) and "ADD-A-BALL" 0x6e1 (row 0x1d). Then FUN_01024460(10, 0x20): ten flips of the panel only.
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

FLIPS = 0x15
TICKS = 6


def pages(args):
    value, more = (list(args) + [0, 0])[:2]
    pal_a = E.pal_new()
    E.pal_set(pal_a, 1, 2, 0xf)
    pal_b = E.pal_new()
    E.pal_set(pal_b, 0, 1, 0xf)
    out = []
    for k in range(FLIPS):
        p = E.Page()
        p.blit(0x1fd7, 0x29, 0, pal_a)
        pal = pal_b if k & 1 else None
        if more == 0:
            p.text(fmt(value), 18, 0x54, 0x12, 2, pal)
            p.text("BALL ADDED", 33, 0x54, 0x1a, 2)
        else:
            p.text(fmt(value), 18, 0x54, 0xf, 2, pal)
            p.text("%u MORE FOR" % more, 33, 0x54, 0x16, 2)
            p.text("ADD-A-BALL", 33, 0x54, 0x1d, 2)
        out.append((k * TICKS, p))
    out.append((FLIPS * TICKS, E.Page()))
    return out


def frames(args):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(args)]


def draws(args):
    return [(t, p.items) for t, p in pages(args)]
