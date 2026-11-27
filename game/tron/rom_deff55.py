"""deff_55 (0x0100461c): the letters of EXTRA BALL / MULTIBALL, drawn the way the ROM does; the task bytes are the effect's arguments.

Task bytes (set by the code that starts the effect): +0x30 / +0x34 letters lit before (row 1 / row 2), +0x38 / +0x3c lit after, +0x40 flags,
+0x44 a count. Images: row 1 = ROM 0x40d2588 (4 letters), row 2 = 0x40d2598; each flip (40 of them, 3 ticks each) the ROM clears the page,
draws every letter at the next x (the row centred on 0x54, 1 dot between letters) with palette 1 (dim) unless it is solid:
solid if index < before, or index < after and the flip number is even.
"""
from . import dmd_engine as E

ROW1 = (0x9db, 0x9d8, 0x9dd, 0x9eb)
ROW2 = (0x9e7, 0x9ec, 0x9e5, 0x9e2)
FLIPS = 0x28
TICKS = 3


# message ids (text_draw_msg / text_printf_msg, FUN_0000a58c): English strings of rom_data/deffs/text_draws.csv
MSG = {0x6ce: "MULTIBALL", 0x6cf: "IS LIT", 0x6d0: "EXTRA BALL", 0x6d1: "IS LIT", 0x6d2: "MULTIBALL + E.B.", 0x6d3: "ARE LIT",
       0x6d4: "%u MORE TO", 0x6d5: "LIGHT MULTIBALL", 0x6d6: "LIGHT EX. BALL", 0x6d7: "LIGHT M.B. + E.B."}
FONT = 0x21


def _text(p, f, cnt):
    """The two text lines (0x01004924..0x01004a94), by the flag bits, centred on x 0x54 at rows 0x1a and 0x20."""
    def line(m, y, *a):
        p.text(MSG[m] % a if a else MSG[m], FONT, 0x54, y, 2)
    if f & 3 == 3:
        line(0x6d2, 0x1a); line(0x6d3, 0x20)
    elif f & 1:
        line(0x6d0, 0x1a); line(0x6d1, 0x20)
    elif f & 2:
        line(0x6ce, 0x1a); line(0x6cf, 0x20)
    else:
        line(0x6d4, 0x1a, cnt)
        if f & 0xc == 0xc:
            line(0x6d7, 0x20)
        elif f & 4:
            line(0x6d6, 0x20)
        elif f & 8:
            line(0x6d5, 0x20)


def frames(args):
    b1, b2, a1, a2, flags, cnt = (list(args) + [0] * 7)[:6]
    out = []
    pal = E.pal_new()
    E.pal_set(pal, 1, 2, 0xf)
    w1 = sum(E.image(n)[0] for n in ROW1)
    w2 = sum(E.image(n)[0] for n in ROW2)
    for k in range(FLIPS + 1):
        p = E.Page()
        for row, y, before, after, wsum in ((ROW1, -1, b1, a1, w1), (ROW2, 9, b2, a2, w2)):
            x = 0x54 - (wsum + 3) // 2
            for i, n in enumerate(row):
                solid = i < before or (i < after and k % 2 == 0)
                p.blit(n, x, y, None if solid else pal, 0xff)
                x += 1 + E.image(n)[0]
        _text(p, flags, cnt)
        out.append((k * TICKS, E.mix(bytes([0xff]) * (E.W * E.H), p.b)))
    # FUN_01024460(10, 0x20): ten frames that copy the page of RAM 0x3d528 (blank here) and redraw only the status panel (columns 0-40)
    out.append((FLIPS * TICKS + TICKS, bytes(E.W * E.H)))
    return out
