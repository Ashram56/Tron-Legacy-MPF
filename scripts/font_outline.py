#!/usr/bin/env python3
"""Vector (TrueType) versions of the ROM's DMD fonts for the HD display mode (game/tools/dmd_mode.gd).

Each glyph's dots are traced into smooth outlines: the same level-set smoothing as scripts/dmd_hd.py
(bilinear enlargement, Gaussian blur of SIGMA dots, cut at CUT) gives a smooth field, marching squares
follow its CUT iso-line at TRACE samples per dot, and the closed polylines are simplified to within
TOLERANCE dots. So staircases become straight or curved edges and single dots become round, as in the HD
effect frames, but the outlines stay sharp at any size (4K included): Godot rasterises them at the
window's resolution.

Metrics are the ROM's, exactly: 1 dot = UNITS font units, units per em = the font's line height
(ascent + descent) in units, so a font drawn at font size = line height in dots puts every glyph where
the ROM's 128x32 layout puts it; advance = glyph width + x offset + font spacing (the ROM's text_width).

One TrueType file per ROM font (rom_font_NN.ttf) holds several layers of each character, drawn in order
by tron/rom_text_hd.gd:
- U+E000 + c: the cell: every dot the ROM draws (plain fonts paint a black rectangle under the glyph,
  outlined fonts a black border around the strokes); drawn black;
- c itself: the lit dots (level > 0), drawn in the text colour at the font's lowest level (so the font
  also works on its own, as an ordinary font);
- U+E000 + 0x100 * k + c (k >= 1): the dots at level >= levels[k] (shaded fonts 42-43 only), drawn over it
  at that level.
A glow atlas (rom_font_NN_glow.fnt + .png, BMFont at GLOW_SCALE pixels per dot) holds every glyph's lit
dots blurred (GLOW_SIGMAS), with the same advances: the soft bloom drawn behind the text.

Needs fontTools (pip install fonttools; in scripts/toolchain.py REQUIREMENTS) and Pillow.
"""
import math
import os
import re

import dmd_hd

TRACE = 16            # field samples per dot for marching squares
UNITS = 128           # font units per dot
TOLERANCE = 0.01      # polyline simplification, in dots (0.3 px on a 3840 px wide DMD)
PAD = 1               # dots of clear border around a glyph before smoothing (as dmd_hd.upscale_glyph)
CELL_PLANE = 0xE000
LEVEL_PLANE = 0xE000  # + 0x100 * k, k >= 1
GLOW_SCALE = 4        # glow atlas pixels per dot (the glow is soft: linear filtering enlarges it cleanly)
GLOW_PAD = 4          # dots of room around each glyph for the glow
GLOW_SIGMAS = ((0.45, 0.7), (1.3, 0.55))   # (Gaussian sigma in dots, weight): a tight halo and a wide bloom
VERSION = "1"
STAMP = 3881174400        # head created/modified: 2026-12-27 (fixed, so the build is reproducible)


def field(mask, w, h, f=TRACE, pad=PAD):
    """mask: rows of booleans -> (Pillow 'L' smoothed field f times larger with pad dots of border, pad)."""
    from PIL import Image, ImageFilter
    img = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    img.putdata([255 if (0 <= y - pad < h and 0 <= x - pad < w and mask[y - pad][x - pad]) else 0
                 for y in range(h + 2 * pad) for x in range(w + 2 * pad)])
    big = img.resize((img.width * f, img.height * f), Image.BILINEAR)
    return big.filter(ImageFilter.GaussianBlur(f * dmd_hd.SIGMA))


