#!/usr/bin/env python3
"""One markdown with every review sheet of the PuP-on-DMD work embedded (and each compare row's effect, clip, durations).

    python scripts/pup/pup_planches_md.py DIR      # DIR = the folder with compare/, remaining/, sprites_cut/, topper_icons/, topper/
"""
import glob
import os
import re
import sys


def main():
    os.chdir(sys.argv[1])
    L = ["# Planches PuP / DMD : revue", "", "Référence = planche-ligne-colonne. Les images sont dans les dossiers à côté de ce fichier.", "",
         "1. [Compare : DMD 128x32 contre clip PuP](#1-compare)", "2. [Ce qui reste du DMD](#2-restes)", "3. [Sprites](#3-sprites)",
         "4. [Icônes topper et glissement](#4-icônes-topper-et-glissement)", "5. [Clips topper](#5-clips-topper)", "", "## 1. Compare", ""]
    idx = open("compare/index.md").read()
    rows = [l for l in idx.splitlines() if re.match(r"\| \d+-\d+\.\.\d+ \|", l)]
    L += [l for l in idx.splitlines() if l.startswith("Column 1")] + [""]
    for p in sorted(glob.glob("compare/planche_*.png")):
        n = int(re.search(r"(\d+)", os.path.basename(p)).group(1))
        L += ["### Planche %d" % n, ""]
        for r in rows:
            c = [x.strip() for x in r.strip("|").split("|")]
            if c[0].startswith("%d-" % n):
                L.append("- lignes %s : effet %s (%s), clip %s (%s s) pour un effet de %s s" % (c[0], c[1], c[2], c[3], c[5], c[6]))
        L += ["", "![planche %d](%s)" % (n, p), ""]
    L += ["## 2. Restes", "", "Les effets des icônes de personnages (visage qui glisse dans l'hexagone) ne sont pas ici : l'icône HD du topper les remplace.", "",
          open("remaining/remaining.md").read().split("\n", 2)[2], ""]
    L += ["![restes %s](%s)\n" % (p[-6:-4], p) for p in sorted(glob.glob("remaining/sheets/planche_*.png"))]
    L += ["Prompt Gemini et liste de fichiers : [remaining/gemini_prompt.md](remaining/gemini_prompt.md)", "", "## 3. Sprites", "",
          open("sprites_cut/sprites.md").read().split("\n", 1)[1], ""]
    L += ["![sprites](%s)\n" % p for p in sorted(glob.glob("sprites_cut/sheet_*.png"))]
    L += ["## 4. Icônes topper et glissement", "", "Les visages sont fixes dans l'hexagone sur tous les clips topper d'info ; seul le fond bouge.", "",
          "![icônes](topper_icons/icons_planche.png)", "", open("topper_icons/glide.md").read().split("\n", 1)[1], ""]
    for p in sorted(glob.glob("topper_icons/glide_*.png")):
        L += ["**%s**" % os.path.basename(p), "", "![](%s)" % p, ""]
    L += ["## 5. Clips topper", "", open("topper/index.md").read().split("\n", 1)[1], ""]
    L += ["![topper](%s)\n" % p for p in sorted(glob.glob("topper/planche_*.png"))]
    open("planches.md", "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
