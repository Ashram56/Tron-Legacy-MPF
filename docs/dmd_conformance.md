# DMD conformance with the ROM's code (and PinMAME as a control)

**Reference since 2026-11-26 (STRICT RULE 4): the frames the ROM's own code draws, not PinMAME.** `assets/rom_data/dmd_code/` holds, for each of
the 144 effects and every random-clip variant, the frames of the ROM routine run in Unicorn (`assets/tools/gen_code_dmd.py`, recipes
`dmd_recipes*.py`, method in `assets/docs/dmd_from_code.md`, one frame per page flip, time in 16.000 ms OS ticks). `scripts/gen_media.py` builds the
classic DMD of the effects that have a recording from those frames only (no `reference_capture.gif`; effect 1's pages are `deff_001_pages`,
effect 22 is `mov pc, lr` and draws nothing). PinMAME stays a control: `index.csv` of that folder counts how many captured frames the code frames
reproduce (columns 41-127): 129 of 144 effects exactly; the 15 others carry a code-based reason in `assets/tools/dmd_recipes*.py` (REASONS): forced
zero-argument or null-record captures (32, 33, 36), tournament-gated paths, a capture of the emulator's memory, or one capture frame at the start.
`scripts/conform/code_conform.py NAME.dmd` (dump of `scripts/conform/godot_run.py`) counts the game's distinct frames that are a frame of the code run.
First measure (2026-11-26, 60 s of a scenario, columns 41-127 / all columns): attract_and_service 118 of 148 / 84; game_flow 178 of 517 / 46;
bonus 154 of 366 / 44; game_flow_tilt 113 of 230 / 48. The frames not found are mostly screens the code run draws with other values (live scores, balls, a
game in progress: the recipes use the factory state) and the live status panel; classifying them effect by effect, and running the effect with the
scenario's state, is the open work list. The misses are mostly the score display (effect 19: 291 of the 339 misses in game_flow, 116 of 212 in bonus; next 25, 77, 105, 10).
Check done on effect 19: run in the ROM code with the scenario's real scores (43,090 ... 275,210) and the credits record set to units -1 or 2 it draws
frames byte-identical to the game's (3 of the game's frames each, all columns), the same layout otherwise; with the factory record (units 0) the code
writes CREDITS 1/3 where the game shows CREDITS 0. So the layout agrees and the residual is the state (credits record, score roll-up animation
between two scores, which a fixed-state run does not produce), not a different drawing. Done since: the code is rerun with the state each scenario put the game in (`scripts/conform/sweep_state.py` effect 19: score moves written at a tick
with `ram_at`, playfield valid 0x372e8 and tick counter 0x21117f4 for the score roll FUN_01023940; `sweep_bonus.py` effect 25: items_table 0x02111690,
SoS 0x2111800, Portal 0x21118b8, multiplier 0x21115d4, totals read from the trace's `deff_args`; `sweep_args.py` effect 75 (the "N MORE TO START" count,
task +0x30); `sweep_gem.py` effect 77: gem_timer 0x3b12c x score). Game frames found in the code run (columns 41-127): **bonus 349 of 350 (99.7 %),
game_flow_tilt 229 of 230 (99.6 %), game_flow 484 of 517 (94 %), attract_and_service 139 of 148 (94 %)** (`sweep_credits.py`: effect 10's argument is the credit record number, 1; the attract pages now run to their end, 60 M instructions). Left: effect 105 (arcade award slot machine, 28 in game_flow: its reels follow 7 `random_below` draws, so a frame matches only with the same draws: the
game's RNG must follow the LCG at 0x372c4 for that, to check); 4 frames of effect 25 in game_flow (a total not yet swept); the attract's high score pages
(the table's initials differ from the ROM's reset table), the credits page, the tournament page and the clock page (state of the machine). Status panel columns 0-40 (game frames whose panel matches one drawn by the code, `sweep_panel.py`/`sweep_more.py` over the score, roll, fade age and the three timer bars): game_flow 455/509, bonus 251/350, tilt 206/230, attract 105/151. The misses are panel variants (gem timer bar at x 40 drawn by FUN_00027174, last-value pairs) whose state the sweeps do not yet reach; not a departure found.
The measure below (game vs PinMAME, per scenario) is the older control.


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

**Score display bottom line (deff 19), 2026-10-30.** The ROM rotates BALL/CREDITS and the replay level on the machine's clock
from power-up, in a cycle of 1718 ticks (156 BALL/CREDITS, 312 replay, 1250 BALL/CREDITS; measured on the reference captures:
the replay line starts at 29.2 s, 55.7 s and 108.3 s after power-up, a 26.5 s period). The game restarted the rotation with every
restart of the effect (an overlay over it) and used a 1562-tick period, so it showed the replay line too often. Now the bridge sends
`rot_ms` (time since power-up) and `score_display.gd` / `dmd_effect.gd` count from it. Same Serum frame found:
tron_targets 83.1 -> 84.1 %, clu_hurryup 81.3 -> 85.9 %. The replay line comes about 1 s late
(power-up epoch of the bridge versus the capture's).

**Score font (deff 19).** The score's font and row now come from the ROM's score-size table (`assets/rom_data/deffs/README.md`:
below 100,000 font 26, from 100,000 font 24, from 1,000,000 font 17, from 100,000,000 font 22) instead of a width guess, which chose
too large a font for 7 to 9 digit scores (it ran to the edge of the picture). clu_hurryup 85.9 -> 86.0 %, tron_targets 84.1 %:
the rest of the misses there are scenario divergence (other scores), not rendering.

## Fourth measure (2026-10-31, 21 scenarios, fixed clip seed, fresh NVRAM)

| | third | now |
|---|---|---|
| Same Serum frame found in the game's DMD (PinMAME's 17119 known frames) | 71.4 % | 71.8 % |
| Distinct frames of the game unknown to Serum | 11.6 % | 3.5 % (690 of 19752) |
| Effects measured alone against their PinMAME capture (distinct Serum frames of the capture also drawn by the game) | 82.5 % | about 93 % |

Rendering fixes of this round: the points of deff 73 at the end of its clip, blinking at the capture's rate (48 ms on, 48 ms off, fitted
on the capture), then the picture cleared; deffs 111 and 142 draw their text when the clip ends (142 also dims the picture and blinks the
points black on it); deffs 108, 83, 78, 97, 140 and 143 draw the clip **over** their text (`TEXT_UNDER_CLIP`: the ROM draws the bitmap after
its text), and 108 leaves the clip's open white area undrawn (`OPEN_WHITE`); the score display's bottom line and font (above).

