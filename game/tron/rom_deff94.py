"""deff_94 (0x01032510, Zuse fast scoring intro): task +0x30 the value (zfs_value).

24 flips of 4 ticks (deff_status_frames(4, 0)); on those with bit 1 set (k & 2) the four pictures 0xa34, 0xa33, 0xa31, 0xa2c at x 0x2a, 0x3f, 0x54, 0x69, row 1 (table 0x040d6fb0)
and "FAST SCORING" 0x5fd (font 0x22, centred 0x54, row 0x1e), the others blank; then 43 flips of 3 ticks of FUN_010323d0: "ALL TARGETS" 0x5fe (font 10, row 8) and
"%,02lu POINTS" 0x600 (row 0x1e) in the palette that sends level 15 to 4, "SCORE" 0x5ff (font 0x11, row 0x15) plain; then deff_hold_frames(1, 0x20): the body blank.
The fonts are the ones the language 0 tables select (FUN_00028c1c on 0x040d6f68 / 0x040d6f6c, 0x040d6f8c): read off the ROM code's calls (deff_trace.py 94).
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

TICKS = 4
FLIPS = 24
HOLD_FLIPS = 43
HOLD_TICKS = 3
PICTURES = ((0xa34, 0x2a), (0xa33, 0x3f), (0xa31, 0x54), (0xa2c, 0x69))


def pages(value):
    pal = E.pal_new()
    E.pal_set(pal, 4, 15, 15)
    out = []
    for k in range(FLIPS):
        p = E.Page()
        if k & 2:
            for img, x in PICTURES:
                p.blit(img, x, 1, None, 0xff)
            p.text("FAST SCORING", 0x22, 0x54, 0x1e, 2)
        out.append((k * TICKS, p))
    t = FLIPS * TICKS
    for j in range(HOLD_FLIPS):
        p = E.Page()
        p.text("ALL TARGETS", 10, 0x54, 8, 2, pal)
        p.text("SCORE", 0x11, 0x54, 0x15, 2)
        p.text("%s POINTS" % fmt(value), 10, 0x54, 0x1e, 2, pal)
        out.append((t + j * HOLD_TICKS, p))
    out.append((t + HOLD_FLIPS * HOLD_TICKS, E.Page()))
    return out


def frames(value):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(value)]


def draws(value):
    return [(t, p.items) for t, p in pages(value)]
