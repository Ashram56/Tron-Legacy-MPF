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
