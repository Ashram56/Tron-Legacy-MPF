#!/usr/bin/env python3
"""game/tron/film_keys.json: the dots of deff 108's film pictures that the ROM's blit skips (RAM key byte 0x10, FUN_00029a20 via bitmap_draw_masked(..., 0x10) at
0x1020388 / 0x1020510 / 0x1020698 / 0x1020820).

The decoded PNGs of the ROM images (assets/mpf_package/media/rom_images_all.zip) clip the value 0x10 to level 15, so a transparent dot of these films looks like a lit one.
This reads the pictures from the ROM (image table RAM 0x36f4c / 0x36f50 -> format header, the RLE row-major type 7 and type 1 decoders FUN_0002a45c / FUN_00029ce4,
the delta types 3 / 9 FUN_0002a868 applied on the previous picture) and writes, per picture, the runs [start, length, ...] (row major) whose value is 0x10.

    TRON_ROM=trn_174h.bin python3 scripts/gen_film_keys.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "assets", "mpf_package", "tools"))
import imgdec as I  # noqa: E402

RANGES = ((0xa7b, 0x1e), (0xa99, 0x1e), (0xa3f, 0x1e), (0xa5d, 0x1e))


def main():
    out = {}
    for first, n in RANGES:
        prev = None
        for k in range(n):
            a, raw = I.decode(first + k, prev)
            prev = bytes(raw)
            flat = a.flatten().tolist()
            runs, i = [], 0
            while i < len(flat):
                if flat[i] == 0x10:
                    j = i
                    while j < len(flat) and flat[j] == 0x10:
                        j += 1
                    runs += [i, j - i]
                    i = j
                else:
                    i += 1
            out[str(first + k)] = runs
    p = os.path.join(HERE, "..", "game", "tron", "film_keys.json")
    json.dump(out, open(p, "w"), separators=(",", ":"))
    print(len(out), "pictures", sum(len(v) // 2 for v in out.values()), "runs")


if __name__ == "__main__":
    main()
