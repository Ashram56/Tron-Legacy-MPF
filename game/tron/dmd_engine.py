"""The ROM's DMD drawing primitives, ported from the decompile, and the effect programs built on them (docs/dmd_engine.md).

An effect program (rom_deff_XX.py) is a port of the ROM's deff routine: it draws with these primitives from the state the game keeps
(the deff task's parameter bytes, RAM values the routine reads), flip by flip. scripts/conform/engine_check.py runs the ROM code in Unicorn
and compares every flip of the program to it, so a primitive or a program that differs from the ROM is found by a frame, not by a look.

Page model (CPU_BOARD_IO.md 3.2; DMD page = 128 x 32 bytes, row major): a byte is low nibble = dot level 0-15, high nibble = mask; the
display shows (bg & mask) | (fg & ~mask) of the two pages it is given, so 0xff is "transparent" in a foreground page.
Primitives and their ROM addresses:
- page_clear      FUN_00027274 (0x27274): the draw page (RAM 0x3d52c) filled with 0;
- blit            FUN_0002b378 / FUN_0002b424 (0x2b378 / 0x2b424) through the type table at 0x40d8638, type 0 handlers
                  FUN_00029754 (copy), FUN_000298b8 (palette), FUN_00029a20 (copy, skip a key byte), FUN_00029b7c (palette, skip a key);
                  an image is w x h bytes after a 13 byte header (w at +8, h at +10), a byte below 0x10 is a level, 0xff transparent;
- pal_new         FUN_0002b554 (0x2b554): the identity table 0..15;  pal_set  FUN_0002b56c (0x2b56c): entries lo..hi (<= 15) set to a value;
- text            FUN_00028ca8 / FUN_00028d5c (text_draw_msg / text_printf_msg): ROM font, flags 2 centred on x, baseline row y.
"""
import io
import os
import zipfile

W, H = 128, 32
TRANSPARENT = 0xff

_ZIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "mpf_package", "media", "rom_images_all.zip")
_IMAGES = {}


def image(n):
    """ROM image n as (w, h, bytes): level 0-15 per dot, 0xff transparent (the type 0 image bytes, read back from the decoded PNG)."""
    if n not in _IMAGES:
        from PIL import Image
        with zipfile.ZipFile(_ZIP) as z:
            im = Image.open(io.BytesIO(z.read("%04d.png" % n))).convert("RGBA")
        px = im.load()
        w, h = im.size
        data = bytearray()
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                data.append(TRANSPARENT if a == 0 else (g + 8) // 17)
        _IMAGES[n] = (w, h, bytes(data))
    return _IMAGES[n]


def pal_new():
    return list(range(16))


def pal_set(pal, value, lo, hi):
    for i in range(lo, min(hi, 15) + 1):
        pal[i] = value


class Page:
    def __init__(self, fill=0):
        self.b = bytearray([fill]) * (W * H)
        self.items = []                         # the draw list the primitives made, in order (tron/service_screen.gd items: i, t, ...)
        self._rec = True

    def clear(self, v=0):                       # FUN_00027274
        self.b[:] = bytes([v]) * (W * H)

    def blit(self, n, x, y, pal=None, key=None):
        """FUN_0002b378 / FUN_0002b424, type 0 handlers: clipped to the page; pal maps a level (below 0x10) to a byte (else 0xff);
        a byte equal to key is not written (FUN_00029a20 / FUN_00029b7c), with no key it is (FUN_00029754 / FUN_000298b8)."""
        w, h, d = image(n)
        if self._rec:
            it = {"i": n, "x": x, "y": y}
            if pal is not None and pal != list(range(16)):
                it["m"] = list(pal)             # the palette: tron/dmd_effect.gd maps the image's levels through it
            self.items.append(it)
        for iy in range(h):
            yy = y + iy
            if not 0 <= yy < H:
                continue
            for ix in range(w):
                xx = x + ix
                if not 0 <= xx < W:
                    continue
                v = d[iy * w + ix]
                if pal is not None:
                    v = pal[v] if v < 0x10 else 0xff
                if key is not None and v == key:
                    continue
                self.b[yy * W + xx] = v

    def fill(self, x0, y0, x1, y1, v):
        """FUN_0002746c / FUN_000274c0: the rectangle x0..x1, y0..y1 (inclusive, clipped to the page) set to v."""
        if self._rec:
            self.items.append({"r": [x0, y0, x1, y1], "v": v})
        for y in range(max(y0, 0), min(y1, H - 1) + 1):
            for x in range(max(x0, 0), min(x1, W - 1) + 1):
                self.b[y * W + x] = v

    def width(self, n):                         # FUN_0002b094 (image width, +8)
        return image(n)[0]


def mix(fg, bg):
    """The display mixer: mask = fg >> 4; (bg & mask) | (fg & ~mask), low 4 bits."""
    return bytes((((b & (f >> 4)) | (f & ~(f >> 4))) & 15) for f, b in zip(fg, bg))


# --- text: FUN_00028f74 (text_draw_str), width FUN_00028a74; fonts as the ROM's font table (game/fonts/fonts.json, scripts/gen_fonts.py) ---
def _fonts():
    from . import rom_draw
    return rom_draw.fonts()


def text_width(font, s):
    """FUN_00028a74: the span from the leftmost to the rightmost dot extent of the glyph boxes (xoff first, then width; spacing after each glyph)."""
    m = _fonts()[font]
    pos = lo = hi = 0
    for c in s:
        g = m["glyphs"].get(c)
        if g is None:
            continue
        pos += g["xoff"]
        if pos < lo:
            lo = pos
        if pos > hi:
            hi = pos
        pos += g["w"]
        if pos < lo:
            lo = pos
        if pos > hi:
            hi = pos
        pos += m["spacing"]
    return hi - lo


def _text(self, s, font, x, y, flags=2, pal=None):
    """FUN_00028f74: flags 2 centres on x (x - width / 2), 4 puts the right edge at x (x + 1 - width). Each glyph is an image blitted at
    (x + xoff, y - h + below + 1); a font with the outline flag blits keyed on 0xff (FUN_0002b2a0), else plain (FUN_0002b194)."""
    m = _fonts()[font]
    x0 = x
    if flags & 2:
        x -= text_width(font, s) >> 1
    elif flags & 4:
        x = x + 1 - text_width(font, s)
    if self._rec:
        it = {"t": s, "f": font, "x": x0, "y": y, "a": flags}
        if pal is not None and pal[15] != 15:
            it["l"] = pal[15]
        self.items.append(it)
    self._rec = False
    for c in s:
        g = m["glyphs"].get(c)
        if g is None:
            continue
        self.blit(g["image"], x + g["xoff"], y - g["h"] + g["below"] + 1, pal, 0xff if m["outline"] else None)
        x += g["w"] + m["spacing"] + g["xoff"]
    self._rec = True


Page.text = _text
