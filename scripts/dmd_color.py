#!/usr/bin/env python3
"""Colour for the HD DMD: the 16 shades of each display effect's animation mapped to colours, as a colour
DMD does, at build time (scripts/gen_media.py build_color_frames).

The colour map, game/tools/dmd_colormap.json (small, tracked):
- "default": the Tron palette of effects without their own (cyan light lines to a white highlight);
- "text": the palette of text baked into an effect's pictures (dark blue, as the HD text drawn live);
- "deffs": {deff: {"hues": [main, accent], ...}} measured on the PuP-Pack video each effect plays with
  (scripts/pup_colormap.py, which also records the capture, the videos and the measured hues).
A palette is 16 colours (ramp): shade 0 black; the dim shades 1-7 (the ROM's film clips and backgrounds)
in the main hue, getting brighter; the bright shades 12-15 (the foreground: lines, objects, logos) in the
accent hue, getting lighter, 15 almost white (the highlight). The art never uses shades 8-11; they blend.

The colour frames are 2x (COLOR_SCALE, 256x64): Scale2x (EPX) on the shades, each dot 2x2 with diagonal
edges one step finer, every shade then in its colour, shown with nearest filtering (crisp dots). At
scale 8 they are upscaled as the HD grey frames are instead (scripts/dmd_hd.py: one smoothed mask per
shade, laid over the lower ones in the shade's colour), smoother but softer in busy film clips.
Text: an effect played from the emulator's capture shows its ROM text lines inside the picture (and the
status panel left of x 41 when the deff draws it). Each line is drawn with the ROM font at its layout
(scripts/rom_layout.py); in each frame that shows it (TEXT_MATCH of its dots lit, TEXT_BG of the black
cells or outlines around them dark), its lit dots take the text palette, as do the panel's lit dots. A
captured frame drawn in a single shade is a text screen (GAME OVER, BALL SAVED, TILT): all text. Other
frames in a single shade (logos, line art: DAFT PUNK) keep their top shades coloured (flat_palette).

No third-party colour data is read: the colour comes from the monochrome frames alone (scripts/mono_colour.py, source "mono")
or, for an effect left out of it, from its PuP-hue palette ("pup" / "default"). palettes.json records each effect's source.

    .venv/bin/python scripts/dmd_color.py DEFF IN.png OUT.png [scale]   # one classic frame in DEFF's colours (2 or 8)
"""
import colorsys
import hashlib
import json
import os
import sys

import fsutil  # Windows/OneDrive-safe renames and folder wipes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COLORMAP = os.path.join(ROOT, "game", "tools", "dmd_colormap.json")
VERSION = "8"            # bump when the colouring changes: the cache (.cache/dmd_hd) keys on it
TEXT_MATCH = 0.9
COLOR_SCALE = 2          # colour frames: 2x (Scale2x, crisp, 256x64), the default; 8 = the smooth per-shade filter

# The film's palette only: blue and cyan light lines, red / red-orange for CLU, Rinzler and the Recognizer, white
# highlights (the top shade) and black. No green, violet or yellow: the PuP videos have big green or amber text
# and graphics that are not the film's colours, so measured hues of those kinds are folded into these (ALIASES).
HUES = {"cyan": 188, "blue": 212, "deep blue": 232, "red": 2, "orange": 14}
ALIASES = {"green": "blue", "violet": "deep blue", "amber": "orange", "yellow": "orange"}
# (shade, saturation, value) of the main hue (dim shades) and of the accent hue (bright shades)
DIM = ((1, 1.0, 0.22), (4, 1.0, 0.55), (7, 0.92, 0.85))
BRIGHT = ((12, 0.95, 0.92), (13, 0.75, 1.0), (14, 0.45, 1.0), (15, 0.1, 1.0))


def load_colormap(path=COLORMAP):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_colormap(data, path=COLORMAP):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")


def hue_of(name):
    return HUES[ALIASES.get(name, name)] if isinstance(name, str) else float(name)


