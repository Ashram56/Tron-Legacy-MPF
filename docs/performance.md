# Performance: measuring smoothness

How to measure whether the game plays smoothly (every frame on time, no video frame lost, sound in sync), find
what causes a hitch, and check a change. Content-agnostic: the same steps work for any slide, show or video.

## Quick start

    bash scripts/perf/run.sh --suite [NVPMODEL_MODE]          # the trouble-spot clips, about 2 minutes
    bash scripts/perf/run.sh SCENARIO [SECONDS] [MODE]        # one scenario (scenarios/ or assets/rules/traces/)

Results go to `perf/<date-time>-<label>/` (git-ignored; `PERF_LABEL=before` names the folder): one folder per
clip with `summary.md`, and `suite.md` with one line per clip. Compare a `before` and an `after` suite for every
change; play a whole game (`full_game_to_portal 620`) only as the final soak.

The clips (`scripts/perf/clips.txt`) are short reference traces that reproduce the known trouble spots:

| clip | length | reproduces |
|---|---|---|
| `light_cycle_multiball_repeat_and_stack` | 45 s | start-up, the two largest DMD animation loads (deff 85, 86), three PuP screens switching video at once |
| `portal_multiball` | 75 s | deff 141 and 143 loads, a three-screen video switch |

## What is measured

`game/tools/perf_probe.gd` (autoload `PerfProbe`) records only when `TRON_PERF_DIR` is set; it reads and changes
nothing. `scripts/perf/sampler.py` samples the threads; `tegrastats` runs on a Jetson.

| file | content |
|---|---|
| `frames.csv` | every frame: start time, process delta, and the main thread's time until the frame's draw was submitted |
| `video.csv` | every video frame shown, per PuP screen: frame number, `step` (1 = on cadence, more = frames skipped), how late against its due time |
| `av.csv` | once a second per video with sound: audio position minus the shown frame's time |
| `events.csv` | video opens; black screens over 0.2 s (a PuP window that should show a picture and shows none) |
| `threads.csv` | CPU % of one core per thread of Godot and MPF, every second; `(main)` marks each main thread |
| `processes.csv` | Godot's and MPF's resident memory (VmRSS) and its peak (VmHWM), every second |
| `memory.csv` | Godot's own monitors every second: static memory, video memory and the textures' share of it |
| `tegrastats.log` | Jetson CPU/GPU load, power (VDD_IN), temperatures, clocks |
| `godot.log`, `mpf.log` | the game's logs: MPF asks for display effect N (`tron_deff_N`), Godot reports `slide_deff_N_created` |

`summary.md` lists frames (FPS, worst second, median, p99, frames over 2 vblanks and over 100 ms), stalls (frame
gaps over 300 ms, with their start time), video per screen (shown, skipped, simultaneous switches), A/V drift, black
screens, the **slowest display effects** (MPF request to slide created), board load, **memory** (Godot resident at
10 s, at the end and at peak, Godot video memory, the effects preload's size and time from `godot.log`, board RAM and
swap from tegrastats) and the busiest threads.

Notes on reading it:
- Frame times are the gaps between frame start times. Godot's process delta is not used: it read one vblank for a
  frame held 433 ms. "Over 2 vblanks" counts gaps over 2.5 vblanks (held 3 vblanks or more), as start times jitter.
- The video decoder figure is the share of tegrastats samples where the decoder clock is on, not its load:
  tegrastats on L4T R35 prints the NVDEC clock only. The real decoder headroom on the Xavier NX is about 5x for
  three 1080p30 videos (parallel `ffmpeg -c:v h264_nvmpi` decodes: 430-446 fps in total).
- The first 8 s (window creation, first video opens) are reported apart.

## Targets

Per clip, after start-up: 0 frames over 2 vblanks, 0 video frames skipped, A/V drift under 40 ms on average,
0 black screens, 0 Godot `ERROR` lines. `summary.md` ends with PASS/FAIL per target.

## Settings measured (Xavier NX, mode 5, the clip suite)

- Core pinning (`scripts/run.py`, Linux with 4+ cores, `TRON_PIN=0` turns it off): Godot's main thread alone on the
  last core, Godot's other threads and MPF on the others. About +1.5 FPS and a third fewer frames over 2 vblanks
  (two runs each way). Putting MPF alone on one core instead made it worse (42.5 / 49.7 FPS against 49.8 / 53.0).
- `jetson_clocks` (every clock at the mode's maximum): no measurable gain (47.8 / 52.9 FPS with it, 48.3 / 53.4
  without) at the same power, so it is not used.
- Godot's worker pool (`threading/worker_pool/low_priority_thread_ratio=0.5` in `game/project.godot`, Godot's
  default 0.3): low-priority tasks (video opens, closes, restarts, background loads) get 2 threads instead of 1 on 4
  cores. Shorter stalls at video switches (1.27 / 1.29 s to 0.95 / 0.61 s), the rest unchanged.
- Large display effects preloaded (`tron/dmd/preload_min_frames=40`, `game/tools/dmd_mode.gd`; 0 = off): the HD
  frames and slide scenes of every effect with 40 frames or more (17 effects, 1558 frames) load on worker threads
  from the start, so their slides no longer load on the main thread when shown. Deff 86 created 0.89 s to under
  0.1 s, deff 143 0.38 s to under 0.13 s; about 200 MB more memory (2.6 to 2.8 GB used of 6.8 GB).
