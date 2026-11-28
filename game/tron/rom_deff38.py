"""deff_38 (0x0102cdd8, the match at the end of a game): 65 flips of 4 ticks, then the winners' flashes; the body (columns 41-127) as the ROM draws it.

Task arguments: +0x30 the winners' bitmask (bit p = player p won), +0x34 the match number. Each flip the plane (RAM 0x3d530) is filled 0xff, the bottom page cleared:
- flip n < 0x40: picture 0xe3f + n at (0x29, 0), key 0xff (bitmap_draw_masked, 0x0102cdd8);
- n < 0x18 the level of palette entry 15 is the byte n / 2 of 0x040d3cf8 (00-07, 0c-0f), kept after that;
- n < 0x1e: "MATCH" (msg 0x6b3, font 0x25 = DAT_040d3ce0[language 0], flag 4 = right edge x 0x7f, row font_height - 2 = 7);
- n == 0x40: the number, "%,02lu" (0x6b2, font 0x1e, centred 0x54, row 0x17).
The panel (columns 0-40: FUN_0102cc48) is the panel's. After the winners' awards (match_award, sounds), if there are winners: 0x19 flips (0..0x18, the test is on the next count < 0x180001) of 4 ticks (FUN_000279c4(4)),
the plane cleared to 0 and the number drawn when (flip & 2) == 0; then 0x7d ticks on the last page and the end.
"""
from . import dmd_engine as E

TICKS = 4
FLIPS = 0x41
LEVELS = (0, 1, 2, 3, 4, 5, 6, 7, 0x0c, 0x0d, 0x0e, 0x0f, 1, 2, 3, 4)   # 0x040d3cf8: only the first 12 are read (n >> 1 for n < 0x18)
NUMBER_FONT = 0x1e
MATCH_FONT = 0x25


def pages(winners, number):
    """[(tick, plane Page)]: the plane over a black page."""
    out = []
    lvl = 0
    for n in range(FLIPS):
        p = E.Page(0xff)
        if n < 0x40:
            p.blit(0xe3f + n, 0x29, 0, None, 0xff)
        if n < 0x18:
            lvl = LEVELS[n >> 1]
        pal = E.pal_new()
        pal[15] = lvl
        if n < 0x1e:
            p.text("MATCH", MATCH_FONT, 0x7f, 7, 4, pal)
        if n == 0x40:
            p.text("%02d" % number, NUMBER_FONT, 0x54, 0x17, 2, pal)
        out.append((n * TICKS, p))
    t = FLIPS * TICKS
    if winners:
        for n in range(0x19):
            p = E.Page(0)
            if n & 2 == 0:
                pal = E.pal_new()
                pal[15] = lvl
                p.text("%02d" % number, NUMBER_FONT, 0x54, 0x17, 2, pal)
            out.append((t + n * TICKS, p))
        t += 0x19 * TICKS
    return out, t


def frames(winners, number):
    pg, _ = pages(winners, number)
    return [(t, E.mix(p.b, bytes(E.W * E.H))) for t, p in pg]


def draws(winners, number):
    pg, t = pages(winners, number)
    return [(tt, p.items) for tt, p in pg] + [(t + 0x7d, [])]