def ramp(main, accent=None, dim=DIM, bright=BRIGHT):
    """16 (r, g, b) bytes: shade 0 black, the dim stops in the main hue, the bright ones in the accent hue
    (main if none), the shades between stops mixed in RGB (no rainbow between two hues)."""
    hm, ha = hue_of(main) / 360, hue_of(accent if accent is not None else main) / 360
    stops = [(0, (0.0, 0.0, 0.0))] + [(k, colorsys.hsv_to_rgb(hm, s, v)) for k, s, v in dim] \
        + [(k, colorsys.hsv_to_rgb(ha, s, v)) for k, s, v in bright]
    gap = abs(hm - ha) * 360
    if min(gap, 360 - gap) > 60:
        # a warm body and cool light lines: mixing them in RGB gives purple/magenta mid shades, which the
        # film never shows, so the shades after the last dim stop start again in the accent hue
        stops.append((dim[-1][0] + 1, colorsys.hsv_to_rgb(ha, 0.95, 0.5)))
    out = []
    for shade in range(16):
        a = max((st for st in stops if st[0] <= shade), key=lambda st: st[0])
        b = min((st for st in stops if st[0] >= shade), key=lambda st: st[0], default=a)
        t = 0 if b[0] == a[0] else (shade - a[0]) / (b[0] - a[0])
        out.append(tuple(round((x + (y - x) * t) * 255) for x, y in zip(a[1], b[1])))
    return out


def palette(deff, cmap=None):
    """The 16 colours of a display effect: its own (PuP hues) or the default."""
    cmap = cmap or load_colormap()
    entry = cmap["deffs"].get(str(deff)) or cmap["default"]
    return ramp(*entry["hues"][:2])


def text_palette(cmap=None):
    cmap = cmap or load_colormap()
    t = cmap["text"]
    return ramp(*t["hues"][:2], dim=[tuple(x) for x in t.get("dim", DIM)], bright=[tuple(x) for x in t.get("bright", BRIGHT)])


def palette_hex(pal):
    return ["#%02x%02x%02x" % c for c in pal]


def scale2x(rows):
    """Scale2x (EPX), the pixel-art doubling: rows of values -> rows twice as wide and high. Each dot becomes
    2x2; a corner takes the neighbours' value where two neighbours agree across it (a diagonal edge), so
    staircases get one step finer while every flat area and one-dot line stays crisp and exact."""
    h, w = len(rows), len(rows[0])
    out = [[0] * (2 * w) for _ in range(2 * h)]
    for y in range(h):
        up, row, down = rows[max(0, y - 1)], rows[y], rows[min(h - 1, y + 1)]
        for x in range(w):
            p = row[x]
            a, d = up[x], down[x]
            c, b = row[max(0, x - 1)], row[min(w - 1, x + 1)]
            e0 = e1 = e2 = e3 = p
            if c != b and a != d:
                e0 = a if c == a else p
                e1 = b if a == b else p
                e2 = c if d == c else p
                e3 = d if b == d else p
            out[2 * y][2 * x], out[2 * y][2 * x + 1] = e0, e1
            out[2 * y + 1][2 * x], out[2 * y + 1][2 * x + 1] = e2, e3
    return out


def upscale_color_2x(img, pal, text_pal=None, text_dots=None):
    """A classic effect frame -> 'RGB' frame 2x larger (COLOR_SCALE): Scale2x on the 16 shades (text dots
    as their own values, so text edges stay text), each shade then drawn in its palette colour. Shown
    with nearest filtering: crisp dots, no blur."""
    from PIL import Image
    import dmd_hd
    grey = dmd_hd.grey(img)
    w, h = grey.size
    g = grey.tobytes()
    t = text_dots if (text_dots is not None and text_pal is not None) else bytes(w * h)
    vals = [min(15, round(v / 17)) + (16 if v and m else 0) for v, m in zip(g, t)]
    big = scale2x([vals[y * w:(y + 1) * w] for y in range(h)])
    lut = [tuple(pal[k]) for k in range(16)] + [tuple((text_pal or pal)[k]) for k in range(16)]
    out = Image.new("RGB", (2 * w, 2 * h))
    out.putdata([lut[v] for row in big for v in row])
    return out


