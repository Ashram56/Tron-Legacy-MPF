#!/usr/bin/env python3
"""Where the platform is. The platform (MPF-Godot-Packaging) is what every game shares: the binary add-ons (GDE GoZen with
its patches and builds, the RGB DMD output), the MPF/Godot toolchain, the setup page. This game takes them
from there instead of keeping copies.

MPF-Godot-Packaging: $MPF_GODOT_PACKAGING (or $MPF_PLATFORM_DIR on a machine installed by the setup page), else a folder
beside this repository (MPF-Godot-Packaging, MPF-Godot); ensure() clones it there when it is missing.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toolchain as tc  # noqa: E402

URL = "https://github.com/Ashram56/MPF-Godot-Packaging.git"
MARK = os.path.join("mpf_godot", "bundle.py")        # in every checkout that has the builder and the add-ons


def candidates():
    return [os.environ.get("MPF_GODOT_PACKAGING"), os.environ.get("MPF_PLATFORM_DIR"),
            os.path.join(os.path.dirname(tc.ROOT), "MPF-Godot-Packaging"), os.path.join(os.path.dirname(tc.ROOT), "MPF-Godot")]


def platform_dir():
    """The platform's checkout, or None."""
    for c in candidates():
        if c and os.path.isfile(os.path.join(c, MARK)):
            return c
    return None


def ensure():
    """The platform's checkout, cloned beside this repository when missing; exits with the reason if it cannot be had."""
    found = platform_dir()
    if found:
        return found
    dest = os.path.join(os.path.dirname(tc.ROOT), "MPF-Godot-Packaging")
    print("   cloning the platform (MPF-Godot-Packaging) -> " + dest, flush=True)
    if subprocess.call(["git", "clone", "--depth", "1", URL, dest]) != 0 or not os.path.isfile(os.path.join(dest, MARK)):
        raise SystemExit("the platform (MPF-Godot-Packaging: GoZen, the DMD output) is missing and could not be "
                         "cloned: clone {} beside this repository or set MPF_GODOT_PACKAGING".format(URL))
    return dest


def addon(name):
    """Path of the platform's add-on `name` (gde_gozen, dmd_out)."""
    return os.path.join(ensure(), "addons", name)


if __name__ == "__main__":
    print(platform_dir() or "")
