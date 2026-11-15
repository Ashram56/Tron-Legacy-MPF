# The rules test bench

`tests/bench/` plays the game as a player does and checks it against the ROM's rule specs
(`assets/rules/modes/*.md`). Run it before and after any change to the rules, the hardware config or the
service menu: it is part of `pytest -q tests`, and `scripts/bench.py` runs it by part.

```sh
python scripts/bench.py                 # everything, about 1.5 minutes
python scripts/bench.py modes           # the modes one by one
python scripts/bench.py adjustments     # the service menu's adjustments, in play
python scripts/bench.py stress          # modes in every order, random games
python scripts/bench.py soak            # 300 random games per kind, about 20 minutes (--games N)
python scripts/bench.py --seeds 17,40   # replay the random games of these seeds
python scripts/bench.py modes -- -k tilt -x      # anything after -- goes to pytest
```

## How it differs from the other tests

The older tests (`tests/test_*.py`) call a rule's function or close a switch and look at the result; the
trace tests replay a ROM recording. Both leave MPF's ball devices on the "smart virtual" platform, where
balls move by themselves. The bench puts three things between the test and the game:

| Piece | File | What it is |
|---|---|---|
| The table | `tests/bench/table.py` | Four real balls. A ball is in the trough, the shooter lane, the VUK or on the playfield, and only a coil or the player moves it (trough kicker, auto launch, VUK, drop target reset, 3-bank motor). MPF runs on the plain "virtual" platform, so every ball the rules count must be one the table holds. |
| The robot | `tests/bench/robot.py`, class `Bench` | The player: START, the plunger, the flippers, the plumb bob, and the ball sent to a shot, the scoop or the drain. It cannot close a playfield switch without a ball on the playfield. `light_*` and `start_*` reach every mode through the switches. |
| The invariants | `Bench.check()` | Checked after every action of the robot (list below). |
| The random player | `tests/bench/monkey.py` | A seeded sequence of shots, dirty shots, bursts, scoops, drains, outlanes, waits, flips, tilt bobs and START presses. A failure names its seed and its last 25 actions. |
| The operator | `tests/bench/test_adjustments_play.py`, class `Operator` | Opens the service menu with the coin door buttons between two games and sets adjustments there: `self.adjust(a31=1)`, `self.adjust("feature", a66=45)`, `self.adjust("options", a1=1)`. |