def upscale_color(img, pal, f, text_pal=None, text_dots=None):
    """A classic effect frame -> 'RGB' frame f times larger, coloured shade by shade: the same level sets
    as dmd_hd.upscale_levels (each "dot >= shade" mask smoothed), each one laid over the lower ones in its
    shade's colour, so an edge blends the two colours it separates. text_dots ('L' 128x32 mask): the dots
    drawn in the text palette."""
    from PIL import Image
    import dmd_hd
    grey = dmd_hd.grey(img)
    size = (grey.width * f, grey.height * f)
    out = Image.new("RGB", size, (0, 0, 0))
    weight = None
    if text_pal is not None and text_dots is not None and text_dots.getbbox():
        weight = dmd_hd.upscale_levels(text_dots, f)
    for v in sorted(c for _, c in (grey.getcolors(256) or []) if c):
        shade = min(15, round(v / 17))
        fill = Image.new("RGB", size, tuple(pal[shade]))
        if weight is not None:
            fill = Image.composite(Image.new("RGB", size, tuple(text_pal[shade])), fill, weight)
        out = Image.composite(fill, out, dmd_hd.smooth_mask(grey.point(lambda p, v=v: 255 if p >= v else 0), f))
    return out


# ---------------------------------------------------------------------- text inside the pictures

PANEL_X = 41            # the status panel (scores, separator) left of this column, in captures that show it
FLAT = 0.95
TEXT_BG = 0.8           # share of a line's glyph cells (outline, plain cell) that must be dark


def text_masks(deff_ids=None):
    """{deff: {"lines": [(text dots, cell dots), ...], "panel": bool}} for every effect that plays the
    emulator's capture: each ROM text line drawn with its font at its layout (lists of 4096 booleans, 128 x
    32: the glyph dots, and the dark dots of the glyph cells or outlines around them), and whether the
    capture shows the status panel (rom_layout.status_panel_deffs)."""
    import csv
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import gen_fonts
    import gen_media
    import rom_layout
    data = json.load(open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8"))["deffs"]
    rows = {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(gen_media.PKG, "event_map.csv"),
                                                           encoding="utf-8"))}
    _, get, _ = gen_fonts.decode_all()
    fonts = json.load(open(os.path.join(ROOT, "game", "fonts", "fonts.json"), encoding="utf-8"))["fonts"]
    calls = rom_layout.deff_calls()
    panels = rom_layout.status_panel_deffs()
    out = {}
    for key, info in data.items():
        deff = int(key)
        if info["source"] != "reference" or (deff_ids is not None and deff not in deff_ids):
            continue
        lines = gen_media.text_lines(gen_media.ROM_TEXT.get(deff, rows.get(deff, {}).get("rom_text", "")))
        lines = [ln for ln in lines if "%" not in ln]
        masks = []
        for line, lay in zip(lines, rom_layout.line_layouts(deff, lines, fonts, calls.get(deff, [])) if lines else []):
            if not lay:
                continue
            canvas = gen_fonts.render(get, fonts[lay["font"]], line, lay["x"], lay["y"], lay["flags"],
                                      [[-1] * 128 for _ in range(32)])
            fg = [v > 0 for row in canvas for v in row]
            bg = [v == 0 for row in canvas for v in row]
            if any(fg):
                masks.append((fg, bg))
        out[deff] = {"lines": masks, "panel": deff in panels}
    return out


def is_flat(grey):
    """A frame drawn in one shade (FLAT of its lit dots right of the panel): a text screen or line art."""
    counts = {}
    for i, v in enumerate(grey.tobytes()):
        if v and i % 128 >= PANEL_X:
            counts[v] = counts.get(v, 0) + 1
    return not counts or max(counts.values()) >= FLAT * sum(counts.values())


