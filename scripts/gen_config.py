#!/usr/bin/env python3
"""Generate game/config/rom/*.yaml from the asset package (adds MPF's config_version header).

The asset package's YAML has no "#config_version=6" first line, which MPF requires. These files are
generated, not edited: re-run after every asset sync (setup_workspace.sh and the tests do it).
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "assets", "mpf_package", "config")
DST = os.path.join(ROOT, "game", "config", "rom")
FILES = ["switches.yaml", "coils.yaml", "lights.yaml"]


def main():
    os.makedirs(DST, exist_ok=True)
    for name in FILES:
        with open(os.path.join(SRC, name)) as f:
            body = f.read()
        # MPF 0.80 has no "flashers:" section; flashers are plain coils there.
        body = body.replace("\nflashers:\n", "\n# (flashers, as coils for MPF 0.80)\n")
        out = "#config_version=6\n# GENERATED from assets/mpf_package/config/{} by scripts/gen_config.py\n{}".format(
            name, body)
        path = os.path.join(DST, name)
        if not os.path.exists(path) or open(path).read() != out:
            with open(path, "w") as f:
                f.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