Class options of a `Bench` test: `DROP_TARGETS = False` (the Pro's standups), `AUTOPLUNGE = None` (the
test plunges itself), `ARCADE = None` (Flynn's Arcade left to its weighted draw; forced to 500K otherwise),
`CHECK = False` (no invariants, for a test that breaks one on purpose).

## The invariants

After every action:

- the table still holds four balls, none of them counted twice;
- no game: the game state is attract or game over, and no multiball or Sea of Simulation flag is left;
- scores never go down, and nothing scores while tilted;
- only Quorra and Light Cycle run together among the multiballs; Sea of Simulation runs with none;
- clocks, bonus multiplier, extra balls, tilt warnings, balls in play and the ball number stay in their
  ranges (the ranges follow the adjustments);
- the rules' balls in play equal the balls out of the trough, once nothing has moved for 25 s;
- at every new ball: no mode task, timer, flag or held ball of the ball before is left (the combo window
  tasks 0xcd/0xce are an exception, as in the ROM: `task_kill(0, 0x100)` keeps them);
- at the game's end: all four balls are back in the trough.

## What is covered

| File | Tests | Against |
|---|---|---|
| `test_bench_selftest.py` | the table and the robot themselves | |
| `test_modes_timed.py` | CLU, GEM, ZUSE, the TRON targets (LE and Pro), Find Flynn | clu.md, gem.md, zuse.md, tron_targets.md, find_flynn.md |
| `test_modes_multiball.py` | Quorra, Light Cycle, Recognizer and Disc Battle, Disc Multiball, End of Line, Sea of Simulation, Portal | their specs |
| `test_game_flow.py` | serve, valid playfield, ball save, tilt, extra ball, replay, bonus, skill shots, combos, Flynn's Arcade, the score of every switch, game over; `TestRegressions` | game_flow.md, skill_shots.md, bonus.md, combos.md, flynns_arcade.md, switches_and_shots.md |
| `test_adjustments_play.py` | 32 adjustments and GAME OPTIONS set in the service menu, then played; `IN_PLAY` and `NOT_IN_PLAY` (with the reason) cover adjustments 1 to 88 | the adjustment tables of the specs |
| `test_stress.py` | random games (LE, Pro, with and without tilt, weighted Arcade awards), the timed modes in every order, each multiball after the timed modes and before them, each multiball after another, all balls draining at once, a tilt in every multiball, two balls for the scoop, four players | the invariants |

## Adding to it

- A new rule or a changed one: a test in the file of its mode, written from the spec (trigger, condition,
  score, display, sound). Use `m = self.mark()` then `self.adds(m)`, `self.deffs(m)`, `self.sounds(m)`.
- A new adjustment: a test in `test_adjustments_play.py` and its number in `IN_PLAY`, or a line in
  `NOT_IN_PLAY` saying why not.
- A new mode: a `light_*` / `start_*` helper in `robot.py`, its flag in `MB_FLAGS` when it is a multiball,
  the mode's tasks in `BALL_TASKS`, and its name in `TestModesInAnyOrder`.
- A bug found: a test in `TestRegressions` that fails without the fix.

Things the robot must not do, because no ball does them: drain a ball before MPF has counted it on the
playfield (`Bench.drain` waits), or drain every ball while the multiball task still launches (the task
launches again, as the ROM's does).

## Found by the bench

Fixed (1 and 2 have a test in `TestRegressions`, 3 and 4 in `test_adjustments_play.py`: tests 36 and 30; 5 has none):

| # | What happened | Fix |
|---|---|---|
| 1 | A tilt between the start of a multiball and the launch of its balls: the game waited for ever for the balls that never came (MPF's `balls_in_play` kept counting them). | `os_layer._mb_cancel` gives them back. |
| 2 | A ball plunged less than 0.5 s after it reached the shooter lane was never counted by MPF (default `entrance_count_delay` 500 ms): for 10 s its drain was ignored, then the ball was served again. | `bd_shooter_lane: entrance_count_delay: 100ms` (the ROM's task 0x3d: 6 ticks). MPF then auto-launches 0.4 s sooner, so the waits before an auto-launched ball take the 0.4 s (`SHOOTER_COUNT_SHIFT`): the trace times are unchanged. |
| 3 | GAME RESTART (START held on ball 2+) with a ball in play: the playfield switches ran on the new game before its players' data existed (an exception at the first bumper hit), and the old ball was served again when it drained, so the new game never started its ball. | State 0x20 from the game start to the first ball start, as in the ROM [0x00020584]; a drain in that state is only counted. |
| 4 | MATCH PERCENTAGE = OFF still showed the match number; and once the machine had matched often enough, the number shown could be the player's own without an award. | `game_over.py` follows `match` [0x0001b660]: no deff 38 when OFF, and a number no player has. |
| 5 | The end of ball waited for the TOTAL display of the last feature asked, not the longest one, when two were pending. | The longest one (`os_layer._ball_ending`). The ROM also stops waiting after `gf_eob_mode_wait` ticks [0x00020764]; that limit is not applied, because the Sea of Simulation trace waits longer than the 169 ticks read for it. |

Not changed, for the owner or the next agent:

- **Adj 80 DISABLE DROP TARGETS** has a reader in the ROM (`FUN_0100b910`, the bank object's "disabled"
  test) but does nothing in the game. tron_targets.md leaves its effect as an open question.
- **Adj 75 ABORT ANIMATIONS** (flipper buttons skip a queued show) and **adj 46 PLAYER COMPETITION** are
  not built.
- **Adj 70 = 4** (no Disc Multiball restart): the multiball then ends with no total display and flag 0x25
  stays set. The game does as the ROM does [0x01007714]; it looks like a ROM oversight.
- **flynns_arcade.md** gives the bag's total as 352 (452 with MORE TIME); its own table adds up to 327
  (427), which is what the game draws from. The percentages of that table follow the wrong total.
- **game_flow.md 4.3** says slingshots and TRON targets do not count for the valid playfield;
  switches_and_shots.md, skill_shots.md and the game count them (three different ones).
- **A game restarted with a ball in play** waits for that ball to drain before it serves (MPF's rule). What
  the ROM does there was not traced.
- `FUN_010009a8` (a self-adjusting threshold driven by adj 27 EXTRA BALL PERCENTAGE) has no caller in the
  decompile and is not built.