def frame_text_dots(spec, grey):
    """The text dots of one classic frame of a captured effect ('L' greys) as 128x32 'L' bytes, or None:
    every lit dot of a frame in one shade (a text screen: BALL SAVED, GAME OVER, TILT, ...); else the lit
    dots of each text line the frame shows (TEXT_MATCH of its glyph dots lit, TEXT_BG of its cell dark),
    and the lit dots of the status panel."""
    lit = [p > 0 for p in grey.tobytes()]
    if is_flat(grey):
        return bytes(255 if t else 0 for t in lit) if any(lit) else None
    text = [False] * len(lit)
    for fg, bg in spec["lines"]:
        n_fg, n_bg = sum(fg), sum(bg)
        on = sum(1 for a, b in zip(fg, lit) if a and b)
        dark = sum(1 for a, b in zip(bg, lit) if a and not b)
        if on >= TEXT_MATCH * n_fg and (not n_bg or dark >= TEXT_BG * n_bg):
            text = [t or (a and b) for t, a, b in zip(text, fg, lit)]
    if spec["panel"]:
        text = [t or (b and i % 128 < PANEL_X) for i, (t, b) in enumerate(zip(text, lit))]
    return bytes(255 if t else 0 for t in text) if any(text) else None


def flat_palette(pal):
    """The palette of line art drawn in one shade (a logo): the top shades kept coloured, not white."""
    return list(pal[:13]) + [pal[13]] * 3


def shades(img):
    """A classic frame (PIL image: the 16 shades as greys 0, 17, .. 255) -> bytes of shades 0..15."""
    import dmd_hd
    return bytes(min(15, round(v / 17)) for v in dmd_hd.grey(img).tobytes())


def scale2x_keep(vals, shades, w, h):
    """2x upscale of a coloured frame: Scale2x on the colour indices, outside the frame counting as no neighbour, except
    that a dot the ROM lit (shades) never takes a neighbour the ROM left dark: the result is the union of Scale2x
    and line doubling, so the ROM's five-dot letters keep every dot. Rows of indices 2w x 2h."""
    out = [[0] * (2 * w) for _ in range(2 * h)]
    for y in range(h):
        for x in range(w):
            k = y * w + x
            e = vals[k]
            b = vals[k - w] if y > 0 else None
            hh = vals[k + w] if y + 1 < h else None
            d = vals[k - 1] if x > 0 else None
            f = vals[k + 1] if x + 1 < w else None
            o = [e, e, e, e]
            if b != hh and d != f:
                pick = [(k - 1 if x > 0 else None) if d == b else k, (k + 1 if x + 1 < w else None) if b == f else k,
                        (k - 1 if x > 0 else None) if d == hh else k, (k + 1 if x + 1 < w else None) if hh == f else k]
                for n, src in enumerate(pick):
                    if src == k:
                        continue
                    if shades[k] and (src is None or not shades[src]):
                        continue                    # never round a lit dot away into emptiness
                    o[n] = vals[src] if src is not None else 0
            out[2 * y][2 * x], out[2 * y][2 * x + 1] = o[0], o[1]
            out[2 * y + 1][2 * x], out[2 * y + 1][2 * x + 1] = o[2], o[3]
    return out


def scale_indices(vals, w, h, f, shades=None):
    """Rows of colour indices (or shades) doubled until f times larger (2, 4, 8): scale2x_keep
    when the ROM's shades are given, else Scale2x."""
    if shades is not None and f == 2:
        return scale2x_keep(list(vals), shades, w, h)
    rows = [list(vals[y * w:(y + 1) * w]) for y in range(h)]
    while f > 1:
        rows, f = scale2x(rows), f // 2
    return rows


def line_colour(vals, lut, shades, dots):
    """The colour a text line is shown in: of its dots (indices k), the most common colour among those in its
    brightest shade, as "#rrggbb"; None when none is lit or all are black."""
    from collections import Counter
    lit = [k for k in dots if shades[k]]
    if not lit:
        return None
    top = max(shades[k] for k in lit)
    counts = Counter(tuple(lut[vals[k]]) for k in lit if shades[k] == top)
    counts = Counter({c: n for c, n in counts.items() if sum(c) > 30}) or counts
    c = counts.most_common(1)[0][0]
    return "#%02x%02x%02x" % c if sum(c) > 30 else None


