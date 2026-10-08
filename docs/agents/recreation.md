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

## 5. Tron status and open work

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

Last updated 2026-10-08.
