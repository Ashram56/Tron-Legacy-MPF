#!/usr/bin/env python3
"""Compare the game's classic DMD dump (game/tools/dmd_dump.gd, godot_run.py) with the frames the ROM's own code draws
(assets/rom_data/dmd_code, tools/gen_code_dmd.py): how many distinct frames of the game are a frame of the code run (all columns, and
columns 41-127 that the status panel does not touch), listing the effects whose frames the game does not reproduce.

    python scripts/conform/code_conform.py NAME.dmd [NAME.dmd ...]
"""
import glob
import os
import struct
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


def code_set():
    from PIL import Image
    full, cols, owner = {}, {}, {}
    for png in glob.glob(os.path.join(ROOT, "assets", "rom_data", "dmd_code", "**", "*.png"), recursive=True):
        im = Image.open(png).convert("L")
        b = bytes(v // 17 for v in im.get_flattened_data())
        full[b] = png
        cols[bytes(b[y * 128 + x] for y in range(32) for x in range(41, 128))] = png
    return full, cols


def game_frames(path):
    data = open(path, "rb").read()
    i, out = 0, []
    while i + 20 <= len(data):
        t, w, h, d = struct.unpack_from("<dIII", data, i) if False else struct.unpack_from("<dIII", data, i)
        i += 20
        out.append((t, data[i:i + w * h]))
        i += w * h
    return out


def main(paths):
    full, cols = code_set()
    seen, hit_full, hit_cols, miss = set(), 0, 0, []
    for p in paths:
        for t, f in game_frames(p):
            if f in seen:
                continue
            seen.add(f)
            if f in full:
                hit_full += 1
            c = bytes(f[y * 128 + x] for y in range(32) for x in range(41, 128))
            if c in cols:
                hit_cols += 1
            else:
                miss.append((t, p))
    print("distinct game frames: {}; found in the code run: {} (all columns), {} (columns 41-127)".format(len(seen), hit_full, hit_cols))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
