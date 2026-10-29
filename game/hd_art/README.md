# Redrawn DMD art (HD mode)

`deff_105/award_NN.png` (NN = 01..12): the mystery award icons of Flynn's Arcade reel, RGBA, 464x352 (29:22). Made with
`python scripts/pup/award_sprites.py export` / `import` (see its docstring). A missing file means the ROM's icon, upscaled.

The pictures are git-ignored (frames of the PuP Pack's videos): `setup.py` makes award_02 to 09 and 11 from the topper icons
and the clips (`award_sprites.py clips`); `import` writes the redrawn ones, which `clips` does not overwrite without `--force`.
