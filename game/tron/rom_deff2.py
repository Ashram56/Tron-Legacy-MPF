"""deff_002_use_to_adjust_volume (0x0103815c): the volume display, drawn from the master volume.

0x34 flips of 6 ticks. Each: the page filled with 0xff (FUN_0002738c, transparent), image 0xce at (0, 0x13) (the dim bar, on the background page), image 0xcf (the
lit bar, keyed on 0xff over it) at (volume x 2 - 0x7e, 0x10), message 0x97 "USE -/+ TO ADJUST VOLUME" (text_draw_msg_fit, font list {2}, x 0x40, row 0x1f) and
message 0x96 "VOLUME %d" (font 0xc, x 0x40, row 10). The volume is FUN_0002d3d0 (NVRAM 0x02110250, 0..0x3f), read every flip.
"""
from . import dmd_engine as E

FLIPS = 0x34
TICKS = 6


def pages(volume):
    out = []
    for k in range(FLIPS):
        p = E.Page(0xff)
        p.blit(0xce, 0, 0x13)
        p.blit(0xcf, volume * 2 - 0x7e, 0x10, None, 0xff)
        p.text("USE -/+ TO ADJUST VOLUME", 2, 0x40, 0x1f, 2)
        p.text("VOLUME %d" % volume, 0xc, 0x40, 10, 2)
        out.append((k * TICKS, p))
    out.append((FLIPS * TICKS, E.Page()))
    return out


def draws(volume):
    return [(t, p.items) for t, p in pages(volume)]


def frames(volume):
    """The shown frames: the transparent dots of the foreground page show the background page, black (cleared) from the second flip on;
    the first flip shows the page as the allocator left it (all 0xff), which is not a picture and is drawn black too."""
    return [(t, E.mix(p.b, bytes(E.W * E.H))) for t, p in pages(volume)]