def trace(img, threshold=dmd_hd.CUT - 0.5):
    """Closed polylines of the iso-line `threshold` of the 'L' image img, in sample coordinates (pixel
    centres at integers), each with the inside (>= threshold) on its left when y points down."""
    from PIL import ImageChops, ImageFilter
    W, H = img.size
    data = img.tobytes()
    inside = img.point(lambda p: 255 if p >= threshold else 0)
    edge = ImageChops.difference(inside.filter(ImageFilter.MaxFilter(3)), inside.filter(ImageFilter.MinFilter(3)))
    points = {}

    def point(key):
        if key not in points:
            kind, x, y = key
            x2, y2 = (x + 1, y) if kind == "h" else (x, y + 1)
            a, b = data[y * W + x], data[y2 * W + x2]
            t = (threshold - a) / (b - a)
            points[key] = (x + (x2 - x) * t, y + (y2 - y) * t)
        return points[key]

    nxt = {}
    for m in re.finditer(rb"[^\x00]", edge.tobytes()):
        i = m.start()
        x, y = i % W, i // W
        if x >= W - 1 or y >= H - 1:
            continue
        va, vb, vc, vd = data[i], data[i + 1], data[i + W + 1], data[i + W]   # tl, tr, br, bl
        ia, ib, ic, id_ = va >= threshold, vb >= threshold, vc >= threshold, vd >= threshold
        if ia == ib == ic == id_:
            continue
        top, right, bottom, left = ("h", x, y), ("v", x + 1, y), ("h", x, y + 1), ("v", x, y)
        corners = (((x, y), ia, top, left), ((x + 1, y), ib, top, right),
                   ((x + 1, y + 1), ic, bottom, right), ((x, y + 1), id_, bottom, left))
        if ia == ic and ib == id_:                    # saddle: the centre decides which corners join
            centre_in = (va + vb + vc + vd) / 4 >= threshold
            cut = [c for c in corners if c[1] != centre_in]
            segs = [(c[2], c[3]) for c in cut]
        else:
            crossing = [e for e, (p, q) in ((top, (ia, ib)), (right, (ib, ic)), (bottom, (id_, ic)),
                                            (left, (ia, id_))) if p != q]
            segs = [tuple(crossing)]
        for p, q in segs:
            (px, py), (qx, qy) = point(p), point(q)
            s = sum(((qx - px) * (cy - py) - (qy - py) * (cx - px)) * (1 if cin else -1)
                    for (cx, cy), cin, _, _ in corners)
            if s > 0:                                 # inside must be on the left (cross < 0 with y down)
                p, q = q, p
            nxt[p] = q
    loops = []
    while nxt:
        start, cur = next(iter(nxt.items()))
        del nxt[start]
        loop = [point(start)]
        while cur != start and cur in nxt:
            loop.append(point(cur))
            cur = nxt.pop(cur)
        if cur == start and len(loop) >= 3:
            loops.append(loop)
    return loops


def simplify(loop, tol):
    """Douglas-Peucker on a closed polyline."""
    n = len(loop)
    if n < 4:
        return loop
    far = max(range(n), key=lambda i: (loop[i][0] - loop[0][0]) ** 2 + (loop[i][1] - loop[0][1]) ** 2)
    keep = {0, far}
    stack = [(0, far), (far, n)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = loop[a]
        bx, by = loop[b % n]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-9
        best, at = -1.0, None
        for i in range(a + 1, b):
            px, py = loop[i]
            d = abs(dx * (py - ay) - dy * (px - ax)) / norm
            if d > best:
                best, at = d, i
        if best > tol:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return [loop[i] for i in sorted(keep)]


def area(loop):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1])) / 2


def outlines(mask, w, h, f=TRACE):
    """Closed contours (lists of (x, y) in dots, x right, y down from the glyph image's top left) of the
    smoothed shape of mask, the inside on the left."""
    if not any(any(r) for r in mask):
        return []
    out = []
    for loop in trace(field(mask, w, h, f)):
        pts = simplify([((x + 0.5) / f - PAD, (y + 0.5) / f - PAD) for x, y in loop], TOLERANCE)
        if len(pts) >= 3 and abs(area(pts)) > 1e-3:
            out.append(pts)
    return out


