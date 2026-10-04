#!/usr/bin/env python3
"""High-resolution DMD media for the optional HD display mode (game/tools/dmd_mode.gd).

The 128x32 DMD art is monochrome with 16 shades. It is upscaled offline with a smoothing + threshold
filter, one shade at a time (level sets): for each shade present, the mask "dot >= shade" is enlarged
with bilinear interpolation, blurred (Gaussian, SIGMA dots) and cut a little under half height (CUT, so
diagonal neighbours stay joined, as pixel art means them) with a one-pixel ramp (anti-aliased edge). Stacking the smoothed masks gives the upscaled picture: dot staircases become
straight or curved edges, one-dot lines keep their width, single dots become round. It needs only
Pillow, runs at build time and is deterministic (no network, no learned model).

The same filter makes the HD fonts (scripts/gen_fonts.py, FONT_SCALE) and the HD frames of the display
effects (scripts/gen_media.py, FRAME_SCALE), so text baked into the effects' pictures and text drawn
live by tron/rom_text.gd look alike.

    .venv/bin/python scripts/dmd_hd.py IN.png OUT.png [scale]     # upscale one picture
"""
import hashlib
import os
import sys

import fsutil  # Windows/OneDrive-safe folder wipes

FONT_SCALE = 16       # HD font atlases: 16 px per dot (crisp up to a 2048 px wide DMD, mipmapped below)
FRAME_SCALE = 8       # HD frames of the display effects: 1024x256 (linear filtering above that)
SIGMA = 0.28          # Gaussian blur, in dots, before the threshold: larger = rounder, loses small details
CUT = 118             # threshold (of 255): a bit under half, so dots touching at a corner stay joined
VERSION = "1"         # bump when the filter changes: the cache (.cache/dmd_hd) keys on it


def smooth_mask(mask, f):
    """mask: 'L' image (0 or 255) -> 'L' image f times larger, smoothed and cut at CUT."""
    from PIL import Image, ImageFilter
    w, h = mask.size
    big = mask.resize((w * f, h * f), Image.BILINEAR).filter(ImageFilter.GaussianBlur(f * SIGMA))
    k = max(1, f // 2)                      # ramp over about one output pixel
    return big.point(lambda p: max(0, min(255, (p - CUT) * k + 128)))


def upscale_levels(img, f, pad=0):
    """img: 'L' image of grey levels (0 = dark) -> 'L' image f times larger, one smoothed level set per
    distinct grey. pad: dots of black added around before smoothing and cut off after (edges then round
    off instead of running straight into the border)."""
    from PIL import Image, ImageChops
    if pad:
        padded = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), 0)
        padded.paste(img, (pad, pad))
        img = padded
    out = Image.new("L", (img.width * f, img.height * f), 0)
    prev = 0
    for v in sorted(c for _, c in (img.getcolors(256) or []) if c):
        mask = img.point(lambda p, v=v: 255 if p >= v else 0)
        step = v - prev
        out = ImageChops.add(out, smooth_mask(mask, f).point(lambda p, s=step: p * s // 255))
        prev = v
    if pad:
        out = out.crop((pad * f, pad * f, out.width - pad * f, out.height - pad * f))
    return out


def grey(img):
    """The grey level of an RGBA/RGB/L picture: its brightest channel (the art is grey; tints are applied
    in Godot), 0 where it is transparent."""
    from PIL import Image, ImageChops
    if img.mode == "L":
        return img
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    lum = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return Image.composite(lum, Image.new("L", img.size, 0), a.point(lambda p: 255 if p >= 128 else 0))


def upscale_frame(img, f=FRAME_SCALE):
    """A display effect frame, drawn over the slide's black background: 'L' picture f times larger."""
    return upscale_levels(grey(img), f)


def upscale_sprite(img, f=FRAME_SCALE):
    """A picture drawn over others (target letters): 'LA', the alpha smoothed like the levels."""
    from PIL import Image
    rgba = img.convert("RGBA")
    alpha = rgba.split()[3].point(lambda p: 255 if p >= 128 else 0)
    return Image.merge("LA", (upscale_levels(grey(rgba), f, pad=1), upscale_levels(alpha, f, pad=1)))


def upscale_glyph(levels, f, outline, transparent=255):
    """A ROM font glyph (rows of levels 0-15, `transparent` = not drawn) -> 'RGBA' glyph f times larger.
    Plain fonts draw their whole cell (level 0 dots are black): the cell stays a sharp rectangle. Outline
    fonts draw a black border around the strokes: the border's outline is smoothed like the strokes."""
    from PIL import Image
    h, w = len(levels), len(levels[0])
    lv = Image.new("L", (w, h), 0)
    op = Image.new("L", (w, h), 0)
    lv.putdata([0 if v == transparent else min(255, v * 17) for row in levels for v in row])
    op.putdata([0 if v == transparent else 255 for row in levels for v in row])
    colour = upscale_levels(lv, f, pad=1)
    if outline or any(v == transparent for row in levels for v in row):
        alpha = upscale_levels(op, f, pad=1)
        alpha = Image.composite(Image.new("L", alpha.size, 255), alpha, colour.point(lambda p: 255 if p else 0))
    else:
        alpha = op.resize((w * f, h * f), Image.NEAREST)
    return Image.merge("RGBA", (colour, colour, colour, alpha))


def cache_key(data, f, kind):
    return hashlib.sha1(b"|".join([VERSION.encode(), str(SIGMA).encode(), str(CUT).encode(), str(f).encode(), kind.encode(),
                                   data])).hexdigest()


def upscale_file(job):
    """(src, dst, f, kind, cache_dir): upscale the PNG src into dst ('frame' or 'sprite'), through the
    cache (a PNG per source content, so a rebuild only redoes what changed). Returns dst."""
    from PIL import Image
    import shutil
    src, dst, f, kind, cache = job
    with open(src, "rb") as fp:
        data = fp.read()
    cached = os.path.join(cache, cache_key(data, f, kind) + ".png") if cache else None
    if cached and os.path.exists(cached):
        shutil.copyfile(cached, dst)
        return dst
    img = Image.open(src)
    out = upscale_sprite(img, f) if kind == "sprite" else upscale_frame(img, f)
    out.save(dst, optimize=False, compress_level=6)
    if cached:
        os.makedirs(cache, exist_ok=True)
        tmp = cached + ".%d.tmp" % os.getpid()
        shutil.copyfile(dst, tmp)
        fsutil.replace(tmp, cached)
    return dst


def upscale_files(jobs, processes=None):
    """Runs upscale_file over jobs, in parallel when there are many."""
    jobs = list(jobs)
    if len(jobs) < 8:
        return [upscale_file(j) for j in jobs]
    import multiprocessing
    with multiprocessing.Pool(processes or os.cpu_count() or 2) as pool:
        return pool.map(upscale_file, jobs, chunksize=4)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    from PIL import Image
    f = int(argv[2]) if len(argv) > 2 else FRAME_SCALE
    upscale_frame(Image.open(argv[0]), f).save(argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
