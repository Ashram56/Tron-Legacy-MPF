#!/usr/bin/env python3
"""The platform's RGB DMD output (PIN2DMD, ZeDMD) for this game. The pieces are MPF-Godot-Packaging's, the same for
every game (platforms/dmd_devices.md there): the Godot add-on dmd_out, the MPF overlays, the ZeDMD platform and the
native feeder. This file only finds that checkout and puts them where the game reads them.

    python scripts/dmd_out.py detect      # pin2dmd, zedmd or nothing (the platform's mpf_godot.dmd_panel)

MPF-Godot-Packaging: $MPF_GODOT_PACKAGING (or $MPF_PLATFORM_DIR on a machine installed by the setup page), else a folder beside this repository (MPF-Godot-Packaging, MPF-Godot).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toolchain as tc  # noqa: E402
import mpf_platform  # noqa: E402

OVERLAYS = {"pin2dmd": "pin2dmd.yaml", "zedmd": "zedmd.yaml", "feed": "zedmd_feed.yaml"}


def platform_dir():
    """The MPF-Godot-Packaging checkout with the DMD output (scripts/mpf_platform.py finds it), or None."""
    for c in mpf_platform.candidates():
        if c and os.path.isfile(os.path.join(c, "addons", "dmd_out", "dmd_out.gd")):
            return c
    return None


def need_platform():
    p = platform_dir()
    if not p:
        raise SystemExit("the DMD output (PIN2DMD, ZeDMD) is MPF-Godot-Packaging's: clone it beside this repository or set "
                         "MPF_GODOT_PACKAGING (its addons/dmd_out is not there yet?)")
    return p


def detect():
    """"pin2dmd", "zedmd" or "": what the platform finds plugged in."""
    p = platform_dir()
    if not p:
        return ""
    r = subprocess.run([sys.executable, "-m", "mpf_godot", "dmd-detect"], cwd=p, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH=p))
    return r.stdout.strip() if r.returncode == 0 else ""


def feeder(python=False):
    """Path of the platform's native ZeDMD feeder, built with the C compiler on first use, or None when it cannot be
    had or finds no ZeDMD (--probe): MPF then drives the ZeDMD through the platform's Python one."""
    if python or os.name == "nt":
        return None
    src = os.path.join(need_platform(), "native", "zedmd_feed", "zedmd_feed.c")
    exe = os.path.join(tc.GAME, "native", "bin", "zedmd_feed")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not cc:
            return None
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        if subprocess.call([cc, "-O2", "-o", exe, src], stderr=subprocess.DEVNULL) != 0:
            return None
    return exe if subprocess.call([exe, "--probe"], stderr=subprocess.DEVNULL, timeout=20) == 0 else None


def prepare(device, game=None):
    """Copy the platform's add-on and the device's MPF overlays into the game (git-ignored); returns the environment
    to start Godot and MPF with (the platform on PYTHONPATH: the overlays name mpf_godot.zedmd_native)."""
    game = game or tc.GAME
    p = need_platform()
    shutil.rmtree(os.path.join(game, "addons", "dmd_out"), ignore_errors=True)
    shutil.copytree(os.path.join(p, "addons", "dmd_out"), os.path.join(game, "addons", "dmd_out"),
                    ignore=shutil.ignore_patterns("*.uid"))
    for name in OVERLAYS.values():
        if name.startswith(device):
            shutil.copy2(os.path.join(p, "examples", "dmd_devices", name), os.path.join(game, "config", name))
    path = os.environ.get("PYTHONPATH", "")
    return {"PYTHONPATH": p + (os.pathsep + path if path else "")}


if __name__ == "__main__":
    print(detect() if sys.argv[1:] == ["detect"] else __doc__)
