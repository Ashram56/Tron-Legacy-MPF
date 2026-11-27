"""deff_57 (0x01005524): the SWITCHES counter of End of Line / Daft Punk, drawn the way the ROM does.

Endless loop: for the 29 images 0x1fd7-0x1ff3 in turn, one flip each of 6 ticks (FUN_010241a0(6, 0)): the page is cleared, the image is copied at
x 0x29 y 0 (FUN_0002b378, no palette), and on the flips whose counter (which runs on over the loop) has bit 1 clear the text of message 0x6dd,
"SWITCHES=%,02lu", with the value RAM 0x3ae00 reads, in font 3 centred on x 0x54 at row 0x1f (FUN_00028d5c).
"""
from . import dmd_engine as E

IMAGES = range(0x1fd7, 0x1ff4)
TICKS = 6
MSG_6DD = "SWITCHES=%s"                      # "%,02lu": decimal with a comma between thousands, at least 2 digits (FUN_00035fb0)


def fmt(v):
    return "{:,}".format(v) if v >= 1000 else "%02d" % v


def frames(value, flips=60):
    out = []
    c = 0
    while len(out) < flips:
        for n in IMAGES:
            if len(out) >= flips:
                break
            p = E.Page()
            p.blit(n, 0x29, 0)
            if c & 2 == 0:
                p.text(MSG_6DD % fmt(value), 3, 0x54, 0x1f, 2)
            out.append((len(out) * TICKS, E.mix(bytes([0xff]) * (E.W * E.H), p.b)))
            c += 1
    return out
