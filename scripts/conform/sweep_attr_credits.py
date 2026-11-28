#!/usr/bin/env python3
"""The attract credits page (attr_page_credits 0x01000128: FUN_00004ff4(record 1) = "CREDITS %d" / "CREDITS %d/%d" / "CREDITS %d %d/%d", the font fitted by
FUN_00029248) of the ROM code for every credits record (units 0..8, whole credits 0..3, as sweep_credits.py does for effect 10); for code_conform.py --extra.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_attr_credits.py OUT.pkl
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402
import deff_frames as F  # noqa: E402

frames = set()
for u in range(0, 9):
    for c in range(0, 4):
        snaps, _ = F.frames(1, args=[1], ram={**S.game(), **S.credit(u, c)}, init=S.INIT, max_insns=G.PAGE_MAX_INSNS, fn_addr=0x01000128, snap_sleep=True)
        frames |= {bytes(F.mix(a, b)) for (_, _, a, b) in snaps}
pickle.dump(frames, open(sys.argv[1], "wb"))
print("done", len(frames))
