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
| `run.py --hw vpx`, `setup.py --vpx` | built |
| **The table in VPX on Windows** | **owner test, outcome not reported yet** (merged in PR #10, 2026-10-04). Start here: ask the owner for the result of the checklist in docs/vpx.md "To check on Windows" and `game\logs\vpx_bridge.log`. |

Second game, **Transformers Pro** (Ashram56/Transformers-MPF, branch `claude/vpx-bridge-d47e04`, 2026-10-08): same
pieces under `game/tf/`, verified the same way (`tests/test_vpx.py`, `--check` against the live game,
`vpx_table.py` on the v2.4 table); owner test on Windows not done yet. Its `vpx_bridge.py` and `vpx_table.py` are
the **generic versions**: the game is one block of constants at the top of `vpx_bridge.py` (GAME, PROGID, CLSID,
ENV, ROM_NAME), and the bridge handles both output modes (see section 4). Copy those, not Tron's, for a third game.

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
2. Read the script **and the VPX core scripts it loads**: fetch `core.vbs`, `sam.vbs` (or `wpc.vbs` ...),
   `controller.vbs` and `VPMKeys.vbs` from github.com/vpinball/vpinball at a recent tag (`scripts/`; the
   `master` path 404s, list tags with `git ls-remote`, e.g. `v10.8.1-5436-af26b2d93`). Note which controller
   calls are made (`Switch`, `ChangedSolenoids`, `ChangedLamps`, `ChangedGIStrings`, `Lamp`, `Run`,
   `RawDmdPixels`, properties), and these table settings:
   - **`UseVPMModSol`**: `True`/1 (Tron) means solenoids 0-255 and lamps 0/1; **2** (Transformers, modern VPW
     tables) means "physical outputs": core.vbs sets `SolMask(2) = 2` and divides solenoids, lamps **and GI**
     by 255. Lamps reported 0/1 then read as 1/255, i.e. dark. The generic bridge reports MPF's brightness
     0-255 and converts to 0/1 (lamps) or 0-8 (GI) only when `SolMask(2) < 2`.
   - **GI**: a table that sets `GiCallback`/`GiCallBack2` polls `ChangedGIStrings`; without an answer its GI
     stays at whatever the editor left (Transformers: GI_PWM drives every GI light and the "GI on" images).
     When MPF has no GI output, report one string at 255 from the start.
   - **SolCallbacks that only animate** (Transformers' `solLSling`/`solRSling`: the sling arm and sound; the
     VPX slingshot object kicks by itself): MPF must fire those coils, so the overlay has `autofire_coils` for
     slings and pops (the SAM CPU fires them on the switch; Tron's table did not need it).
   - **`UseVPMDMD`** (desktop and VR): core.vbs reads `RawDmdPixels` every frame (inside On Error Resume Next);
     the bridge answers Empty, the table's DMD stays as it is.
   - Fast flips (`InitVpmFFlipsSAM`: solenoid 33 + flipper coils 15/16 on every SAM table), ball stacks,
     `cvpmTrough` (Transformers' `SolTrough` also pulses the trough jam switch 22 on every eject; MPF's
     trough copes, `tests/test_vpx.py` plays it).
3. Map every switch, coil, flasher, lamp and GI string to the MPF config's numbers and names; renumber only
   what PinMAME numbers differently (dedicated switches, extra outputs above the ROM's range). The dedicated
   switches' PinMAME numbers are a column of A's `rom_data/io/dedicated_switches.csv`. An NC switch in the MPF
   config that the table sets to 1 when the ball is there gets `type: NO` in the overlay (Tron's disc opto).
4. Start from Transformers' generic `vpx_bridge.py` / `vpx_table.py` (change the constants block: a new
   CLSID per game so two bridges can be registered side by side) and its `vpx_hardware.py` (constants at the
   top: flipper coils, solenoid range, coils powered with the door open, GI strings).
5. Check the MPF config repo is reachable before mapping (a stale local copy maps wrong numbers).
6. Verify in the cloud: the unit tests drive the platform like the bridge; `vpx_bridge.py --check` drives the
   live game. Without Godot (no media yet), stand in for GMC on port 5050 with a 20-line socket server that
   answers `hello` with `hello?version=1.1&...` and **`reset` with `reset_complete`**: MPF waits for every
   display client's `reset_complete` in `machine_reset_phase_1`, so without it attract never starts and START
   does nothing. Run `vpx_table.py` on the real `.vpx` (unzip it to the scratchpad) and diff against
   B's `script.vbs`: only the loader and the End key line may differ.
7. The End key line uses DirectInput 207 (VPMKeys' default `keyCoinDoor`); `keyFront` (Transformers'
   tournament button) is key 2, no clash.

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
   embedding it in the table (or B2S/FlexDMD) is not done. The table reads `RawDmdPixels` every frame, so
   frames rendered by Godot could be sent back to it through MPF (not done). B2S needs PinMAME behind it:
   `LoadMPF` sets `B2SOn = False`.
6. Port the generic bridge back to Tron (Tron's `vpx_bridge.py` still hard-codes its names; behaviour is the
   same for its `UseVPMModSol = True` table) once the owner's Windows test of either game passes.
5. MPF on another PC: `TRON_MPF_HOST` / `TRON_MPF_PORT`, and MPF's BCP server must listen on an outside address
   (unverified).

Keep this file current with every owner test result and fix. Last updated 2026-10-08 (Transformers Pro bridge).
