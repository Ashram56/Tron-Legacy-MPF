# Agent C: strict recreation of the ROM's game in MPF

Rebuild a Stern SAM game in MPF + Godot (GMC) **exactly as the ROM plays it**: rules, scoring, display,
sound, lamps, service menu and every operator setting. Nothing here improves on the original; that is the
optional [improvement agent](improvement.md). Part of the [master plan](README.md). Tron Legacy LE 1.74 is
the worked example (this repo).

## 1. Scope

**In** (all as the ROM does it, from the asset repo's specs, `rom_data/` and traces):

| Area | Includes |
|---|---|
| Rules | every reachable mode, multiball, hurry-up, wizard mode, combo, skill shot, extra ball, ball save, bonus, match, tilt and slam tilt, ball search, playfield validation, multi-player |
| OS semantics | ROM tasks as tick timers, switch hooks in the ROM's order, deff priorities and the show queue, deff/lamp rules, audits, `score_add` gating |
| Display | one slide per display effect with the ROM's frames and timing, the ROM's fonts and text layout with live values, the score display and status panel, attract pages, **classic 128x32 output byte-exact** |
| Sound | one pool per ROM sound call, channel stops, music replacement |
| Lights | lamp states, lamp-matrix effects (captured and code-drawn), flashers, GI, game-specific outputs (Tron: RGB ramp tubes), shaker |
| Service | **service menu reached as on the machine** (coin door buttons BACK, MINUS, PLUS, SELECT), every adjustment with the ROM's labels, defaults and ranges, audits with their formulas, credits and pricing tables, high scores, coin door open / interlock behaviour, tests the menu offers |
| Hardware overlays | virtual (desktop + MPF Monitor), the real machine (Tron: P-ROC on the SAM boards), every model of the game (Tron: Pro default, LE), the ROM's coil drive times |
| Portability | one setup script on Windows, macOS, Linux; installers; CI |

**Out**: anything that changes what the player sees or hears compared with the ROM (HD display, other fonts,
colour, glow, new modes, rule changes) belongs to the [improvement agent](improvement.md). The VPX bridge is
the [VPX bridge agent](vpx_bridge.md); the MPF Monitor layout comes from the [VPX extraction agent](vpx_extraction.md).

## 2. Read, in this order

1. [sam_to_mpf_playbook.md](../handover/sam_to_mpf_playbook.md): architecture, build order, verification
   loop and every gotcha so far. It is this agent's main manual; this page adds scope and what changed since.
2. The asset repo's `AGENTS.md` section 14 (what it delivers) and `rom_data/README.md` (where each fact is;
   `rom_data/` wins over older files).
3. [rom_differences.md](../rom_differences.md) before changing any rule: what is meant to differ, and ROM
   behaviour that looks like a bug but is the original.
4. The handover README's token rules: grep specs, read module docstrings, `git log --no-merges` for the why.

## 3. Definition of done

- `tests/test_traces.py` (scenario → event kinds that match the reference trace) only ever gains kinds; a
  feature is accepted when its scenario's trace matches (`scripts/trace_check.py <scenario>`).
- `pytest -q tests` green; `scripts/render_check.py` (no blank DMD); `scripts/render_diff.py` for display work
  (text pixel-exact against the reference captures); classic frames unchanged (pixel-hash tests).
- Unit tests for paths no reference scenario reaches; RNG seeded in tests only.
- No unreachable ROM code built (the asset repo lists dead code).
- Where MPF cannot do what the ROM does, the smallest departure that keeps the player's experience, logged in
  `rom_differences.md` with the ROM's behaviour and its address, and said to the owner.

## 4. Learned since the playbook (2026-10-04 to 2026-10-08)

- **Coin door open** (deff 4, priority 247, never ends by itself): "50V / 20V DISABLED" covers the display
  while the door is open, dims after 30 s; BACK takes it away (sound 0x009) instead of a service credit; the
  interlock cuts every coil but the optional coil 24. Model the power handler, not a timer
  (`os_layer._power_off_warning`, `tests/test_coin_door.py`). [SAM]
- **Service menu during a game**: the ROM suspends the game task (`task_suspend(0, 0x800)`) and resumes it on
  exit. MPF's timers cannot be suspended, so the game asks "END GAME?" and a second SELECT ends it into the
  menu (logged as a departure). [MPF]