**What the first figure cannot reach.** It asks for the same clip frame at the same effect, and two things make that impossible without
the ROM's own random numbers: the ROM picks the film clips of 19 effects at random (the game picks too, but not the same ones: the jackpot
of Light Cycle Multiball played a different variant, same effect), and the scenarios drift from the ROM's (other scores, other stages, other
timing, so other values on the same effect). The Serum file colours **every** variant and every value, so a ZeDMD shows the right colour
either way; for colour the figure that counts is the share of the game's frames **unknown** to Serum (3.5 %), which stay in Tron blue.
Measured alone, Flynn's awards (105), the Sea of Simulation values (115) and the Portal progress effects still differ only where the capture
shows a different award, stage or number than the values the measure feeds in.

Still open: the score display's overlays timing against the ROM's (108/111 start at other moments), the first attract pages (the reference
capture of the attract has no event log, so it cannot be paired effect by effect), Light Cycle intro (86), 47, the ZUSE letters of 93/94
(drawn from sprites, not in the isolated capture).

## Fifth measure (2026-10-31, equal draw)

The ROM's film clips are random; the game's are too, but not the same draws. To compare the rules rather than the dice, both sides are
forced to the same draw: PinMAME's tracer returns 0 from the ROM's `random_below` / `random_percent` (`TRON_RNG_ZERO=1`, the hook in
`scripts/conform/tron_ref_dmddump.diff`, rebuilt with `build_tron_ref.sh`), and the game takes its first variant (`TRON_DMD_SEED=first`).

| | fourth (random draw) | fifth (equal draw) |
|---|---|---|
| Same Serum frame found in the game's DMD | 71.8 % | 80.2 % |
| Distinct frames of the game unknown to Serum | 3.5 % | 550 of 19318 |

Light Cycle jackpots (87, 88, 89) are not random in the ROM: the clip follows the ROM's `lc_clip_level` and the n-th Jackpot of the level
(`JACKPOT_CLIPS` in `features/light_cycle.py`, variants `level_L_N.gif`); the game now passes it as the `clip` argument. Alone: 87 26/27, 88 31/32,
89 21/22 known frames. Next by weight: 86, 141, 105 (Flynn), 114, 106, 47.

Re-measured after the jackpot clips (20 scenarios, equal draw): same Serum frame found 80.9 % of 16665 known frames, 570 of 19156 game frames
unknown to Serum. Weakest scenarios: Sea of Simulation 44 %, Portal Multiball 55 %, Light Cycle Multiball 67 %, Disc Multiball 71 %.
Effects 86 and 141 are exact alone (86: 16/16 known frames); what is left in the scenarios is drift, not rendering: for example in
light_cycle_multiball the capture shows 155,130 where the game shows 157,630 (a 2,500 point scoring or timing difference earlier in the
scenario), so every frame with a score differs. Next: trace such score differences scenario by scenario (rules, not display), then 105, 114,
106, 47.

Seventh measure (same day): the ROM's weighted bags (`bag_weighted_pick`, e.g. the Flynn's Arcade award) were still drawn at random in PinMAME;
`TRON_RNG_ZERO=1` now forces them to their first entry too (hook in `tron_ref_dmddump.diff`), and the game's `os_.pick` takes the lowest draw
under `TRON_DMD_SEED=first`. Result: **81.8 %** of 16669 known frames found (Flynn's Arcade 105: 60 -> 208 of 288), 575 of 19339 game frames
unknown to Serum; Bonus 94 %, Quorra 88 %, Clu 91 %. Weakest: Sea of Simulation 48 %, Portal 58 %, Light Cycle MB 65 %, Disc MB 70 %.

Eighth measure: Sea of Simulation's stage-completing shot (deffs 116-124, task+0x34 set) plays the fixed clip of FUN_01027478, not one of the two
random ones: Sea 48 % -> 74 %, total **82.9 %**. The conformance pairing now gives a window to the effect that caused a Sea of Simulation status
(deff 114) restart, not to the restart. Deff 108 variants leave the open white area undrawn too and "N MORE" blinks 2 frames on, 2 off
(FUN_01020388). Deff 115's points blink on the clip's frame period (48.5 ms); a one-frame clip offset remains.

Ninth measure: the film clips (variants) of the effects that dim under their text (87-89, 142, 111, 48, 49) dim like the effect's own frames
(`DIM_AFTER_MS`); Light Cycle Multiball 65 % -> 73 %, total **83.6 %**. The points of 115-124 blink with the clip's pictures (`blink_frames`),
144 and the End of Line jackpots (58-60) blink every ROM frame (3 / 6 ticks), shown first. `DMD_SORT=1` gives a per-effect pairing (starts
less than 0.2 s apart sorted by id) for diagnosis; the headline figure uses the traces' order.

Tenth measure (full, 20 scenarios, equal draw, all fixes above): **85.0 %** of 16669 known frames found, 632 of 18942 game frames unknown to
Serum. Disc Multiball 86 %, Recognizer 87 %, Light Cycle MB 72 %, Sea of Simulation 72 %, Portal 64 %, Flynn's Arcade 74 %; Bonus fell from
94 % to 80 % (to check: its points blink).

Open (found 2026-10-31): in `switches_and_shots` the game and the ROM score the same points, but the Disc access counter differs ("3 MORE" in the
ROM, "4 MORE" in the game): the first hit on the Recognizer bank counts double when the moving target is lit, and the moving target's
phase (task 0x7d, 93 ticks per step) differs after the first minute of the ball (lamps 51-53, `docs` trace: the ROM's pattern is not periodic
there, the game's is). Frames of every effect that shows a counter then differ; this is a rules timing gap, not a display one. Clip variants of
deffs 108 and 116-124 now use the capture's frame period (32 ms and 49 ms), not the gifs' 40-52 ms.

Lead for the Recognizer phase gap: the ROM's moving-target task 0x7d (`task_7d_moving_lit_target`, 0x01020034) leaves a step early (and skips
targets) when the lit target's bit is set in the per-player disabled-switch mask (0x021117b7, built from `sw_is_disabled` 0x0000e098: a switch
whose stuck/ignore bits or hit counter 0x02110108[sw] say so). The game's `recognizer.py` states that no target is ever disabled; the ROM trace
of switches_and_shots (lamps 51-53 after the first minute) is not periodic, which fits a disabled target. Not modelled yet.
Measure noise: a scenario moves by up to 8 points between two identical runs (timing), and 120 fps instead of 30 gives the same total (85.0 %).

