#!/usr/bin/env python3
"""Rules audit helper: for each feature file, the numeric constants of the decompiled routines it cites (ROM addresses 0x01xxxxxx / 0x000xxxxx in the file) that
do not appear in the file (as decimal or hex), grouped by routine. A constant not found is a value to read, not necessarily a divergence.

    python3 scripts/audit_constants.py game/tron/features/arcade.py [...]
"""
import re
import sys

S = open("assets/code/tron_game_decompiled_v2.c", encoding="utf-8", errors="replace").read()
HEAD = [(int(m.group(1), 16), m.group(2), m.start()) for m in re.finditer(r"// ==== ([0-9a-f]+) (\S+)", S)]
BY = {a: (n, p, HEAD[i + 1][2] if i + 1 < len(HEAD) else len(S)) for i, (a, n, p) in enumerate(HEAD)}
TRIVIAL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0xff, 0xffff, 0x10, 0x20, 0x1f, 0x3fff, 0x300, 0x1002, 0x2002, 0x100}


def consts(body):
    out = set()
    for m in re.finditer(r"\b(0x[0-9a-fA-F]+|\d+)\b", body):
        t = m.group(1)
        try:
            v = int(t, 16) if t.startswith("0x") else int(t)
        except ValueError:
            continue
        if v in TRIVIAL or v >= 0x1000000:            # addresses are not values
            continue
        out.add(v)
    return out


def main(paths):
    for path in paths:
        text = open(path, encoding="utf-8").read()
        seen = set()
        for m in re.finditer(r"0x0*([0-9a-fA-F]{5,8})\b", text):
            a = int(m.group(1), 16)
            if a in BY:
                seen.add(a)
        have = {int(t, 16) if t.startswith("0x") else int(t) for t in re.findall(r"\b(0x[0-9a-fA-F]+|\d[\d_]*)\b", text.replace("_", "")) if t}
        print("==", path, len(seen), "routines cited")
        for a in sorted(seen):
            n, p, e = BY[a]
            miss = sorted(c for c in consts(S[p:e]) if c not in have)
            if miss:
                print("  %#x %s: %s" % (a, n, ", ".join(hex(c) if c > 255 else str(c) for c in miss[:14])))


if __name__ == "__main__":
    main(sys.argv[1:])
