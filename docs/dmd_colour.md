# Colour of the HD DMD

The HD DMD (`--dmd hd`, the default on the desktop) shows the ROM's display effects in colour. Nothing here reads a
colourisation file: the colour is made from the ROM's own monochrome frames and, when the PuP Pack is installed, from the
pack's clips. `--dmd-color off` (or `TRON_DMD_COLOR=off`) gives the plain HD DMD in the tint; `--dmd classic` is the ROM's dots.

## From the monochrome frames (`scripts/mono_colour.py`, `scripts/dmd_color.py`)

Setup (`scripts/gen_media.py`, HD) writes `game/media/dmd_color/`: every effect frame at 2x (256x64, crisp dots) in colour, a
`palettes.json` (one 16-colour ramp per effect, source `mono`) and `text_colors.json` (the colour of each line of text the HD
draws live), and tells each effect's data (`effect.json`) its colours. The ROM draws 16 shades per dot; the colour is a pure
function of an effect's frames and its recipe: shade ramps from two hues (`game/tools/dmd_colormap.json`, hues measured on the
PuP Pack's videos, folded into the film's blue, cyan, red and orange), objects tracked from frame to frame so a moving light
cycle or disc keeps its colour, one colour per line of text. `python scripts/mono_colour.py sheet GIF... --out sheet.png`
renders the monochrome next to the colour. `--no-color` on `gen_media.py` skips the step.

## From the PuP Pack's clips (needs the pack, ffmpeg)

The video-like effects play the pack's clip of the same sequence behind the live vector text; characters use the topper's HD
icons; the ZUSE and TRON letters and the mystery award icons come from the topper clips. See [pup/README.md](pup/README.md),
"DMD effects with PuP clips", and `game/hd_art/README.md` for the icons redrawn by the owner.

## Third-party colourisation files

A colourisation file (Serum) is not used by the public game. Work that reads one lives in the private repository.
