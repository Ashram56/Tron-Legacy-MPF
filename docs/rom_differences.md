# Differences from the ROM

The game recreates Stern Tron Legacy LE v1.74 from the ROM-derived specs in `assets/rules/`, and the
trace tests (`tests/test_traces.py`, `scripts/trace_check.py`) compare it with recordings of the ROM.
This page is the one list of where the game is meant to behave differently, and of ROM behaviour that
looks like a bug but is the original. Read it before "fixing" a rule, and add to it whenever a change
departs from the ROM, for example a new mode.

## Rules for a departure

- **Record it here** in the same commit: what the ROM does, what the game does, why, and the switch that
  restores the ROM behaviour (if there is one).
- **Keep the ROM behaviour reachable** where that's practical (a command-line option, an MPF setting or a
  machine variable), so the trace tests keep checking the original.
- **Rules changes** (scoring, lighting, modes) get a scenario or unit test for the new behaviour; mark the
  trace checks they change on purpose rather than re-recording the traces.
- **New modes** that are not in the ROM go in their own feature module under `game/tron/features/`, listed
  in the table below, and must not change any ROM scenario.

## Intentional departures

| Area | ROM | This game | Back to the ROM |
|---|---|---|---|
| DMD look | 128x32 orange dots | HD by default: vector fonts and upscaled animations, drawn at any window size | `run.py --dmd classic` (exact ROM output; always used on the P-ROC and for render checks) |
| DMD colour | orange | Tron blue, text and animations | `--dmd-tint orange` |
| Text glow | none | none by default; optional glow | default (`--dmd-text-glow X` adds one) |
| Pricing on the desktop | coins (factory settings) | free play with virtual hardware | `run.py --no-free-play` |
| Hardware | SAM CPU board | MPF on virtual hardware, a P-ROC, or the Visual Pinball X table | `--hw proc` drives the original driver boards |

No scoring or rules departures yet.

## ROM behaviour that looks like a bug

| What you see | Why it is right | Source |
|---|---|---|
| Disc Multiball: Gem, the ramps, the inner loops and the orbits all show "JACKPOT" with points | Only the spinning disc collects the Jackpot. The other blue shots score their own value and add it to the Jackpot, but the ROM plays the same "DISC MULTIBALL / JACKPOT" screen (deff 48) for them | `assets/rules/modes/disc_multiball.md` (blue shot row); the disc_multiball trace: a left-ramp hit grows the Jackpot 250k to 350k, only sw41 pays it; `game/tron/features/disc_multiball.py` `disc_mb_shot` |