- **Pro and LE**: one config in one model's ROM numbers, the other model as an overlay; rules look devices up
  by name (`tron/hw_numbers.py`). Pro decompile: outputs the Pro lacks are reused as flashers (Tron Pro ramp
  flashers 19/25, lower flashers 22/23 fired with them). docs/hardware.md "Pro or LE". [SAM]
- **Asset sync**: a scheduled job opens "Sync assets to <sha>" PRs; run setup, the render check and the tests
  on it, then the owner merges. [Tron]
- **Installers and private repositories**: check read access anonymously first, then ask for a fine-grained
  token (Contents read-only); never open Git Credential Manager's window; a clone whose branch was deleted
  moves to `main`. Windows PowerShell 5.1 turns git's stderr into a terminating error: test exit codes only.
- **OneDrive**: deletes and renames fail transiently; every build-time file operation goes through
  `scripts/fsutil.py`. Keep the install folder out of OneDrive.
- **CI runs only on pushes to `main`**: test locally before pushing a branch, don't wait on CI there.
- **Answers that matched the ROM** (check before "fixing"): Disc Multiball "JACKPOT" screen on every blue
  shot; Sea of Simulation stages played by their shots pay the shot value, not the stage million. Both are
  in `rom_differences.md`; future owner reports may be the same kind.

## 5. Starting a second game (Transformers Pro 1.80, 2026-10-08)

What the second game showed; read before porting a third.

- **Start from the Tron OS, not from scratch.** Compare the new ROM's OS tables with Tron's first (A's
  `rom_map.json` table registry): on tf_180, deffs 1-39, leffs 1-19, sound calls 0x001-0x019, adjustments 1-64
  and the audit counter ids have Tron's numbers, priorities and flags. Copy `game/tron` as `game/<tag>` with a
  rename (`tron` -> tag, `TronOS`, event prefix, env vars), keep the OS modules, and isolate every game value
  (start/shoot-again lamps, music and speech calls, game-over leff) in one `GAME` dict set to `None` until A's
  specs say otherwise. The machine boots and plays a full game on virtual hardware in a few hours that way;
  the boot test (`tests/test_boot.py` in Transformers-MPF) is the first test to write. [code]
- **One repository** works: A in `rom/`, B in `game/monitor/` + `docs/vpx/`, C everywhere else. Merge A's and
  B's branches into C's (the first merge needs `--allow-unrelated-histories`); re-merge as they push.
- **Dedicated switches** come numbered 129-160 in A's package (128 + n): `gen_config.py` turns them into "D<n>".
- **Read what A has not packaged yet from the ROM yourself**, as interim files under `game/config/interim/`
  with a generator that needs `TF_ROM` (adjustments, audits, deff and leff tables, the font table), and let the
  build prefer A's files when they land. It keeps C unblocked without guessing.
- **Fonts are ROM data**: the font table gives every glyph's image and x/y offsets, so `gen_fonts.py` builds
  BMFonts straight from `fonts.json` (Tron had to rebuild offsets from captures).
- **A's per-deff `timing.json` carries every text draw** (`pages[].texts`: string, font, x, y, flags, return
  address) and image draw. The score display's layout comes from there, not from guesses; the status panel is
  found by its draw call's return address (`216cc` on tf_180). TF's DMD has a Tron-like status panel (columns
  0-40, separator at 40).
- **Music loops**: A exports intro + looped body as one WAV with `loop_start_at`; write a RIFF `smpl` loop into
  the copied WAV and Godot's importer loops only the body.
- **Godot imports CSVs as translations**: put a `.gdignore` in `game/config/` when CSVs live there.
- Scenario runners carry Tron's switch numbers (VUK sw 11, opto sw 41): replace them with the new game's ball
  device holes.
- **Leff table moved**: Transformers' leffs are in `rom_data/io/lamp_effects.csv` (columns `priority`, `loops`
  = "yes" for until stopped, `run_ms`, `coils_pulsed`, `show`, `tag` = code for leffs drawn from game state with
  no show); shows put flasher pulses under `coils:` with `pulse_ms`. Its traces log coil drivers raw (3-17 ms
  slices), so drop Tron's 0.24 s coil hold (`COIL_OFF_DELAY`).
- **Read a function before trusting its decompile name.** On tf_180, `any_timed_mode_running` [0x01006704]
  tests the six multiball flags; the timed modes (battle timers, double and fast scoring) are [0x010067bc]. The
  specs had copied the name, so Energon looked frozen during battles; the switches trace showed it is not.
