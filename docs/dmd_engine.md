# The game's own DMD engine (2026-11-27)

Until now every display effect was a slide of frames made by running the ROM code once (Unicorn, `scripts/gen_media.py`) plus text and letters laid over it
from the game's state. An effect that depends on state (letters lit, a switch count, an award value) could only be approximated. The engine draws such an
effect **from the ROM's own routine**: the routine is ported from the decompile into a function of the state, run flip by flip, and checked against the
ROM code frame by frame.

## Layers

| Layer | File | What it is |
|---|---|---|
| Primitives | `game/tron/dmd_engine.py` | The ROM's draw calls: page clear FUN_00027274, image blit FUN_0002b378 / FUN_0002b424 (type 0 handlers FUN_00029754, FUN_000298b8, FUN_00029a20, FUN_00029b7c: copy / palette / key byte 0xff), palette FUN_0002b554 / FUN_0002b56c, text FUN_00028ca8 / FUN_00028d5c / FUN_00028f74 (glyph images at x + xoff, y - h + below + 1) with the width of FUN_00028a74. A `Page` rasterises (for the checks) and records a draw list. |
| Programs | `game/tron/rom_deff55.py`, `rom_deff57.py`, `rom_deff60.py` | The routines deff_55 (0x0100461c), deff_57 (0x01005524), deff_60 (0x01005d44): the loop, the counters, the palettes, the message ids, in the ROM's order. Input: the deff task's bytes (+0x30...) and the RAM value deff_57 reads (0x3ae00). |
| Packing | `game/tron/rom_engine.py` | `payload(deff, args)` = the event arg `engine` {ticks per flip, loop, frames (distinct draw lists), seq (frame of each flip)}; `media_bridge.deff_lines` sends it for the effects whose media source is `engine`. |
| Drawing | `game/tron/dmd_effect.gd` item type `engine` | Draws the draw list of the flip the effect's time is in, under the status panel the effect keeps: ROM images through the palette, ROM text (classic: the glyph images, so every dot is the ROM's; HD: the vector text). |
| Check | `scripts/conform/engine_check.py`, `tests/test_dmd_engine.py` | Runs the ROM code (Unicorn, `deff_trace.py` also lists every primitive call) and compares every flip of the program, columns 41-127. Results below. |

`scripts/gen_media.py` `ENGINE_DEFFS` lists the effects drawn this way (no frames, no text lines: background, `engine`, panel).

## Results (columns 41-127, whole run including the end of the effect)

| Effect | Arguments tried | Flips matching |
|---|---|---|
| 55 (ZUSE letters of End of Line: EXTRA BALL / MULTIBALL / n MORE TO) | 6 sets: lit before / after, flags 0-12, count | all (121, 126, 129, 133 frames) |
| 57 (SWITCHES= value over the film) | 5, 1234, 10000, 12000 | all (150 frames) |
| 60 (award value over the dimmed film, BALL ADDED / n MORE FOR ADD-A-BALL) | (200000, 1), (200000, 0), (12, 2), (1500000, 0) | all (124-129 frames) |

The ROM's end of an effect (FUN_01024460(10, 0x20)) copies the previous page and redraws only the panel: the body is blank in 55 and 60 (checked).

## Adding an effect

1. Decompile the routine (`assets/code/tron_game_decompiled.c`), list its draw calls with `python scripts/conform/deff_trace.py EFFECT ARGS`.
2. Write `rom_deffNN.py` with `pages(args)` (the ROM's loop; the primitives of `dmd_engine.py`), `frames()` and `draws()`.
3. Add it to `rom_engine.payload`, to `ENGINE_DEFFS` in `scripts/gen_media.py` and to `engine_check.py`; run the check on several argument sets.
4. Re-run `scripts/gen_media.py`, then `godot_run.py` and `code_conform.py` on a scenario that shows it.

A primitive the program needs and `dmd_engine.py` does not have (another image type of the table at 0x40d8638: 1, 3, 7, 9, 12; page copy FUN_000272e4;
rectangles FUN_0002746c) is added the same way: from its decompile, verified on a trace first.

## Left to port (same method)

Effect 19 (score and bottom line), 47, 86-89, 140-145 and the attract pages: their state-dependent parts. Pure animations keep the code-run frames.
