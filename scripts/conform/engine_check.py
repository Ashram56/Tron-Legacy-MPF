#!/usr/bin/env python3
"""The game-side DMD engine against the ROM code (Unicorn): every flip of an effect program is compared with the frame the ROM draws.

    TRON_ROM=trn_174h.bin python3 scripts/conform/engine_check.py 55 [ARG ...]

Prints, per flip, whether the program's frame (columns 41-127 by default: the effect's own area, the status panel is the panel's) equals the ROM's.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "game"))
import deff_trace as T  # noqa: E402
from tron import dmd_engine as E  # noqa: E402

X0 = 41


def oracle(effect, args, ram=None):
    """The ROM's frames: the distinct pictures (columns X0-127, as 128 x 32 levels) in the order shown, with the tick each starts."""
    snaps, ticks, _ = T.trace(effect, args, ram, int(os.environ.get("ENGINE_INSNS", "4000000")))
    out = []
    for (r0, r1, fg, bg), t in zip(snaps, ticks):
        f = E.mix(fg, bg)
        out.append((t, f))
    return out


def body(frame, rows=range(E.H)):
    return bytes(frame[y * E.W + x] for y in rows for x in range(X0, E.W))


def compare(effect, args, program, ram=None, rows=range(E.H)):
    """program(args) -> [(tick, 128*32 levels)]: the engine's frames. Returns (matching, total, first_mismatch)."""
    ora = oracle(effect, args, ram)
    mine = program(args)
    ok = 0
    first = None
    for i, (t, f) in enumerate(ora):
        # the engine's frame shown at that tick
        m = None
        for tt, ff in mine:
            if tt <= t:
                m = ff
        if m is not None and body(m, rows) == body(f, rows):
            ok += 1
        elif first is None:
            first = (i, t)
    return ok, len(ora), first


if __name__ == "__main__":
    from tron import rom_deff55, rom_deff57, rom_deff58, rom_deff60, rom_deff83
    eff = int(sys.argv[1])
    args = [int(a, 0) for a in sys.argv[2:]] or None
    if eff == 57:                   # arg: the value RAM 0x3ae00 holds; the ROM loop never ends, so the comparison covers the first frames only
        v = args[0] if args else 0
        print(compare(57, None, lambda a: rom_deff57.frames(v, flips=60), ram={0x3ae00: v}))
    else:
        prog = {55: rom_deff55.frames, 60: rom_deff60.frames,
                83: lambda a: rom_deff83.frames83(a, 400), 58: lambda a: rom_deff58.frames(58, a), 59: lambda a: rom_deff58.frames(59, a)}[eff]
        print(compare(eff, args, prog, rows=range(0, 32)))