Deff 140 (Portal start) draws its Sea of Simulation bonus text (screen 1) OVER the clip, so it leaves `TEXT_UNDER_CLIP`: Portal 63 % -> 72 %, total **85.5 %**.

Score roll (2026-11-01): while the playfield is valid, the ROM rolls the current score once 62 ticks have passed without points, and again
every 62 + 4H ticks (FUN_01023940; H from the score-size table at ROM 0x40d3484: band rows 4-20 from 1,000,000, else 2-23): the band is
blanked from the top one row every 2 ticks, then shown again from the top; the current player's score in the status panel does the same in
6 + 6 steps (deff_draw_status_panel). The game had a still score; `score_display.gd` `roll()` now does it for deff 19 and every effect with
the panel. Deff 83 ("N MORE TO LIGHT") now crosses in the ROM's direction (two clip variants chosen by the mask): no known frame of 83 missed.

Eleventh measure (full, 20 scenarios, equal draw; score roll, deff 83 direction, Flynn's Arcade reel at equal draw, last points per score
change): **86.3 %** of 16669 known frames found. Flynn's Arcade 75 % -> 84 % (deff 105: 287 of 288), Light Cycle MB 82 %. The roll's phase still
differs from the ROM's on the score display. Deff 140 (Portal intro) after its animation: the last picture at level 1 (palette 0x30) and the
text blinking every 3-tick frame, lit first (palette 0x40); COMPLETE ALL SHOTS holds about 370 ms first (`blink_after_ms`): Portal 73 % -> 77 %.

Bottom-line rotation of the score display: deff_019 counts its own ticks (156 BALL / credits, 312 REPLAY AT, 1250 BALL / credits), so the
rotation starts over each time the score display gets the display again (an effect in front ends, or deff 19 starts with nothing in front),
not from power-up (`MediaBridge.score_display_shown`, called by `display.py`). Zen rollover 76 % -> 89 %, Combos 82 % -> 90 %.

Twelfth measure (full, 20 scenarios, equal draw, with the bottom-line rotation): **89.6 %** of 16669 known frames found (score display 91 %;
skill shots 100 %, Flynn's Arcade 99 %, game flow 98 %). Weakest: Sea of Simulation 74 %, Portal 79 %, Tron targets 84 %, Find Flynn 85 %.

Deff 112 (TRON timed award, 0x0100d108) played its capture (SUPER SPINNERS, with the panel of the recording) for every award. It is now drawn:
the TRON outline at level 1 (palette slot 15 -> 1), the award's two words (DOUBLE SCORING, SUPER POPS or SUPER SPINNERS, `screen` from the
rules) lit 2 frames of 4, then from 1410 ms the second screen (ALL SCORES DOUBLED, POPS SCORE 3X, SPINNERS SCORE 3X: title at level 4, value
held then blinking every 50 ms), with the live status panel; times read off the capture. Zen rollover 89 % -> 93 %, Tron targets 84 % -> 96 %.

Deff 83's right-to-left variant was drawn on an opaque canvas that hid the text under it: now transparent (Find Flynn 85 % -> 98 %). The
ticks since the last points (DAT_021117f4) start over at ball start (event 0x13, FUN_01023858), as in the ROM.

Thirteenth measure (full, 20 scenarios, equal draw): **92.2 %** of 16669 known frames found (score display 95 %; skill shots 100 %, combos
99 %, Find Flynn, Flynn's Arcade and game flow 98 %). Weakest: Sea of Simulation 73 % (deff 19 paired at the VUK where the ROM runs rule task
0xa9 with no effect start), Portal 80 % (deff 141), disc multiball and Recognizer 87 %. Left by weight: 19, 47, 86, 141, 106, 115, 73, 25.

Deff rules at the ball start: every reference trace starts deff 104 (FLYNN'S ARCADE IS LIT, 0x100de10), then 19 (0x2074c), then 19 again
(the rules, 0x19944). The game started 19 first (a rules refresh between game start and ball start) and restarted 19 on every music change;
FUN_000198a8 starts the rule's deff only when it is not running. From the ball end to the ball start the rules now wait (`display.held`).
Sea of Simulation 73 % -> 84 %.

Fourteenth measure (full, 20 scenarios, equal draw): **93.2 %** of 16667 known frames found (score display 96 %; Portal 88 %, Sea 84 %).

End of ball bonus (deff 25): the game showed TOTAL BONUS for the whole count. It now draws the ROM's screens (0x01000e7c): BONUS / base,
a screen per item, SEA OF SIMULATION and PORTAL line (name, +value, running total), each multiplier step (%dX, total x n), then TOTAL BONUS
(`rom_layout.SCREENS[25]`, values live from `features/bonus.py`). Bonus scenario 89 % -> 94 %, every frame of deff 25 found.

Last points (FUN_010238ac on event 0x4d, posted by every score_add): one value per add, not one task run's sum (a jackpot
with its switch's 10,000 showed 510,000 for 500,000). Portal's super jackpot (deff 143): the text over the picture at 4240 ms
(the clip hid it). Jackpots with a picked clip (deffs 48, 49 at random; 87-89 by the Light Cycle level): the ROM's clip function
returns its last bitmap and the text loop starts then, so each clip dims and shows its text at its own end
(`rom_layout.CLIP_END_TEXT`, effect.json `variant_shift`); the game waited the captured clip's 1410 ms (the first Disc
Multiball clip ends at 600 ms).

