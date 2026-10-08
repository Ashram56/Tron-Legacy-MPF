# Agent A: ROM extraction

**The instructions live in the asset repo:**
[Ashram56/Tron-Legacy-LE-ROM-Decryption `AGENTS.md`](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption/blob/main/AGENTS.md).
That file is the agent; this page only places it in the [master plan](README.md). Update `AGENTS.md`, not this
page, when something about taking a ROM apart changes.

## Role

Take a Stern SAM ROM apart and deliver everything a rebuild needs, as tables first: IO (switches, coils with
their in-game drive times, lamps, aux outputs), sounds (one pool per sound call), DMD images and every display
effect with its timing, fonts and text layout, lamp-matrix and game-specific light effects, settings, audits,
pricing, the service menu, the OS model, and the rules as specs with **reference traces** recorded in an
instrumented PinMAME. Every fact tagged observed / code / inferred with its ROM address.

## Inputs and outputs

| In | Out |
|---|---|
| ROM image per model (PinMAME set zip) | An asset/spec repo, used by the game repo as a git submodule at `assets/` |
| Optional: manual, schematics, analyzer captures | `rom_data/` (machine-readable facts), `rules/` (specs, traces, compare tool), `mpf_package/` (MPF config, sounds, DMD, shows), `code/` (decompile) |

## What the downstream agents read from it

| Agent | Reads |
|---|---|
| [C, strict recreation](recreation.md) | everything; the traces are its acceptance test. Its feedback is `AGENTS.md` section 14; [rom_decomp_feedback.md](../handover/rom_decomp_feedback.md) is the dated record it came from. |
| [B, VPX extraction](vpx_extraction.md) | `mpf_package/config/switches.yaml`, `lights.yaml`, `coils.yaml` for device names by number |
| [D, VPX bridge](vpx_bridge.md) | the IO tables with PinMAME's numbers next to the ROM's (`AGENTS.md` section 14, item 13) |
| [E, improvements](improvement.md) | fonts, per-frame text draws in the captures, all ROM images |

## Tron status

Done for Tron Legacy LE 1.74 (`trn_174h`) and ported to Pro 1.74 (`trn_17402`); the game repo pins it as a
submodule and a sync job opens a PR when it moves. Transformers Pro 1.80 (`tf_180`) was the second game taken
apart with `AGENTS.md`; what it taught is merged into that file. Last updated 2026-10-08.
