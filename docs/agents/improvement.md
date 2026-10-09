# Agent E: improvements (optional)

Make the recreated game look, sound or play better than the ROM **without losing the original**: an HD
display, cleaner fonts, colour, new modes, desktop conveniences. Runs only after the
[strict recreation](recreation.md) works, and never changes what that agent guarantees. Part of the
[master plan](README.md). Tron is the worked example.

## 1. Rules

1. **Switchable, with the ROM one option away.** Every improvement is a mode or an option (command-line flag,
   environment variable, Godot project setting or MPF setting); the ROM's behaviour stays reachable.
2. **Classic stays byte-exact.** The 128x32 classic output, the render captures and the real-hardware DMD
   (P-ROC) are always classic. Pixel-hash tests guard classic frames; re-take a hash only after rendering the
   same frames on the base branch and seeing them agree.
3. **Every departure gets a row in [rom_differences.md](../rom_differences.md)** in the same commit: what the
   ROM does, what the game does, why, and the switch back. Rules changes and new modes also get their own
   tests and must not change any ROM scenario; new modes go in their own feature module.
4. **Same layout as the ROM** for display work: glyph advances and positions are the ROM's; only the
   rendering changes. No learned upscaler, no network at build time: deterministic and offline.
5. **The owner judges the look.** Offer a default, show before/after pictures, keep the alternatives as
   options. Record each decision below with its date.
6. **Third-party colourisation and anything else with third-party rights stays in the private repo**
   (`Ashram56/Tron-Legacy-MPF-Private`); the public repo only points there. Its agent notes are in that
   repo's `docs/agents/colorization.md`. Don't name the third-party tools or packs here.

## 2. The HD display (built)

How it works, game agnostic: [dmd_hd_upscaling.md](../handover/dmd_hd_upscaling.md). In short: frames
upscaled shade by shade (level sets) at build time; ROM fonts traced to vector outlines; by default text in
a clean TrueType font at the ROM's positions (MSDF, sharp at any size); text baked into recorded animations
found, cleared and redrawn live (`scripts/frame_text.py`); pictures that are only frames and blocks drawn as
rectangles. Mode precedence and options are in `game/tools/dmd_mode.gd`.

Current defaults (Tron, `dmd_mode.gd` constants and `project.godot`): HD on, Tron blue text `#2a6cff`, glow
`#22b8ff` at 0.8, font Rajdhani Bold, text scale 0.85. Back to the ROM: `--dmd classic`, `--dmd-font rom`,
`--dmd-tint orange`, `--dmd-text-glow 0`.

## 3. Owner decisions (Tron, keep adding)

| Date | Decision |
|---|---|
| 2026-10-04 | HD DMD in Tron blue, animations included; orange only as `--dmd-tint orange`. |
| 2026-10-04 | **No colourisation on `main`**, no colour option left in the public repo; colour work lives in the private repo only. |
| 2026-10-04 | Free play by default on the desktop (`--no-free-play` for coins). |
| 2026-10-06 | Clean font for HD text; Orbitron + glow tried as default, then Rajdhani default with glow 0.8; text scale 0.85 (the clean fonts looked bigger than the ROM's and stacked lines touched). |
| 2026-10-06 | Outlined ROM fonts sized and placed by their lit dots. |
| 2026-10-07 | ZUSE/TRON target letters stay the ROM's pictures, upscaled: the clean-font versions looked worse. |
| 2026-10-07 | Effects that are only frames and blocks drawn as sharp rectangles. |

## 4. Ideas not built (ask before starting)

- New modes or rule changes (the owner has said they may come; nothing built yet: `rom_differences.md`
  says "No scoring or rules departures yet").
- A Tron-style font for the ZUSE/TRON letters (each sprite carries `metadata/letter` for it).
- Colour from the private repo's work, once the owner wants it public in some form (their call: rights).

## 5. Checks

`pytest -q tests` (includes `tests/test_dmd_hd.py`, `tests/test_dmd_text.py`), `scripts/render_check.py`,
and pictures at 1920x480 and 3840x960 for the owner (render through Xvfb with `--rendering-driver opengl3`;
`--headless` draws nothing). Bump `frame_text.VERSION` when the text matching changes (it keys the cache).

Last updated 2026-10-08.
