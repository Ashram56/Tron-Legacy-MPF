#!/usr/bin/env python3
"""Creator's tool, run once (when the game is made or the PuP Pack's version changes), never by a build: makes the two committed parts
of the game's source package that come from the PuP Pack, and nothing else:

    pup/manifest.json        the list of the pack's files the game uses (written by scripts/pup/gen_pup.py)
    addons/pup_art/          the HD art made from the pack: dmd_clip/ (clips), hd_art/letters/, service/ (still of the service menu)

Needs the workspace that `scripts/setup.py` made with the PuP Pack installed (scripts/pup/pup_setup.py). Then commit both folders:
the bundle build (scripts/package/build_bundle.py) only checks they are there and copies them (MPF-Godot-Packaging, platforms/game-bundles.md).
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADDON = os.path.join(ROOT, "addons", "pup_art")
MANIFEST = os.path.join(ROOT, "pup", "manifest.json")


def main():
    src = os.path.join(ROOT, "pup_media", "trn_174h", "manifest.json")
    if not os.path.isfile(src):
        sys.exit("no pup_media/trn_174h/manifest.json: install the PuP Pack first (scripts/pup/pup_setup.py)")
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    shutil.copy2(src, MANIFEST)
    shutil.rmtree(ADDON, ignore_errors=True)
    for from_rel, to_rel in (("game/media/dmd_clip", "dmd_clip"), ("game/hd_art/letters", "hd_art/letters"),
                             ("pup_media/trn_174h/service", "service")):
        full = os.path.join(ROOT, from_rel)
        if not os.path.isdir(full):
            sys.exit("missing " + from_rel + " (run scripts/setup.py)")
        shutil.copytree(full, os.path.join(ADDON, to_rel), ignore=shutil.ignore_patterns("*.import"))
    print("wrote pup/manifest.json and addons/pup_art: commit them")


if __name__ == "__main__":
    main()
