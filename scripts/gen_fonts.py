#!/usr/bin/env python3
"""Rebuild the ROM's DMD fonts as BMFont files for Godot (1 px = 1 DMD dot).

The ROM draws text with text_draw_str (code 0x28f74): the font table (RAM 0x36f48, 20-byte entries)
gives per font a list of character ranges, a glyph table (8 bytes: image pointer, s16 x offset,
s16 y offset), the height and the spacing added after each glyph. A glyph is drawn with its bottom
on the text's baseline y (y - h + yoff + 1) and the pen moves by w + xoff + spacing. Flag 2 centres
the text on x (x - width/2), flag 4 right-aligns it (x + 1 - width).

The ROM file itself is not in the asset package; its images are (media/rom_images_all.zip). Each
font's glyphs are one image group there (the group's last image carries flag 2), and ROM font n is
the n-th such group (44 fonts, images 218-2602): fonts 0-18 are ' '..'Z' sets (5-14 px, plain and
black-outlined), 19-32 digit sets (',' and 0-9), 33-41 the Tron-style sets (',' 0-9 A-Z), 42-43 big
Tron digits. Characters are assigned by group layout (label_group); the one punctuation glyph a
few sets lack is found by a shape match against font 5. The font numbers, spacing and placement were
checked against the reference captures: 161 of the 198 static text draws found in the deff code are
pixel-exact in at least one captured frame (the others are not on screen in the captures), see
scripts/render_diff.py. Glyph x/y offsets and the font spacing are ROM data not in the images: the
rules below (bottom_offset, x_offset, SPACING, outline fonts -1, plain fonts +1) reproduce the captures.

Output (git-ignored): game/fonts/rom_font_NN.fnt + rom_font_NN.png, and game/fonts/fonts.json
(per font: image group, cap height, spacing, glyphs). For the HD display mode, game/fonts/hd/ holds the same
44 fonts as TrueType outlines traced from the dots (scripts/font_outline.py: rom_font_NN.ttf, the ROM's
advances exactly, so the text lands where the 128x32 layout puts it, sharp at any resolution) with a glow
atlas each (rom_font_NN_glow.fnt), and fonts_hd.json, the design (style, weight, width) and layers of each. Usage: .venv/bin/python scripts/gen_fonts.py
"""
import io
import json
import os
import zipfile

import fsutil  # Windows/OneDrive-safe folder wipes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ZIP = os.path.join(ROOT, "assets", "mpf_package", "media", "rom_images_all.zip")
OUT = os.path.join(ROOT, "game", "fonts")
TRANSPARENT = 255
ALPHABET = [chr(c) for c in range(0x20, 0x5b)]          # ' ' .. 'Z'
REFERENCE_GROUP = 515                                    # full ' '..'Z' font, 7 px


def load_images():
    """Returns (index, get) where get(i) is the image as a list of rows of levels (255 = clear)."""
    z = zipfile.ZipFile(ZIP)
    index = json.loads(z.read("index.json"))
    cache = {}

    def get(i):
        if i not in cache:
            from PIL import Image
            im = Image.open(io.BytesIO(z.read("%04d.png" % i))).convert("RGBA")
            w, h = im.size
            px = im.load()
            cache[i] = [[TRANSPARENT if px[x, y][3] == 0 else round(px[x, y][0] / 17) for x in range(w)]
                        for y in range(h)]
        return cache[i]
    return index, get


def groups(index):
    """Image groups (first, last): a group ends at an image with flag 2."""
    out, start = [], 0
    for e in index:
        if e["flags"] & 2:
            out.append((start, e["image"]))
            start = e["image"] + 1
    return out


def lit(img):
    return [[1 if 0 < v < TRANSPARENT else 0 for v in row] for row in img]


