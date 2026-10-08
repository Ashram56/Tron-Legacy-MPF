# Jetson: hardware video decoding fixes

This page lists every change we carry so that the PuP Pack's videos play with the Jetson's hardware decoder (NVDEC)
without freezes or crashes: what was wrong, the fix, where it lives and how it was checked. Start here when
bringing up another Jetson, such as the Xavier NX.

**Tested:** Jetson AGX Orin Developer Kit (t234), L4T R36.4.3 / JetPack 6.2, Ubuntu 22.04, `oot` kernel, Godot
4.6.3, one 1920x1080 DisplayPort screen with the three PuP windows on it (git tag `jetson-agx-orin-l4t-r36.4.3`).
**Decoder self-test passed:** Jetson Xavier NX Developer Kit (t194), L4T R35.6.4 / JetPack 5.1.4, Ubuntu 20.04.6,
on the PuP Pack's 1080p trailer (2026-10-08). The game itself is not played on it yet. See
[Xavier NX checklist](#xavier-nx-checklist).

## The video stack

| Layer | What it is | Ours | Built by |
|---|---|---|---|
| PuP screens | `game/pup/pup_screen.gd`, `game/pup/gozen_player.gd` | changed | - |
| GoZen player script | `pup_addons/gde_gozen/video_playback.gd` (GDE GoZen's `VideoPlayback` node) | changed | - |
| GoZen GDExtension | `pup_addons/gde_gozen/bin/libgozen.linux.*.so`, GDE GoZen at `f9448619` + FFmpeg 7.1 linked in | `scripts/gozen/gozen.patch` | `scripts/build_gozen.sh` (Docker) |
| FFmpeg nvmpi wrapper | jetson-ffmpeg's `*_nvmpi` decoders, compiled into GoZen's FFmpeg (`nvmpi_dec.c`) | `scripts/gozen/nvmpi_flush.patch` (`ffmpeg/` part) | `scripts/build_gozen.sh` |
| libnvmpi | jetson-ffmpeg at `8d70c17` (v3.10.0), installed in `/usr/local/lib`, loaded by the wrapper at run time | `scripts/gozen/nvmpi_flush.patch` (`src/` part) | `scripts/install/install_jetson_hwdec.sh` |
| NVIDIA | V4L2 decoder, NvMMLite, NvBufSurface (L4T BSP, `nvidia-l4t-multimedia*`) | - | JetPack |

The wrapper and libnvmpi share one patch file. `build_gozen.sh` and `install_jetson_hwdec.sh` both apply the whole
file to their jetson-ffmpeg checkout, so GoZen's FFmpeg and the board's libnvmpi always carry the same fixes.
Changing only the `src/` part needs a new install on the board but no GoZen rebuild. Changing the `ffmpeg/`
part needs `bash scripts/build_gozen.sh arm64` and committing the new `.so`.

## Fixes

### 1. Looping or seeking a video froze the game forever (FFmpeg wrapper)
- **Symptom:** the first loop or seek of any video hung the next decode; every time; mp4, mkv and ts.
- **Cause:** `avcodec_flush_buffers()` resets libnvmpi's decoder in place (STREAMOFF/STREAMON). On L4T R36 the
  V4L2 decoder sends no new resolution-change event for the same stream, so the capture plane never restarts and
  `put_packet()` blocks in the OUTPUT plane's `dqBuffer()`. Re-arming the capture plane in place was tried: its
  DQBUF then fails with `EINVAL`.
- **Fix:** `nvmpi_flush_decoder()` closes the decoder and `nvmpi_decode()` creates a new one from the saved
  `nvDecParam` with the next packet (lazily, primed with the extradata again). A flush with nothing decoded since
  the decoder was created does nothing (GoZen flushes right after opening and right before freeing).
- **Checked:** 3 loops and 3 mid-stream seeks pass for mp4/mkv/ts; `ffmpeg -stream_loop 9 -c:v h264_nvmpi`
  completes. Report: [upstream_issues/jetson-ffmpeg-flush-hang.md](upstream_issues/jetson-ffmpeg-flush-hang.md).

### 2. Closing a decoder took about 1 s (libnvmpi)
- **Symptom:** every video switch froze the whole game for 1 to 2.5 s (software decoding: about 0.1 s).
- **Cause:** a decoder that has not output a frame yet (just created, or recreated by fix 1) waits out two
  500 ms `dqEvent()` timeouts in its capture thread before `close()` can join it.
- **Fix:** a `closing` flag set first in `nvmpi_decoder_close()`; the capture thread's event wait runs in 50 ms
  slices and skips its extra 500 ms "race guard" wait when closing.
- **Checked:** close 1061 ms → 55 ms. Report:
  [upstream_issues/jetson-ffmpeg-slow-close-crash.md](upstream_issues/jetson-ffmpeg-slow-close-crash.md).

### 3. Closing a decoder mid-video sometimes crashed (libnvmpi)
- **Symptom:** SIGSEGV in NVIDIA's decoder thread (`libnvmmlite_video.so`), inside `v4l2_close` or after the
  buffers were freed; 9 of 100 runs of the repro with stock libnvmpi.
- **Cause:** the decoder was torn down while it was still decoding queued bitstream, and its CAPTURE DMA buffers
  were freed while the decoder device was still open.
- **Fix:** in `nvmpi_decoder_close()`, wait at most 300 ms for the OUTPUT plane to drain (the capture thread drops
  frames instead of waiting for the frame pool while closing), then stop the capture plane, delete the decoder,
  and only then free the CAPTURE buffers and the frame pool.
- **Checked:** 0 crashes in 100 runs. Same report as fix 2.

### 4. The game froze when several screens switched videos at once (libnvmpi)
- **Symptom:** in a long game, one screen's video stopped, and Godot's main thread waited for it forever.
- **Cause:** with decoders created and closed from several threads, a decoder's CAPTURE DQBUF now and then fails
  with `EINVAL`. Its capture thread exits, nothing returns OUTPUT buffers, and `put_packet()` blocks forever.
  4 of 6 runs of the 3-thread repro hung, with stock libnvmpi too.
- **Fix:** a global mutex `nvmpi_dec_setup_mutex` serialises decoder creation, teardown (after the capture thread
  is joined) and `respondToResolutionEvent()`. When the capture thread stops on an error, it STREAMOFFs the
  OUTPUT plane, which wakes a blocked `put_packet()` with an error, and `put_packet()` fails at once while the
  decoder is in error. GoZen then ends or restarts that video with a new decoder (fix 1).
- **Checked:** 0 hangs in 20 runs (3 decoders recovered from the error). Report:
  [upstream_issues/jetson-ffmpeg-concurrent-decoders-hang.md](upstream_issues/jetson-ffmpeg-concurrent-decoders-hang.md).

### 5. Video work stalled Godot's main thread (GoZen player script)
- **Symptom:** every stall above hit all three PuP windows and the DMD, because they are drawn by the same
  Godot process.
- **Fix, in `video_playback.gd`:**
  - the audio stream opens on the worker thread with the video;
  - `_process()` takes the opened video only once `WorkerThreadPool.is_task_completed()` (it used to wait on the
    first frame);
  - `close()` hands the closed `GoZenVideo` to a worker task, so its decoder is freed there; `_exit_tree()` waits
    for those tasks;
  - new `restart()`: back to the first frame on a worker task, showing the current frame meanwhile. Looping uses
    it, and so does `gozen_player.gd`'s `play()`.
- **Checked:** with timing logs over a 2-minute game, the longest video step on the main thread went from
  2.4 s to 10 ms. Report: [upstream_issues/gde-gozen-main-thread-stalls.md](upstream_issues/gde-gozen-main-thread-stalls.md).

### 6. The topper went black between videos (PuP screens)
- **Cause:** `pup_screen.gd` stopped the player, which hides the picture, before opening the next video.
- **Fix:** with GoZen it opens the next video directly; the previous video's last frame stays up until the next
  one's first frame is ready.

### 7. Hardware decoder selection and safe fallback (GoZen, earlier PRs)
- `gozen.patch`: GoZen asks FFmpeg for `<codec>_nvmpi` first, then the software decoder; `GOZEN_HWDEC=0` forces
  software.
- `gozen_player.gd`: no decoder device in `/dev` (`nvmap` plus `nvhost-nvdec*` or `v4l2-nvdec`) → software
  decoding, because NVIDIA's libraries crash rather than fail without them.

### 8. Install and cabinet (install scripts, run.py)
- `install_jetson_hwdec.sh` pins NVIDIA's packages to the board's own L4T release (the r36.4 apt repo also offers
  36.4.7), keeps existing config files instead of stopping on a dpkg prompt, reads the whole loader cache when it
  looks for libnvmpi, and applies `nvmpi_flush.patch` before building libnvmpi.
- No blanking mid-game: the install turns off GNOME's idle blanking, dimming, lock and suspend (`--keep-blanking`
  leaves them), and `run.py` runs `xset s off -dpms`. Without both, the screen went black after 5 minutes.
- GDM automatic login and an X11 session (Godot places one window per monitor only on X11): [pup.md](pup.md).

## Known leftovers
- A recreated decoder can lose up to about 10 trailing frames when it drains at the end of a video.
- About every 10 to 20 s, around a video switch, the game hitches for about 0.1 s. The same happens with
  software decoding.
- A loop point can hold the last frame for about 0.1 s (the new decoder's first frame), while everything else
  keeps moving.
- When a screen closes a video that is still opening, `close()` waits for the open (seen once, 0.4 s, at start-up).

## How the fixes were checked
- Repro programs, built against GoZen's patched FFmpeg (build line at the top of each):
  [nvmpi_seek_close.c](upstream_issues/repro/nvmpi_seek_close.c) (`flush`, `close`, `crash` modes) and
  [nvmpi_concurrent.c](upstream_issues/repro/nvmpi_concurrent.c) (`in.mp4 3 40 10`).
  `scripts/install/jetson_selftest.sh` builds and runs them all on a board.
- Decode speed: 1080p H.264 at about 350 fps on NVDEC, against about 70 fps on one CPU core.
- Games on the board: `scripts/run.py --scenario clu_hurryup --seconds 120`, with Godot's log showing
  `GoZen: hardware decoder h264_nvmpi` per video. `scripts/run.py --scenario full_game_to_portal`
  (`scenarios/full_game_to_portal.txt`) plays a whole game to Portal Multiball in about 10 minutes.

## Xavier NX checklist
JetPack 5 (L4T R35, t194) differs from the Orin in ways that touch these fixes:
- NVIDIA's libraries are in `/usr/lib/aarch64-linux-gnu/tegra/` instead of `.../nvidia/` (the install and the
  self-test handle it). R35's Multimedia API already has `nvbufsurface.h`, so libnvmpi builds on the same NvUtils
  path (`WITH_NVUTILS`) as on the Orin, not on the legacy `nvbuf_utils` one.
- The Xavier NX has fewer NVDEC sessions and less memory than the AGX Orin: check three screens decoding at once.

**On the board** (Xavier NX Developer Kit, L4T R35.6.4, minimal image, no nvpmodel mode set: 6 CPUs at 1.9 GHz),
`jetson_selftest.sh --stock` with `pup_pack/trn_174h/AttractMode/AttractMode-Trailer1.mp4` (1080p30 H.264):

| Check | Patched | Stock jetson-ffmpeg `8d70c17` |
|---|---|---|
| flush (fix 1) | pass | hang (killed after 60 s): the in-place reset fails on R35 too |
| close (fix 2) | 59 ms / 48 ms | 1086 ms / 24 ms (no packet / after 30 frames) |
| crash (fix 3), 100 runs | 0 crashed | 0 crashed (the Orin: 9) |
| concurrent (fix 4), 20 runs | 0 failed | 5 segfaults (the Orin hung instead) |

So fixes 1, 2 and 4 are needed on JetPack 5 too; fix 3 is kept (no cost).

**Checked without the board** (an arm64 Ubuntu 20.04 root under qemu, posing as a Xavier NX with L4T R35.4.1 and
NVIDIA's r35.4 apt packages): the full Linux install (`install_prereqs_linux.sh --yes`) passes, including Python
3.11 from uv, MPF Monitor, Godot 4.6.3 arm64, the PuP Pack and the Godot import; `nvmpi_flush.patch` applies and
libnvmpi builds with NvUtils against R35.4.1 and links NVIDIA's own `libv4l2.so.0`. The self-test's ffmpeg 7.1 with nvmpi and
both repro programs build and link there too. The GoZen arm64 `.so` needs
glibc 2.29 at most (Ubuntu 20.04 has 2.31). Decoding itself needs the board.

To bring one up:
1. `bash scripts/install/install_jetson_hwdec.sh` (or the full Linux install), and check that libnvmpi is in
   `ldconfig -p`.
2. `bash scripts/install/jetson_selftest.sh --stock`: builds the `--test` ffmpeg and the repro programs, then runs
   `flush`, `close`, `crash` (100 runs) and `nvmpi_concurrent in.mp4 3 40 10` (20 runs), each with a time limit,
   against our patched build and then against jetson-ffmpeg without the patch. The patched build must pass every
   check (exit status 0); the stock results show which bugs R35 has on its own: note them under "Not checked yet
   on JetPack 5" in the matching report. Logs: `~/.cache/tron-legacy-mpf/selftest/`.
3. Play `scripts/run.py --scenario clu_hurryup --seconds 120`, then `scripts/run.py --scenario full_game_to_portal`, on the
   screen. Watch for freezes and black screens, and check `game/logs/godot.log` for `h264_nvmpi` and errors.
4. Record the result in the "Tested" line at the top of this page and in the headers of `nvmpi_flush.patch` and
   `gozen.patch`.
5. If a hunk does not apply or behaves differently on R35, change `nvmpi_flush.patch` and re-run step 1; when its
   `ffmpeg/` part changes, also rebuild GoZen (`bash scripts/build_gozen.sh arm64`) and commit the `.so`.

## Updating a pin
To move jetson-ffmpeg or GDE GoZen to a newer revision:
1. Change `JETSON_FFMPEG_REV` / `GOZEN_REV` in `scripts/build_gozen.sh` and the jetson-ffmpeg revision in
   `scripts/install/install_jetson_hwdec.sh`. Both must name the same jetson-ffmpeg revision: the wrapper in GoZen
   and the library on the board have to match.
2. Check that both patches still apply (`git apply --check`) and drop the hunks upstream has fixed (see the reports
   in `upstream_issues/`).
3. Rebuild GoZen, re-run the Jetson install, then repeat steps 2 and 3 of the checklist.
