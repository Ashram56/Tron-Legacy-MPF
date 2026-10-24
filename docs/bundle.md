# The prebuilt bundle: the game with nothing left to build

`scripts/package/build_bundle.py` makes one archive of the game as it runs: the generated MPF config, sounds,
DMD frames, slides, fonts, the baked HD fonts and the Godot import, so a machine that has MPF and Godot only
unpacks it. No setup run, no media generation, no import (measured on a 4-core PC: 4 to 8 minutes, of which
the media, the Godot import and the font bake are 85%; the font bake alone is about 100 s on a Jetson Xavier NX). It is the "game" half of a
ready-to-use image: the image supplies Python with MPF, Godot, ffmpeg and the display stack, the bundle supplies
Tron.

Format version 1. `bundle.json` at the root of the archive says everything a loader needs; this page says why.

## Build one

On a computer where `python scripts/setup.py` has finished (the workspace must be current: the builder refuses a
stale one):

```sh
python scripts/package/build_bundle.py                    # dist/tron-legacy-mpf-<date>-<commit>-linux-arm64.tar.xz
python scripts/package/build_bundle.py --target x86_64    # a PC
python scripts/package/build_bundle.py --target all       # both texture formats, every GoZen build
python scripts/package/build_bundle.py --version 2026.10.24 --out DIR --no-archive
```

About 2.5 minutes after setup, on 4 cores (the Godot import is most of it); the archive has a `.sha256` next to it.
The build runs on a PC for an ARM target: the textures are made for the target's format, not the builder's.

Measured 2026-10-24 (arm64 target, game commit 21af8ad plus this change): **235 MB packed, 633 MB unpacked**,
29 377 files. About 350 MB of the unpacked tree is generated media and sounds, 100 MB the import cache, 63 MB the
baked fonts, 16 MB the runtime part of `assets/`.

## What is in it

```
tron-legacy-mpf/
  bundle.json         id, version, source commits, what it requires, how to start it, options, PuP install, what to keep on update
  SHA256SUMS          every file's hash (check with: sha256sum -c SHA256SUMS)
  scripts/            run.py, toolchain.py, fsutil.py, gmc_patch.py, pup/ (install), package/ (start, options)
  game/               the Godot project and the MPF machine folder; config/rom, sounds, media, slides/deffs, fonts, fonts_ttf/baked,
                      addons/mpf-gmc (patched) and addons/gde_gozen (the target's build), .godot (the import)
  assets/             only what the game reads at run time (16 MB): the event and lamp-effect tables, service_menu.json,
                      rom_images_all.zip, mpf_package/config, rom_data/{io,pro,settings,deffs}, io, callouts, each effect's timing.json
```

Not in it, on purpose: the ROM, the decompile, rules and traces, the tests, the PuP Pack and its converted media,
**any cabinet data**. The builder refuses to finish when `game/data`, `game/audits`, `game/logs`, any `*.local.cfg`,
`options.json` or a Scorbit device key is in the tree; `tests/test_bundle.py` pins the list.

## Texture formats: one bundle per GPU family

Godot imports each picture for the GPU's compressed format. ARM GPUs (the Pi 4's V3D, the Jetson) use ETC2, PCs
use S3TC/BPTC. A Godot import on a PC always makes the S3TC variant, whatever the project setting says, and the
setting `import_etc2_astc` adds ETC2. So an `arm64` bundle is imported with ETC2 added, then **the S3TC files are
deleted and taken out of every texture's `.import`** (otherwise a GPU that supports both could pick the missing
S3TC file). An `x86_64` bundle keeps S3TC only; `all` keeps both (about 400 MB more unpacked).

The build prints the count (`2765 lossless, 2595 etc2`) and stops if the VRAM variants are missing. The 2 595
VRAM-compressed pictures are the HD effect frames; `scripts/gen_media.py` writes their import settings
(`HD_FRAME_IMPORT`) and the builder writes them again before the import, since `.import` files are not tracked.

**Checked:** a PC with a software Vulkan GPU that lacks ETC2 ran the arm64 bundle through a 90 s scenario: Godot
logged "ETC2_RGB8 not supported by hardware, converting to RGBA8" and drew the DMD, no crash (a PC with OpenGL
only, which cannot convert, crashed: use Vulkan). **Not checked:** a real V3D (Pi 4) or Jetson GPU.

## Install on a base system

