#!/usr/bin/env python3
"""The PuP Pack part of the workspace: setup.py and run.py call it, or run it on its own.

    python scripts/pup_setup.py            # pup_pack submodule, an ffmpeg with Theora, the converted media
    python scripts/pup_setup.py --status   # one line: is the PuP on, and if not why

Kept out of setup.py and run.py (upstream files, one-line hooks only) so upstream merges stay clean.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toolchain as tc  # noqa: E402

sys.path.insert(0, tc.GAME)
from tron_pup import settings  # noqa: E402


def status():
    """(on, text): whether Godot will start the PuP windows, and a line saying so or what is missing."""
    cfg = settings.load()
    if not cfg["pup"].get("enabled", False):
        return False, "PuP off ([pup] enabled=false or TRON_PUP=0): original game only"
    pack, media = settings.pack_dir(cfg), settings.media_dir(cfg)
    if not os.path.exists(os.path.join(pack, "triggers.pup")):
        return False, ("PuP off: no PuP Pack in {} (run `python scripts/setup.py`, or "
                       "`git submodule update --init pup_pack`)".format(os.path.relpath(pack, tc.ROOT)))
    if not os.path.exists(os.path.join(media, "manifest.json")):
        return False, ("PuP off: the pack's videos are not converted yet (run `python scripts/setup.py`, or "
                       "`python scripts/pup_setup.py`)")
    screens = "backglass, DMD" + (", topper" if cfg["pup"].get("third_screen", True) else "")
    music = "PuP OST music" if cfg["pup"].get("ost_music", True) else "ROM music"
    return True, "PuP on: {} windows, {}".format(screens, music)


def say(text):
    print(text, flush=True)


def ensure_ffmpeg(py):
    """Installs imageio-ffmpeg in the venv unless an ffmpeg with libtheora is there for gen_pup.py."""
    for exe in (os.environ.get("FFMPEG"), shutil.which("ffmpeg")):
        if exe and "libtheora" in subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True,
                                                 text=True).stdout:
            return
    if subprocess.run([py, "-c", "import imageio_ffmpeg"], capture_output=True).returncode:
        say("   no ffmpeg with Theora: installing imageio-ffmpeg in the venv")
        subprocess.run([py, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"], check=True)


def setup(py=None, dry=False):
    py = py or tc.python()
    say("== PuP Pack (pup_pack submodule, videos converted for Godot into pup_media/)")
    cfg = settings.load()
    pack = settings.pack_dir(cfg)
    if not os.path.exists(os.path.join(pack, "triggers.pup")):
        cmd = ["git", "submodule", "update", "--init", "--depth", "1", "pup_pack"]
        say("   $ " + " ".join(cmd))
        if not dry and subprocess.run(cmd, cwd=tc.ROOT).returncode:
            say("   could not fetch the PuP Pack (private repo: your git needs access to "
                "Ashram56/Tron-LE-PuP-Pack). The game runs without the PuP.")
            return 1
    if dry:
        return 0
    ensure_ffmpeg(py)
    say("   converting the pack's videos (the first time takes a while; later runs only redo changed files)")
    code = subprocess.run([py, os.path.join(tc.ROOT, "scripts", "gen_pup.py")], cwd=tc.ROOT).returncode
    say("   " + status()[1])
    return code


if __name__ == "__main__":
    if sys.argv[1:] == ["--status"]:
        on, text = status()
        say(text)
        sys.exit(0 if on else 1)
    sys.exit(setup())
