# Performance: settings and what they gain

The game's settings that keep every frame on time, and the measurements behind them. Measured on a Jetson Xavier
NX (nvpmodel mode 5, 4 cores at 1.9 GHz, the slowest target), where every hitch shows; the same settings apply on
every platform. The measuring tools (frame, video, memory and power probes, a clip suite) and the Jetson findings
live in the PuP repository: [Tron-Legacy-MPF-PuP](https://github.com/Ashram56/Tron-Legacy-MPF-PuP)
`docs/performance.md` and `docs/jetson_xavier_nx.md`. Asset rules for new media: [agents/improvement.md](agents/improvement.md)
section 2a.

| Setting | Where | Gain (Xavier NX) | Turn off |
|---|---|---|---|
| Godot's separate render thread | `rendering/driver/threads/thread_model=2`, `game/project.godot` | Main thread 29% of a core instead of 54%; 55.3 / 57.1 FPS instead of 53.3 / 54.2 on the two test clips. Logs harmless `_texture_2d_update` glyph-cache errors (a Godot bug). The captures (`scripts/render_diff.py`, opengl3) wrote no frames with it, so `run.py` always runs them with `--render-thread safe` | `run.py --no-render-thread`, `TRON_RENDER_THREAD=0` (Docker too) |
| Pipeline cache saved while running | `rendering/rendering_device/pipeline_cache/save_chunk_size_mb=0.1` | With the render thread, Godot's save at exit fails, so every start recompiled every pipeline: 1.4-4.7 s at the first use of an effect. Gone from the second start | - |
| Worker pool | `threading/worker_pool/low_priority_thread_ratio=0.5` | Background loads get 2 threads on 4 cores instead of 1: stalls 1.3 to 0.6-0.95 s where loads overlap | - |
| Large effects preloaded | `tron/dmd/preload_min_frames=40`, `game/tools/dmd_mode.gd` | Deff 86 0.89 s to under 0.1 s; about +200 MB | `0` |
| HD effect frames VRAM-compressed | `scripts/gen_media.py` `HD_FRAME_IMPORT` | 7 to 1.5 ms per frame loaded, half the GPU memory | - |
| Letter glows on worker threads | `game/tron/letter_panel.gd` | Deff 94 380 to 25-36 ms; nothing made with the glow off | - |
| Clean fonts baked at setup | `game/tools/bake_fonts.gd`, `scripts/setup.py` | 20-30 s freezes on first text gone | - |
| Core pinning (Linux, 4+ cores, a real display) | `scripts/run.py` | Godot's main thread alone on the last core: +1.5 FPS, a third fewer late frames | `TRON_PIN=0` |

A whole game on the Xavier NX with all of these (Orbitron with glow, two screens): 57.8 FPS, longest stall 0.6 s
(start-up), every display effect within 0.2 s, board RAM peak 3.4 GB of 6.8 GB.
