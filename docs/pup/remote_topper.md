# Remote topper: the topper videos on a Raspberry Pi

The PuP Pack's topper videos (PuP screens 13 and 14) can play on a small screen of their own, driven by a Raspberry
Pi in the topper, instead of in a window on the cabinet's computer. The game sends the Pi short commands over the
network (Wi-Fi or Ethernet); the videos themselves are on the Pi's SD card. The cabinet keeps all the sound.

Tested: the game, the link and the player on Linux with a desktop mpv. Not tested yet on a real Raspberry Pi.

## What you need

- A **Raspberry Pi 3 Model A+** (recommended: four cores, the Pi's H.264 decoder) or a Pi Zero W (the same decoder
  but one slow core: it should play topper-sized videos, untested), with its screen on HDMI.
- **Raspberry Pi OS Lite** (Bookworm, no desktop), written with Raspberry Pi Imager. In the Imager's settings: a
  hostname (for example `tron-topper`), a user and password, the Wi-Fi of the cabinet's network, and SSH on.
- The Pi and the game computer on the same network.

## Setting it up

1. **On the Pi** (over SSH: `ssh <user>@tron-topper.local`):

   ```bash
   curl -fsSL https://raw.githubusercontent.com/Ashram56/Tron-Legacy-MPF/main/remote/topper/install.sh | bash
   ```

   It installs mpv and the topper agent (`/opt/tron-topper`), its settings (`/etc/tron-topper.cfg`) and a service
   that starts it at boot. From a clone of this repository, `bash remote/topper/install.sh` does the same.

2. **On the game computer**, turn the remote screens on in `game/pup.local.cfg`:

   ```ini
   [remote]
   enabled=true
   ```

   and, if the cabinet no longer needs its own topper window:

   ```ini
   [pup]
   third_screen=false
   ```

3. **Copy the topper videos to the Pi**, from the game computer (SSH asks for the Pi's password unless you set up
   a key):

   ```bash
   python scripts/pup/topper_media.py --push <user>@tron-topper.local
   ```

   It takes the topper's playlists from the PuP Pack (its default backgrounds and every trigger on screens 13
   and 14), copies the videos as they are into `pup_media/topper/` and sends them to `~/tron-topper/media` on the
   Pi (rsync: later runs send only what changed). A video the Pi's decoder can't play (not H.264, above 1920x1080
   or 30 fps, a 10-bit or 4:4:4 profile) is re-encoded first, and the run lists which and why. Run it again after a
   pack update.

4. **Start the game.** The Pi finds it by itself (a broadcast on the local network, UDP port 5052) and shows the
   topper's background; the game's log says `remote PuP display 'topper' connected`.

## Settings on the Pi

`/etc/tron-topper.cfg` (then `sudo systemctl restart tron-topper`):

| Key | Default | What it does |
|---|---|---|
| `host` | `auto` | the game computer; `auto` finds it by broadcast. Set its name or address when the network drops broadcasts (some routers' guest or isolated Wi-Fi) |
| `fit` | `fill` | `fit` (black bars), `fill` (crops to cover the screen) or `stretch` |
| `align` | `0.5` | vertical place of a fitted video: 0 top, 1 bottom |
| `audio` | `false` | `true` plays the videos' own sound on the Pi |
| `mpv_args` | `--vo=gpu --gpu-context=drm --hwdec=v4l2m2m-copy` | how mpv draws and decodes (straight to the screen, hardware H.264) |
| `screens` | `13,14` | the PuP screens it shows: underlay, then pop-up layer |

Its log: `journalctl -u tron-topper -f` (each video it plays, the game coming and going).

## How it works

```
 Game computer                                            Raspberry Pi
 MPF: PuP triggers (game/tron_pup/engine.py)              tron_topper.py (systemd service)
   |-- BCP --> Godot (backglass, DMD, local topper)         PinUP rules of screens 13 and 14
   `-- remote.py: TCP 5052, JSON lines  ── network ──>      (screen_rules.py, the game's own file)
                  UDP 5052: answers the Pi's broadcast       --> mpv on its IPC socket --> the screen
```

- The game's PuP mode (`game/tron_pup/mode.py`) gives every PuP command to `game/tron_pup/remote.py` as well as to
  Godot, so the topper plays whether or not the cabinet has a topper window.
- When the Pi connects, the game sends it each screen's default background, the playlists' rules
  (`playlists.pup`: order and volume) and what its screens show now (the last SetBG and a running mode loop), so a
  Pi that starts late, or the game restarting, gets in step at once without restarting a loop already on screen.
  Then every command for screens 13 and 14, and a ping every 5 s: after 15 s without news the Pi reconnects.
- The Pi keeps PinUP Player's rules itself (`game/tron_pup/screen_rules.py`, the same rules as Godot's
  `game/pup/pup_screen.gd`: priority, Loop, SetBG, StopFile, StopPlayer, SkipSamePrty, the background back when a
  video ends), because only the Pi knows when its own video ends.
- One mpv plays both layers: the pop-up (14) while it plays, else the underlay (13), which resumes where it was.
- Protocol and messages: the docstring of `game/tron_pup/remote.py`. Tests: `tests/test_pup_remote.py`.

## Testing without a Pi

On any Linux or macOS computer with mpv, beside the game (with `[remote] enabled=true`):

```bash
python scripts/pup/topper_media.py
python remote/topper/tron_topper.py --window --media pup_media/topper
```

## To check on the Pi

1. Smooth playback with `--hwdec=v4l2m2m-copy` on the 3 A+ and on a Zero W (`journalctl` shows mpv's errors; try
   `--hwdec=no` to compare).
2. Discovery on the cabinet's network (else set `host=`).
3. The underlay resuming where it was after a pop-up.
