"""deff_83 (0x01018ba0, "N MORE TO LIGHT LIGHT CYCLE", the Light Cycle multiball's shots to go) and deff_42 (0x01029fd8, RIGHT SPINNER = ...), drawn like the ROM.

deff_83: task + 0x30 (byte) = the count, + 0x34 = mask (bits 0-2 clear: the cycle runs right to left from x 0x7d at 8 dots a flip, images 0xf65-0xf67; else left to
right from x -0x49, images 0xf68-0xf6a). 0x3b1 flips of 2 ticks (FUN_01024230(2, 0)); each fills the page with 0xff (FUN_00027400: the ROM draws this effect on
the foreground page, the picture under it is the background page), prints "%d MORE" (message 0x5a9, font 39, row 10; through palette B, levels 1-15 -> 0, while
bit 2 of the flip number is set), "TO LIGHT" (0x5aa, first font of the list 0x040d302c that fits 85 dots, row 0x14, FUN_00028e48 / FUN_00028c6c), "LIGHT CYCLE"
(0x5bc, font 0, row 0x1b) and the next of three cycle images (keyed on 0xff) at x = step * flip + start, y 0. FUN_01024460(1, 0x20) ends it.

deff_42: waits for rspin_last (RAM 0x3b71c) != 0; each time draws "RIGHT SPINNER =" (0x545, font 2, row 7), the last value ("%,02lu" 0x546, font 2, row 0xf) and the
total (RAM 0x3b720, font 15, row 0x1c) in one 1 tick flip, clears rspin_last, and ends 0x5d ticks after the last spin (FUN_01024460(10, 0x20): panel only).
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

FLIPS = 0x3b1
TICKS = 2
FIT_FONTS = (39, 38, 37, 36, 34, 33)                  # list at 0x040d302c, 0-terminated


def fit_font(s, width=85):
    for f in FIT_FONTS:
        if E.text_width(f, s) <= width:
            return f
    return 0                                           # FUN_00028c6c returns the terminator


def pages83(args, flips=FLIPS):
    more, mask = (list(args) + [0, 0])[:2]
    start, step, base = (0x7d, -8, 0xf65) if mask & 7 == 0 else (-0x49, 8, 0xf68)
    pal = E.pal_new()
    E.pal_set(pal, 0, 1, 0xf)
    out = []
    n = 0
    for c in range(flips):
        p = E.Page(0xff)
        p.text("%d MORE" % (more & 0xff), 39, 0x54, 10, 2, pal if c & 4 else None)
        p.text("TO LIGHT", fit_font("TO LIGHT"), 0x54, 0x14, 2)
        p.text("LIGHT CYCLE", 0, 0x54, 0x1b, 2)
        p.blit(base + n, step * c + start, 0, None, 0xff)
        n = (n + 1) % 3
        out.append((c * TICKS, p))
    out.append((flips * TICKS, E.Page()))
    return out


def frames83(args, flips=FLIPS):
    return [(t, E.mix(p.b, bytes(E.W * E.H))) for t, p in pages83(args, flips)]


def draws83(args):
    return [(t, p.items) for t, p in pages83(args)]


def pages42(last, total):
    p = E.Page()
    p.text("RIGHT SPINNER =", 2, 0x54, 7, 2)
    p.text(fmt(last), 2, 0x54, 0xf, 2)
    p.text(fmt(total), 15, 0x54, 0x1c, 2)
    return [(0, p), (0x5d, E.Page())]


def frames42(last, total):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages42(last, total)]
