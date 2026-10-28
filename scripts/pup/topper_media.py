#!/usr/bin/env python3
"""The remote topper's videos: the PuP Pack's topper playlists, copied for the Raspberry Pi and sent to it.

    python scripts/pup/topper_media.py                        # pup_media/topper/: the files and manifest.json
    python scripts/pup/topper_media.py --push pi@pup-topper.local   # ... and copied to the Pi (rsync or scp, SSH)
    python scripts/pup/topper_media.py --dry-run              # what would be copied or re-encoded

The topper's playlists are the ones its PuP screens (13 and 14) play: their default backgrounds (screens.pup) and
every triggers.pup row on those screens. Videos the Pi's hardware decoder plays (H.264, 8-bit 4:2:0, at most
1920x1080 and 30 fps) are copied as they are; any other is re-encoded to that, and the run lists which and why.
Re-runs only redo changed files; --push sends only what changed (rsync). docs/pup/remote_topper.md has the rest.
Needs ffmpeg on the PATH (or FFMPEG=<path>) to read the videos; standard library otherwise.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "game"))
from tron_pup import pupfiles, settings  # noqa: E402

SCREENS = (13, 14)
VIDEO = (".mp4", ".m4v", ".mov", ".avi", ".wmv", ".webm", ".mkv", ".f4v")
PI_PROFILES = ("baseline", "constrained baseline", "main", "high")
MAX_W, MAX_H, MAX_FPS = 1920, 1080, 30.5
STREAM = re.compile(r"Stream #\S+.*?Video: (\w+)(?: \(([^)]*)\))?[^,]*, (\w+)")
SIZE = re.compile(r"Video:.*?, (\d{2,5})x(\d{2,5})")
FPS = re.compile(r"Video:.*?, ([\d.]+) fps")
DEST = "pup-topper/media"                     # on the Pi, in the user's home


def topper_playlists(pack, screens=SCREENS):
    lists = set()
    for num, row in pupfiles.load_screens(pack).items():
        if num in screens and row["playlist"]:
            lists.add(row["playlist"].lower())
    for row in pupfiles.load_triggers(pack):
        if row.screen in screens and row.active and row.playlist:
            lists.add(row.playlist.lower())
    return lists


def pack_files(pack, playlists):
    """{pack path ("Folder/File.mp4"): absolute path} of every file in those playlist folders."""
    files = {}
    for folder in sorted(os.listdir(pack)):
        path = os.path.join(pack, folder)
        if folder.lower() in playlists and os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if os.path.isfile(os.path.join(path, name)):
                    files[folder + "/" + name] = os.path.join(path, name)
    return files


def find_ffmpeg():
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("needs ffmpeg: install it (apt install ffmpeg, brew install ffmpeg, winget install ffmpeg) "
                         "or set FFMPEG")
    return exe


def probe(ffmpeg, path):
    err = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True,
                         errors="replace").stderr
    info = {}
    m = STREAM.search(err)
    if m:
        info["codec"], info["profile"], info["pix_fmt"] = m.group(1), (m.group(2) or "").lower(), m.group(3)
    m = SIZE.search(err)
    if m:
        info["w"], info["h"] = int(m.group(1)), int(m.group(2))
    m = FPS.search(err)
    if m:
        info["fps"] = float(m.group(1))
    return info


def why_reencode(info):
    """Why the Pi's decoder can't take this video ("" = it can)."""
    if not info.get("codec"):
        return "no video stream found"
    if info["codec"] != "h264":
        return "codec " + info["codec"]
    if info.get("profile") and info["profile"] not in PI_PROFILES:
        return "H.264 profile " + info["profile"]
    if info.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
        return "pixel format " + str(info.get("pix_fmt"))
    if info.get("w", 0) > MAX_W or info.get("h", 0) > MAX_H:
        return "{}x{}".format(info["w"], info["h"])
    if info.get("fps", 0) > MAX_FPS:
        return "{:g} fps".format(info["fps"])
    return ""


def reencode(ffmpeg, src, dst, info):
    scale = "scale='min({w},iw)':'min({h},ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
        .format(w=MAX_W, h=MAX_H)
    if info.get("fps", 0) > MAX_FPS:
        scale += ",fps=30"
    tmp = dst + ".part.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vf", scale,
                    "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-preset", "medium", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, dst)


def up_to_date(src, dst):
    return os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)


def build(pack, out, dry_run=False, screens=SCREENS):
    playlists = topper_playlists(pack, screens)
    files = pack_files(pack, playlists)
    if not files:
        raise SystemExit("no topper media in {} (playlists: {})".format(pack, ", ".join(sorted(playlists)) or "none"))
    ffmpeg = find_ffmpeg()
    manifest, copied, encoded = {}, [], []
    for key, src in files.items():
        ext = os.path.splitext(key)[1].lower()
        info = probe(ffmpeg, src) if ext in VIDEO else {}
        reason = why_reencode(info) if ext in VIDEO else ""
        out_key = os.path.splitext(key)[0] + ".mp4" if reason else key
        dst = os.path.join(out, out_key)
        manifest[key] = {"out": out_key}
        if reason:
            manifest[key]["reencoded"] = reason
            encoded.append((key, reason))
        else:
            copied.append(key)
        if dry_run or up_to_date(src, dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if reason:
            print("re-encoding {} ({})".format(key, reason))
            reencode(ffmpeg, src, dst, info)
        else:
            shutil.copy2(src, dst)
    if not dry_run:
        with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"pack": os.path.basename(pack), "screens": list(screens), "files": manifest}, f, indent=1)
    print("{} files from playlists {}: {} copied as they are, {} re-encoded".format(
        len(files), ", ".join(sorted(playlists)), len(copied), len(encoded)))
    for key, reason in encoded:
        print("  re-encoded: {} ({})".format(key, reason))
    return manifest


def push(out, target):
    """Copy the media to the Pi over SSH: rsync (only what changed, removes what is gone), else scp."""
    host, _, path = target.partition(":")
    path = path or DEST
    subprocess.run(["ssh", host, "mkdir -p " + path], check=True)
    if shutil.which("rsync"):
        cmd = ["rsync", "-rt", "--delete", "--info=stats1", out.rstrip("/\\") + "/", "{}:{}/".format(host, path)]
    else:
        print("no rsync here: scp copies everything every time")
        cmd = ["scp", "-r"] + [os.path.join(out, name) for name in sorted(os.listdir(out))] + \
              ["{}:{}/".format(host, path)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def main(argv=None):
    cfg = settings.load()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pack", default=settings.pack_dir(cfg), help="the PuP Pack folder (default: game/pup.cfg's)")
    ap.add_argument("--out", default=os.path.join(ROOT, "pup_media", "topper"))
    ap.add_argument("--push", metavar="[USER@]HOST[:PATH]",
                    help="copy to the Pi over SSH (default path ~/{})".format(DEST))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.exists(os.path.join(a.pack, "triggers.pup")):
        raise SystemExit("no PuP Pack at {} (git submodule update --init pup_pack, or --pup-zip)".format(a.pack))
    build(a.pack, a.out, a.dry_run)
    if a.push and not a.dry_run:
        push(a.out, a.push)


if __name__ == "__main__":
    main()
