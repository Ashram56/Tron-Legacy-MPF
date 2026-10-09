# With the separate render thread, the Vulkan pipeline cache is never saved

**Project:** https://github.com/godotengine/godot

## Environment

- Godot 4.6.3 stable, Linux arm64, Vulkan, Mobile renderer
- Jetson Xavier NX, L4T R35.6.4 (JetPack 5.1.4), NVIDIA Tegra Vulkan driver, X11
- `rendering/driver/threads/thread_model=2` (separate render thread)

## What happens

Every start compiles every pipeline again: the pipeline cache file is never written.

- Godot saves the pipeline cache at exit, and whenever it has grown by
  `rendering/rendering_device/pipeline_cache/save_chunk_size_mb` (3 MB by default).
- With the separate render thread, the save at exit fails:
  `finalize can only be called from the render thread`. A game ended by a kill, a power cut or a cabinet's
  power switch never reaches it anyway.
- A small 2D game rarely grows the cache by 3 MB in one run, so the cache stays empty.

On a slow GPU each first use of a material stalls the game: a particle effect with a light took 4.0-4.7 s on its
first appearance, on every start; a test scene had 1.4 s and 2.3 s hitches on every start.

## Workaround

`rendering/rendering_device/pipeline_cache/save_chunk_size_mb=0.1`: the cache is saved while the game runs, as it
grows. From the second start the stalls are gone (start-up stall 0.6 s instead of 4.7 s).

## Expected

The save at exit works with the separate render thread (run it on the render thread), and the documentation of
`save_chunk_size_mb` mentions that a killed process never saves.
