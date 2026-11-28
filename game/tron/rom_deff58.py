"""deff_58 (0x010057e0, JACKPOT) and deff_59 (0x01005a48, DOUBLE JACKPOT): the award value of the Daft Punk / End of Line multiball over the dimmed film.

Both: 21 flips of 6 ticks; each clears the page, draws image 0x1fd7 at (0x29, 0) through palette A (levels 2-15 -> 1), the message (0x6de JACKPOT / 0x6df
DOUBLE JACKPOT; font 33, row 0xb), then the value (task + 0x30, "%,02lu", font 18, row 0x1a) in plain levels on even flips and through palette B
(levels 1-15 -> 0) on odd ones; FUN_01024460(10, 0x20) ends it (panel only).
"""
from . import dmd_engine as E
from .rom_deff57 import fmt

FLIPS = 0x15
TICKS = 6
MSG = {58: "JACKPOT", 59: "DOUBLE JACKPOT"}              # messages 0x6de, 0x6df


def pages(deff, args):
    value = (list(args) + [0])[0]
    pal_a = E.pal_new()
    E.pal_set(pal_a, 1, 2, 0xf)
    pal_b = E.pal_new()
    E.pal_set(pal_b, 0, 1, 0xf)
    out = []
    for k in range(FLIPS):
        p = E.Page()
        p.blit(0x1fd7, 0x29, 0, pal_a)
        p.text(MSG[deff], 33, 0x54, 0xb, 2)
        p.text(fmt(value), 18, 0x54, 0x1a, 2, pal_b if k & 1 else None)
        out.append((k * TICKS, p))
    out.append((FLIPS * TICKS, E.Page()))
    return out


def frames(deff, args):
    return [(t, E.mix(bytes([0xff]) * (E.W * E.H), p.b)) for t, p in pages(deff, args)]


def draws(deff, args):
    return [(t, p.items) for t, p in pages(deff, args)]
