# DMD conformance with PinMAME (and so with Serum)

A colourisation (Serum) finds a frame by the dots its comparison mask keeps, so the classic 128x32 DMD of this game must
draw the ROM's dots. How close it is is measured, not assumed: PinMAME plays a scenario on the real ROM and dumps every DMD
frame; the game plays the same scenario and dumps its classic DMD; `scripts/conform/dmd_conform.py` compares them window by
window (the paired `deff_start` events).

```sh
# the ROM is yours (trn_174h.zip in $TRON_ROMS, never committed); PinMAME pinned, hook patch, tron_ref with a DMD dump
scripts/conform/build_tron_ref.sh WORK assets
TRON_ROMS=DIR PINMAME_NOJIT=1 TRON_DMDLOG=ref.dmd WORK/tron_ref assets/rules/traces/NAME.txt ref.jsonl
python scripts/conform/godot_run.py NAME SECONDS OUTDIR        # the game, real time: OUTDIR/NAME.dmd and .jsonl (Godot, xvfb)
python scripts/conform/dmd_conform.py ref.dmd ref.jsonl OUTDIR/NAME.dmd OUTDIR/NAME.jsonl
```

Record of a `.dmd`: per change `<double t><int32 w><int32 h><int32 depth=4>` then 128x32 shade bytes (0-15).

## First measure (2026-10-30, 21 scenarios of assets/rules/traces, ROM without music)

| | |
|---|---|
| Distinct PinMAME frames | 17131; 17119 (99.9 %) are known to the Serum v2 file of this game |
| Same Serum frame found in the game's DMD (same window, -0.2 / +0.6 s) | 11456 of 17119 (66.9 %) |
| Best scenarios (80-94 %) | game_flow_tilt, skill_shots, zuse_fast_scoring, gem_hurryup, bonus, find_flynn, end_of_line, zen_rollover, tron_targets, clu_hurryup, switches_and_shots |
| Weak | quorra 51 %, portal 42 %, light_cycle 40 %, sea_of_simulation 33 %, recognizer / disc battle 29 %, disc_multiball 25 %; the attract (effect 1) and coin (10) pages 0 % |
| Points exact (not what Serum needs) | 1739 of 17131 frames |

What was seen: the ROM's boot version screen (effect 5) is never shown; the attract pages lack the "00" panel and its vertical
line; most of the missing frames are the ROM's animated transitions between text screens (Disc Multiball, Quorra, Light Cycle,
Portal, Sea of Simulation, the Flynn's Arcade awards), where the game shows the final text over a static picture. A frame
the game draws that no Serum frame matches is shown plain. Closing these is a list of effects to rebuild one by one from the
ROM's frames: use the measure above as the work list.

## Second measure (2026-10-30, after the first rendering fixes)

| | first | now |
|---|---|---|
| Same Serum frame found in the game's DMD | 11456 of 17119 (66.9 %) | 11987 of 17119 (70.0 %) |
| Distinct frames of the game unknown to Serum | about 28 % | 2963 of 19891 (14.9 %) |
| Quorra / Light Cycle / Portal multiball (unknown game frames) | 568 / 820 / 379 | 167 / 193 / 229 |

What changed: the jackpot effects (deffs 48, 49, 68, 69, 87-89, 143) draw the clip bare and bring the text at the ROM's time
(the last sound call of the effect, `timing.json`), with the picture dimmed to level 1 under the text where the ROM does so
(`DIM_AFTER_MS`); Quorra's deff 65 shows level 1 as 0 (`LEVEL_MAP`); the attract pages get the version screen at power-up and the
status panel (line at x 40, points "00"). Checked in isolation (`render_diff.py` and a Serum identification of the reference
capture and the game's frame): 48, 49, 65, 68, 69, 87-89 now have every frame known to Serum (before: 17 of 66, 0, 0, 57 of 100,
63 of 108, 0, 0, 30 of 53).

**The "same Serum frame" figure under-counts the effects with random clips.** The ROM picks one of 3 to 12 film clips at random
for 19 effects (`assets/mpf_package/config/dmd_variants.yaml`), the game now does the same (`variants`, rom_differences.md),
but two runs rarely pick the same clip: the figure for Disc Multiball (27 %) cannot rise above the chance of the same clip.
For those effects the figure to watch is the share of the game's frames **unknown** to Serum (the frame must be one the file
colours), which falls from 913 to 525 of 2091 for Disc Multiball.

Still open (the work list, by weight): the score display deff 19 with the progress overlays (deffs 108 and 111 over it: 9349
distinct frames, 6912 found), the Flynn's Arcade awards (105: 62 of 400), the coin page (10: 0 of 95; the credit digits), the
Light Cycle intro (86), the Sea of Simulation stages (114), deff 83, the first attract pages (1), Portal's super jackpot blink
(143), the Recognizer and Disc Battle scenario (28 %). Tools used here (they need the Serum identification of the private
tree, so they are not in this repository; copies are in the project's files, `serum_zedmd/`): `dmd_serum_parity.py` (the
tables above), `unk.py` (the game's unknown frames by effect, with a picture), `idk.py` (reference capture against the game's
frame, per frame), `tfirst.py` (when an effect's text starts in the capture).

## Third measure (2026-10-30, fixed clip seed, fresh NVRAM per run)

The harness now seeds the random clips (`TRON_DMD_SEED=7`) and puts `game/data` aside for each run, so the scenarios no longer
start from the previous run's audits.

| | second | now |
|---|---|---|
| Same Serum frame found in the game's DMD | 70.0 % | 71.4 % |
| Distinct frames of the game unknown to Serum | 14.9 % | 11.6 % (2291 of 19831) |
| Coin page (10) | 0 of 95 | 95 of 95 |
| Combos (138, " COMBO" after the name) | | 92 % |

Added since: the credits screens (deffs 10, 15, 17) drawn live on the panel, named combos' " COMBO", the arm64 cross build of
the two tools with zig. Still open: the score display (19) bottom line and font size by magnitude, Flynn 105 (random reel, every
frame known to Serum), 86, 47, 114, 83, 79, the first attract pages, Portal 143's blink.
