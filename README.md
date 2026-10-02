# Tron-Legacy-MPF

A Mission Pinball Framework (MPF) recreation of **Stern Tron Legacy Limited Edition, code v1.74**,
built from the reverse-engineered rules, media and effects in
[Ashram56/Tron-Legacy-LE-ROM-Decryption](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption).

## Layout

| Path | What it is |
|---|---|
| `assets/` | Git submodule: [Tron-Legacy-LE-ROM-Decryption](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption), the rules specs, MPF config and media read from the ROM. Never copy files out of it; reference them, so a sync never leaves stale copies. |
| `game/` | The MPF machine folder and the Godot (GMC) project in one: `config/`, `modes/`, `slides/`, `project.godot`, `gmc.cfg`. Kept apart from `assets/` so Godot does not import the asset repo's 12,000 files. |
| `scripts/` | Workspace setup, the headless render check and the asset sync. |

## Toolchain (Linux x86_64)

| Component | Version |
|---|---|
| MPF | 0.80.1 (Python venv in `.venv/`) |
| Godot | 4.5.2 stable (`tools/godot/godot`) |
| GMC (Godot media controller) | 1.0.0 (`game/addons/mpf-gmc/`) |

```sh
scripts/setup_workspace.sh   # installs all of the above and the assets submodule; safe to re-run
```

## Running

On a desktop: start Godot first (it is the BCP server), then MPF.

```sh
tools/godot/godot --path game &
(cd game && ../.venv/bin/mpf game .)
```

Without a screen (CI, cloud sessions), the render check runs both on a virtual display (Xvfb),
captures the 128x32 DMD in real time and fails if nothing was drawn:

```sh
scripts/render_check.sh [seconds]   # writes captures/dmd_latest.png and an 8x preview
```

Godot's `--headless` mode uses a dummy renderer that draws nothing, so the check uses Xvfb with
the OpenGL renderer (Mesa llvmpipe). `game/tools/dmd_capture.gd` does the capture; it is inert
unless Godot is started with `-- --capture-dir=...`.

## Keeping assets in sync

The asset repo is still being completed. `scripts/sync_assets.sh` moves the submodule to its
latest commit and writes `captures/asset_sync.md`: commits, changed files by area, any
`UPDATE_*`/`REMOVED_*` package notes, and files deleted or renamed upstream. A scheduled routine
runs it and opens a pull request whenever the assets move.
