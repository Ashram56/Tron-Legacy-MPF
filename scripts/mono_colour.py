#!/usr/bin/env python3
"""Colour for the HD DMD from the monochrome frames alone (no Serum, no third-party colour data).

The input is what the ROM draws: 16 shades per dot, 128x32. The colour is made from three things, all ours:

1. A shade ramp per effect (RECIPES, authored here): shade 0 black, dim shades a main hue, bright shades an
   accent hue, 15 near white. This alone is the flat look; it is the fallback for an effect without a recipe.
2. Objects. The bright dots (shade >= BRIGHT) are grouped into connected objects (a one-dot gap is bridged, the
   ROM draws dotted lines). Each object takes the next accent of the recipe, and keeps it from frame to frame:
   an object that overlaps one of the previous frame's inherits its colour, so a moving light cycle or disc does
   not flicker. Tiny objects (sparks) stay white.
3. Place: a vertical tilt of the main hue (cooler at the top, warmer at the bottom) so a flat film clip is not
   one block of colour. A recipe sets the tilt; 0 turns it off.

Colour is a pure function of (frames of one effect, recipe): no state between effects, nothing read from a colour
file. The recipes are the owner's to tune; `python scripts/mono_colour.py sheet GIF... --out sheet.png` renders
the monochrome next to the colour for a look.
"""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

BRIGHT = 12          # shades from here are objects, below are background
BIGFLAT = 120        # objects of at least this many dots are tinted, not near white
SPARK = 5            # objects of fewer dots stay white
H, W = 32, 128

HUES = {"cyan": 188, "blue": 214, "deepblue": 232, "red": 2, "orange": 24, "amber": 38, "white": None}
DEFAULT = {"main": "blue", "accents": ["cyan"], "tilt": 10}
# Recipes by display effect number; add as the owner reviews. main = background hue, accents = object hues.
RECIPES = {
    46: {"main": "blue", "accents": ["cyan", "orange"], "tilt": 14},     # Disc Multiball intro
    48: {"main": "blue", "accents": ["orange", "cyan"], "tilt": 10},
    56: {"main": "deepblue", "accents": ["cyan", "orange", "red"], "tilt": 12},
    64: {"main": "deepblue", "accents": ["cyan", "white"], "tilt": 10},
    71: {"main": "red", "accents": ["orange"], "tilt": 8},               # CLU
    85: {"main": "blue", "accents": ["cyan", "orange"], "tilt": 10},     # light cycle
}


