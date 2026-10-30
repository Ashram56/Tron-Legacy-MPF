# Tron Legacy: game page for the agents

The agents that built this game, and the knowledge base they share, live in the game-agnostic repository
**[Ashram56/Stern-SAM-Decryption](https://github.com/Ashram56/Stern-SAM-Decryption)**. Start there:
[master plan](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md) (what the owner provides, which agent does what, in what order), then the one
agent file your task needs. This page holds only what is true of Tron: its inputs, where its pieces live, each
agent's Tron status and open work, and the owner's Tron decisions.

**Reading the agents.** In a session with Stern-SAM-Decryption attached or cloned beside this repository
(`../Stern-SAM-Decryption`), read the files there; otherwise read them on GitHub. Update them there (a PR on
Stern-SAM-Decryption) when you learn something any SAM game would need; update this page for Tron facts.

| Agent | Instructions (Stern-SAM-Decryption) | Tron section below |
|---|---|---|
| A, ROM extraction | [agents/rom_extraction.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/rom_extraction.md) | [A](#a-rom-extraction) |
| B, VPX extraction | [agents/vpx_extraction.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/vpx_extraction.md) | [B](#b-vpx-extraction) |
| C, strict recreation | [agents/recreation.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/recreation.md) | [C](#c-strict-recreation) |
| D, VPX bridge | [agents/vpx_bridge.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/vpx_bridge.md) | [D](#d-vpx-bridge) |
| E, improvements | [agents/improvement.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/improvement.md) | [E](#e-improvements) |
| F, packaging | [agents/packaging.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/packaging.md) | [F](#f-packaging) |
| G, PuP Pack | [agents/pup_pack.md](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/pup_pack.md) | [G](#g-pup-pack) |
| Knowledge base | [knowledge/](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/knowledge/README.md): SAM to MPF playbook, HD DMD method, decomp feedback | |

## Tron's inputs (the kickoff values)

| Input | Tron |
|---|---|
| Game | Stern Tron Legacy LE, code v1.74; Pro v1.74 ported as a second model |
| ROM | PinMAME sets `trn_174h` (LE 1.74), `trn_17402` (Pro 1.74); never committed |
| VPX table | VPW Mod v1.1, in the project's files as `Tron Legacy (Stern 2011) VPW Mod v1.1.vpx` |
| Repositories | asset repo [Tron-Legacy-LE-ROM-Decryption](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption) (git submodule at `assets/`); game repo this one; colour work that reads a third-party colourisation file in the private repo `Ashram56/Tron-Legacy-MPF-Private` |
| Hardware | P-ROC on the SAM boards, Pro by default, LE selectable; VPX on Windows; Jetson cabinet with the PuP Pack (in this repository since 2026-10-10: [docs/pup/README.md](../pup/README.md); the pack itself from its author's zip or the private `pup_pack` submodule) |

## Where the Tron instance lives

| What | Where |
|---|---|
| Game repo (MPF + Godot) | this repository; built as stacked phase branches `phase2-machine` .. `phase11-hd` (PRs #2-#9), VPX bridge PR #10 |
| Asset/spec repo (ROM-derived) | `Ashram56/Tron-Legacy-LE-ROM-Decryption`, git submodule at `assets/`; its `AGENTS.md` points to agent A and keeps the Tron extraction notes |
| ROM | the game runs the LE rules on Pro (default) or LE hardware: [hardware.md](../hardware.md), "Pro or LE" |
| Coil times | the ROM's, generated into `game/config/rom/coil_times.yaml` from `assets/rom_data/io/coils.csv` |
| User docs | [README](../../README.md), [requirements.md](../requirements.md), [hardware.md](../hardware.md) (P-ROC), [vpx.md](../vpx.md) (Visual Pinball X), [development.md](../development.md), [performance.md](../performance.md) |
| Departures from the ROM | [rom_differences.md](../rom_differences.md): read before changing a rule; add every new departure there |

## A, ROM extraction

Done for Tron Legacy LE 1.74 (`trn_174h`) and ported to Pro 1.74 (`trn_17402`); this repo pins it as a
submodule and a sync job opens a "Sync assets to <sha>" PR when it moves (run setup, the render check and the
tests on it, then the owner merges).

## B, VPX extraction

Done on the VPW Mod v1.1 table: the layout is `game/monitor/` (`monitor.yaml`, playfield picture), started with
`python scripts/run.py --monitor`. The run's commands and expected counts (44 switches, 64 lamps, 8 flashers)
are the worked example in the agent file, "Checking a run".

## C, strict recreation

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

## D, VPX bridge

**The table in VPX on Windows**: **owner test, outcome not reported yet** (merged in PR #10, 2026-10-04). Start here: ask the owner for the result of the checklist in docs/vpx.md "To check on Windows" and `game\logs\vpx_bridge.log`.

Open:

1. **Owner test on Windows** (above): registration (as Administrator; pywin32 post-install if a DLL
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

## E, improvements

Current defaults (`dmd_mode.gd` constants and `project.godot`): HD on, Tron blue text `#2a6cff`, glow
`#22b8ff` (off by default since 2026-10-29: `--dmd-text-glow 0.8`), font Rajdhani Bold, text scale 0.85. Back to the ROM: `--dmd classic`, `--dmd-font rom`,
`--dmd-tint orange`, `--dmd-color off`. The operator can also set the text glow and size in the service
menu (ADJUSTMENTS > DISPLAY ADJUSTMENTS, persisted; FACTORY returns to the options).

Scorbit and Wi-Fi (2026-10-16, merged with PR #50 on 2026-10-18): UTILITIES > GO TO NETWORK MENU (nmcli or
wpa_cli backend) and GO TO SCORBIT MENU; Scorbit SDK 2.0.4 via `setup.py --scorbit` (Linux only), modes played and completed (completions need an SDK after 2.0.4), credentials in
`game/scorbit.local.cfg` ([docs/scorbit.md](../scorbit.md), [docs/network.md](../network.md)). Open: the owner's
Scorbit provider credentials; a check of both Wi-Fi backends and of pairing on the cabinet.

Service menu icons of the items the game adds (FEATURE AUDITS/ADJUSTMENTS, DISPLAY ADJUSTMENTS, NETWORK, SCORBIT):
its own, in the ROM's style, game images 9000+ in `game/service_icons/` drawn as text art by
`scripts/gen_service_icons.py` (2026-10-18; the owner asked for them, his look is open).

PIN2DMD and ZeDMD (2026-10-24, branch claude/project-thread-31bkyc, PR #56; 2026-10-28 the platform's): the RGB DMD output
(Godot add-on, MPF overlays, ZeDMD platform, native feeder, detection) is **MPF-Godot-Packaging's**, the same for every
game ([platforms/dmd_devices.md](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/platforms/dmd_devices.md)); the game keeps `scripts/dmd_out.py`
(installs it), `game/tools/dmd_out_loader.gd`, the classic-DMD rule in `dmd_mode.gd` and `run.py --pin2dmd|--zedmd|--dmd-out auto`
([hardware.md](../hardware.md)). Serum colour on a ZeDMD (2026-10-30, PR #69): the game's own `game/native/dmd_serum` (libserum, GPL v2) in front of the platform's plain
`zedmd_feed`: Vincent's rule, the DMD is part of the game, so the colourisation is the game's, not the platform's; the player brings the
`.cROMc`, the bundle builds both tools per CPU ([docs/hardware.md](../hardware.md)). The DMD's conformance with PinMAME, measured per
effect, is [docs/dmd_conformance.md](../dmd_conformance.md) (the work list; the ROM's random film clips are reproduced). Open: a check on a real PIN2DMD
and ZeDMD (colour order, firmware); the 256x64 and HD pictures a game can publish (platform PR #13).

### Owner decisions (keep adding)

| Date | Decision |
|---|---|
| 2026-10-04 | HD DMD in Tron blue, animations included; orange only as `--dmd-tint orange`. |
| 2026-10-04 | **No colourisation on `main`**, no colour option left in the public repo; colour work lives in the private repo only. |
| 2026-10-04 | Free play by default on the desktop (`--no-free-play` for coins). |
| 2026-10-29 | Text glow off by default (it looked worse than planned); the soft glow stays one option away (`--dmd-text-glow 0.8`, service menu DISPLAY ADJUSTMENTS). |
| 2026-10-29 | **HD colour is public** (supersedes 2026-10-04): the colour of the HD DMD comes from the monochrome frames alone (`scripts/mono_colour.py`, `scripts/dmd_color.py`) and the PuP clips, with no Serum or other colourisation file; docs/dmd_colour.md. Colour work that reads a colourisation file stays in the private repo. |
| 2026-10-06 | Clean font for HD text; Orbitron + glow tried as default, then Rajdhani default with glow 0.8; text scale 0.85 (the clean fonts looked bigger than the ROM's and stacked lines touched). |
| 2026-10-06 | Outlined ROM fonts sized and placed by their lit dots. |
| 2026-10-07 | ZUSE/TRON target letters stay the ROM's pictures, upscaled: the clean-font versions looked worse. |
| 2026-10-07 | Effects that are only frames and blocks drawn as sharp rectangles. |
| 2026-10-10 | Service menu DISPLAY ADJUSTMENTS: TEXT SIZE capped at 110% (above it stacked lines touch); TEXT GLOW OFF to 300%. |
| 2026-10-10 | PuP videos on Windows play through GDE GoZen with GPU decoding (Direct3D 11 Video), like Linux; the native video add-on (it stuttered) stays as the fallback. Built in the PuP fork ([Tron-Legacy-MPF-PuP](https://github.com/Ashram56/Tron-Legacy-MPF-PuP) PR #15). |
| 2026-10-28 | **native_video removed**: GDE GoZen is the cross-platform video player (Linux, Windows, macOS; macOS software decoding, built by the platform's workflow). |
| 2026-10-10 | **PuP Pack merged into this repository** (the fork Tron-Legacy-MPF-PuP is history). Optional: the installers take the private `pup_pack` submodule only with a token or credentials that read it, else install the game alone; `--pup-zip` takes the author's zip. Godot 4.6.3 (the native video add-on needs 4.6), separate render thread on by default (`--no-render-thread`). Colourisation stays out of the public repo. |
| 2026-10-18 | Service menu duplicated on the backglass, the DMD keeping the ROM's look (same branch for DMD-only machines); both neon frames of the backglass art stay lit, content stays clear of the lower frame; fade in and out on entering and leaving the menu. |
| 2026-10-25 | Frames capped at 30 FPS on every platform (`game/project.godot`; `run.py --max-fps`, the bundle's frame rate option). Raspberry Pi 4: the LCD DMD drawn in the backglass window (`[dmd] window`: overlay in prod; the bundle's `auto` = a PIN2DMD or ZeDMD when one answers, else stacked), no light cycles. |

### Ideas not built (ask before starting)

- New modes or rule changes (the owner has said they may come; nothing built yet: `rom_differences.md`
  says "No scoring or rules departures yet").
- A Tron-style font for the ZUSE/TRON letters (each sprite carries `metadata/letter` for it).
- Colour from the private repo's work, once the owner wants it public in some form (their call: rights).

## F, packaging

**Before building a bundle read the platform's "Known failures" table** ([platforms/game-bundles.md](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/platforms/game-bundles.md)):
every row is a bundle that built fine and failed on a machine. The rule that bit Tron: every Python file the start chain reaches goes in
`SCRIPTS` of `scripts/package/build_bundle.py` (`mpf_platform.py` was missing, 2026-10-29); `tests/test_bundle.py` now follows the imports
of `start.py` through every file, and the platform's builder and installer refuse an archive that fails the same check.

Built: `setup.py` and `run.py` on three OSes, the three installers with one-line install, the P-ROC build,
Docker, CI on three OSes. Open:

1. Port `-Vpx` / `-Table` from Transformers' Windows installer (packaging agent, section 4, step 4); `docs/vpx.md` then gives the
   one line.
2. A double-click launcher per platform (Windows shortcut or `.bat`, macOS `.command`) that runs `run.py` with
   the installed options: not built; the owner runs the command line today.
3. Transformers has only the Windows installer; macOS and Linux installers, Docker and CI are not ported.
4. Prebuilt bundle (2026-10-24, [docs/bundle.md](../bundle.md)): `scripts/package/build_bundle.py` makes the game with
   its media and Godot import already built, per GPU family (arm64 ETC2 for a Raspberry Pi 4 and a Jetson, x86_64 S3TC),
   with `bundle.json`, a settings schema and tool for a web page (`scripts/package/options.json`,
   `bundle_options.py`) and the PuP install from the author's zip. Built and run on a PC; not run on a real Pi 4 or
   Jetson. The web page and file serving are another project's.

## G, PuP Pack

Built (in the fork Tron-Legacy-MPF-PuP, merged here 2026-10-10): Terry Red's "End of Line" pack on backglass,
DMD and topper windows, OST in place of the ROM music, GoZen (Linux, Windows, macOS: the platform's add-on; native_video removed 2026-10-28) player,
Jetson hardware decoding: [docs/pup/README.md](../pup/README.md), [docs/jetson/README.md](../jetson/README.md),
[docs/performance.md](../performance.md). The DMD window has the DMD with the light cycles round it or full size
(320x80 mm, no light cycles): `[dmd] dmd_size`, service menu PUP DMD SIZE (2026-10-12). The service menu
also shows on the backglass (2026-10-18: `game/pup/service_backglass.gd`, `game/tron/service_backglass.py`; the DMD
keeps the ROM's screens), fading in and out over a median still of the backglass loop made by `gen_pup.py`;
`[backglass] service_menu`. Remote topper on a Raspberry Pi (2026-10-19, Vincent: Pi 3 A+ first, Zero W to try;
videos copied as they are, re-encoded only when the Pi can't decode them): `[remote] enabled`; server, rules, Pi agent and installer are the
platform's (MPF-Godot-Packaging `mpf_godot/pup_remote/`), the game keeps `scripts/pup/topper_media.py`: [docs/pup/remote_topper.md](../pup/remote_topper.md); not yet run on a real Pi. Open: the remote topper on
the Pi (the platform's pup-remote-topper.md, "To check on the Pi"); the owner's look on a real backglass; after a display change, re-run `scripts/pup/pup_captures.py`
and fix the flagged rows of `game/tron_pup/trigger_map.yaml`.

## Owner preferences

Go ahead without asking for approval; pick a default, say which, and list what needs the owner's judgement as
a short numbered list. Small update zips of changed files only, never a full rebuild (A). Answer in the
owner's language (Vincent sometimes writes in French). CI runs only on pushes to `main`: test locally before
pushing a branch.

Last updated 2026-10-27 (PIN2DMD output; earlier: PuP Pack merged in from the fork; DMD glow and size in the service menu; PuP video on Windows; agents and knowledge base moved to Stern-SAM-Decryption; this page keeps Tron's part).
