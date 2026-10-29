#!/usr/bin/env python3
"""The mystery award (Flynn's Arcade reel, deff 105) icons: export them for an image generator, import the redrawn ones.

    python scripts/pup/award_sprites.py export [OUT_DIR]     # the 12 icons, 16x, on black, one file each + the prompt
    python scripts/pup/award_sprites.py import IN_DIR        # IN_DIR/award_NN*.png (NN = 01..12) -> game/hd_art/deff_105/
    python scripts/pup/award_sprites.py clips [PACK] [--force]   # the characters' topper icons and frames of the PuP clips ->
                                                                 # game/hd_art/deff_105/ (the files already there stay unless --force)

The game draws game/hd_art/deff_105/award_NN.png (RGBA, 464x352 = 29x22 dots at 16x; any size of that 29:22 shape works)
in place of the ROM's icon when the HD DMD is on, in its own colours: bright while the award blinks, dimmed otherwise
(tron/dmd_effect.gd _arcade). No file: the ROM's icon, upscaled, in the DMD's blue. TRON_AWARD_ART=0 turns the redrawn
icons off. The black of a picture becomes transparent on import (alpha from the brightness), so a generator that cannot
make a transparent background can paint on black.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import pup_art  # noqa: E402

np = None                    # numpy, loaded when a picture is made (pup_art.use_numpy: a Python without it gets it with pip)


def load_numpy():
    global np
    if np is None:
        if not pup_art.use_numpy():
            sys.exit("award_sprites: numpy is needed")
        import numpy
        np = numpy
SRC = os.path.join(ROOT, "game", "media", "dmd", "deff_105")
DST = os.path.join(ROOT, "game", "hd_art", "deff_105")        # the owner's redrawn icons (tracked) and `import`
MADE = os.path.join(pup_art.art_dir(), "deff_105")        # icons made from the pack's clips, linked beside them
NAMES = ("500K", "ADV. GEM", "ADV. CLU", "ADV. ZUSE", "ADV. QUORRA", "ADV. DISC", "ADV. LIGHT CYCLE",
         "ADV. RECOGNIZER", "ADV. SEA OF SIMUL.", "MORE TIME", "LIGHT EXTRA BALL", "LIGHT SPECIAL")
BLUE = (42, 108, 255)
SIZE = (464, 352)

PROMPT = """Redraw this {w}x{h} pixel icon as a clean, detailed, high resolution icon for the Tron Legacy pinball's dot matrix
display. Keep the same subject ({name}) and the same silhouette and the same composition, in the Tron Legacy style: neon
lines on black, thin glowing edges, electric blue (#2a6cff, cyan highlights #22b8ff) as the main colour; the character or
object may use Tron's orange (#ff7a1a) or white where it belongs. Output a 464x352 PNG (aspect 29:22), the icon centred
with a margin of about 6%, on a pure black background (#000000), no text, no frame, no border, nothing else in the
picture. The icon is shown very small (about 29x22 millimetres) on a dark screen: bold shapes, high contrast, no fine detail."""


def export(out):
    load_numpy()
    os.makedirs(out, exist_ok=True)
    lines = ["# Mystery award icons for Gemini", "",
             "One file per icon: `award_NN_<name>.png` (the ROM's 29x22 dots, 16x, on black, in Tron blue). For each one, send the file with the prompt below (change the name); ask for a 464x352 PNG on pure black. Save the results as `award_NN.png` (NN = 01..12) in one folder and run `python scripts/pup/award_sprites.py import THAT_FOLDER`.",
             "", "| file | award |", "|---|---|"]
    for i, name in enumerate(NAMES, 1):
        p = os.path.join(SRC, "award_%02d_a.png" % i)
        if not os.path.exists(p):
            continue
        im = np.array(Image.open(p).convert("L"), dtype=float) / 255.0
        rgb = (im[..., None] * np.array(BLUE)).astype(np.uint8)
        big = Image.fromarray(rgb).resize((im.shape[1] * 16, im.shape[0] * 16), Image.NEAREST)
        canvas = Image.new("RGB", SIZE, (0, 0, 0))
        canvas.paste(big, ((SIZE[0] - big.width) // 2, (SIZE[1] - big.height) // 2))
        fn = "award_%02d_%s.png" % (i, name.lower().replace(". ", "_").replace(" ", "_").replace(".", ""))
        canvas.save(os.path.join(out, fn))
        lines.append("| %s | %s |" % (fn, name))
    lines += ["", "## Prompt", "", "```", PROMPT.format(w=29, h=22, name="<the award's name>"), "```", ""]
    with open(os.path.join(out, "gemini.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("exported to", out)


def fit_content(im, pad=0.03):
    """Crop to what is drawn (alpha) and fit it back into the icon's 29:22 box: a subject that sits small in a picture
    (a ring and an arrow in a black field) would leave the reel's slot mostly empty."""
    a = np.array(im.getchannel("A"))
    ys, xs = np.nonzero(a > 40)
    if not len(xs):
        return im
    w, h = im.size
    px, py = int(pad * w), int(pad * h)
    box = (max(xs.min() - px, 0), max(ys.min() - py, 0), min(xs.max() + px + 1, w), min(ys.max() + py + 1, h))
    crop = im.crop(box)
    k = min(SIZE[0] / crop.width, SIZE[1] / crop.height)
    crop = crop.resize((round(crop.width * k), round(crop.height * k)), Image.LANCZOS)
    out = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    out.paste(crop, ((SIZE[0] - crop.width) // 2, (SIZE[1] - crop.height) // 2), crop)
    return out


def fade_cut_edges(im, share=0.08):
    """An icon whose picture runs off an edge (a ring cut by the frame) would show a flat cut: that edge fades out instead."""
    a = np.array(im.getchannel("A"), dtype=float)
    h, w = a.shape
    ramp = lambda n: np.clip(np.arange(n) / (share * n), 0, 1)
    m = np.ones((h, w))
    if a[:3].mean() > 25: m *= ramp(h)[:, None]
    if a[-3:].mean() > 25: m *= ramp(h)[::-1][:, None]
    if a[:, :3].mean() > 25: m *= ramp(w)[None, :]
    if a[:, -3:].mean() > 25: m *= ramp(w)[::-1][None, :]
    out = np.array(im)
    out[..., 3] = (out[..., 3] * m).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def import_dir(src):
    load_numpy()
    os.makedirs(DST, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(src)):
        if not fn.lower().startswith("award_") or not fn.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        try:
            i = int(fn[6:8])
        except ValueError:
            continue
        im = Image.open(os.path.join(src, fn)).convert("RGBA")
        if im.getchannel("A").getextrema()[0] == 255:       # opaque: the black becomes transparent
            rgb = np.array(im.convert("RGB"), dtype=float)
            a = np.clip(rgb.max(axis=2) / 255.0 * 1.6, 0, 1)
            out = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
            with np.errstate(divide="ignore", invalid="ignore"):
                col = np.where(a[..., None] > 0, rgb / np.maximum(a[..., None], 1e-3), 0)
            out[..., :3] = np.clip(col, 0, 255).astype(np.uint8)
            out[..., 3] = (a * 255).astype(np.uint8)
            im = Image.fromarray(out, "RGBA")
        im = fade_cut_edges(fit_content(im))
        im.save(os.path.join(DST, "award_%02d.png" % i))
        n += 1
    print(n, "icons ->", DST)


# award id -> ("icon", name of game/media/dmd_clip/icon_<name>.png) or ("clip", clip in the pack, seconds)
CLIP_ART = {2: ("icon", "gem"), 3: ("icon", "clu"), 4: ("icon", "zuse"), 5: ("icon", "quorra"),
            6: ("clip", "DiscBattleReady/DiscWarsReady.mp4", 3.64), 7: ("clip", "LightCycleMB/LightCycleMB.mp4", 6.25),
            8: ("clip", "Recognizer/Recognizer1.mp4", 2.3), 9: ("clip", "SeaofSimulation/SeaOfSimulation.mp4", 11.4),
            11: ("clip", "ExtraBall/ExtraBall.mp4", 2.2)}
CLIP_BOX = (896, 680, 512, 168)      # w, h, x, y of the 1920x1080 frame inside the clips' neon frame and title card


def feather(im, share=0.07):
    """Soft edges: alpha falls to 0 over `share` of the size, so a photo does not show as a hard rectangle."""
    w, h = im.size
    ax = np.minimum(np.arange(w), np.arange(w)[::-1]) / (share * w)
    ay = np.minimum(np.arange(h), np.arange(h)[::-1]) / (share * h)
    a = np.clip(np.minimum(ay[:, None], ax[None, :]), 0, 1)
    out = np.array(im.convert("RGBA"))
    out[..., 3] = (out[..., 3] * a).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def from_clips(pack, force=False):
    import shutil
    import subprocess
    import tempfile
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("no ffmpeg (set FFMPEG)")
    os.makedirs(MADE, exist_ok=True)
    icons = os.path.join(pup_art.art_dir(), "dmd_clip")
    todo = [i for i in sorted(CLIP_ART) if force or not any(os.path.exists(os.path.join(d, "award_%02d.png" % i)) for d in (DST, MADE))]
    if not todo:
        print("award icons: all there (redrawn by the owner or made before)")
        return
    load_numpy()
    for i, spec in sorted(CLIP_ART.items()):
        if i not in todo:
            continue                 # a redrawn icon (import) or an earlier run stays
        if spec[0] == "icon":
            src = os.path.join(icons, "icon_%s.png" % spec[1])
            if not os.path.exists(src):
                print("missing", src, "(run scripts/pup/gen_dmd_clips.py)")
                continue
            ic = Image.open(src).convert("RGBA")
            k = min(SIZE[0] / ic.width, SIZE[1] / ic.height)
            ic = ic.resize((round(ic.width * k), round(ic.height * k)), Image.LANCZOS)
            im = Image.new("RGBA", SIZE, (0, 0, 0, 0))
            im.paste(ic, ((SIZE[0] - ic.width) // 2, (SIZE[1] - ic.height) // 2), ic)
        else:
            w, h, x, y = CLIP_BOX
            with tempfile.TemporaryDirectory() as tmp:
                png = os.path.join(tmp, "f.png")
                subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", str(spec[2]), "-i", os.path.join(pack, spec[1]), "-frames:v", "1",
                                "-vf", "crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos" % (w, h, x, y, SIZE[0], SIZE[1]), png], check=True)
                im = feather(Image.open(png).convert("RGB"))
        im.save(os.path.join(MADE, "award_%02d.png" % i))
    print(len(todo), "icons ->", MADE)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "captures", "award_sprites"))
    elif sys.argv[1:2] == ["clips"]:
        args = [a for a in sys.argv[2:] if a != "--force"]
        from_clips(args[0] if args else os.path.join(ROOT, "pup_pack", "trn_174h"), "--force" in sys.argv)
    elif len(sys.argv) == 3 and sys.argv[1] == "import":
        import_dir(sys.argv[2])
    else:
        sys.exit(__doc__)