def glyph_layers(levels, transparent=255):
    """The shapes of a ROM glyph (rows of levels 0-15, `transparent` = not drawn): (cell, lit, by_level)
    where cell is None for a glyph drawn over its whole rectangle, lit = dots with a level > 0 and
    by_level[v] = dots with a level >= v for each level v present."""
    drawn = [[v != transparent for v in row] for row in levels]
    full = all(all(r) for r in drawn)
    present = sorted({v for row in levels for v in row if 0 < v < transparent})
    by_level = {v: [[0 < p < transparent and p >= v for p in row] for row in levels] for v in present}
    lit = [[0 < p < transparent for p in row] for row in levels]
    return (None if full else drawn), lit, by_level


def font_levels(font, get):
    return sorted({v for g in font["glyphs"].values() for row in get(g["image"]) for v in row if 0 < v < 255})


def glyph_contours(font, c, get, levels):
    """{plane codepoint: contours in font units (y up, origin at the pen on the baseline)} for character c."""
    g = font["glyphs"][c]
    img = get(g["image"])
    w, h = g["w"], g["h"]
    cell, lit, by_level = glyph_layers(img)
    top = h - g["below"]                            # the image's top edge above the baseline, in dots

    def units(contours):
        out = []
        for pts in contours:
            q = []
            for x, y in reversed(pts):              # y flips: reversed keeps TrueType's clockwise outer contours
                p = (round((g["xoff"] + x) * UNITS), round((top - y) * UNITS))
                if not q or q[-1] != p:
                    q.append(p)
            if len(q) > 1 and q[0] == q[-1]:
                q.pop()
            if len(q) >= 3:
                out.append(q)
        return out

    x0, x1 = g["xoff"] * UNITS, (g["xoff"] + w) * UNITS
    y0, y1 = (top - h) * UNITS, top * UNITS
    planes = {CELL_PLANE + ord(c): ([[(x0, y0), (x0, y1), (x1, y1), (x1, y0)]] if cell is None
                                    else units(outlines(cell, w, h))),
              ord(c): units(outlines(lit, w, h))}
    for k, v in enumerate(levels[1:], 1):
        planes[LEVEL_PLANE + 0x100 * k + ord(c)] = units(outlines(by_level[v], w, h)) if v in by_level else []
    return planes


