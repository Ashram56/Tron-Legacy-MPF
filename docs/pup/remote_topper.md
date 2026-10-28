# Remote topper: the topper videos on a Raspberry Pi

The PuP Pack's topper videos (PuP screens 13 and 14) can play on a small screen of their own, driven by a Raspberry Pi in
the topper, instead of in a window on the cabinet's computer. The game sends the Pi short commands over the network; the
videos are on the Pi's SD card. The cabinet keeps all the sound.

The server, PinUP Player's screen rules and the Pi's agent and installer are the **platform's**, shared by every game:
[MPF-Godot-Packaging `platforms/pup-remote-topper.md`](https://github.com/Ashram56/MPF-Godot-Packaging/blob/main/platforms/pup-remote-topper.md)
(what you need, Pi set-up, settings, protocol, how to check). This page is Tron's part. Not tested on a real Pi yet.

## Setting it up

1. **On the Pi** (Raspberry Pi OS Lite, over SSH), run the platform's installer:

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

3. **Copy the topper videos to the Pi**:

   ```bash
   python scripts/pup/topper_media.py --push <user>@<the Pi's name>.local
   ```

   It takes the topper's playlists from the PuP Pack (its default backgrounds and every trigger on screens 13 and 14),
   copies the videos as they are into `pup_media/topper/` and sends them to `~/pup-topper/media` on the Pi (rsync). A
   video the Pi's decoder can't play (not H.264, above 1920x1080 or 30 fps, 10-bit or 4:4:4) is re-encoded first, and the
   run lists which and why. Run it again after a pack update.

4. **Start the game.** The Pi finds it by itself (broadcast on UDP port 5052); the game's log says
   `remote PuP display 'topper' connected`.

## Tron's side in the code

- `game/tron_pup/mode.py` hands every PuP command to the platform's `RemoteServer` as well as to Godot, so the topper plays
  whether or not the cabinet has a topper window; `pupfiles.load_screens/load_playlists` read the pack's `screens.pup` and
  `playlists.pup` for it; `game/pup.cfg` `[remote]` holds the port, listen address and discovery switch.
- `scripts/pup/topper_media.py` (and its test, `tests/test_pup_remote.py`) is the game's media tool.

## Testing without a Pi

On Linux or macOS with mpv, beside the game (with `[remote] enabled=true`):

```bash
python scripts/pup/topper_media.py
python ../MPF-Godot-Packaging/mpf_godot/pup_remote/topper/topper.py --window --media pup_media/topper
```
