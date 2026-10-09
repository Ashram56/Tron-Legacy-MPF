# Agent D: VPX to MPF bridge (work in progress)

Make a Visual Pinball X table play with the MPF game instead of PinMAME and the ROM: VPX keeps the ball, the
physics and the mechanical sounds; MPF runs the rules; Godot draws the DMD and plays the ROM's speech and
music. Part of the [master plan](README.md). The player-facing set-up is [docs/vpx.md](../vpx.md); this
page is what an agent needs to continue the work. Labels: **verified** (run), **unverified**, **owner test**
(only possible on the owner's Windows PC).

## 1. Status

| Piece | State |
|---|---|
| Overlay `game/config/hw_vpx.yaml` (LE), `hw_vpx_pro.yaml` (Pro) | built, unit-tested (`tests/test_vpx.py`) |
| MPF side `game/tron/vpx_hardware.py` | built, unit-tested |
| COM bridge `scripts/vpx_bridge.py` (`TronMPF.Controller`) | built; `--check` (its client without COM) verified on Linux against the real game |
| Script override `scripts/vpx_table.py` | verified on the VPW v1.1 table: one loader line changed, one KeyDown line added, the rest byte for byte |
| `run.py --hw vpx`, `setup.py --vpx` | built; the one-line Windows set-up (`-Vpx -Table`) is the [packaging agent](packaging.md)'s, built on Transformers, not yet on Tron |
| **The table in VPX on Windows** | **owner test, outcome not reported yet** (merged in PR #10, 2026-10-04). Start here: ask the owner for the result of the checklist in docs/vpx.md "To check on Windows" and `game\logs\vpx_bridge.log`. |

## 2. Architecture

```
VPX table script --COM--> TronMPF.Controller --BCP 5051--> MPF (hw_vpx, virtual_pinball) --BCP 5050--> Godot
 (core.vbs, sam.vbs)       scripts/vpx_bridge.py            game/tron/vpx_hardware.py
```

- **Never modify the `.vpx`**: VPX refuses a table whose script changed without its MAC being recomputed.
  VPX 10.7+ loads `<table name>.vbs` next to the `.vpx` instead of the embedded script; delete or rename it
  to go back to PinMAME. (verified for the format; the load itself is owner test)
- The only script change: `LoadVPM ... "sam.VBS"` becomes `LoadMPF "sam.VBS"`, which loads the same
  VPinMAME helper scripts (core.vbs, sam.vbs: keys, timers, ball stacks, fast flips) and creates
  `TronMPF.Controller` instead of `VPinMAME.Controller`. Plus one KeyDown line: `End` toggles the coin door.
- **Own bridge, not mpf-vpcom-bridge**: missionpinball/mpf-vpcom-bridge is not on PyPI and breaks on the
  table's `.Run GetPlayerHWnd`. `vpx_bridge.py` speaks the same `vpcom_bridge` BCP commands MPF's
  `virtual_pinball` platform answers, plus what this table needs: `Run(hwnd)`, starting MPF when nothing
  listens (`run.py --hw vpx` in a new console), accepting unknown properties (`Hidden`, `SolMask`,
  `Games().Settings`), returning Empty for "nothing changed" as VPinMAME does, `Stop` quitting a game it started.
- Start order: Godot first (MPF waits for GMC on 5050), then MPF (waits for the table), then the table. If
  the table starts first, the bridge launches `run.py --hw vpx` and VPX looks frozen meanwhile.

## 3. Numbering: what PinMAME's SAM driver and sam.vbs use

Matrix switches 1-64, coils 1-32 and lamps 1-80 are the ROM's own numbers, so every device keeps its MPF
name. The differences are all in the overlay and the adapter:

| Table side (PinMAME) | MPF | Notes |
|---|---|---|
| switches 84 / 82 (`swLLFlip` / `swLRFlip`) | flipper buttons (SAM dedicated 9 / 11) | the upper left flipper follows the left button |
| -7 `swTilt`, -6 `swSlamTilt`, 65 `swCoin1` | plumb bob tilt, slam tilt, coin | coins 2-3 (66, 67) ignored |
| -3, -2, -1, 0 | service BACK, MINUS, PLUS, SELECT | |
| -4 | coin door open | sam.vbs has none; the `End` key line added by vpx_table.py |
| 41 (Tron disc opto) | not inverted | the table closes it while the ball is on the disc |
| solenoids 1-32 | coils/flashers of the same number | reported 0 or 255 (`UseVPMModSol`); a pulse is reported at least once even if it ends between two polls |
| solenoid 33 | "flippers enabled" | input of sam.vbs fast flips (`cvpmFFlipsSAM`, `SolCallback(33)`); on while any MPF flipper rule is on; the ticket outputs moved to aux numbers out of its way |
| solenoids 15, 16, 12 | flipper coils | follow their button while the rule is on, as the SAM CPU does |
| lamps 101-103 / 104-106 | Tron ramp tubes (blue, green, red) | PinMAME's SAM_GAME_TRON numbering of strobe 0x10 / 0x20, reported 0-255 for `RGB()`; 0 on a Pro unless fiber optics are enabled |
| GI | none | MPF does not drive the GI relay; the table turns its GI on |

Coin door open: every solenoid but 24 reads 0 and solenoid 33 is off, as the ROM masks its outputs while the
interlock is open (IO interrupt 0x12070 writes shadow & mask 0x3b984 while RAM 0x3727c & 3 != 3).

The ball devices count the table's own trough (18-21), shooter lane (23) and VUK (11); MPF's ejects
(solenoids 1, 2, 4) fire the table's kickers; the table's `bsTrough` starts with 4 balls.

## 4. Doing this for another table

1. Run the [VPX extraction agent](vpx_extraction.md) first: `script.vbs` and the numbered CSVs are the input.
2. Read the script: which controller calls it makes (`Switch`, `Solenoid`/`ChangedSolenoids`,
   `ChangedLamps`, `ChangedGIStrings`, `Lamp`, `Run`, properties), which helper script it loads (sam.vbs,
   wpc.vbs ...), whether it uses modulated solenoids, fast flips, ball stacks or `cvpmTrough`.
3. Map every switch, coil, flasher, lamp and GI string to the MPF config's numbers and names; renumber only
   what PinMAME numbers differently (dedicated switches, extra outputs above the ROM's range).
4. Generalise what is Tron-specific in `vpx_bridge.py` (ProgID `TronMPF.Controller`, env names) and
   `vpx_hardware.py` (tube lamps, coin door mask) before reusing them.
5. Check the MPF config repo is reachable before mapping (a stale local copy maps wrong numbers).
6. Hand the set-up steps (bridge packages, COM registration, the table's `.vbs`) to the
   [packaging agent](packaging.md), which puts them in the Windows installer's `-Vpx` option.

## 5. Open items

1. **Owner test on Windows** (section 1): registration (as Administrator; pywin32 post-install if a DLL
   error), `.vbs` written, `run.py --hw vpx`, then the table: no message box, switches in MPF's console, 4 balls
   in the trough, coin/start, kick to the shooter lane, plunger, flippers, drain and tilt stop the flippers,
   flashers and lamps, ramp tube colours, drop target reset (sol 3), VUK (4), Recognizer and 3-bank motors
   (6, 23), orbit post (7), closing the table quits the game.
2. Only the owner can judge: flipper latency (fast flips should make it a non-issue; unverified), ball search,
   the trough, mechanisms (motors, moving targets).
3. GI is not driven by MPF; if the owner wants GI effects, map MPF's GI to the table's `GiCallback` strings.
4. The DMD shows in Godot's window, not the table's DMD: `--dmd-size 1280x320` and placing the window by hand;
   embedding it in the table (or B2S/FlexDMD) is not done.
5. MPF on another PC: `TRON_MPF_HOST` / `TRON_MPF_PORT`, and MPF's BCP server must listen on an outside address
   (unverified).

Keep this file current with every owner test result and fix. Last updated 2026-10-08.
