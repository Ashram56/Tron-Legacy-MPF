"""The effects drawn by the game from the ROM's routines (tron/dmd_engine.py programs) instead of from the code run's frames.

payload(deff_id, args) -> the event arg `engine` of the effect's slide: {"ticks": ROM ticks a flip lasts, "loop": the sequence repeats,
"frames": the distinct draw lists (tron/service_screen.gd items), "seq": the frame number of each flip}. tron/dmd_effect.gd draws the list
of the flip the effect's time is in (the clock: tick_ms of tron/score_display.gd), over the status panel the effect keeps.
"""
from . import rom_deff55, rom_deff57, rom_deff58, rom_deff60, rom_deff83, rom_deff138

DEFFS = (42, 55, 57, 58, 59, 60, 83, 138)


def _pack(flips, ticks, loop):
    """items: every distinct draw item once; frames: the distinct draw lists as lists of item numbers; seq: the frame of each flip."""
    items, frames, seq = [], [], []
    for _, lst in flips:
        row = []
        for it in lst:
            if it not in items:
                items.append(it)
            row.append(items.index(it))
        if row not in frames:
            frames.append(row)
        seq.append(frames.index(row))
    return {"ticks": ticks, "loop": loop, "items": items, "frames": frames, "seq": seq}


def payload(deff_id, args):
    """args: what the game passes the effect (before / after: (left, right) letters lit, flags, more; value: the switch count of deff 57)."""
    if deff_id == 55:
        before, after = args.get("before", (0, 0)), args.get("after", (0, 0))
        flips = rom_deff55.draws([before[0], before[1], after[0], after[1], int(args.get("flags", 0)), int(args.get("more", 0))])
        return _pack(flips, rom_deff55.TICKS, False)
    if deff_id == 57:
        return _pack(rom_deff57.draws(int(args.get("value", 0) or 0)), rom_deff57.TICKS, True)
    if deff_id == 138:
        return _pack(rom_deff138.draws(int(args.get("points", 0) or 0), int(args.get("count", 0) or 0), int(args.get("jackpot", 0) or 0),
                                       str(args.get("named", "") or "")), rom_deff138.TICKS, False)
    if deff_id == 83:
        return _pack(rom_deff83.draws83([int(args.get("more", 0) or 0), int(args.get("mask", 0) or 0)]), rom_deff83.TICKS, False)
    if deff_id == 42:
        p0 = rom_deff83.pages42(int(args.get("last", 0) or 0), int(args.get("total", 0) or 0))
        return _pack([(i, p0[0][1].items) for i in range(0x5d)] + [(0x5d, [])], 1, False)
    if deff_id in (58, 59):
        return _pack(rom_deff58.draws(deff_id, [int(args.get("value", 0) or 0)]), rom_deff58.TICKS, False)
    if deff_id == 60:
        return _pack(rom_deff60.draws([int(args.get("value", 0) or 0), int(args.get("more", 0) or 0)]), rom_deff60.TICKS, False)
    return {}
