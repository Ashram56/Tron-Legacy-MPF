# Remote topper: the topper videos on a Raspberry Pi

The PuP Pack's topper videos (PuP screens 13 and 14) can play on a small screen of their own, driven by a Raspberry Pi in
the topper (a Pi Zero W is enough), instead of in a window on the cabinet's computer. The game sends the Pi short commands
over the network and **serves the topper's videos itself**, read in place from the PuP Pack: the Pi downloads what is new at
each connection. No video is in an image or a bundle, nothing is copied by hand, nothing runs on the cabinet. The cabinet
keeps all the sound.

The server, the media server, PinUP Player's screen rules and the Pi's agent, installer and Pi Zero W image are the
**platform's**, shared by every game:
[MPF-Godot-Packaging `platforms/pup-remote-topper.md`](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/platforms/pup-remote-topper.md)
(what you need, Pi set-up, settings, protocol, how to check). This page is Tron's part. Not tested on a real Pi yet.

## Setting it up

1. **On the Pi**: flash the platform's Pi Zero W image (`platforms/raspberrypi/zero/`: Wi-Fi and hostname set in files on the
   boot partition), or on any other Pi (Raspberry Pi OS Lite, over SSH) run the platform's installer:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/Ashram56/MPF-Godot-Packaging/main/mpf_godot/pup_remote/topper/install.sh | bash
   ```

2. **On the game computer**, turn the remote screens on in `game/pup.local.cfg`:

   ```ini
   [remote]
   enabled=true
   ```

   and, if the cabinet no longer needs its own topper window, `[pup]` `third_screen=false`. The game takes the server
   from the platform (cloned beside this repository when missing, see `scripts/mpf_platform.py`).

3. **Start the game.** The Pi finds it by itself (broadcast on UDP port 5052), downloads the topper's videos from the game's
   media port (TCP 5053, `[remote] media_port`; open it in the firewall) and plays them; the game's log says
   `remote PuP display 'topper' connected` and `remote PuP screens: N media files served on port 5053`.

The topper's videos are the playlists its PuP screens play: their default backgrounds (screens.pup) and every active
triggers.pup row on screens 13 and 14. A video the Pi's decoder can't play (not H.264, above 1920x1080 or 30 fps, 10-bit
or 4:4:4) is not detected yet: it is a future bundle add-on of re-encoded copies, never a step on the cabinet.

## Tron's side in the code

- `game/tron_pup/mode.py` hands every PuP command to the platform's `RemoteServer` as well as to Godot, so the topper plays
  whether or not the cabinet has a topper window, and gives it `media.topper_media(pack, screens, triggers)` for the videos;
  `pupfiles.load_screens/load_triggers/load_playlists` read the pack's `.pup` files for it; `game/pup.cfg` `[remote]` holds
  the ports, listen address and discovery switch. A platform without the media server still gets the commands (the Pi then
  uses its own videos).
- The old copy tool `scripts/pup/topper_media.py` (rsync to the Pi, re-encoding) is removed: the tests of the download and
  of the media list are the platform's (`tests/test_pup_remote.py` there).

## Testing without a Pi

On Linux or macOS with mpv, beside the game (with `[remote] enabled=true`), the topper in a window:

```bash
python ../MPF-Godot-Packaging/mpf_godot/pup_remote/topper/topper.py --window --media /tmp/topper-media
```
