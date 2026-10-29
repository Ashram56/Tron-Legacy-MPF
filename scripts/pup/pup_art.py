#!/usr/bin/env python3
"""The HD DMD's art made from the PuP Pack: where it lives, how the game finds it, and how it is made again when it is missing.

The PuP clips behind the DMD effects (game/media/dmd_clip), the ZUSE / TRON letters (game/hd_art/letters) and the award icons
made from the clips (game/hd_art/deff_105) come from the author's pack, so they are made on the machine (scripts/pup/pup_setup.py)
and never ship in a bundle. A platform that installs the pack once and links it to later versions of the game keeps only the
pack's own folders (bundle.json "pup": pack_dir, media_dir). So the art is made into `<media_dir>/dmd_art/` (pup_media/trn_174h/dmd_art),
which stays with the pack, and `link()` puts each file where the game reads it, as a link (a copy where links are not allowed);
`ensure()` runs at every start (scripts/run.py): it links, and when a pack is installed but the art is missing it makes it in the
background (log: game/logs/pup_art.log), ready at the next start.

numpy is needed by the letter and icon scripts; a Python without it (the platform's game environment has MPF only) gets it with
pip into `<media_dir>/dmd_art/pylib` (`use_numpy()`).

    python scripts/pup/pup_art.py            # link, and make what is missing from the installed pack (as at a start)
    python scripts/pup/pup_art.py --make     # make it all again now (what pup_setup.py does after the videos)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "game"))
from tron_pup import settings  # noqa: E402

# (folder of the art, where the game reads it)
PLACES = (("dmd_clip", ("game", "media", "dmd_clip")), ("letters", ("game", "hd_art", "letters")),
          ("deff_105", ("game", "hd_art", "deff_105")))
LOG = os.path.join("game", "logs", "pup_art.log")


def media_dir(root=ROOT):
    return settings.media_dir(settings.load(os.path.join(root, "game")), root)


def art_dir(root=ROOT):
    return os.path.join(media_dir(root), "dmd_art")


def pack_installed(root=ROOT):
    return os.path.exists(os.path.join(settings.pack_dir(settings.load(os.path.join(root, "game")), root), "triggers.pup"))


def complete(root=ROOT):
    """True when the clips and the ZUSE / TRON letters are made (clips.json is written last by gen_dmd_clips.py)."""
    art = art_dir(root)
    return os.path.exists(os.path.join(art, "dmd_clip", "clips.json")) and \
        os.path.exists(os.path.join(art, "letters", "Z_on.png")) and os.path.exists(os.path.join(art, "letters", "N_on.png"))


def _place(src, dst):
    if os.path.islink(dst) or os.path.exists(dst):
        if os.path.islink(dst) and os.path.realpath(dst) == os.path.realpath(src):
            return
        if os.path.isdir(dst) and not os.path.islink(dst):
            return
        os.remove(dst)
    try:
        os.symlink(src, dst)
    except OSError:                       # no links (Windows without the right, a FAT card): a copy
        shutil.copyfile(src, dst)


def link(root=ROOT):
    """Each file of the art folder where the game reads it. A file the game's own tree has (an award icon redrawn by the owner) stays;
    links to files that are gone are removed."""
    art = art_dir(root)
    n = 0
    for name, rel in PLACES:
        dst_dir = os.path.join(root, *rel)
        if os.path.islink(dst_dir):       # an earlier whole-folder link
            os.remove(dst_dir)
        if os.path.isdir(dst_dir):
            for f in os.listdir(dst_dir):
                p = os.path.join(dst_dir, f)
                if os.path.islink(p) and not os.path.exists(p):
                    os.remove(p)
        src_dir = os.path.join(art, name)
        if not os.path.isdir(src_dir):
            continue
        os.makedirs(dst_dir, exist_ok=True)
        for f in sorted(os.listdir(src_dir)):
            dst = os.path.join(dst_dir, f)
            if os.path.exists(dst) and not os.path.islink(dst):
                continue
            _place(os.path.join(src_dir, f), dst)
            n += 1
    return n


def use_numpy(root=ROOT):
    """Make `import numpy` work: from the Python itself, else from pylib (pip --target, once)."""
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        pass
    lib = os.path.join(art_dir(root), "pylib")
    if not os.path.isdir(os.path.join(lib, "numpy")):
        os.makedirs(lib, exist_ok=True)
        print("   numpy is not in this Python: pip install --target " + os.path.relpath(lib, root), flush=True)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--target", lib,
                            "numpy>=1.24"])
        if r.returncode:
            print("   pip could not install numpy (network?): run `{} -m pip install numpy` as the user of the game, then {}"
                  .format(sys.executable, os.path.relpath(__file__, root)), flush=True)
            return False
    sys.path.insert(0, lib)
    try:
        import numpy  # noqa: F401,F811
        return True
    except ImportError:
        return False


def make(root=ROOT, py=None):
    """Make the art from the installed pack into the art folder, then link it. Returns True when it is complete."""
    py = py or sys.executable
    pack = settings.pack_dir(settings.load(os.path.join(root, "game")), root)
    scripts = os.path.join(root, "scripts", "pup")
    letters = subprocess.run([py, os.path.join(scripts, "letter_art.py"), "--clu"], cwd=root).returncode
    print("   encoding the clips of the HD DMD effects (" + os.path.relpath(os.path.join(art_dir(root), "dmd_clip"), root) + "/)", flush=True)
    subprocess.run([py, os.path.join(scripts, "gen_dmd_clips.py")], cwd=root)
    subprocess.run([py, os.path.join(scripts, "award_sprites.py"), "clips", pack], cwd=root)
    if subprocess.run([py, os.path.join(scripts, "letter_art.py"), pack], cwd=root).returncode or letters:
        print("   the ZUSE / TRON letters could not be made (see above): the HD DMD shows the ROM's dots for them", flush=True)
    link(root)
    return complete(root)


def ensure(root=ROOT):
    """At a start: only link the art the pack install made (symlinks, instant). A start never makes anything (platforms/game-bundles.md
    rule 2); a pack installed without its art is told to be installed again (the install makes the art)."""
    try:
        link(root)
        if not complete(root) and pack_installed(root):
            print("PuP art (DMD clips, ZUSE/TRON letters) is missing: install the PuP Pack again (scripts/pup/pup_setup.py --pup-zip ...)",
                  flush=True)
    except Exception as e:        # never stop a game start for this
        print("PuP art: " + str(e), flush=True)


def main(argv):
    if "--make" in argv:
        ok = make()
        if "--unlock" in argv:
            try:
                os.remove(os.path.join(art_dir(), "making.lock"))
            except OSError:
                pass
        print("PuP art: " + ("complete" if ok else "incomplete"), flush=True)
        return 0 if ok else 1
    ensure()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
