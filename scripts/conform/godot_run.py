#!/usr/bin/env python3
"""Play a tron_ref scenario in real time on the game (MPF + Godot, classic DMD) and dump every change of the DMD.

    python scripts/conform/godot_run.py SCENARIO SECONDS OUTDIR

Writes OUTDIR/SCENARIO.dmd (game/tools/dmd_dump.gd), .jsonl (MPF's trace with the wall clock) and the logs. Compare with
PinMAME's dump of the same scenario (build_tron_ref.sh; dmd_conform.py).
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ["TRON_TRACE_WALL"] = "1"      # game/tron/trace.py adds the wall clock to each event
import run  # noqa: E402


def main(argv):
    if len(argv) != 3:
        raise SystemExit(__doc__)
    name, secs, out = argv[0], int(argv[1]), os.path.abspath(argv[2])
    os.makedirs(out, exist_ok=True)
    base = os.path.join(out, name)
    gargs = ["--rendering-driver", "opengl3", "--", "--dmd=classic", "--dmd-dump=" + base + ".dmd"]
    # a scenario starts on fresh NVRAM, like PinMAME's (credits, audits and high scores of earlier runs change the screens):
    # the game's data folder is put aside for the run
    data = os.path.join(run.tc.GAME, "data")
    aside = data + ".conform_keep"
    if os.path.isdir(aside):
        raise SystemExit("{} is left from an interrupted run: put it back as game/data first".format(aside))
    if os.path.isdir(data):
        os.rename(data, aside)
    try:
        return run.run("virtual", scenario=name, seconds=secs, godot_args=gargs, godot_log=base + ".godot.log",
                       mpf_log=base + ".mpf.log", trace=base + ".jsonl")
    finally:
        shutil.rmtree(data, ignore_errors=True)
        if os.path.isdir(aside):
            os.rename(aside, data)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
