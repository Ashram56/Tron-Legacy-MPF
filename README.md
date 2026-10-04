# Tron Legacy MPF + PuP Pack

Stern's **Tron Legacy Limited Edition** (code v1.74) rebuilt in the Mission Pinball Framework, with Terry Red's
"End of Line" PuP Pack on three screens:

- the backglass (4:3 videos),
- a large LCD DMD (the pack's DMD panel art, with the game's DMD in the middle),
- an optional topper.

The pack's soundtrack replaces the ROM music. It runs on Windows, macOS and Linux, on a desktop or on the
real machine through a P-ROC.

## Install

Run the line for your OS in a terminal. It installs what is missing (Git, Python 3.11, the libraries), clones
this repository into a `Tron-Legacy-MPF-PuP` folder in your home folder, and runs `scripts/setup.py`. That
downloads Godot, MPF and the PuP Pack and builds the media. The first run takes a while.

**Windows 10/11** (PowerShell or cmd):

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF-PuP/main/scripts/install/install_prereqs_windows.ps1 | iex"
```

**macOS 12+:**

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF-PuP/main/scripts/install/install_prereqs_macos.sh)
```

**Linux** (Debian/Ubuntu, Fedora, Arch):

```sh
bash <(curl -fsSL https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF-PuP/main/scripts/install/install_prereqs_linux.sh)
```

You can change where the files go and which branch is installed:

- **Folder:** set `TRON_DIR` before running the line. On Windows: `$env:TRON_DIR = "D:\Tron"`. On macOS and Linux: `TRON_DIR=~/games/tron bash <(curl ...)`.
- **Branch:** set `TRON_BRANCH` the same way.

On macOS and Linux, options go after the command, for example `bash <(curl ...) --proc` for the real machine. Add `--dry-run` to see the plan first.

On Windows, keep the folder out of OneDrive (the default, your home folder, is). OneDrive locks files while it
syncs them.

## Play

From the install folder:

| | Windows | macOS / Linux |
|---|---|---|
| Start the game | `.venv\Scripts\python scripts\run.py` | `.venv/bin/python scripts/run.py` |
| ... with MPF Monitor | `... run.py --monitor` | `... run.py --monitor` |
| ... on the real machine (P-ROC) | `... run.py --hw proc` | `... run.py --hw proc` |

The three PuP windows open one under the other at the left of the screen: backglass, DMD, then topper. You
can resize each window. With a PuP window focused, `5` inserts a coin, `1` starts a game, `Space` plunges,
and the arrow keys are the flippers. `Esc` or `Ctrl+C` in the terminal quits.

Useful `run.py` options:

- `--dmd-size 1920x480`: sets the DMD window's size.
- `--dmd classic`: shows the original 128x32 dots instead of HD.
- `--dmd-color off`: plays the DMD animations in a single colour.
- `--no-free-play`: requires coins.

`python scripts/run.py --help` lists them all.

## Screens and PuP settings

Put your settings in `game/pup.local.cfg`. It uses the same sections as [`game/pup.cfg`](game/pup.cfg),
which documents every key. For a cabinet, put each window on its own monitor in fullscreen:

```ini
[pup]
layout="manual"
third_screen=false        ; no topper

[backglass]
screen=1
fullscreen=true
borderless=true

[dmd]
screen=2
fullscreen=true
borderless=true
```

`TRON_PUP=0` in the environment runs the original game without the PuP.

## Update

From the install folder: `git pull`, then `python scripts/setup.py`. You can also run the install line
again. Both are safe to repeat; setup only rebuilds what changed.

## More

- [docs/pup.md](docs/pup.md): how the PuP Pack is wired in, and keeping up with the upstream game.
- [docs/development.md](docs/development.md): the upstream game in detail (layout, setup options, the HD DMD, tests).
- [docs/requirements.md](docs/requirements.md): what a computer needs, per OS.
- [docs/hardware.md](docs/hardware.md): virtual hardware and the P-ROC.