def clear_text(vals, lut, shades, text, blank=()):
    """A colour frame's text drawn live in HD (frame_text: text = {"dots": [k, ...], "lines": [[x0, y0, x1, y1], ...]}
    of the frame) taken out of the picture: (indices with those dots black, palette, shades with them dark, the
    colour of each line as the colourisation shows it). blank: dots also shown black (text_blanks). Unchanged
    without either."""
    text = text or {}
    if not text.get("dots") and not blank:
        return vals, lut, shades, []
    dots = set(text.get("dots", ()))
    cols = [line_colour(vals, lut, shades, [k for k in dots if x0 <= k % 128 <= x1 and y0 <= k // 128 <= y1])
            for x0, y0, x1, y1 in text.get("lines", ())]
    lut = list(lut) + [(0, 0, 0)]
    black = len(lut) - 1
    dots |= set(blank)
    vals = [black if k in dots else v for k, v in enumerate(vals)]
    shades = bytes(0 if k in dots else v for k, v in enumerate(shades))
    return vals, lut, shades, cols


def text_blanks(shades, texts):
    """The dots of a recorded effect's frame (shades) the colour picture shows black, so that all its text is the
    HD's own (drawn live in the clean font): where the ROM leaves them dark, every dot of a text screen (a frame in
    one shade, or none: the colourisation's own lettering, credits, the text of another blink phase), and in other frames
    the dots inside the boxes of the lines the effect shows in any of its frames (texts: {frame: text})."""
    lit = [k for k in range(4096) if shades[k] and k % 128 >= PANEL_X]
    levels = {shades[k] for k in lit}
    if len(levels) <= 1:
        return [k for k in range(4096) if not shades[k]]
    boxes = {tuple(b) for t in texts.values() for b in t.get("lines", ())}
    return [y * 128 + x for x0, y0, x1, y1 in boxes for y in range(max(0, y0), min(32, y1 + 1))
            for x in range(max(0, x0), min(128, x1 + 1)) if not shades[y * 128 + x]]


def rgb_image(rows, lut):
    from PIL import Image
    img = Image.new("RGB", (len(rows[0]), len(rows)))
    img.putdata([tuple(lut[v]) for row in rows for v in row])
    return img




# ---------------------------------------------------------------------- build

def color_file(job):
    """(src classic png, dst, palette, text palette, text dots (frame_text_dots) or None, scale, cache dir):
    writes the colour HD frame dst, through the cache (keyed on the picture, the palettes and the dots)."""
    import shutil
    from PIL import Image
    import dmd_hd
    src, dst, pal, text_pal, mask, f, cache = job
    with open(src, "rb") as fp:
        data = fp.read()
    key = hashlib.sha1(b"|".join([b"color", VERSION.encode(), dmd_hd.VERSION.encode(), str(dmd_hd.SIGMA).encode(),
                                  str(dmd_hd.CUT).encode(), str(f).encode(), json.dumps([pal, text_pal]).encode(),
                                  mask or b"-", data])).hexdigest()
    cached = os.path.join(cache, key + ".png") if cache else None
    if cached and os.path.exists(cached):
        shutil.copyfile(cached, dst)
        return dst
    img = Image.open(src)
    if f == 2:
        upscale_color_2x(img, pal, text_pal, mask).save(dst, compress_level=6)
    else:
        dots = Image.frombytes("L", img.size, mask) if mask else None
        upscale_color(img, pal, f, text_pal, dots).save(dst, compress_level=6)
    if cached:
        os.makedirs(cache, exist_ok=True)
        tmp = cached + ".%d.tmp" % os.getpid()
        shutil.copyfile(dst, tmp)
        fsutil.replace_cached(tmp, cached)    # another worker may hold the same entry (Windows)
    return dst


def fallback_frame(job):
    """(src classic png, dst, palette, text or None, scale): an effect frame in its effect's shade palette (the
    PuP-hue or default ramp), its live text taken out; returns its lines' colours
    in the text palette."""
    from PIL import Image
    src, dst, pal, text, f, tpal = job
    sh = shades(Image.open(src))
    vals, lut, sh2, _ = clear_text(sh, pal, sh, text)
    cols = [("#%02x%02x%02x" % tuple(tpal[15])) for _ in (text or {}).get("lines", [])]
    rgb_image(scale_indices(vals, 128, 32, f, sh2), lut).save(dst, compress_level=6)
    return cols


def recorded_text(src_root, recorded):
    """{folder name: {frame file: {"dots": [k], "lines": [[x0, y0, x1, y1], ...]}}}: the ROM text HD draws live over
    the recorded effects' frames (scripts/frame_text.py: the lines of media/dmd_hd/text.json), as dots of the
    128x32 frame (the lit dots its cleared copy leaves dark, the rectangles drawn as such left in) and each line's
    box."""
    import glob
    from PIL import Image
    import frame_text
    fonts = {f["id"]: f for f in json.load(open(os.path.join(ROOT, "game", "fonts", "fonts.json"),
                                                encoding="utf-8"))["fonts"]}
    frames = sorted(glob.glob(os.path.join(src_root, "deff_*", "f*.png")))
    found = frame_text.process_files(frames, os.path.join(ROOT, ".cache", "frame_text"), recorded)
    out = {}
    for src, (lines, boxes, cleared) in found.items():
        if not cleared or not lines:
            continue
        a, c = shades(Image.open(src)), shades(Image.open(cleared))
        kept = set()
        for x0, y0, x1, y1, _, solid in boxes:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if solid or x in (x0, x1) or y in (y0, y1):
                        kept.add(y * 128 + x)
        dots = [k for k in range(4096) if a[k] and not c[k] and k not in kept]
        rows = []
        for ln in lines:
            m = fonts.get(int(ln[1]), {"ascent": 7, "descent": 1})
            x0 = int(ln[2])
            rows.append([x0, int(ln[3]) - int(m["ascent"]) + 1, x0 + int(ln[5]) - 1, int(ln[3]) + int(m["descent"])])
        out.setdefault(os.path.basename(os.path.dirname(src)), {})[os.path.basename(src)] = {"dots": dots, "lines": rows}
    return out


def build(src_root, dst_root, scale=COLOR_SCALE, cache=None, processes=None, recorded=None, mono=True):
    """Every effect frame (f*.png) of src_root (game/media/dmd) in colour, scale times larger, into dst_root (same
    names): from the monochrome frames alone (mono, scripts/mono_colour.py), else in their effect's shade palette. The text HD
    draws live over the recorded effects (recorded: their folder names, recorded_text) is taken out of the pictures
    and its colour kept per line. Returns the info written to dst_root/palettes.json."""
    import glob
    from PIL import Image
    cmap = load_colormap()
    tpal = text_palette(cmap)
    fsutil.remove_dir(dst_root)
    os.makedirs(dst_root, exist_ok=True)
    folders = sorted(glob.glob(os.path.join(src_root, "deff_*")))
    texts = recorded_text(src_root, set(recorded or ()))
    jobs, palettes, mono_jobs = [], {}, []
    for folder in folders:
        name = os.path.basename(folder)
        deff = int(name.split("_")[1])
        frames = sorted(glob.glob(os.path.join(folder, "f*.png")))
        if frames and Image.open(frames[0]).size != (128, 32):      # a picture of the generated effects (attract logo): not a DMD frame
            continue
        if mono:                                # from the monochrome frames alone (scripts/mono_colour.py)
            import mono_colour
            rec = mono_colour.effect_recipe(deff)
            rp = mono_colour.ramp(rec.get("main", "blue"), (rec.get("accents") or ["cyan"])[0])
            palettes[name] = {"source": "mono", "palette": ["#%02x%02x%02x" % tuple(int(v * 255) for v in c) for c in rp]}
            if frames:
                mono_jobs.append((name, deff, frames, os.path.join(dst_root, name), scale, texts.get(name, {})))
            continue
        pal = palette(deff, cmap)
        palettes[name] = {"palette": palette_hex(pal), "source": "pup" if str(deff) in cmap["deffs"] else "default"}
        if not frames:
            continue
        os.makedirs(os.path.join(dst_root, name), exist_ok=True)
        for p in frames:
            n = os.path.basename(p)
            jobs.append(((p, os.path.join(dst_root, name, n), pal, texts.get(name, {}).get(n), scale, tpal), name, n))
    if jobs:
        import multiprocessing
        with multiprocessing.Pool(processes or os.cpu_count() or 2) as pool:
            cols = pool.map(fallback_frame, [j[0] for j in jobs], chunksize=4)
        for (_, name, n), c in zip(jobs, cols):
            if c:
                palettes[name].setdefault("text_colors", {})[n] = c
    if mono_jobs:
        import multiprocessing
        import mono_colour
        with multiprocessing.Pool(processes or os.cpu_count() or 2) as pool:
            for j, cols in zip(mono_jobs, pool.map(mono_colour.build_folder, mono_jobs, chunksize=2)):
                if cols:
                    palettes[j[0]]["text_colors"] = cols
    info = {"scale": scale, "text": palette_hex(tpal), "deffs": palettes}
    with open(os.path.join(dst_root, "palettes.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=0, sort_keys=True)
    return info


# ---------------------------------------------------------------------- the effects' data in colour









def annotate(media_root, dst_root, info):
    """The effects' data (media_root/deff_NNN/effect.json, scripts/gen_media.py) told their colours, read by
    tron/dmd_effect.gd when the colour is on (HD): the frames item's "color_frames" (the colour pictures, frame for
    frame; checksum-identical pictures share one file), a text line's "color" and a rectangle's "color_rgb" (from
    the effect's recipe, scripts/mono_colour.py). dst_root/text_colors.json: the
    colour of each line of text HD draws live over a recorded frame. Returns the number of effects told colours."""
    import glob
    from PIL import Image
    res = "res://media/"
    color_res = res + os.path.basename(dst_root) + "/"
    effects = {}
    for path in sorted(glob.glob(os.path.join(media_root, "deff_*", "effect.json"))):
        with open(path, encoding="utf-8") as f:
            effects[path] = json.load(f)
    # colour pictures: one file per distinct picture
    shared, moved, told = {}, {}, 0
    for path, eff in effects.items():
        folder = os.path.dirname(path)
        name = os.path.basename(folder)
        own = {}
        for p in sorted(glob.glob(os.path.join(folder, "f*.png"))):
            own[hashlib.md5(Image.open(p).convert("RGBA").tobytes()).hexdigest()] = os.path.basename(p)
        changed = False
        for i, it in enumerate(eff["items"]):
            if it["type"] == "frames":
                twins = []
                for pic, ms in it["frames"]:
                    rel = pic[len(res) + len("dmd/"):]
                    digest = hashlib.md5(Image.open(os.path.join(media_root, rel)).convert("RGBA").tobytes()).hexdigest()
                    mine = own.get(digest)
                    cpath = os.path.join(dst_root, name, mine) if mine else None
                    if cpath in moved:
                        twins.append(color_res + moved[cpath])
                        continue
                    if not cpath or not os.path.exists(cpath):
                        twins = None
                        break
                    with open(cpath, "rb") as f:
                        key = hashlib.sha1(f.read()).hexdigest()
                    first = moved[cpath] = shared.setdefault(key, name + "/" + mine)
                    if first != name + "/" + mine:
                        os.remove(cpath)
                    twins.append(color_res + first)
                if twins:
                    it["color_frames"] = twins
                    changed = True
            elif it["type"] == "text" and info["deffs"].get(name, {}).get("source") == "mono":
                it["color"] = info["deffs"][name]["palette"][14]     # the effect's text shade, from its recipe
                changed = True
            elif it["type"] == "rect" and info["deffs"].get(name, {}).get("source") == "mono" \
                    and it.get("level") and it.get("name") not in ("Background", "PanelClear") \
                    and not it["name"].startswith("Clear"):
                it["color_rgb"] = info["deffs"][name]["palette"][max(1, min(15, int(it["level"])))]
                changed = True
        if changed:
            told += 1
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(eff, f, indent=1)
                f.write("\n")
    lines = {}
    for name, entry in info["deffs"].items():
        for n, cols in entry.get("text_colors", {}).items():
            lines[name + "/" + n] = cols
    with open(os.path.join(dst_root, "text_colors.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(lines, f, indent=0, sort_keys=True)
    return told


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    from PIL import Image
    import dmd_hd
    f = int(argv[3]) if len(argv) > 3 else COLOR_SCALE
    img = Image.open(argv[1])
    (upscale_color_2x(img, palette(int(argv[0]))) if f == 2 else upscale_color(img, palette(int(argv[0])), f)).save(argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