- **Drive scenarios on the reference's input times** (each hit, drain and button waits until the reference
  input's time after "ready"). Otherwise timing drifts up to 0.4 s across a long trace and every timed rule
  looks wrong. Forced random picks come from watched variables. Ignore values that are uninitialised RAM
  (0xffff before the game starts).
- **Switch flags matter.** The captive ball (flags 0x1fff0000) runs its handler on both edges, 3 ticks after
  each. Mode-total deffs reload the ball-search countdown ([0x0100664c]), and a search near a drain delays the
  bonus.
- **A captured deff starts its own leffs and sounds.** Calling `leff_start` too doubles them in the trace; a
  helper that starts the rule's leff and first sound only when the capture lacks them (`os.deff_media`) fixes it.
  Passing `sounds=` replaces the capture's sounds, so use it only for deffs with none. A deff with no capture
  length never ends and blocks every lower one: give each such deff a length from the traces (`UNCAPTURED`).
- **Show tasks**: a show ends when another effect replaces its deff; queueing a show task that is already playing
  replaces it (BALL n LOCKED over the previous lock); a multiball intro waits on its own priority, not on the
  show playing below it. The replay deff waits for a running award deff above 0x9f.
- **Sound channels decide some rules.** The Allspark's warning 0x157 is refused while a higher priority sample
  holds its channel (sample `mask` in samples.csv, low byte of the call's `flags_0x10`), and the ROM then ejects
  at once after 937 retries (logged). Track the playing samples to know.
- **MPF ball devices**: a ball that comes back while an eject is unconfirmed is a failed eject to MPF and goes
  straight out again; keep `eject_timeouts` under the scenario's shortest return (1 s on the left eject, with
  the ROM's 2 s device task kept in the rules) and lower `exit_count_delay` / `entrance_count_delay` to let a
  lock release four balls 0.4 s apart. A ball hold must cover every ball the rules keep.
- **Timers that pause**: the combo window does not count while the eject holds a ball ([0x0103a4f0(3)]).
- Do not give a feature an attribute and a method of the same name (`side_super`): Python replaces the method
  silently and the hook dies with "int is not callable" deep in a scenario.
- **Read the gate, not its name.** A decompile name can say the opposite of the code (Transformers'
  `any_timed_mode_running` 0x01006704 tests the multiball flags); ask A for the flag list behind every
  "multiball / timed mode" condition and check it against a trace where only one of them runs.
- **The shaker** belongs to the deff, not the rule: run it when the deff gets the display (A's `shaker.csv`:
  deff, pattern, minimum adj level), never when the rule requests it; a new run never cuts a longer one short.
- **Ball search timing is a reload hunt.** Each search that lands at the wrong time is a missing or extra
  reload: look 10 s before the ROM's search for the event that reloaded it, then grep the decompile for the
  reload function's callers (Transformers: score, playfield switches, each show task at queue/start/end, the
  mode totals, FUN_01006350 deffs; flipper buttons pause it; a scoop eject does not reload). Compare the
  kicker coil runs per trace (on times, ref vs ours) once scores match: they show every search.
- **Ball end clears the display, the ROM does not always.** A mode total on screen at the drain plays out
  before the ball-end total shows again (Transformers fast scoring deff 137); time it from its start.

## 6. Tron status and open work

Built: phases 1-10 (PRs #1-#8), the hardware overlays (P-ROC, virtual + MPF Monitor, VPX), Pro/LE,
coin door and in-game service (PR #17). Open:

1. Trace kinds that still differ: the `TRACES` table in `tests/test_traces.py` is the work list (for
   example `bonus` and `zuse_fast_scoring` match on audits only; End of Line waits on Flynn's Arcade awards
   at the VUK, deff 83, leff 159).
2. The 11 newer reference traces in the asset repo's `rom_data/states/traces/` (multi-player, tilt and slam,
   match, Sea of Simulation stages 4-8) are not in `TRACES` yet (inferred from the table, check).
3. The Pro's own rules are not ported (the game runs LE 1.74 rules on Pro hardware; rom_differences.md).
4. Ramp tube wiring on the IO board: documentation PR #16 is open; tubes stay off on the P-ROC until checked
   with a logic analyzer (docs/hardware.md).
5. Real-machine checks only the owner can do: coil strengths on the P-ROC, tube sides, coin door input.

Last updated 2026-10-08 (section 5: Transformers Pro, battles, multiballs, wizard modes, ball search).
