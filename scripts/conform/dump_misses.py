#!/usr/bin/env python3
"""The distinct game frames (columns 41-127) that no frame of the ROM code run reproduces, saved as pictures (4x) named by wall time and the effect running.

    python scripts/conform/dump_misses.py OUTDIR [--extra SWEEP.pkl ...] NAME.dmd [NAME.dmd ...]

Same comparison as code_conform.py (the code set plus the --extra sweeps); NAME.jsonl beside a dump attributes each frame to the last deff_start / deff_args."""
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import code_conform as C  # noqa: E402


def main(argv):
    from PIL import Image
    out, paths, extra = argv[0], [], []
    i = 1
    while i < len(argv):
        if argv[i] == "--extra":
            extra.append(argv[i + 1])
            i += 2
        else:
            paths.append(argv[i])
            i += 1
    os.makedirs(out, exist_ok=True)
    full, cols = C.code_set()
    for e in extra:
        for f in pickle.load(open(e, "rb")):
            cols[bytes(f[y * 128 + x] for y in range(32) for x in range(41, 128))] = e
    seen, n = set(), 0
    for p in paths:
        jl = p[:-4] + ".jsonl"
        starts = [(e["wall"], e["id"]) for e in map(json.loads, open(jl)) if e.get("ev") in ("deff_start", "deff_args") and "wall" in e] if os.path.exists(jl) else []
        for t, f in C.game_frames(p):
            if f in seen:
                continue
            seen.add(f)
            c = bytes(f[y * 128 + x] for y in range(32) for x in range(41, 128))
            if c in cols:
                continue
            cur = [i for w, i in starts if w <= t]
            im = Image.new("L", (128, 32))
            im.putdata([v * 17 for v in f])
            name = "{}_{:09.3f}_e{}_{}.png".format(os.path.basename(p)[:-4], t, cur[-1] if cur else "none", n)
            im.resize((512, 128), Image.NEAREST).save(os.path.join(out, name))
            n += 1
    print("{} missed frames saved in {}".format(n, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
