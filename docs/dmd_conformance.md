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
