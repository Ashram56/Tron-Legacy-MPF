#!/usr/bin/env python3
"""The rules test bench (docs/test_bench.md): a player robot on a physical table model, the modes one by
one against the ROM's rule specs, the service menu's adjustments checked in play, and random whole games.

    python scripts/bench.py                 everything, about 1.5 minutes
    python scripts/bench.py modes           the modes one by one (timed modes, multiballs, game flow)
    python scripts/bench.py adjustments     the service menu's adjustments, set by the buttons, in play
    python scripts/bench.py stress          modes in every order and the random games
    python scripts/bench.py soak            300 random games per kind (--games N), about 20 minutes
    python scripts/bench.py --seeds 17,40   replay the random games of these seeds (a failure names its seed)

Anything after `--` goes to pytest (`-- -k tilt -x`)."""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join("tests", "bench")
SUITES = {
    "all": [BENCH],
    "modes": [os.path.join(BENCH, name) for name in ("test_bench_selftest.py", "test_modes_timed.py",
                                                     "test_modes_multiball.py", "test_game_flow.py")],
    "adjustments": [os.path.join(BENCH, "test_adjustments_play.py")],
    "stress": [os.path.join(BENCH, "test_stress.py")],
    "soak": [os.path.join(BENCH, "test_stress.py"), "-k", "Random"],
}


def python():
    """The workspace's venv when it is there (scripts/setup.py), else this interpreter."""
    for rel in (os.path.join(".venv", "bin", "python"), os.path.join(".venv", "Scripts", "python.exe")):
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            return path
    return sys.executable


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    extra = []
    if "--" in argv:
        at = argv.index("--")
        argv, extra = argv[:at], argv[at + 1:]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", nargs="?", default="all", choices=sorted(SUITES))
    parser.add_argument("--games", type=int, default=300, help="soak: random games per kind (default 300)")
    parser.add_argument("--seeds", help="random games: these seeds only, e.g. 17,40")
    args = parser.parse_args(argv)
    env = dict(os.environ)
    target = SUITES[args.suite]
    if args.seeds:
        env["TRON_BENCH_SEEDS"] = args.seeds if "," in args.seeds else args.seeds + ","
        target = SUITES["soak"]
    elif args.suite == "soak":
        env["TRON_BENCH_SEEDS"] = str(args.games)
    return subprocess.call([python(), "-m", "pytest", "-q"] + target + extra, cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
