#!/usr/bin/env python3
"""The GRAND CHAMPION attract page (routine 0x0100075c after the high score reset FUN_0001a9f4(1), "G S" 75,000,000), which the stored page frames
(assets/rom_data/dmd_code/deff_001_pages) do not hold; for code_conform.py --extra.

    TRON_ROM=trn_174h.bin python scripts/conform/sweep_gc.py OUT.pkl
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import gen_code_dmd as G  # noqa: E402
import deff_state as S  # noqa: E402
import deff_frames as F  # noqa: E402

snaps, _ = F.frames(1, args=[1], ram={**S.game(), **S.credit(0, 0)}, init=S.INIT + ((0x22c08, 0), (0x1a9f4, 1)), max_insns=G.PAGE_MAX_INSNS,
                    fn_addr=0x0100075c, snap_sleep=True)
pickle.dump({bytes(F.mix(a, b)) for (_, _, a, b) in snaps}, open(sys.argv[1], "wb"))
print("done", len(snaps))
