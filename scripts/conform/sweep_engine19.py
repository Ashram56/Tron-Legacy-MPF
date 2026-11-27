#!/usr/bin/env python3
"""The score display's frames from the ported program (game/tron/rom_deff19.py, equal to the ROM code in check19.py) for every score total a scenario went
through x ball 1-3 x playfield valid or not x ticks 0..TICKS, as a set for code_conform.py --extra.

    python3 scripts/conform/sweep_engine19.py OUT.pkl TICKS NAME.jsonl [...]
"""
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game"))
from tron import dmd_engine as E, rom_deff19  # noqa: E402


def main(out, ticks, *logs):
    scores = {0}
    for p in logs:
        for line in open(p):
            if '"ev": "score"' in line:
                e = json.loads(line)
                if e.get("player") == 1:
                    scores.add(e["total"])
                    scores.add(e["total"] - e["delta"])
    frames = set()
    blank = bytes([0xff]) * (E.W * E.H)
    for s in sorted(scores):
        for ball in (1, 2, 3):
            for valid in (0, 1):
                for t in range(int(ticks)):
                    for credits in ("CREDITS 0", "FREE PLAY", "CREDITS 1"):
                        for replay in ("", "REPLAY AT 20,000,000"):
                            if (replay or credits != "CREDITS 0") and t < 0x9b and replay:
                                continue
                            frames.add(E.mix(blank, rom_deff19.page(s, ball, credits, valid, t, t, replay=replay).b))
    pickle.dump(frames, open(out, "wb"))
    print("done", len(frames))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *sys.argv[3:])