def pup_recipe(n):
    """Starting recipe of effect n: the hues measured on the PuP pack (game/tools/dmd_colormap.json; hues only, no
    media), folded into HUES; RECIPES override it."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game", "tools", "dmd_colormap.json")
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)["deffs"].get(str(n))
    except OSError:
        d = None
    if not d:
        return {}
    hues = [h if h in HUES else {"green": "blue", "violet": "deepblue", "yellow": "orange"}.get(h, "cyan")
            for h in d["hues"]]
    return {"main": hues[0], "accents": (hues[1:] + hues[:1]) or ["cyan"]}


def hsv(h, s, v):
    return np.array(colorsys.hsv_to_rgb((h % 360) / 360.0, s, v))


def ramp(main, accent, tilt_row=0.0, flat=False):
    """16 RGB colours (0..1) for one hue pair; tilt_row shifts the main hue in degrees."""
    hm = HUES[main]
    ha = HUES[accent]
    out = [np.zeros(3)]
    for s in range(1, 16):
        if s < BRIGHT:
            t = s / (BRIGHT - 1)
            out.append(hsv(hm + tilt_row, 1.0 - 0.1 * t, 0.12 + 0.78 * t))
        elif ha is None:
            out.append(hsv(0, 0.0, 0.8 + 0.2 * (s - BRIGHT) / 3))
        else:
            k = (s - BRIGHT) / 3.0
            out.append(hsv(ha, 0.95 - 0.8 * k * k, 0.92 + 0.08 * k))
    if flat and ha is not None:
        out[14] = hsv(ha, 0.7, 1.0)
        out[15] = hsv(ha, 0.5, 1.0)
    else:
        out[15] = np.maximum(out[15], hsv(ha if ha is not None else 0, 0.08, 1.0))
    return np.array(out)


def components(mask):
    """Connected objects of a boolean HxW mask; a one-dot gap is bridged. Returns an int label map (0 = none)."""
    pad = np.zeros_like(mask)
    pad[:, :-1] |= mask[:, 1:]
    pad[:, 1:] |= mask[:, :-1]
    pad[:-1] |= mask[1:]
    pad[1:] |= mask[:-1]
    work = mask | (pad & _bridge(mask))
    lab = np.zeros(mask.shape, dtype=np.int32)
    n = 0
    for y, x in zip(*np.nonzero(work)):
        if lab[y, x]:
            continue
        n += 1
        stack = [(y, x)]
        lab[y, x] = n
        while stack:
            cy, cx = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and work[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        stack.append((ny, nx))
    lab[~mask] = 0
    return lab


def merge_text(lab, max_h=11, max_gap=5):
    """Letters of one text line become one object: small objects on the same rows, a few dots apart, are merged."""
    ids = [i for i in range(1, lab.max() + 1) if (lab == i).any()]
    box = {}
    for i in ids:
        ys, xs = np.nonzero(lab == i)
        box[i] = (ys.min(), ys.max(), xs.min(), xs.max())
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in ids:
        for b in ids:
            if a >= b:
                continue
            ya0, ya1, xa0, xa1 = box[a]
            yb0, yb1, xb0, xb1 = box[b]
            if ya1 - ya0 + 1 > max_h or yb1 - yb0 + 1 > max_h:
                continue
            ov = min(ya1, yb1) - max(ya0, yb0) + 1
            if ov < 0.7 * min(ya1 - ya0 + 1, yb1 - yb0 + 1):
                continue
            if max(xa0, xb0) - min(xa1, xb1) - 1 <= max_gap:
                parent[find(b)] = find(a)
    out = lab.copy()
    for i in ids:
        out[lab == i] = find(i)
    return out


def _bridge(mask):
    """Dots between two lit dots on a line (the one-dot gap)."""
    g = np.zeros_like(mask)
    g[:, 1:-1] |= mask[:, :-2] & mask[:, 2:]
    g[1:-1] |= mask[:-2] & mask[2:]
    return g


def colour_effect(frames, recipe=None):
    """frames: list of HxW uint8 shade arrays (0..15). Returns list of HxWx3 uint8 colour frames."""
    r = dict(DEFAULT)
    r.update(recipe or {})
    accents = r["accents"]
    rows = np.linspace(-1, 1, H)[:, None] * r["tilt"]
    ramps = {a: ramp(r["main"], a) for a in accents}
    prev_lab, prev_col, nxt = None, {}, 0
    out = []
    for sh in frames:
        lab = merge_text(components(sh >= BRIGHT))
        col = {}
        for i in np.unique(lab[lab > 0]):
            area = int((lab == i).sum())
            if area < SPARK:
                col[i] = None
                continue
            inherit = None
            if prev_lab is not None:
                hit = prev_col_at(prev_lab, prev_col, lab == i)
                inherit = hit
            if inherit is None:
                inherit = accents[nxt % len(accents)]
                nxt += 1
            col[i] = inherit
        img = np.zeros((H, W, 3))
        # background ramp with the vertical tilt, per row
        base = ramps[accents[0]]
        for y in range(H):
            rr = ramp(r["main"], accents[0], rows[y, 0])
            m = (sh[y] > 0) & (sh[y] < BRIGHT)
            img[y, m] = rr[sh[y][m]]
        for i, a in col.items():
            m = lab == i
            rp = ramps[a] if a else ramp(r["main"], "white")
            if a and int(m.sum()) >= BIGFLAT:      # a large bright area stays in its hue, white only for small highlights
                rp = ramp(r["main"], a, flat=True)
            img[m] = rp[sh[m]]
        prev_lab, prev_col = lab, col
        out.append((img * 255).astype(np.uint8))
    return out


def prev_col_at(prev_lab, prev_col, mask):
    ids = prev_lab[mask]
    ids = ids[ids > 0]
    if not len(ids):
        return None
    best = np.bincount(ids).argmax()
    return prev_col.get(best)


def load_gif(path, step=1):
    im = Image.open(path)
    raw = []
    for i in range(0, im.n_frames, step):
        im.seek(i)
        g = np.array(im.convert("L"))
        raw.append(g.reshape(H, g.shape[0] // H, W, g.shape[1] // W)[:, g.shape[0] // H // 2, :, g.shape[1] // W // 2])
    top = max(int(r.max()) for r in raw) or 1   # the GIF's brightest dot is shade 15
    return [np.rint(r * 15.0 / top).astype(np.uint8) for r in raw]


def dots(img, scale=6):
    """HD-ish dot render of an HxWx3 uint8 frame: round dots with a soft glow."""
    big = Image.fromarray(img).resize((W * scale, H * scale), Image.NEAREST)
    yy, xx = np.mgrid[0:scale, 0:scale]
    d = np.hypot(yy - (scale - 1) / 2, xx - (scale - 1) / 2) <= scale * 0.42
    mask = np.tile(d, (H, W))[..., None]
    arr = np.array(big) * mask
    glow = Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(scale * 0.9))
    return Image.fromarray(np.clip(arr + 0.6 * np.array(glow), 0, 255).astype(np.uint8))


def sheet(paths, out, moments=4):
    rows = []
    for p in paths:
        n = int(os.path.basename(p).split("_")[1])
        fr = load_gif(p)
        col = colour_effect(fr, effect_recipe(n))
        idx = [int(i * (len(fr) - 1) / max(moments - 1, 1)) for i in range(moments)]
        for i in idx:
            mono = np.stack([np.rint(fr[i] * 255 / 15).astype(np.uint8)] * 3, -1)
            rows.append((dots(mono, 4), dots(col[i], 4)))
    w, h = rows[0][0].size
    img = Image.new("RGB", (2 * w + 8, len(rows) * (h + 4)))
    for k, (a, b) in enumerate(rows):
        img.paste(a, (0, k * (h + 4)))
        img.paste(b, (w + 8, k * (h + 4)))
    img.save(out)


# Per-character rules on the effect's name (game/tools/dmd_colormap.json names): first match wins. Our own choices
# from the film's look: CLU, Rinzler and the Recognizer red/orange, the Users and the Grid blue/cyan, Flynn's
# world amber, danger red.
RULES = [
    (r"clu|recognizer|disc_battle|rinzler", {"main": "red", "accents": ["orange", "amber", "white"], "tilt": 6}),
    (r"tilt|danger|slam", {"main": "red", "accents": ["orange", "white"], "tilt": 0}),
    (r"quorra", {"main": "deepblue", "accents": ["cyan", "white", "orange"], "tilt": 10}),
    (r"light_cycle|disc_multiball|disc_access", {"main": "blue", "accents": ["cyan", "orange"], "tilt": 10}),
    (r"end_of_line", {"main": "deepblue", "accents": ["cyan", "orange", "red"], "tilt": 12}),
    (r"gem", {"main": "amber", "accents": ["orange", "cyan"], "tilt": 8}),
    (r"flynn|arcade|tickets|bump", {"main": "amber", "accents": ["cyan", "orange"], "tilt": 8}),
    (r"zuse|zen|portal|sea_|sea$", {"main": "blue", "accents": ["cyan", "white"], "tilt": 12}),
]


def rule_recipe(n):
    import re
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game", "tools", "dmd_colormap.json")
    try:
        with open(path, encoding="utf-8") as f:
            name = json.load(f)["deffs"].get(str(n), {}).get("name", "")
    except OSError:
        name = ""
    for pat, r in RULES:
        if re.search(pat, name):
            return r
    return {}


def effect_recipe(n):
    """PuP hues first, then the character rules, then the hand-tuned RECIPES."""
    return {**pup_recipe(n), **rule_recipe(n), **RECIPES.get(n, {})}


def epx(img):
    """Scale2x (EPX) of an HxWx3 colour image: each dot 2x2, a diagonal edge one step finer."""
    h, w, _ = img.shape
    p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    c = p[1:-1, 1:-1]
    a, b, d, e = p[:-2, 1:-1], p[1:-1, :-2], p[1:-1, 2:], p[2:, 1:-1]   # up, left, right, down
    eq = lambda x, y: (x == y).all(-1)[..., None]
    out = np.repeat(np.repeat(c, 2, 0), 2, 1).copy()
    quads = ((0, 0, a, b, ~eq(a, d) & ~eq(b, e)),      # top left: up = left, not right, not down
             (0, 1, a, d, ~eq(a, b) & ~eq(d, e)),
             (1, 0, e, b, ~eq(e, d) & ~eq(b, a)),
             (1, 1, e, d, ~eq(e, b) & ~eq(d, a)))
    for dy, dx, u, v, rest in quads:
        out[dy::2, dx::2] = np.where(eq(u, v) & rest, u, c)
    return out


def build_folder(job):
    """(name, deff, frame paths, dst folder, scale, {frame file: {"dots": [k]}} the text drawn live): every frame of
    one effect in colour, as colour_effect makes it, the live text's dots taken out. Returns the colour of each text
    line per frame file, as the first accent's text shade."""
    name, deff, paths, dst, scale, texts = job
    import dmd_color
    frames = []
    for p in paths:
        sh = np.frombuffer(dmd_color.shades(Image.open(p)), dtype=np.uint8).reshape(H, W).copy()
        for k in (texts.get(os.path.basename(p)) or {}).get("dots", ()):
            sh.flat[k] = 0
        frames.append(sh)
    rec = effect_recipe(deff)
    out = colour_effect(frames, rec)
    os.makedirs(dst, exist_ok=True)
    text_rgb = (ramp(rec.get("main", DEFAULT["main"]), (rec.get("accents") or DEFAULT["accents"])[0])[14] * 255).astype(int)
    hexcol = "#%02x%02x%02x" % tuple(text_rgb)
    cols = {}
    for p, img in zip(paths, out):
        n = os.path.basename(p)
        big = epx(img) if scale == 2 else np.repeat(np.repeat(img, scale, 0), scale, 1)
        Image.fromarray(big).save(os.path.join(dst, n), compress_level=6)
        lines = (texts.get(n) or {}).get("lines", [])
        if lines:
            cols[n] = [hexcol for _ in lines]
    return cols


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "sheet":
        args = sys.argv[2:]
        o = args[args.index("--out") + 1]
        sheet([a for a in args if a.endswith(".gif")], o)
    else:
        print(__doc__)
