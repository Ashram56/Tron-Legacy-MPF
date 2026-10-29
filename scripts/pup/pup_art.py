#!/usr/bin/env python3
"""The HD DMD's art made from the PuP Pack, at the bundle's creation and never on the machine that runs the game.

The PuP clips behind the DMD effects (game/media/dmd_clip), the ZUSE / TRON letters (game/hd_art/letters) and the award icons
made from the clips (game/hd_art/deff_105) come from the author's pack. `scripts/package/build_bundle.py --pup-zip ZIP` installs
the pack on the builder, makes the art here (`make()`, needs numpy: the platform's build requirements) into `<media_dir>/dmd_art/`
and copies it into the game's folders, which the bundle then ships. Nothing here runs on the target (a Raspberry Pi, a Jetson, a PC
only start MPF and serve the settings page): no start and no install of a bundle makes anything.

    python scripts/pup/pup_art.py --make     # the pack is installed (pup_setup.py): make the art and copy it into the game
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


def _place(src, dst, copy=False):
    if os.path.islink(dst) or os.path.exists(dst):
        if os.path.islink(dst) and os.path.realpath(dst) == os.path.realpath(src):
            return
        if os.path.isdir(dst) and not os.path.islink(dst):
            return
        os.remove(dst)
    try:
        if copy:
            raise OSError("copy")
        os.symlink(src, dst)
    except OSError:                       # no links (Windows without the right, a FAT card): a copy
        shutil.copyfile(src, dst)


def link(root=ROOT, copy=False):
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
            _place(os.path.join(src_dir, f), dst, copy)
            n += 1
    return n


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
    link(root, copy=True)
    return complete(root)


def main(argv):
    if "--make" not in argv:
        print(__doc__)
        return 2
    ok = make()
    print("PuP art: " + ("complete" if ok else "incomplete"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
