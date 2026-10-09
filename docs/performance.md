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
| `tegrastats.log` | Jetson CPU/GPU load, power (VDD_IN), temperatures, clocks |
| `godot.log`, `mpf.log` | the game's logs: MPF asks for display effect N (`tron_deff_N`), Godot reports `slide_deff_N_created` |

`summary.md` lists frames (FPS, worst second, median, p99, frames over 2 vblanks and over 100 ms), stalls (frame
gaps over 300 ms, with their start time), video per screen (shown, skipped, simultaneous switches), A/V drift, black
screens, the **slowest display effects** (MPF request to slide created), board load and the busiest threads.

Notes on reading it:
- The video decoder figure is the share of tegrastats samples where the decoder clock is on, not its load:
  tegrastats on L4T R35 prints the NVDEC clock only. The real decoder headroom on the Xavier NX is about 5x for
  three 1080p30 videos (parallel `ffmpeg -c:v h264_nvmpi` decodes: 430-446 fps in total).
- The first 8 s (window creation, first video opens) are reported apart.

## Targets

Per clip, after start-up: 0 frames over 2 vblanks, 0 video frames skipped, A/V drift under 40 ms on average,
0 black screens, 0 Godot `ERROR` lines. `summary.md` ends with PASS/FAIL per target.

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
(about 1.5 ms per frame when imported VRAM-compressed).
