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


# FUN_010323d0's lead-in, FUN_00027acc(0xc) = the handler 0x0102b980 [table 0x040e1b60]: ten stages of 2 ticks, each a copy of rows of 87 columns (x 0x29-0x7f) into
# cleared pages: stages 0-4 from the pages shown (blank: the oracle's body is empty from tick 96, the lead-in ends on a cleared page), stages 5-9 from the new ones (ALL TARGETS). Records (source row, destination row, height) of
# the stage tables at 0x040d3a18 (old, record lists 0x040d3a68, 0x040d3a80, 0x040d3ab8, 0x040d3b30, 0x040d3b70) and 0x040d3a40 (new, 0x040d3b80, 0x040d3bc0,
# 0x040d3c38, 0x040d3c70, 0x040d3c88); the ROM stores row x 16 as u16 and the height as a byte.
SQUEEZE_TICKS = 2
SQUEEZE_OLD = (((0, 1, 8), (9, 9, 15), (25, 24, 7)),
               ((0, 3, 4), (5, 7, 3), (9, 10, 3), (13, 13, 7), (21, 20, 3), (25, 23, 3), (29, 26, 3)),
               ((0, 7, 2), (3, 9, 1), (5, 10, 1), (7, 11, 1), (9, 12, 1), (11, 13, 1), (13, 14, 1), (15, 15, 1), (17, 16, 1), (19, 17, 1),
                (21, 18, 1), (23, 19, 1), (25, 20, 1), (27, 21, 2), (30, 23, 2)),
               ((0, 12, 1), (3, 13, 1), (7, 14, 1), (11, 15, 1), (17, 16, 1), (21, 17, 1), (25, 18, 1), (31, 19, 1)),
               ((0, 15, 1), (31, 16, 1)))
SQUEEZE_NEW = (SQUEEZE_OLD[3], SQUEEZE_OLD[2], SQUEEZE_OLD[1], SQUEEZE_OLD[0], ((0, 0, 32),))
BODY_X, BODY_W = 0x29, 0x57


def squeeze(old, new):
    """The ten stage pages between two pages (level arrays of 128 x 32)."""
    out = []
    for stage, (src, records) in enumerate([(old, r) for r in SQUEEZE_OLD] + [(new, r) for r in SQUEEZE_NEW]):
        p = E.Page()
        for s_row, d_row, h in records:
            levels = []
            for iy in range(h):
                base = (s_row + iy) * E.W + BODY_X
                levels += list(src[base:base + BODY_W])
            p.bitmap(BODY_X, d_row, BODY_W, h, levels)
        out.append(p)
    return out


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

    def hold_page():
        p = E.Page()
        p.text("ALL TARGETS", 10, 0x54, 8, 2, pal)
        p.text("SCORE", 0x11, 0x54, 0x15, 2)
        p.text("%s POINTS" % fmt(value), 10, 0x54, 0x1e, 2, pal)
        return p
    for stage, p in enumerate(squeeze(E.Page().b, hold_page().b)):
        out.append((t + stage * SQUEEZE_TICKS, p))
    t += 10 * SQUEEZE_TICKS
    for j in range(HOLD_FLIPS):
        out.append((t + j * HOLD_TICKS, hold_page()))
    out.append((t + HOLD_FLIPS * HOLD_TICKS, E.Page()))
    return out


def frames(value):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(value)]


def draws(value):
    return [(t, p.items) for t, p in pages(value)]
