# GDE GoZen for the PuP on Linux (Jetson hardware decoding)

[GDE GoZen](https://github.com/VoylinsGamedevJourney/gde_gozen) is a Godot add-on that plays videos with FFmpeg.
On Linux, `scripts/setup.py` copies this folder to `game/addons/gde_gozen/` and the PuP plays the pack's mp4s
as they are (no Theora conversion). Each PuP screen uses GoZen's `VideoPlayback` node through
`game/pup/gozen_player.gd`.

This build differs from upstream GoZen in two ways (`scripts/gozen/gozen.patch`, rebuilt by
`scripts/build_gozen.sh`):

- Its FFmpeg 7.1 carries [jetson-ffmpeg](https://github.com/gjrtimmer/jetson-ffmpeg)'s `*_nvmpi` decoders, and
  GoZen asks for `<codec>_nvmpi` (`h264_nvmpi` for this pack) before the software decoder. Those decoders load
  `libnvmpi.so` when a video opens: without it (any PC that is not a Jetson), GoZen falls back to FFmpeg's
  software decoder. `GOZEN_HWDEC=0` in the environment forces software decoding.
- FFmpeg is trimmed to what a PuP Pack uses (mp4/mkv/ogg; H.264, HEVC, MPEG-4, VP8, VP9, Theora; AAC, MP3,
  Vorbis, Opus, FLAC), with no libvpx, libaom or TLS.

| File | Built for |
|---|---|
| `bin/libgozen.linux.template_release.arm64.so` | Linux arm64 (Jetson, Raspberry Pi), glibc 2.31+ (JetPack 5, Ubuntu 20.04+) |
| `bin/libgozen.linux.template_release.x86_64.so` | Linux x86_64, glibc 2.31+ |

Both are release builds; `gozen.gdextension` maps the debug entries (the Godot editor binary that `run.py`
starts) to them as well.

## Hardware decoding on the Jetson (JetPack 5 or 6)

Build and install libnvmpi once, on the Jetson (it needs the Jetson Multimedia API:
`sudo apt install nvidia-l4t-jetson-multimedia-api` if `/usr/src/jetson_multimedia_api` is missing):

```bash
sudo apt install cmake build-essential git
git clone https://github.com/gjrtimmer/jetson-ffmpeg && cd jetson-ffmpeg
./scripts/build.sh --install          # libnvmpi.so in /usr/local/lib, ldconfig
```

When the game starts, Godot's log (`game/logs/` or the terminal) says for each video either
`GoZen: hardware decoder h264_nvmpi` or `GoZen: hardware decoder h264_nvmpi unavailable, using software`.
`sudo tegrastats` shows `NVDEC` busy while videos play.

## Licence

GDE GoZen and FFmpeg are LGPL 2.1 (`LICENSE`); FFmpeg is linked statically into `libgozen*.so`. The sources are
the pinned revisions in `scripts/build_gozen.sh` plus `scripts/gozen/gozen.patch`.
