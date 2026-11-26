#!/usr/bin/env python3
"""SET DATE/TIME (routine 0x01045b44, draw 0xd814) run in the ROM code for a list of dates, 12 / 24 h, and the edited field.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_datetime.py OUT.pkl
The RTC read (0xd244) is a stub returning a struct (year u16, weekday, month, day, hour, minute, second); adj 3 (time format) is read
through adj_get 0xe90 from the adjustment record, set here with ram_late.
"""
import os
import pickle
import struct
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import deff_unicorn as D  # noqa: E402
import deff_state as S  # noqa: E402
import deff_frames as F  # noqa: E402

TICKS = 64


def one(job):
    (year, month, day, hour, minute, sec), twelve = job
    D.STUBS.clear()

    def rtc(mu):
        from unicorn.arm_const import UC_ARM_REG_R0
        mu.mem_write(mu.reg_read(UC_ARM_REG_R0), struct.pack("<HBBBBBB", year, 3, month, day, hour, minute, sec))
        return 1
    D.STUBS[0xd244] = rtc
    try:
        snaps, ticks = F.frames(1, args=[], ram=S.game(), init=S.INIT, max_insns=1500000, fn_addr=0x1045b44, snap_sleep=True,
                                ram_late=None if twelve else {0x2102018: 1, 0x210201c: 0xfe})
    except Exception as e:
        print("fail", job, e)
        return job, []
    return job, [(t, bytes(F.mix(a, b))) for t, (_, _, a, b) in zip(ticks, snaps)]


def mine(job, hidden):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game"))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import gen_fonts
    from tron import rom_datetime as R
    index, get, fonts = gen_fonts.decode_all()
    canvas = [[None] * 128 for _ in range(32)]
    rec, twelve = job
    for it in R.draw(list(rec), twelve, 26, hidden):
        gen_fonts.render(get, fonts[it["f"]], it["t"], it["x"], it["y"], it["a"], canvas)
    return [(canvas[y][x] or 0) for y in range(32) for x in range(128)]


if __name__ == "__main__":
    jobs = [((2026, m, 26, 19, 32, 51), True) for m in range(1, 13)]
    jobs += [((2024, 2, 29, h, 5, 9), tw) for h in (0, 1, 11, 12, 13, 23) for tw in (True, False)]
    jobs += [((2000, 1, 1, 0, 0, 0), False), ((2099, 12, 31, 23, 59, 59), True)]
    bad = 0
    with Pool(4) as pool:
        for job, fr in pool.imap_unordered(one, jobs):
            body = {f[1][128 * 22:128 * 28] if False else f[1] for f in fr}
            # the line is rows 22-28; compare the bottom part of each frame
            lines = {bytes(f[128 * 20:128 * 32]) for f in body}
            seen = {h: bytes(mine(job, h)[128 * 20:128 * 32]) in lines for h in (None, 1, 2, 3, 4, 5, 6)}
            ok = seen[None] and any(seen[h] for h in (1, 2, 3, 4, 5, 6))
            print(job, len(fr), seen, "OK" if ok else "DIFF")
            bad += not ok
    print("bad", bad)
