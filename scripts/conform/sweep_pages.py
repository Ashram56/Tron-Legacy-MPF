#!/usr/bin/env python3
"""The attract pages that read the machine's state (the credits record 0x2111008: units, credits) run in the ROM code for every state.
A page routine is the one in the attract table 0x36e10 (gen_code_dmd.attract_pages), run alone like gen_code_dmd.page_frames does.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_pages.py OUT.pkl [PAGE ...]
"""
import os
import pickle
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402
import deff_frames as F  # noqa: E402


def one(job):
    addr, units, credits = job
    G.page_frames  # (the factory custom message page needs its stub: gen_code_dmd.page_frames)
    free = units < 0            # units -1: FREE PLAY on (adj 34 = 1, record 0x2102110: value, then its checksum byte ~sum)
    late = {0x2102110: 1, 0x2102114: 0xfe} if free else None
    try:
        snaps, ticks = F.frames(1, args=[1], ram={**S.game(), **S.credit(max(units, 0), credits)}, init=S.INIT + ((0x22c08, 0), (0x1a9f4, 2)),
                                max_insns=G.PAGE_MAX_INSNS, fn_addr=addr, snap_sleep=True, ram_late=late)
    except Exception:
        return []
    return [bytes(F.mix(a, b)) for (_, _, a, b) in snaps]


def main(out, pages):
    table = dict(G.attract_pages())
    jobs = [(table[p], u, c) for p in pages for u in range(-1, 9) for c in range(0, 4)]
    frames = set()
    with Pool(4) as pool:
        for fs in pool.imap_unordered(one, jobs):
            frames.update(fs)
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(sys.argv[1], [int(a) for a in sys.argv[2:]] or [1, 27, 28, 29])
