# Recording and replaying a played game

Not in the ROM: a tool to reproduce what an owner saw. Implemented in `game/tron/recording.py` (MPF side) and
`game/tools/replay_overlay.gd` (Godot side).

## Recording

Every run of `scripts/run.py` records (`--no-record` turns it off). From each return to the attract mode to the next,
every switch change is kept with its time in seconds, with the **seed** of the game started in between. The file is
`game/data/recordings/<date>-<time>.json` (written every 10 s and when the game ends or MPF quits, only when a game was
started):

    {"format": 1, "seed": 123456789, "events": [[0.0, "s_left_flipper", "on"], [0.07, "s_left_flipper", "off"], ...]}

The events are in the platform's scenario format (`format 1`), so the platform's replay page also reads them.

## Seed

At each game start the rules' random generator is seeded with a number drawn at that moment (`--seed N` / `TRON_SEED`
fixes it). It is written to MPF's log (`tron_seed N`) and to the trace, and sent to Godot, which seeds its clip variant and
clip file picks. The same seed and the same switch changes give the same draws (variants, match number, jackpot awards...).
The light cycle background of the PuP DMD window is decoration and is not seeded.

## Replay

    python scripts/run.py --replay game/data/recordings/20261102-114702.json

The switch changes are played at their times from the moment MPF enters the attract mode, with the file's seed, on
the virtual hardware (the trough switches are left out: the virtual trough moves the balls). Godot shows a clock (mm:ss.s) in the
window's top left corner. `<file>.timeline.txt` lists, on the same clock, every switch change and every display effect the game
starts (`deff_start id=N`), the seed and the game milestones, to say "at 04:12.3 the screen was blue" and get the effect.
