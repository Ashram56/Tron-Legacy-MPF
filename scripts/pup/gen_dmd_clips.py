#!/usr/bin/env python3
"""The PuP Pack's clips cut for the DMD: game/media/dmd_clip/deff_NNN_vK.mp4 (the part of the clip the plan says, cropped
to the DMD's 4:1 shape, 640x160, stretched over the effect's length or at its own speed), the characters' HD icons
(icon_<name>.png, the topper's face in its hexagonal frame, cut out), and clips.json, which tron/dmd_effect.gd reads.

    python scripts/pup/gen_dmd_clips.py [--pack DIR] [--force]

The plan (which clip, which part, which crop) is scripts/pup/dmd_clip_plan.json (dmd_clip_plan.py). --pack is the PuP
Pack's folder with the videos (default: pack_dir of game/pup.cfg, pup_pack/trn_174h). Needs ffmpeg (FFMPEG, the PATH, or
imageio-ffmpeg in the venv). Without the pack nothing is made and the game draws the ROM's frames as before. The output
holds third-party media: it is git-ignored (private repository or not).
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import toolchain as tc  # noqa: E402

sys.path.insert(0, tc.GAME)
from tron_pup import settings  # noqa: E402
import pup_art  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

PLAN = os.path.join(HERE, "dmd_clip_plan.json")
OUT = os.path.join(pup_art.art_dir(), "dmd_clip")      # with the pack (pup_media), linked into game/media/dmd_clip
SIZE = (1280, 320)
FPS = 30


def find_ffmpeg():
    candidates = [os.environ.get("FFMPEG"), shutil.which("ffmpeg")]
    py = tc.venv_python()
    if os.path.exists(py):
        out = subprocess.run([py, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"], capture_output=True, text=True)
        candidates.append(out.stdout.strip() if out.returncode == 0 else None)
    for exe in candidates:
        if exe and (os.path.exists(exe) or shutil.which(exe)):
            return exe
    raise SystemExit("no ffmpeg: install it, or `.venv/bin/pip install imageio-ffmpeg` (Windows: .venv\\Scripts\\pip), or set FFMPEG")


def encoder(ffmpeg):
    encs = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if "libx264" in encs:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    return ["-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p"]


def make_clip(ffmpeg, enc, src, v, ms, dst):
    span = (v["hi"] - v["lo"]) * v["seconds"]
    x0, y0, w, h = v["crop"]
    k = (ms / 1000.0) / span if span > 0 else 1.0
    vf = "crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos,setpts=PTS*%.5f,fps=%d" % (w, h, x0, y0, SIZE[0], SIZE[1], k, FPS)
    cmd = [ffmpeg, "-v", "error", "-y", "-ss", "%.3f" % (v["lo"] * v["seconds"]), "-t", "%.3f" % span, "-i", src, "-vf", vf,
           "-an", "-t", "%.3f" % (ms / 1000.0)] + enc + ["-movflags", "+faststart", dst]
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def hexagon(size):
    """Alpha mask of a pointy-top regular hexagon filling `size` (w, h), antialiased."""
    w, h = size
    s = 4
    r = min(h / 2.0, w / math.sqrt(3))
    cx, cy = w / 2.0, h / 2.0
    pts = [(cx + r * math.cos(math.radians(a)) * 1.0, cy + r * math.sin(math.radians(a))) for a in (-90, -30, 30, 90, 150, 210)]
    m = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(m).polygon([(x * s, y * s) for x, y in pts], fill=255)
    return m.resize((w, h), Image.LANCZOS)


def make_icon(ffmpeg, pack, src, dst):
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "f.png")
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", str(src["t"]), "-i", os.path.join(pack, src["clip"]), "-frames:v", "1", f],
                       check=True)
        im = Image.open(f).convert("RGBA").crop(tuple(src["box"]))
    im.putalpha(hexagon(im.size))
    im.thumbnail((256, 256), Image.LANCZOS)
    im.save(dst)


def main():
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else settings.pack_dir(settings.load())
    force = "--force" in sys.argv
    if not os.path.isdir(pack) or not os.path.exists(PLAN):
        print("DMD clips: no PuP Pack at %s (or no plan): the DMD keeps the ROM's frames" % pack)
        return 0
    plan = json.load(open(PLAN, encoding="utf-8"))
    ffmpeg = find_ffmpeg()
    enc = encoder(ffmpeg)
    os.makedirs(OUT, exist_ok=True)
    clips, made, missing = {}, 0, 0
    for n, eff in sorted(plan["effects"].items(), key=lambda kv: int(kv[0])):
        files = []
        for k, v in enumerate(eff["variants"]):
            src = os.path.join(pack, v["clip"])
            dst = os.path.join(OUT, "deff_%03d_v%d.mp4" % (int(n), k))
            if not os.path.exists(src):
                missing += 1
                continue
            if force or not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(PLAN):
                if not make_clip(ffmpeg, enc, src, v, v.get("ms", eff["ms"]), dst):
                    print("  ffmpeg failed: " + dst)
                    continue
                made += 1
            still = dst[:-4] + ".jpg"       # the clip's first picture: shown while the player opens the video (tron/dmd_screen.gd)
            if force or not os.path.exists(still) or os.path.getmtime(still) < os.path.getmtime(dst):
                subprocess.run([ffmpeg, "-v", "error", "-y", "-i", dst, "-frames:v", "1", "-q:v", "3", still], capture_output=True)
            files.append("res://media/dmd_clip/" + os.path.basename(dst))
        if files:
            clips["deff_%03d" % int(n)] = {"files": files, "loop": eff["loop"], "ms": eff["ms"]}
    icons = {}
    for name, src in plan["icon_sources"].items():
        dst = os.path.join(OUT, "icon_%s.png" % name)
        if os.path.exists(os.path.join(pack, src["clip"])):
            if force or not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(PLAN):
                make_icon(ffmpeg, pack, src, dst)
                made += 1
            icons[name] = "res://media/dmd_clip/icon_%s.png" % name
    icon_of = {"deff_%03d" % int(n): icons[c] for n, c in plan["icons"].items() if c in icons}
    with open(os.path.join(OUT, "clips.json"), "w", encoding="utf-8") as f:
        json.dump({"clips": clips, "icons": icon_of}, f, indent=1, sort_keys=True)
    print("DMD clips: %d effects, %d icon effects, %d files made, %d clips missing in the pack" % (len(clips), len(icon_of), made, missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
