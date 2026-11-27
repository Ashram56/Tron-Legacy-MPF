#!/usr/bin/env python3
"""The draw calls an effect's ROM routine makes (Unicorn), flip by flip, and the frame each flip shows: the reference for the game-side DMD engine
(game/tron/rom_deff*.py) whose primitives are checked call by call.

    TRON_ROM=trn_174h.bin python scripts/conform/deff_trace.py EFFECT [ARG ...]      (prints the calls)

trace(effect, args, ram, max_insns) -> (frames, flips): frames = [(tick, 4096-byte pages, ...)] as deff_frames.frames, flips = [[(name, regs, stack), ...] per flip]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "tools"))
import deff_frames as F  # noqa: E402
import deff_unicorn as D  # noqa: E402
import gen_code_dmd as G  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP  # noqa: E402

# The draw primitives (ROM address: name), game code 0x0002xxxx: see docs/dmd_engine.md for what each does.
PRIMS = {0x276d0: "clear_page", 0x27274: "begin_frame", 0x27400: "fill_page", 0x2b378: "blit_image", 0x2b424: "blit_image_pal",
         0x28ca8: "text_msg", 0x28d5c: "text_printf", 0x28e48: "text_msg_font", 0x2b554: "pal_new", 0x2b56c: "pal_set",
         0x241a0: "flip_wait", 0x24230: "flip_wait2", 0x27830: "show_pages", 0x27a70: "flip_ticks"}


def trace(effect, args=None, ram=None, max_insns=4000000, rng=None, real_show_pages=False, **recipe):
    calls = []
    orig = D.build

    def build():
        mu = orig()

        def hook(mu, addr, size, ud):
            sp = mu.reg_read(UC_ARM_REG_SP)
            regs = [mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            st = [struct.unpack("<I", bytes(mu.mem_read(sp + 4 * i, 4)))[0] for i in range(4)]
            calls.append((D.STATE["tick"] if D.STATE else 0, PRIMS[addr], regs, st))
        for a in PRIMS:
            mu.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)
        return mu
    D.build = build
    try:
        r = G.recipe(effect, dict(G.RECIPES.get(effect, {}), **recipe, **({"args": args} if args else {}), **({"ram": ram} if ram else {}), max_insns=max_insns))
        snaps, ticks = F.frames(effect, args=r["args"], ram=r["ram"], rng=rng, init=r["init"], max_insns=max_insns, counters=r["counters"], real_show_pages=real_show_pages)
    finally:
        D.build = orig
    return snaps, ticks, calls


if __name__ == "__main__":
    e = int(sys.argv[1])
    snaps, ticks, calls = trace(e, [int(a, 0) for a in sys.argv[2:]] or None)
    print(len(snaps), "frames", len(calls), "calls")
    for t, n, r, s in calls[:80]:
        print(t, n, [hex(x) for x in r], [hex(x) for x in s])