- Video frames decoded ahead (`pup_addons/gde_gozen/video_playback.gd`): up to 3 frames per video are decoded on
  worker threads and shown when their time comes. A silent video never drops a frame: after a stall its clock slips
  by the delay. A video with its own sound takes its clock from the sound heard (playback position minus the output
  latency) and drops the frames it is late by. Video frames skipped 89 / 85 to 15 / 7 per clip (all on videos with
  sound; 0 on the silent screens), A/V drift 79-130 ms to 30-46 ms on average.
- Frames decoded at the shown size, as NV12 (GoZen `set_target_size()`, `decode_to_display_size`; docs/jetson.md
  fix 10): 4 to 8 times fewer pixels per video frame. Godot's main thread 44-46% of a core instead of 51-55%;
  52.9 / 54.7 to 53.4 / 55.7 FPS, frames over 2 vblanks 19 / 33 to 18 / 26.
- Godot's separate render thread (`rendering/driver/threads/thread_model=2` in `game/project.godot`): rendering moves
  off the main thread (27-28% of a core instead of 44-46%). 53.4 / 55.7 to 55.7 / 58.1 FPS, p99 33.9 / 31.6 to
  29.1 / 25.0 ms, frames over 2 vblanks 18 / 26 to 16 / 21. Godot calls the mode experimental; it logs harmless
  `_texture_2d_update` glyph-cache errors (docs/upstream_issues/godot-separate-render-thread-glyph-cache.md), which
  the summary counts apart. MSDF fonts avoid them but stalled start-up 3 to 7 s, so they are not used. The captures
  (`scripts/render_diff.py`, the tests; renderer opengl3) wrote no frames with it: `scripts/run.py` runs them with
  `--render-thread safe`. On by default on every platform; `scripts/run.py --no-render-thread` (or
  `TRON_RENDER_THREAD=0`, Docker too) turns it off, should a GPU driver misbehave with it.
- The Vulkan pipeline cache saved while the game runs (`rendering/rendering_device/pipeline_cache/save_chunk_size_mb=0.1`
  in `game/project.godot`; Godot's default 3 MB): Godot saved it only at exit or when it grew by 3 MB, and with the
  separate render thread its save at exit fails ("finalize can only be called from the render thread"), as does
  any exit by a kill or a power cut. Every start compiled every pipeline again: the PuP light cycle background
  stalled 4.0-4.7 s at its first derez (particles and a flash light). Saved as it grows, the next start finds the
  pipelines: that stall gone (start-up stall 0.6 s, as without the light cycles); a test scene alone, 1.4 s and
  2.3 s hitches every start to none from the second start.
- Letter glows off Godot's main thread (`game/tron/letter_panel.gd`): the letters of deffs 91, 92, 94 and 107 had their
  glow made on the main thread when the slide was created (reading the pictures back from the GPU and blurring them
  in script), even with the glow off (`tron/dmd/text_glow=0`, the default): deff 94's slide took 380 ms to create
  and deff 95, asked for with it, waited behind it. Now nothing is made with the glow off; with it on, the glows
  are made on worker threads from the start (the letter pictures load with the effects preload). Deff 94 created
  380 to 25-36 ms; slowest display effect in the clip suite 0.56 s (deff 95) to 0.19 s, in the full game 0.55 s to
  0.24 s (every effect under 0.25 s).
- Preloading every effect (`preload_min_frames=1`) was measured and not kept: 2677 resources instead of 1575,
  15-16 s instead of 11 s, about 130 MB more video memory (Godot video memory peak 480-518 MB instead of 345-386 MB),
  and an effect shown during the longer preload waited for it (deff 104 0.49 s); effects shown for the first time
  later came about 50 ms sooner. Memory with the default (full game, 620 s): Godot resident 972 MB at 10 s,
  1649 MB peak; Godot video memory peak 466 MB; board RAM 3.0 GB average, 3.2 GB peak of 6.8 GB; no swap.

## Finding the cause of a hitch

1. Take the stall's start time from `summary.md` (seconds since the probe started).
2. Its wall-clock time: the probe starts with the first `Registered display` line of `godot.log`; add the seconds.
3. In `mpf.log`, look at the events just before: a `tron_deff_N` whose `slide_deff_N_created` comes late (the
   summary's slowest display effects) is a slide whose resources load on Godot's main thread. The silent gap in
   `godot.log` confirms a blocked main thread.
4. `threads.csv` shows which thread was busy: Godot's main thread at about 100% means work on it (loading,
   scripts); worker threads busy with the main thread idle points at waiting (a lock, a decoder).
5. If Godot stops for good, dump every thread's stack while it hangs:
   `sudo gdb -batch -p $(pgrep -f Godot_v | head -1) -ex 'thread apply all bt 25'`.

Found this way (Xavier NX, L4T R35.6.4): the 2.3 s stall at the Light Cycle multiball start is deff 85 and 86
(319 HD frames of 1024x256) loading on the main thread, about 7 ms per frame for lossless decompression
(about 1.5 ms per frame when imported VRAM-compressed). `scripts/gen_media.py` therefore imports the HD effect
frames VRAM-compressed (ETC2 R11 on ARM; 40.8 dB PSNR against the lossless frame, no visible difference at
1280x320): the stall went from 2.34 to 1.00 s, deff 86 from 2.24 to 0.91 s.
