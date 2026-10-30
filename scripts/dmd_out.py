#!/usr/bin/env python3
"""The platform's RGB DMD output (PIN2DMD, ZeDMD) for this game. The pieces are MPF-Godot-Packaging's, the same for
every game (platforms/dmd_devices.md there): the Godot add-on dmd_out, the MPF overlays, the ZeDMD platform and the
native feeder. This file only finds that checkout and puts them where the game reads them.

    python scripts/dmd_out.py detect      # pin2dmd, zedmd or nothing (the platform's mpf_godot.dmd_panel)

MPF-Godot-Packaging: $MPF_GODOT_PACKAGING (or $MPF_PLATFORM_DIR on a machine installed by the setup page), else a folder beside this repository (MPF-Godot-Packaging, MPF-Godot).
"""
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toolchain as tc  # noqa: E402
import mpf_platform  # noqa: E402

ROM = "trn_174h"            # the PinMAME set a Serum colourisation is named after
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


def arch():
    """The CPU the bundle's prebuilt feeder folder is named after: x86_64 or arm64."""
    m = platform.machine().lower()
    return "arm64" if m in ("aarch64", "arm64") else "x86_64"


def prebuilt(name):
    """A native program built offline for this CPU (game/native/bin/<arch>/, put there by the bundle's build: nothing is compiled
    on the machine that runs the game), or the one built here in a development checkout; None when there is none."""
    for folder in (os.path.join(tc.GAME, "native", "bin", arch()), os.path.join(tc.GAME, "native", "bin")):
        if os.path.isfile(os.path.join(folder, name)):
            return os.path.join(folder, name)
    return None


def zig():
    """The zig command (cross builds for the other CPU): `zig` on the PATH, else the ziglang Python package, else None."""
    import shutil
    if shutil.which("zig"):
        return ["zig"]
    try:
        import ziglang  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "ziglang"]


def _build(cmd, out, cc, cxx):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    env = dict(os.environ)
    if cc:
        env["CC"] = cc
    if cxx:
        env["CXX"] = cxx
    return os.path.exists(cmd[1]) and subprocess.call(cmd, env=env, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL) == 0


def build_feeder(out, cc=None, cxx=None):
    """Build the platform's plain ZeDMD feeder (native/zedmd_feed/zedmd_feed.c: C, libc only) into OUT on a build box. cc: another
    target, e.g. "zig cc -target aarch64-linux-gnu". Returns True when built."""
    import shlex
    src = os.path.join(need_platform(), "native", "zedmd_feed", "zedmd_feed.c")
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = shlex.split(cc or os.environ.get("CC", "cc")) + ["-O2", "-Wall", "-o", out, src]
    return subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL) == 0


def build_serum(out, cc=None, cxx=None):
    """Build the game's Serum colouriser (game/native/dmd_serum: libserum linked in; git, CMake >= 3.25, a C++17 compiler) into
    OUT on a build box. Returns True when built."""
    return _build(["bash", os.path.join(tc.GAME, "native", "dmd_serum", "build.sh"), out,
                   os.path.join(tc.GAME, "native", "serum_build", os.path.basename(os.path.dirname(out)))], out, cc, cxx)


def _tool(name, build, python=False):
    """Path of a native tool of the DMD output, or None when it cannot be had. Built offline (the bundle's build,
    scripts/package/build_bundle.py, puts one per CPU in game/native/bin/<arch>/); only a development checkout (a .git folder)
    builds it on first use. Windows has none."""
    if python or os.name == "nt":
        return None
    exe = prebuilt(name)
    if exe is None and os.path.exists(os.path.join(tc.ROOT, ".git")):
        exe = os.path.join(tc.GAME, "native", "bin", arch(), name)
        if not build(exe):
            return None
    return exe if exe and os.path.isfile(exe) else None


def feeder(python=False):
    """Path of the platform's native ZeDMD feeder, or None when it cannot be had or finds no ZeDMD (--probe): MPF then drives
    the ZeDMD through the platform's Python one."""
    exe = _tool("zedmd_feed", build_feeder, python)
    return exe if exe and subprocess.call([exe, "--probe"], stderr=subprocess.DEVNULL, timeout=20) == 0 else None


def serum_filter():
    """Path of the game's Serum colouriser (it starts the feeder itself), or None when it cannot be had."""
    return _tool("dmd_serum", build_serum)


def serum_env(altcolor, feed, colour="2a6cff"):
    """The environment the colouriser reads (Godot's add-on cannot pass it arguments): colour the DMD with Serum from
    ALTCOLOR/trn_174h/trn_174h.cROMc and pipe the colours to FEED, the plain feeder; a frame the file does not know stays in
    COLOUR (Tron blue)."""
    return {"DMD_SERUM_ARGS": "|".join(["--serum", os.path.abspath(altcolor), "--rom", ROM, "--color", colour.lstrip("#"),
                                         "--feeder", feed])}


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