def write_ttf(font, get, path):
    """rom_font_NN.ttf; returns its design entry for fonts_hd.json (levels, units per em)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    levels = font_levels(font, get) or [15]
    upem = (font["ascent"] + font["descent"]) * UNITS
    order, cmap, glyphs, metrics = [".notdef"], {}, {}, {}
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    metrics[".notdef"] = (0, 0)
    for c in sorted(font["glyphs"], key=ord):
        g = font["glyphs"][c]
        advance = (g["w"] + g["xoff"] + font["spacing"]) * UNITS
        for code, contours in sorted(glyph_contours(font, c, get, levels).items()):
            name = "uni%04X" % code
            pen = TTGlyphPen(None)
            for pts in contours:
                pen.moveTo(pts[0])
                for p in pts[1:]:
                    pen.lineTo(p)
                pen.closePath()
            glyph = pen.glyph()
            glyph.recalcBounds(None)
            order.append(name)
            cmap[code] = name
            glyphs[name] = glyph
            metrics[name] = (advance, getattr(glyph, "xMin", 0) if contours else 0)
    family = "Tron ROM %02d" % font["id"]
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    asc, desc = font["ascent"] * UNITS, font["descent"] * UNITS
    fb.setupHorizontalHeader(ascent=asc, descent=-desc, lineGap=0)
    fb.setupNameTable({"familyName": family, "styleName": "Regular", "uniqueFontIdentifier": family + " " + VERSION,
                       "fullName": family, "psName": "TronRom%02d-Regular" % font["id"], "version": "Version " + VERSION})
    fb.setupOS2(sTypoAscender=asc, sTypoDescender=-desc, sTypoLineGap=0, usWinAscent=asc, usWinDescent=desc,
                fsSelection=0x40, achVendID="NONE", version=4)
    fb.setupPost()
    fb.setupHead(unitsPerEm=upem, fontRevision=float(VERSION), created=STAMP, modified=STAMP)
    fb.font["head"].flags |= 1 << 3                  # integer scaling (ppem rounds whole: no layout drift)
    fb.save(path)
    return {"levels": levels, "units_per_dot": UNITS, "units_per_em": upem}


def write_glow(font, get, out_dir, name):
    """rom_font_NN_glow.fnt + .png: every glyph's lit dots (as levels) blurred, white with the glow as alpha,
    at GLOW_SCALE pixels per dot, same advances as the font."""
    from PIL import Image, ImageChops, ImageFilter
    s, pad = GLOW_SCALE, GLOW_PAD
    glyphs = sorted(font["glyphs"].items(), key=lambda kv: ord(kv[0]))
    images = {}
    for c, g in glyphs:
        img = get(g["image"])
        lv = Image.new("L", (g["w"] + 2 * pad, g["h"] + 2 * pad), 0)
        lv.putdata([min(255, img[y - pad][x - pad] * 17) if (0 <= y - pad < g["h"] and 0 <= x - pad < g["w"]
                                                             and 0 < img[y - pad][x - pad] < 255) else 0
                    for y in range(g["h"] + 2 * pad) for x in range(g["w"] + 2 * pad)])
        big = lv.resize((lv.width * s, lv.height * s), Image.BILINEAR)
        acc = Image.new("L", big.size, 0)
        for sigma, weight in GLOW_SIGMAS:
            blur = big.filter(ImageFilter.GaussianBlur(sigma * s))
            acc = ImageChops.add(acc, blur.point(lambda p, k=weight: min(255, int(p * k * 1.6))))
        images[c] = Image.merge("RGBA", (Image.new("L", big.size, 255),) * 3 + (acc,))
    gap = 2
    places, x, y, row_h, width = {}, gap, gap, 0, 0
    for c, _ in glyphs:
        w, h = images[c].size
        if x + w + gap > 2048:
            x, y, row_h = gap, y + row_h + gap, 0
        places[c] = (x, y)
        x += w + gap
        row_h = max(row_h, h)
        width = max(width, x)
    height = y + row_h + gap
    atlas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    asc = font["ascent"]
    lines = []
    for c, g in glyphs:
        gx, gy = places[c]
        atlas.paste(images[c], (gx, gy))
        w, h = images[c].size
        lines.append("char id=%d x=%d y=%d width=%d height=%d xoffset=%d yoffset=%d xadvance=%d page=0 chnl=15"
                     % (ord(c), gx, gy, w, h, (g["xoff"] - pad) * s, (asc - g["h"] + g["below"] - pad) * s,
                        (g["w"] + g["xoff"] + font["spacing"]) * s))
    atlas.save(os.path.join(out_dir, name + "_glow.png"))
    size = (asc + font["descent"]) * s
    head = ['info face="%s_glow" size=%d bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 '
            'padding=0,0,0,0 spacing=0,0 outline=0' % (name, size),
            "common lineHeight=%d base=%d scaleW=%d scaleH=%d pages=1 packed=0 alphaChnl=0 redChnl=0 "
            "greenChnl=0 blueChnl=0" % (size, asc * s, width, height),
            'page id=0 file="%s_glow.png"' % name, "chars count=%d" % len(glyphs)]
    with open(os.path.join(out_dir, name + "_glow.fnt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + lines) + "\n")
    return {"glow": name + "_glow.fnt", "glow_scale": s, "glow_pad": pad}


def build_font(job):
    """(font, out_dir): the TrueType font and glow atlas of one ROM font (in a worker process)."""
    font, out_dir = job
    import gen_fonts
    _, get = gen_fonts.load_images()
    name = "rom_font_%02d" % font["id"]
    entry = {"file": name + ".ttf"}
    entry.update(write_ttf(font, get, os.path.join(out_dir, name + ".ttf")))
    entry.update(write_glow(font, get, out_dir, name))
    return entry