def feature(img, hmax):
    """Shape of a glyph: 6x8 coverage of its lit pixels' box plus its size against the font."""
    m = lit(img)
    h, w = len(m), len(m[0])
    ys = [y for y in range(h) if any(m[y])]
    xs = [x for x in range(w) if any(m[y][x] for y in range(h))]
    if not ys:
        return None
    y0, y1, x0, x1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    grid = []
    for gy in range(8):
        for gx in range(6):
            ya, yb = y0 + (y1 - y0) * gy / 8, y0 + (y1 - y0) * (gy + 1) / 8
            xa, xb = x0 + (x1 - x0) * gx / 6, x0 + (x1 - x0) * (gx + 1) / 6
            yi = min(int(ya), y1 - 1)
            xi = min(int(xa), x1 - 1)
            yj = max(yi + 1, int(-(-yb // 1)))
            xj = max(xi + 1, int(-(-xb // 1)))
            cells = [m[y][x] for y in range(yi, min(yj, y1)) for x in range(xi, min(xj, x1))]
            grid.append(sum(cells) / len(cells))
    return grid, (y1 - y0) / hmax, (x1 - x0) / hmax


def distance(a, b):
    if a is None or b is None:
        return 0.0 if a is b else 99.0
    return sum(abs(p - q) for p, q in zip(a[0], b[0])) / 12 + 3 * abs(a[1] - b[1]) + 1.5 * abs(a[2] - b[2])


def label_group(first, last, index, get, ref):
    """Characters of the group's glyphs, in image order (None for an extra glyph after 'Z')."""
    ids = list(range(first, last + 1))
    hmax = max(index[i]["h"] for i in ids)
    chars = []
    if not any(any(r) for r in lit(get(ids[0]))):         # blank first glyph: the space
        chars, ids = [" "], ids[1:]
    n = len(ids)
    digits = "0123456789"
    letters = ALPHABET[ALPHABET.index("A"):]
    if n >= 57:                                          # '!'..'Z', maybe one missing, maybe an extra
        extra = n == 59 or (n == 58 and index[ids[-1]]["h"] * 2 < hmax)
        n -= extra
        full = ALPHABET[1:]
        if n == len(full) - 1:                           # one punctuation glyph is missing: find it
            cost = []
            for k in range(ALPHABET.index("0")):
                cand = full[:k] + full[k + 1:]
                cost.append(sum(distance(feature(get(i), hmax), ref[c]) for i, c in zip(ids, cand[:16])))
            k = min(range(len(cost)), key=cost.__getitem__)
            full = full[:k] + full[k + 1:]
        return chars + full[:n] + ([None] if extra else [])
    if n == 10:
        return chars + list(digits)
    if n == 11:                                          # score fonts: comma and digits
        return chars + [","] + list(digits)
    if n == 41:
        return chars + list("'+,.") + list(digits) + [":"] + letters
    if n == 37:
        return chars + [","] + list(digits) + letters
    return None


def font_groups(index):
    """The image groups that are fonts: small glyphs, at least the 10 digits."""
    out = []
    for a, b in groups(index):
        ids = range(a, b + 1)
        if 10 <= b - a + 1 <= 64 and max(index[i]["w"] for i in ids) <= 24 and index[a]["h"] <= 26 \
                and all(index[i]["format"] == 0 for i in ids):
            out.append((a, b))
    return out


# Vertical placement of the glyphs shorter than the font's digits/capitals ("cap" height), as the
# reference captures show them: offset of the glyph's bottom row below the baseline row.
def bottom_offset(c, h, cap):
    if c in ",;":
        return 1                                         # comma and semicolon hang one row below
    if h >= cap:
        if c in "Q$" and h > cap:                        # Q's tail hangs, $ sticks out both ways
            return h - cap if c == "Q" else (h - cap) // 2
        return 0
    if c in "\"'`":
        return h - cap                                   # quotes sit at the top
    if c in "-+*=:<>~":
        return -((cap - h) // 2)                         # centred
    return 0


def is_outline(get, glyphs):
    """Outline fonts draw a black border around each glyph: no lit pixel on the left/right edge."""
    votes = []
    for c in "0123456789AEHMN":
        if c in glyphs:
            g = lit(get(glyphs[c]))
            votes.append(not any(r[0] or r[-1] for r in g))
    return sum(votes) * 2 > len(votes)


# Spacing the images do not tell, read off the reference captures:
# - the tron digit fonts (27-32, glyphs padded to the font height) draw their outlined digits with the
#   borders side by side (spacing 0; deff 38 match number "00", font 30);
# - the plain fonts draw the comma one dot to the left (glyph x offset -1: deff 25 bonus "50,000" in
#   font 15, deff 19 "REPLAY AT 20,000,000" in font 0).
SPACING = {27: 0, 28: 0, 29: 0, 30: 0, 31: 0, 32: 0}


def x_offset(c, outline):
    if c == "," and not outline:
        return -1
    return 0


def decode_all():
    """(index, get, fonts): fonts[n] is ROM font n (the n-th font image group in the ROM)."""
    index, get = load_images()
    ra, rb = [g for g in groups(index) if g[0] == REFERENCE_GROUP][0]
    rh = max(index[i]["h"] for i in range(ra, rb + 1))
    ref = {c: feature(get(i), rh) for c, i in zip(ALPHABET, range(ra, rb + 1))}
    fonts = []
    for a, b in font_groups(index):
        chars = label_group(a, b, index, get, ref)
        if chars is None:
            continue
        glyphs = {c: i for c, i in zip(chars, range(a, b + 1)) if c is not None}
        n = len(fonts)
        cap = index[glyphs["0"] if "0" in glyphs else glyphs["A"]]["h"]
        place = {c: bottom_offset(c, index[i]["h"], cap) for c, i in glyphs.items()}
        if "," in glyphs and all(v == TRANSPARENT for v in get(glyphs[","])[0]):
            place[","] = 0                               # comma padded with clear rows: drawn as is
        outline = is_outline(get, glyphs)
        fonts.append({"id": n, "group": a, "last": b, "cap": cap, "outline": outline,
                      "spacing": SPACING.get(n, -1 if outline else 1),
                      "ascent": max(index[i]["h"] - place[c] for c, i in glyphs.items()),
                      "descent": max(0, max(place.values())),
                      "glyphs": {c: {"image": i, "w": index[i]["w"], "h": index[i]["h"], "below": place[c],
                                     "xoff": x_offset(c, outline)}
                                 for c, i in glyphs.items()}})
    return index, get, fonts


def text_width(font, text):
    """Width the ROM gives the text (text_width): glyph widths plus the spacing between glyphs."""
    gs = [font["glyphs"][c] for c in text if c in font["glyphs"]]
    return sum(g["w"] + g["xoff"] + font["spacing"] for g in gs) - font["spacing"] if gs else 0


def text_left(font, text, x, flags):
    if flags & 2:
        return x - text_width(font, text) // 2
    if flags & 4:
        return x + 1 - text_width(font, text)
    return x


def render(get, font, text, x, y, flags, canvas):
    """Draws text like text_draw_str into canvas (32 rows of 128 levels); y is the baseline row."""
    x = text_left(font, text, x, flags)
    for c in text:
        g = font["glyphs"].get(c)
        if g is None:                                    # characters the font lacks are skipped
            continue
        img = get(g["image"])
        top = y + g["below"] - g["h"] + 1
        left = x + g["xoff"]
        for gy, row in enumerate(img):
            for gx, v in enumerate(row):
                if v != TRANSPARENT and 0 <= left + gx < 128 and 0 <= top + gy < 32:
                    canvas[top + gy][left + gx] = v
        x += g["w"] + g["xoff"] + font["spacing"]
    return canvas


def write_bmfont(font, get, out_dir):
    """rom_font_NN.fnt (BMFont text format) + rom_font_NN.png atlas, 1 px = 1 dot, levels as grey."""
    from PIL import Image
    name = "rom_font_%02d" % font["id"]
    glyphs = sorted(font["glyphs"].items(), key=lambda kv: ord(kv[0]))
    width = sum(g["w"] + 1 for _, g in glyphs) + 1
    height = max(g["h"] for _, g in glyphs) + 2
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = atlas.load()
    lines = []
    x = 1
    asc = font["ascent"]
    for c, g in glyphs:
        for gy, row in enumerate(get(g["image"])):
            for gx, v in enumerate(row):
                if v != TRANSPARENT:
                    px[x + gx, 1 + gy] = (v * 17, v * 17, v * 17, 255)
        lines.append("char id=%d x=%d y=1 width=%d height=%d xoffset=%d yoffset=%d xadvance=%d page=0 chnl=15"
                     % (ord(c), x, g["w"], g["h"], g["xoff"], asc - g["h"] + g["below"],
                        g["w"] + g["xoff"] + font["spacing"]))
        x += g["w"] + 1
    atlas.save(os.path.join(out_dir, name + ".png"))
    size = asc + font["descent"]
    head = ['info face="%s" size=%d bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 '
            'padding=0,0,0,0 spacing=0,0 outline=0' % (name, size),
            "common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=1 packed=0 alphaChnl=0 redChnl=0 "
            "greenChnl=0 blueChnl=0" % (size, asc, width, height),
            'page id=0 file="%s.png"' % name, "chars count=%d" % len(glyphs)]
    with open(os.path.join(out_dir, name + ".fnt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + lines) + "\n")
    return name


def design(font, get):
    """What the font looks like, for the HD font made from it: style (plain: text over its black cell;
    outlined: a black border around the strokes; tron: the game's outlined display face; digits: score
    digit sets; big tron digits: the shaded 20-dot digits), stroke weight in dots (lit dots per lit run
    across a row, on the digits and capitals) and width (mean glyph width / cap height: < 0.6 condensed)."""
    chars = [c for c in "0123456789ABCDEHMNOSTUWZ" if c in font["glyphs"]]
    runs = lit_dots = 0
    widths = []
    for c in chars:
        img = get(font["glyphs"][c]["image"])
        for row in img:
            on = [0 < v < TRANSPARENT and v >= 8 for v in row]
            lit_dots += sum(on)
            runs += sum(1 for i, v in enumerate(on) if v and (i == 0 or not on[i - 1]))
        widths.append(sum(1 for x in range(len(img[0])) if any(0 < r[x] < TRANSPARENT for r in img)))
    shades = sorted({v for c in font["glyphs"].values() for row in get(c["image"]) for v in row
                     if 0 < v < TRANSPARENT})
    n = len(font["glyphs"])
    style = ("big tron digits" if len(shades) > 1 else "tron" if n in (37, 38, 42) else
             "digits" if n <= 11 else "outlined" if font["outline"] else "plain")
    if style == "digits" and font["outline"]:
        style = "outlined digits"
    width = sum(widths) / len(widths) / font["cap"] if widths else 0
    return {"id": font["id"], "style": style, "cap": font["cap"], "outline": font["outline"],
            "weight": round(lit_dots / runs, 2) if runs else 0, "width": round(width, 2),
            "condensed": width < 0.6, "shades": len(shades)}


def build_hd(fonts, get, out_dir, processes=None):
    """game/fonts/hd/: the vector (TrueType) font and the glow atlas of every ROM font (scripts/font_outline.py)
    and fonts_hd.json (design and layers per font). Without fontTools the HD fonts are left out (the HD
    mode then shows the classic DMD) and False is returned."""
    try:
        import fontTools  # noqa: F401
    except ImportError:
        print("fonts: no fontTools (pip install fonttools, or run scripts/setup.py): no HD fonts")
        fsutil.remove_dir(out_dir)
        return False
    import font_outline
    fsutil.clear_dir(out_dir)
    jobs = [(f, out_dir) for f in fonts]
    if processes == 1:
        entries = [font_outline.build_font(j) for j in jobs]
    else:
        import multiprocessing
        with multiprocessing.Pool(processes or os.cpu_count() or 2) as pool:
            entries = pool.map(font_outline.build_font, jobs, chunksize=1)
    with open(os.path.join(out_dir, "fonts_hd.json"), "w", encoding="utf-8", newline="\n") as fp:
        json.dump({"vector": True, "version": font_outline.VERSION,
                   "fonts": [dict(design(f, get), **e) for f, e in zip(fonts, entries)]},
                  fp, indent=0, sort_keys=True)
    return True


def build(out_dir=OUT, hd=True):
    """Writes every ROM font and fonts.json (metrics the slides and the render check use), and with hd the
    HD fonts in out_dir/hd."""
    index, get, fonts = decode_all()
    os.makedirs(out_dir, exist_ok=True)
    for f in fonts:
        write_bmfont(f, get, out_dir)
    with open(os.path.join(out_dir, "fonts.json"), "w", encoding="utf-8", newline="\n") as fp:
        json.dump({"fonts": fonts}, fp, indent=0, sort_keys=True)
    if hd:
        build_hd(fonts, get, os.path.join(out_dir, "hd"))
    return fonts


def main():
    fonts = build()
    print("fonts: %d ROM fonts in game/fonts (%s)" % (len(fonts), ", ".join(
        "%d:%dpx%s" % (f["id"], f["cap"], "o" if f["outline"] else "") for f in fonts)))


if __name__ == "__main__":
    main()