The base system needs (also in `bundle.json` `requires`): Python 3.10 or newer with a venv holding `mpf==0.80.1`,
`pillow`, `fonttools` (and `ruamel.yaml.clib==0.2.14` below Python 3.13); Godot 4.6.3 for the CPU; `ffmpeg` with
libtheora (the PuP install reads the pack's videos with it); `xvfb-run` when there is no screen. Point the bundle at
them with `GODOT=/path/to/godot` and `TRON_VENV=/path/to/venv` (or put them in the bundle's `tools/godot/` and
`.venv/`).

```sh
tar -xJf tron-legacy-mpf-<version>-linux-arm64.tar.xz -C /opt/games     # -> /opt/games/tron-legacy-mpf
cd /opt/games/tron-legacy-mpf && sha256sum -c SHA256SUMS --quiet
GODOT=... TRON_VENV=... python3 scripts/package/start.py                # starts Godot, then MPF, with the saved options
```

The game writes into `game/data` (settings, audits, high scores), `game/audits`, `game/logs` and keeps the
PuP Pack in `pup_pack/` and `pup_media/`. **Updating** is: unpack a newer bundle over a new folder, then copy
`bundle.json` `keep_on_update` (data, audits, options, the two `*.local.cfg`, the pack and its media) across. A bundle
is never stale (`toolchain.media_stale` returns nothing when `bundle.json` exists), so `run.py` does not try to
regenerate media that the bundle cannot regenerate (it has no generator inputs).

## Settings

`scripts/package/options.json` lists every setting a person can change, with type, range, default, help text, the
group it belongs to (display, PuP, machine, Scorbit) and where it is stored. A settings page builds its form from
it and writes with `scripts/package/bundle_options.py` (or imports `load_schema`, `get_values`, `set_values`,
`unset_values`):

```sh
python3 scripts/package/bundle_options.py list                       # the schema, as JSON
python3 scripts/package/bundle_options.py set dmd.text_glow 1.2 dmd.font orbitron pup.video_volume 60
python3 scripts/package/bundle_options.py get                        # what was set (a secret only shows {"set": true})
python3 scripts/package/bundle_options.py unset dmd.text_glow
python3 scripts/package/bundle_options.py run-args                   # the run.py flags the saved values make
```

Every value is validated before anything is written; one bad value writes nothing. The 25 options:

| Group | Options | Stored in |
|---|---|---|
| display | `dmd.mode`, `dmd.tint`, `dmd.font`, `dmd.text_scale` (0.5-1.1), `dmd.text_glow` (0-3), `dmd.text_color`, `dmd.dots`, `dmd.size` | `game/options.json`, added by `start.py` as `run.py --dmd-...` |
| PuP | `pup.enabled`, `pup.third_screen`, `pup.ost_music`, `pup.video_volume`, `pup.music_volume`, `pup.layout`, `pup.backglass.enabled`, `pup.backglass.service_menu`, `pup.dmd.dmd_size` | `game/pup.local.cfg` (the cfg the game reads after `pup.cfg`) |
| machine | `machine.hw` (virtual, proc), `machine.model` (pro, le), `machine.free_play`, `machine.fiber_optics` | `game/options.json`, as `run.py --hw`, `--machine`, `--free-play`/`--no-free-play`, `--fiber-optics` |
| Scorbit | `scorbit.provider`, `scorbit.machine_id`, `scorbit.encrypted_key` (secret), `scorbit.hostname` | `game/scorbit.local.cfg`, mode 0600 |

Where the game has two ways to set the same thing, the service menu wins over the file: the operator's DISPLAY
ADJUSTMENTS (text glow, text size), PUP DMD SIZE and SCORBIT SERVER are saved by the game and replace the
values above (`help` says so on each). Window positions and sizes of the PuP screens (a cabinet layout) are
not in the schema yet: `pup.layout=manual` plus a hand-written `game/pup.local.cfg` ([pup/README.md](pup/README.md)).
`tests/test_bundle.py` checks that every key exists in the shipped cfg, every flag in `run.py --help`, and that
the game's own parsers read what the tool writes.

## The PuP Pack

The pack is never in the bundle (its author's zip, from VP Universe, is the source). Installing it is one
command, run in the bundle folder:

```sh
python3 scripts/pup/pup_setup.py --pup-zip /path/or/https-URL/to/pack.zip
python3 scripts/pup/pup_setup.py --status     # "PuP on: ..." or why not
```

It finds `triggers.pup` at any depth in the zip, extracts that folder to `pup_pack/trn_174h` (a second run with the
same zip changes nothing), probes the videos with ffmpeg without converting them (GoZen plays the mp4s as they
are), and makes the backglass still the service menu draws on. A bundle keeps its own add-on: `pup_setup` no longer
tries to copy GoZen from a `pup_addons/` that a bundle does not have. The game picks the pack up on its next start.

**Checked:** the whole install with a stand-in pack (two small mp4s, one run, then a second that changed nothing).
**Not checked:** the real pack (private, not readable in the session that built this; it is about 1 GB or more).

## Known limits

- The arm64 GoZen build in the bundle is the Jetson's (FFmpeg with the NVIDIA decoder, `libnvmpi` loaded when
  present). On a Pi 4 it decodes in software unless it is rebuilt with V4L2 support; three 1080p videos at once may
  be too much for the Pi 4's four cores. `pup.enabled=false` (or `pup.third_screen=false`) is the fallback.
- Not run on a real Pi 4 or Jetson yet: the arm64 bundle was built and run on a PC (software Vulkan), with the PC's
  x86_64 Godot. The ETC2 import, GoZen on a Pi and every frame rate are untested on the hardware.
- Python 3.13 and newer need no `ruamel.yaml.clib` pin; Python 3.10 to 3.12 do.
- The bundle carries the game's own `scripts/run.py`, so `run.py --scenario NAME` works only for a scenario file you
  add under `scenarios/`.