Fifteenth measure (full, 20 scenarios, equal draw): **93.9 %** of 16667 known frames found. Bonus 94 %, Portal 91 %, Disc
Multiball 91 %, Find Flynn 99 %. Weakest: Sea of Simulation 85 %, Recognizer 87 %. Left by weight: 19, 106, 77, 95, 86, 115, 72,
141, 1, 73.

Deff 108 (N MORE TO ACCESS DISC): `blink_frames` in OVERRIDES never reached the effect data (keys ending in "_frames" were
taken for frame times; deffs 115-124 lost theirs too); "%u MORE" is lit on frames 0-1 of every 4 and hidden, not black, on the
others; the Recognizer clip runs 3 ticks a picture (FUN_01024378(3)), not the capture's 33 ms; and it is drawn over the status
panel (bitmap_draw_masked from x 0, `rom_layout.CLIP_OVER_PANEL`). Recognizer and disc battle 87 % -> 91 %.

Sixteenth measure (full, 20 scenarios, equal draw): **94.4 %** of 16667 known frames found (score display 97 %). Disc
Multiball 94 %. Weakest: Sea of Simulation 86 % (deff 115: 1 of 74, its background picture one column off), Portal 91 %,
Recognizer 91 %. Left by weight: 19, 95, 77, 106, 86, 115, 141, 1, 73, 72.

Seventeenth and eighteenth measures. Zuse does not restart its background (deff 95) at the end of deff 96 (observed). That
rule was first applied to every mode's background, and Portal and Quorra fell (17th measure: 93.9 %). The ROM restarts
Quorra's 65 at the end of 68 (41.51 s), so the rule is now limited to Zuse's 95. Eighteenth measure (full, 20 scenarios,
equal draw): **94.6 %** of 16667 known frames found (score display 97 %, Zuse 98 %, Quorra 93 %, Portal 91 %). Weakest:
Sea of Simulation 86 % (deff 115), Portal 91 %, Recognizer 91 %. Left by weight: 19, 77, 86, 106, 141, 72, 115, 1, 73, 65.

Nineteenth measure. The fonts now take their spacing and each glyph's x offset from the ROM's font table (asset repo
`rom_data/fonts.json`) instead of rules read off captures. The outlined fonts also draw the comma one dot left, and fonts
25 and 27 have the table's spacing. Deff 115 goes from 1 to 74 of 74 frames (its outlined value's border erased one
column of the picture). Full measure (20 scenarios, equal draw): **95.7 %** of 16667 known frames found (Portal 98 %, Sea
96 %, bonus 99 %, deff 141 97 %, deff 72 96 %). Left by weight: 19 (250), 86 (69), 77 (58), 1 (57), 73 (54), 106 (53),
65 (40), 47 (35), 95 (34).

