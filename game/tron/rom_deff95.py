"""deff_95 (0x010327d8, Zuse fast scoring running): endless loop of flips of 3 ticks (deff_status_frames(3, 0)).

Each flip: the page cleared, image 0xaee + c at (0x29, 0) where c is the frame counter RAM 0x3b92c (FUN_010327a4 sets it to 0 above 0x2d, FUN_010327c0 adds 1 after each flip
and wraps to 0 above 0x2d: 46 pictures), the band x 0x29-0x7f rows 0x1a-0x1f filled with 0 (FUN_000274c0), the timer (RAM 0x3b8f0, "%u" 0x602, font 1) at the left (flag 1,
x 0x2a, row 6) and the right (flag 4, x 0x7f, row 6), and "ALL TARGETS=%,02lu" 0x603 (font 0, centred 0x55, row 0x1f) with the value (zfs_value).
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

TICKS = 3
PICTURES = 0x2e


def page(timer, value, counter):
    p = E.Page()
    p.blit(0xaee + counter, 0x29, 0)
    p.fill(0x29, 0x1a, 0x7f, 0x1f, 0)
    p.text("%u" % timer, 1, 0x2a, 6, 1)
    p.text("%u" % timer, 1, 0x7f, 6, 4)
    p.text("ALL TARGETS=%s" % fmt(value), 0, 0x55, 0x1f, 2)
    return p


def pages(timer, value, counter=0, flips=PICTURES):
    c = counter if counter < PICTURES else 0
    out = []
    for k in range(flips):
        out.append((k * TICKS, page(timer, value, c)))
        c = c + 1 if c + 1 < PICTURES else 0
    return out


def frames(timer, value, counter=0, flips=PICTURES):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(timer, value, counter, flips)]


def draws(timer, value, counter=0, flips=PICTURES):
    return [(t, p.items) for t, p in pages(timer, value, counter, flips)]
