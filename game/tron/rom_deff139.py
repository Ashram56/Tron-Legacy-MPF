"""deff_139 (0x01003eb0, "END OF LINE JACKPOT", the End of Line combo jackpot): task +0x30 the value ("%,02lu", font 36, row 0x1b).

31 flips of 3 ticks (deff_status_frames(3, 0)); each: the page cleared, image 0x1778 at (0x29, 0), "END OF LINE" 0x6b0 (font 33, centred 0x54, row 0xb), "JACKPOT"
0x6b1 (row 0x11), the value on even flips in plain levels and on odd ones through the palette levels 1-15 -> 0; then deff_hold_frames(10, 0x20): the body blank.
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

FLIPS = 0x1f
TICKS = 3


def pages(value):
    pal = E.pal_new()
    E.pal_set(pal, 0, 1, 0xf)
    out = []
    for k in range(FLIPS):
        p = E.Page()
        p.blit(0x1778, 0x29, 0)
        p.text("END OF LINE", 33, 0x54, 0xb, 2)
        p.text("JACKPOT", 33, 0x54, 0x11, 2)
        p.text(fmt(value), 36, 0x54, 0x1b, 2, pal if k & 1 else None)
        out.append((k * TICKS, p))
    out.append((FLIPS * TICKS, E.Page()))
    return out


def frames(value):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(value)]


def draws(value):
    return [(t, p.items) for t, p in pages(value)]