**Attract animation page (2026-11-02).** PinMAME draws the status panel (P1's "00" and the separator column x 40, level 15) left of the
animation (images 0x5a0-0x5c4); the game drew the animation alone, so every frame of the page (about 30 of 298 in an 85 s attract, the
"Tron Legacy" logo animation) was unknown to Serum and shown in Tron blue. `build_attract_art` now draws them into each frame: unknown
frames of the 85 s attract run 99 -> 10 (PinMAME: 0). A game's last scores are not drawn on this page (the page is not given the
panel's live scores). Found by comparing the game's frames with their nearest PinMAME frame: 56 pixels apart, always the same ones.

## Pass over the scenarios (2026-11-03)

Frames the Serum file does not know, game / PinMAME, per scenario (classic DMD, equal draw): game_flow 1/1134,
bonus 0, combos 0, Light Cycle MB 0/955, gem and CLU hurry-ups 0, Portal MB 2/739, Quorra MB 11/812 (effects 62, 63: the
small film is at another phase), disc multiball 33/933 and recognizer+disc battle 40/411 (effects 108, 111: film
phase and contour, PinMAME 0), Sea of Simulation stages 4-8 20/1151 (PinMAME 21; was 197: deff 125 never plays in 1.74,
the ROM shows deff 126 TOTAL 2.28 s after completion, and stage 6 needs all six shots through the chain table),
attract 3 (the clock page). Open: Daft Punk MB 132/611 (effect 57, "n MORE FOR ADDABALL": the bright triangle and
the background lines differ from PinMAME's frames over ~675 dots per frame; the level histogram is the same, so the
cause is a blink or background phase, not the palette).

**Deff 108, the panel under the clip (2026-11-03).** The Recognizer's film (deff 108) is drawn with `bitmap_draw_masked`, which does
not draw level 0, so the status panel's score shows through it. Some clip variants (the tower film) had their level-0 pixels over the
panel (x < 41) opaque black from the extraction, so the score vanished during the film while PinMAME keeps it (frames unknown to Serum
in Vincent's play). `gen_media.clear_black_panel` makes them transparent for the effects of `CLIP_OVER_PANEL`. The panel is now right in
those frames; the rest of the unknown frames of 108 (23 distinct with the first variant, 4 variants measured) are slivers along the
film's contour and the "N MORE" digits, the film phase listed above, still open. Deff 111's last frames (about 2.1-2.8 s) are open too.

Deff 111, the text at the end of each clip (2026-11-03): the text of "N MORE TO START DISC MULTIBALL" comes when the picked clip ends, over its last picture dimmed, not at a fixed 1960 ms (that is clip 0's length only). Deff 111 is in `CLIP_END_TEXT` and each clip's pictures last the ROM's ticks (`random_parts.csv`: 2 to 5 ticks of 15.8 ms a picture, `scripts/gen_media.py`). Four seeds of the Recognizer scenario: the frames Serum does not know in 111 went from 15 to 0 on the variants that had them.

Forcing another clip of a random effect (2026-11-03): `TRON_RNG_ZERO=1 TRON_RNG_VALUE=N` makes the ROM's draws at the effects' sites return N instead of 0 (clip N of deff 108's four, of deff 111's eleven), so PinMAME gives a reference for clips 1 to 3 as well (hook in `tron_ref_dmddump.diff`). Deff 108, the film's white (2026-11-03): the film is the ROM's own bitmaps (`dmd_library`, the four clips of `random_parts.csv`, drawn masked at x 0 or 41, `ROM_CLIPS` and `rom_clip()` in `scripts/gen_media.py`) and the full-white areas of 100 dots or more are transparent (`open_white_big`: the bitmaps hold white where the ROM draws nothing, the text shows there; the shine spots of the film are 60 dots at most, the white components of the four clips are all below 60 or above 120). The earlier gif-based clips lost those spots (the edge rule erased them) and kept the filler. Four seeds of the Recognizer scenario, frames unknown to Serum: 66 before, 14 after (3, 0, 7 and 4). Making every black dot of the film transparent is worse (40 to 45 unknown).

## Running the code conformance (2026-11-26)

```sh
for s in game_flow bonus game_flow_tilt attract_and_service; do python scripts/conform/godot_run.py $s 60 OUT; done     # the game, classic DMD, with deff_args
export TRON_ROM=trn_174h.bin
python scripts/conform/sweep_state.py S19.pkl OUT/*.jsonl            # effect 19 (scores, moves, roll)
python scripts/conform/sweep_bonus.py S25.pkl OUT/*.jsonl            # effect 25 (items, SoS, Portal, multiplier, totals)
python scripts/conform/sweep_args.py S75.pkl 75 20000000 1 2 3 4 5 6 # effect 75
python scripts/conform/sweep_gem.py S77.pkl OUT/*.jsonl              # effect 77
python scripts/conform/sweep_credits.py S10.pkl                      # effect 10
python scripts/conform/sweep_arcade.py S105.pkl OUT/*.jsonl          # effect 105 with the game's draws
python scripts/conform/code_conform.py --extra S19.pkl --extra S25.pkl --extra S75.pkl --extra S77.pkl --extra S10.pkl --extra S105.pkl OUT/NAME.dmd
```

Result of the last run (game frames found in the code run, columns 41-127): game_flow 508 of 509 (the missing one is the first, blank frame before any
effect), bonus 349 of 350, game_flow_tilt 229 of 230, attract_and_service 139 of 148 (the rest: the high score table's initials, the credits page, the
tournament page and the clock page, which depend on the machine's data).

Status panel (columns 0-40, drawn by deff_draw_status_panel 0x010230ec), game frames whose panel is a panel of some frame of the code run: game_flow 444 of 509,
game_flow_tilt 206 of 230, attract 105 of 148, bonus 216 of 350. The misses are panels with another state than the sweeps feed (the hurry-up value row
fading under the score in bonus, other players): the sweeps of effects 19 and 77 must also vary what the panel reads (open work).

## Font placement from the ROM (2026-11-26)

`scripts/gen_fonts.py` placed glyphs vertically with heuristics read off captures; the ROM's glyph table gives the exact y offset
(`assets/rom_data/fonts.json`, text_draw_str 0x28f74: `y - h + y_offset + 1`). 73 of 1635 glyphs differed (the "#" of fonts 10-13, "*", ";", "<=>", quotes):
"HIGH SCORE #n" had its "#" one row too low. The fonts now read the ROM's offset. Attract, columns 41-127: 139/148 -> 143/151 distinct frames found in the code run;
the 8 left are the credits, clock and custom-message pages (machine state), to run in Unicorn with the machine's own state.

## Attract pages checked against the code (2026-11-26)

- The ROM's attract table (RAM 0x36e10, file 0x36e10, 32 entries: predicate, routine) is walked by deff 1 (0x01034364), which skips a page whose predicate returns 0.
  Entry 30 (clock, routine 0x32d04) has predicate 0x32cfc = `mov r0, #0`: **the ROM never shows a clock page**. The game's CLOCK page
  (an invention, date and 12/24 h time) is removed; `attract_pages.py` cites the entry.
- Entry 31 (custom message, predicate 0x010002dc = adj 2 == 1, routine 0x01000308): with no message stored FUN_00005858 asks FUN_00006110 for the language's
  factory message id (824 = "PARTICIPATE IN\nLOCAL TOURNAMENTS!" in 5 languages, table 0x040eeb7c); `gen_code_dmd.py` stubs 0x6110 (`deff_unicorn.STUBS`) and
  writes `rom_data/dmd_code/deff_001_pages/deff_031`; the game's frame is that frame.
- Entry 1 (credits, 0x01000128) with FREE PLAY (adj 34 = 1, record 0x2102110) and 0..3 credits, 0..8 units: `scripts/conform/sweep_pages.py`.
- Result (attract_and_service.dmd, columns 41-127): every distinct frame of the game is a frame of the code run except the DOT MATRIX TEST
  page (service, below). Entries 11-26 (player-record pages, FUN_0002553c) need competition records and are not shown at the factory settings.
- Not decoded yet: DOT MATRIX TEST (service, routine 0x01003fb44 in the menu table `service_texts.csv` 0xbd): the ROM sweeps one lit column at a time
  (x 0-127, 6 ticks each), one lit row at a time (y 0-31), then fills row by row with alternating 0/0xff, twice; the game's
  `DotMatrixScreen` shows three still pages (ALL DOTS ON, ALL DOTS OFF, STRIPES) that the ROM does not have.

Attract, second pass (2026-11-26, same day): the ROM's panel in the attract draws the separator (x 40) and the three 10-dot segments of row 31 (x 4-13, 16-25, 28-37) at level 1, and
"00" or the scores at level 15 / 1; the game drew a full-level line (text pages from `text_page.tscn`, the animation page from `gen_media.build_attract_art`, which copied
PinMAME's level). Both now use level 1 and the segments (page 28 of the code run: 0 differing dot). There is no "PLAYER n" page in the ROM's table: the last scores go
to the panel (`attract_pages.py` `panel()`: the same ScoreDisplay as the in-game panel, P1-P4, the last turn's player bright), so those invented pages are gone. The REPLAY pages are four table entries (2-5, FUN_00022a90(n) != 0),
one "REPLAY AT <value>" page per level that is set. Entries 11-26 (FUN_0002553c / FUN_00025598, mode 4 of FUN_000251cc: the competition records) are not modelled (adj 46).
Measured on the attract + service scenario: panel 142/143, columns 41-127 141/143 (the two left: the service entry fade and SET DATE/TIME, which shows the machine's clock).

## SET DATE/TIME from the code

The screen is ported from FUN_01045b44 (0x01045b44) and its line FUN_0000d814 (`game/tron/rom_datetime.py`, `DateTimeScreen`): fields in the
order month, day, year, hour, minute, second (the old five-field YEAR-first version was invented), the edited field blinking (shown 9 loops,
hidden 8, a loop = 2 ticks, solid 16 loops after +/-), BACK to the previous field, "DATE/TIME SET" (msg 0x1e8, font 8 row 10, the running
clock on row 18, msg 0x1e9 on row 27) after the seconds. +/- rules from FUN_0000d438..d6dc (wraps, month length table 0x040d7cb8, leap years).
Widths follow FUN_00028a74 (a glyph with a negative x offset, the comma, counts to the left of 0: 2 dots, not 1) and the line is centred on
(128 - total) / 2 with total = the ROM's sum (13 gaps). Checked by `scripts/conform/sweep_datetime.py` (ROM routine in Unicorn, RTC stubbed
via `D.STUBS[0xd244]`, 12 months, 12 h and 24 h, hours 0/1/11/12/13/23, leap day, 2000 and 2099): 26 of 26 pictures found among the code's frames, with the blink hiding the right field.

## Competition mode (adj 46, attract pages 11-26): what the code says (2026-11-26)

- **Pages 11-26 and the TOURNAMENT menu need a tournament record**: their predicates read the current record of the 10 records at
  0x02100000 (`FUN_000251cc` = state, 4 = running; `FUN_0002553c`, `FUN_00025598`, record word 0x49). A record is only created by START
  TOURNAMENT (`FUN_0103cde8` -> QUICK START `FUN_0103a49c` / CUSTOM `FUN_0103bf68`, both end in `FUN_000252c4`), by the start of a game with
  the Tournament Start button (sw 15, `0x20d1c` param 2, state 4 only) or by the USB / network tournament files. That menu is shown only
  when `FUN_0002ffc0` -> `FUN_00005ff0` finds a valid country record (0x021100d8, written at boot by `FUN_0000605c` from the inverted DIP
  port 0x01100005, masked 0x7f) whose index is below 28 (table 0x040e17e0). The factory DIP value (0x80, PinMAME's default, and the
  one the machine ships with) gives index 0x7f: no tournament menu, no record, pages 11-26 skipped. The game does the same
  (`service.py` `visible()`: 0x2ffc0 false). Reason, not an omission.
- **Adj 46 PLAYER COMPETITION** (factory YES): `FUN_0002dcc0` (the START button's press handler) calls `FUN_00019f98`, which starts task 0x3b
  (`FUN_00019f20`): for 62 ticks it checks that the machine is in attract (`0x37274 & 0x118 == 0x10`), adj 46 = YES, a credit or free play
  (`FUN_000202a8`) and START still held; then deff 39 (COMPETITION READY, six 62-tick frames in `rom_data/dmd_code/deff_039`) starts. A START with
  a credit starts the game at once (`0x20d1c` -> `0x20584`, which clears state bit 0x10), so the task ends on its first tick; the held
  START only reaches deff 39 when the start is refused: `FUN_0001f470` false or `FUN_0001f6fc` (balls counted by the trough differ from the
  installed count `FUN_0001e044`), which runs the ROM's ball search task 0x2b (`FUN_0001f4a0`) behind deff 11 LOCATING PINBALLS. A game started
  while deff 39 runs sets game flag 0xf (`0x20584`): the competition game, whose only effect in the code is Flynn's Arcade's 500K weight
  +1000 (`0x0100df9c` via `FUN_00019e98`, ported: `features/arcade.py`). So adj 46 has no effect with the trough full, the ROM's own design.
- **START with balls missing (ported 2026-11-26)**: `FUN_0001f6fc` (0x0001f6fc) refuses the start when the balls counted (`balls_count_all`
  0x0001bd18) are 0 or differ from both the installed count (`FUN_0001e044`, the trough's switch list) and the recorded one (`FUN_0001e080`,
  NVRAM 0x0211191c); it runs `task_ball_search` (0x0001f4a0, `FUN_0001f758`), and the press that started it does not start the game. Per
  round (4 rounds): audit 0x25, deff 11, then 52 re-counts every 6 ticks, ending at once when the count is right; at the end game flag 0xb when
  fewer balls than recorded, recorded count := min(counted, installed) (`FUN_0001e0e4`), deff 11 stops. The next START starts the game and,
  with flag 0xb, clears it and adds audit 0x27 (0x00020d14). `os_layer.py` `_start_search`, `tests/test_start_search.py`. The seven calls after audit 0x25, read in the code (2026-11-27): (1) `FUN_00003138` loops over the coils (count 0x040c01a0) and `FUN_000030a8` pulses each whose
  descriptor has a ball search length (+0x12) and none of the flag bits 0xa0dc: the two slingshots, 64 ms each (the bumpers carry flag 0x2000, the flashers 0x4,
  the kickers 0x40; `rom_data/io/coils.csv` ballsearch_ms): ported, `os_layer._search_pulses`, at every search round and every in-game search, checked by
  `tests/test_start_search.py`; (2)-(7) `FUN_000072c8`, `FUN_0000364c`, `FUN_0001fd48`, `FUN_00003b68`, `FUN_00023dd4`, `FUN_00004068` loop over
  tables (counts 0x00037270, 0x040d1024, 0x040c321c, 0x040d1028, 0x040d1034) with per-entry routines `FUN_000071f4`, `FUN_00003560`, `FUN_0001fc94`, `FUN_00003a8c`,
  `FUN_00023c6c`: resets of the switch, timer and ball-device records. `FUN_0001fd48` also starts, for ball devices 1-3 (the trough, shooter lane and VUK:
  table 0x040e41f4, kinds 5, 1 and 8, record +0x15 = 0), the device task 0x18 + dev (`FUN_0001dc70`: the kind handler of the RAM table 0x3744c via
  `FUN_0001bf70`, then the trough drain check body of `FUN_0001dd90`) without a ball-presence test, and sets game flag 0xa. The kind handlers are in ROM at 0x0003744c
  (12 bytes per kind, slot +8 = the eject handler: kind 1 shooter lane `FUN_0001c264`, kind 5 trough `FUN_0001c668`, kind 8 VUK `FUN_0001d05c`; slot 0 init, slot 4 entry).
  Each reads the device's flag word (record +0xc): the search's 0x1a sets 0x10 (request), 0x8 and 0x2; with a request and bit 2 set it posts event 3 to the
  device's own handler (record +0xc: 0x0101bbc0 for the trough), recounts its switches and, when the device holds more balls than the target in record +0x12
  (0 here: any ball), runs the kick sequence (events 7, 8, 9 with the retries of descriptor +0x22): an empty device is not kicked, a device holding balls
  is. In a game `FUN_0001fc94` takes the other branch for a device whose RAM record +0x15 is nonzero (the balls it must keep): only the 4th search
  calls `FUN_0001e17c` once (game flag 0xa then blocks a repeat). The game does not reproduce the device kicks (departure, `docs/rom_differences.md`): MPF's ball
  devices own the ejects, and kicking the trough or the VUK from outside would put balls in the shooter lane in attract or desynchronise their count. Event 0xc: the static registrations (`FUN_00007944`, 121 calls) hold none for events 0xd and 0xe
  (`event_post` 0x79ec then returns 1) and four for 0xc (`FUN_00017128`, `FUN_00018560`, 0x0100a414, 0x0100bc88), each walking one object list (RAM 0x37408,
  0x37410, 0x37404, 0x37400) and calling one virtual method of every object (base slot tables in ROM, e.g. 0x39d08: slot 0xdc `FUN_0001723c` starts the object's task 0x2b
  `FUN_00017174` that re-reads its switch ring; slot 0xfc `FUN_00017bf0` sets a bit): resynchronisations after a search, not kicks. The held-START deff 39 is ported (`_start_pressed`, `_competition_hold`): at the press (the ROM acts at the press, MPF at the release) a
  refused start runs the search and task 0x3b (`FUN_00019f20`) times 62 ticks while attract, adj 46 = YES, a credit and START hold; at its end it calls
  `deff_start(0x27)`. During the search deff 11 (priority 224, `assets/rom_data/deffs/deffs.json`) holds the display and deff 39 has priority 80, so the ROM's own display
  rule refuses it: COMPETITION READY is never seen behind a ball search, and flag 0xf stays clear there. The other refusal, `FUN_0001f470` false (a ball
  device task or task 0x15 running at the press, no search), is the one where deff 39 can show; it is not modelled (a ball device task is MPF's).

## Status panel in game: the last award (2026-11-26)

`sweep_panel.py` now builds its (last award, total) pairs from the `score_add` events: `FUN_010238ac` (0x010238ac) keeps the larger points
within 16 ticks (age `0x21117fc` < 0x10) and only restarts the age for smaller ones, so after 42 000 + 1 090 the panel shows 42 000, not the
sum 43 090 (the game's `media_bridge.score_added` does the same). With these pairs (1 869 states, 2 169 distinct frames) the in-game panel
(columns 0-40) of `game_flow` matches the code for all but 2 of 121 distinct panels (58 before):
the very first frame (a uniform level before the ROM draws anything: the display's start-up, not a ROM frame) and one frame of
effect 10 (the credit text, three coins at 0.6 s) that the credit sweep reproduces for its own columns. Not claimed beyond these runs: the
gem timer bar (0x3b584) pairs other than the swept ones.

Result of the same run against all the sweeps kept so far (state, bonus, args, gem, credits, arcade, 10, 25, 105, panel): columns 41-127 of
`game_flow` 515/516 distinct frames (the one miss is the start-up frame above); the status panel 119/121 as above. The panels of the other
scenarios (bonus, tilt, attract) are not swept with the score_add pairs yet: the same script takes their `.jsonl`.

Other scenarios, same method (2026-11-27): `game_flow_tilt` panel 47/48, `bonus` panel 120/121 (29 missing at first: the gem timer bar 0x3b584 held at 9
or 10 rows, column x = 40 rows 21-31, while the last award fades (`SWEEP_GEM=9,10`) and while the score rolls up in the 15 000 000 bonus
(`SWEEP_GEM_ROLL=9,10`, counters 0x21117f4 and 0x21117fc), both options of `sweep_panel.py`). Each scenario's one remaining panel is the
display's start-up frame, which is not a ROM frame. Bodies (columns 41-127): game_flow 515/516, bonus 349/350, tilt 229/230, same single frame.
The attract scenario, re-run on the current game (2026-11-27; the first dump of the day predated the attract panel fix and wrongly showed the separator at
level 15, so a "REPLAY page panel" departure noted for a few minutes in this file's history does not exist): panel 86/87 distinct panels (the one miss is the
start-up frame), columns 41-127 222/233, the 10 misses being frames of effect 1 (the pages that show the machine's own state: high score table initials, credits page,
clock-free pages; see the attract notes above).

The one body miss of the attract run (9.7 s, repeated) is the GRAND CHAMPION page ("G S" 75,000,000): the stored page frames hold only #1-#4. The ROM
routine 0x0100075c after FUN_0001a9f4(1) (`scripts/conform/sweep_gc.py`) draws it with 0 differing dots from the game's frame. So the attract: panel
86/87, body 233/233 apart from the start-up frame.

## Multiball scenarios against the code (2026-11-27)

Fresh runs (`godot_run.py`) of the six multiball scenarios, compared with the frames the ROM code draws (columns 41-127), after feeding the code the state
each effect had in the game (`scripts/conform/sweep_live.py`, one pickle per effect passed to `code_conform.py --extra`). The game now traces the RAM values a
live effect prints (`deff_live` events, `media_bridge._log_live`) in addition to the start arguments (`deff_args`); `CONFORM_BANDS` and the attribution by
`deff_args` are options of `code_conform.py`.

| Scenario | Found before | Found after | Left (last effect before the frame) |
|---|---|---|---|
| portal_multiball | 426 / 751 | 700 / 740 | 19: 31, 141: 4, 25: 3 |
| light_cycle_multiball | 501 / 1072 | 942 / 1072 | 86: 71, 19: 58 |
| disc_multiball | 903 / 1292 | 1117 / 1272 | 19: 78, 47: 75 |
| flynns_arcade | 293 / 783 | 742 / 783 | 19: 38, 107: 2 |
| daft_punk_multiball | 351 / 996 | 499 / 996 | 57: 341, 19: 155 |
| end_of_line_multiball | 323 / 1071 | 577 / 1071 | 19: 382, 57: 111 |

What fed the code, with the ROM addresses: effect 141 (0x0102ffa0) `pm_phase` 0x3b878, `pm_super_value` 0x3b854, the seven shot counters 0x3b85c + 4 i
(next award FUN_0102f5f4); effects 140 (0x0102faec), 142-145, 103, 62, 48-51, 58-61, 83, 90, 112, 139, 26: the task arguments (task + 0x30, + 0x34); effect 47
(0x01007f34): `dmb_phase` 0x3af04, disc and recognizer counts 0x3af10 / 0x3af14 (shots left = adjustment 68 / 69 minus the count), jackpot 0x3af18, super
0x3af1c; Light Cycle jackpot films 87-89: the clip level (task + 0x3c, < 6) and the clip (task + 0x40, inside the level's range of table 0x040d2ffc, else
its first; 88 and 89 take the table's +4 and +6 entries via the jump table 0x040d3084). The "86" misses were these films (the film runs in front of the
background effect 86, whose own frames match).

Not closed, with what is known (not a conclusion that the game is right):
- Effect 19: the sweep puts the score move at tick 30 of the effect and starts the roll at one phase (`sweep_state.py`); the multiball scores move at other
  ticks, so the roll's intermediate scores and the rotating bottom line are not all produced. Not yet checked with other move ticks.
- Effects 55, 57, 58, 59, 60, 83, 42 (Daft Punk and End of Line): drawn by the game's own engine from the ROM's routines since 2026-11-27 ([dmd_engine.md](dmd_engine.md)). Daft Punk 654 -> 1382 / 1383 and End of Line 700 -> 1196 / 1197 frames found; the one left in each is the display's start-up frame. The report's "last deff_start" attribution hid these effects behind 19 and 57: 58 / 59 draw their own dimmed film.
- Effect 47: 75 frames left after the state sweep, 47 is drawn between effects 48/49 (jackpot awards), timing not reproduced yet.
- Effects 25 and 77 (sweeps run, not yet folded into this table).

## Light Cycle multiball with the engine (2026-11-27)

Effect 138 (N WAY COMBO) is ported (`rom_deff138.py`, 129/129, 128/128, 129/129 frames against the ROM code in Unicorn); in the
light_cycle_multiball scenario it leaves 4 misses (the named-combo text, ROM message not yet read), effect 55 two.
Effect 105 (Flynn's awards): with the draws the game made (`sweep_arcade.py`) its 50 misses go to 0, so the comparison is exact at
equal draws. The ROM's generator is ported (`game/tron/rom_rng.py`: FUN_0000c684 state = state * 0x19660d + 1 at RAM 0x372c4,
FUN_0000c6b4 random_below(n) = (n * state) >> 32; the game's `os.random`, `TRON_RNG_SEED` fixes the state; Godot's clip picks use it
with the same variable). Not yet shared: Godot and Python keep separate states, so a run's clip picks do not interleave with the
ROM's other draws; `DMDPICK` lines in the Godot log + `sweep_clips.py` give the draw of each clip to the ROM code as input.

The 562 misses attributed to effect 19 are the score display itself: frames viewed (credits page, 4,780, 927,580, 1,182,310 with REPLAY AT
..., "TO LIGHT" over 55,130) are 19 with score values and rolls that the state sweeps (`sweep_state.py`) do not reach, 512 of 574 being 200 dots or
more from any code frame because a big score font differs everywhere. 108 and 111 are not started in this scenario (no deff_start). The open
point is therefore the value state of 19, which only a ported program reading the live score and roll (engine) removes; it needs
FUN_01023940 (roll), FUN_000249e4, FUN_01023704, FUN_00022a90, FUN_010230ec from the decompile.

**Effect 19 ported (2026-11-27, `game/tron/rom_deff19.py`, checked by `scripts/conform/check19.py` against the ROM code, columns 41-127).**
The score display's program: the score ("%,02lu", so 0 is "00") in the font and row of the score-size table (ROM 0x40d3484), the band blanked by
the blink (playfield not valid) or the wipe (valid) from the tick counter RAM 0x21117f4, the BALL / CREDITS line or the special line (replay level),
`dmd_engine.Page.fill` = FUN_0002746c. Exact on 4,780, 927,580, 0, 55,130 (with the replay line, to tick 414) and 1,534,750 (to tick 458), 100 % of the flips.
Found by the port: the special line's phase is 0x9b + n * 1562 ticks for 0x138 ticks (the loop counters 0x9c / 0x138 / 0x4e2 are decremented before
the line is chosen), not a 1718 tick cycle from 156 (`score_display.gd` `replay_phase` fixed; the measured 29.2 s / 26.5 s of 2026-10-30 are
tick 1717 and a 1562 tick period at 16.9 ms). Not yet carried to Godot as an engine program (the effect never ends and its values change live: it keeps
`score_display.gd`, whose band / wipe rows equal the program's); the special / replay text sources (FUN_000249e4, FUN_01023704) come from the rules.
