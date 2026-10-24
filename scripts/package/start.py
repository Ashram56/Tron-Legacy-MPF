#!/usr/bin/env python3
"""Start the installed bundle with its saved settings: scripts/run.py plus the flags in game/options.json.

    python scripts/package/start.py                 # as saved
    python scripts/package/start.py --seconds 20    # any run.py option; one given here wins over the saved one

Settings are changed with scripts/package/bundle_options.py (docs/bundle.md).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
sys.path.insert(0, HERE)

import bundle_options  # noqa: E402
import run  # noqa: E402


def merge(saved, given):
    """The saved flags without those the command line sets again (--name or --name=value, either form)."""
    def name(a):                    # --free-play and --no-free-play are one setting
        return a.split("=", 1)[0].replace("--no-", "--", 1)

    names = {name(a) for a in given if a.startswith("--")}
    out, i = [], 0
    while i < len(saved):
        a = saved[i]
        if name(a) in names:
            i += 1 if "=" in a or i + 1 >= len(saved) or saved[i + 1].startswith("--") else 2
            continue
        out.append(a)
        i += 1
    return out + list(given)


def main(argv=None):
    given = list(sys.argv[1:] if argv is None else argv)
    return run.main(merge(bundle_options.run_args(), given))


if __name__ == "__main__":
    sys.exit(main() or 0)
