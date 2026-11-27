"""deff_108 (0x010209b0, Recognizer / disc hit: "N MORE TO ACCESS DISC"): one of four film variants, chosen by random_below(4) (0x10209d8).

The variant routines FUN_01020388 / 01020510 / 01020698 / 01020820 are the same loop with other numbers (table VARIANTS):
a flip per iteration i, FLIP_TICKS ticks (FUN_01024378 n) long, i = 0 .. LAST: the picture page filled with 0xff (transparent, it lies over the other) and the text page cleared,
the film picture FIRST + i (only while i < 0x1e) blitted on the picture page at (X, 0), the messages on the text page 0x62d "%u MORE" (font 0x27,
centred on 0x54, row 10, the count = the task's byte +0x30; blink: the palette of all zeros, text black, when bit 1 of i is set), 0x62e "TO ACCESS" (row 0x14)
and 0x62f "DISC" (row 0x1e). At i = SPEECH_AT the ROM plays snd 0x0d1 (count < 3) or the speech task FUN_0101c198 (the game side plays it).
The font is the language table entry (FUN_0000a3b4 = 0, English) at 0x040d32c4 = 0x27.
"""
from . import dmd_engine as E

FONT = 0x27
# variant: (first picture, x of the picture, ticks a flip lasts, last i, i of the speech)
VARIANTS = (
    (0xa7b, 0x00, 3, 0x1e, 0x14),
    (0xa99, 0x00, 3, 0x1e, 0x14),
    (0xa3f, 0x29, 2, 0x36, 0x1e),
    (0xa5d, 0x29, 2, 0x36, 0x1e),
)
PICTURES = 0x1e


def ticks(variant):
    return VARIANTS[variant][2]


def pages(variant, more):
    first, x, tk, last, _ = VARIANTS[variant]
    out = []
    for i in range(last + 1):
        txt = E.Page(0)
        pal = E.pal_new()
        if i & 2:
            E.pal_set(pal, 0, 0, 0xf)
        txt.text("%u MORE" % more, FONT, 0x54, 10, 2, pal if i & 2 else None)
        txt.text("TO ACCESS", FONT, 0x54, 0x14, 2)
        txt.text("DISC", FONT, 0x54, 0x1e, 2)
        img = E.Page(0xff)
        if i < PICTURES:
            img.blit(first + i, x, 0, None, 0x10)
        out.append((i * tk, txt, img))
    return out


def draws(variant, more):
    """The draw lists: the text page's items, then the picture page's, marked "o" (drawn over the status panel, which the ROM draws on the text page)."""
    return [(t, txt.items + [dict(it, o=1) for it in img.items]) for t, txt, img in pages(variant, more)]


def frames(variant, more):
    return [(t, E.mix(img.b, txt.b)) for t, txt, img in pages(variant, more)]
