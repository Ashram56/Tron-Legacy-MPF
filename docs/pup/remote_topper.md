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

3. **The videos come from the game.** Nothing to copy or run on the cabinet: the game serves the topper's videos (the
   playlists of its PuP screens 13 and 14: default backgrounds and every trigger), read in place from the PuP Pack, over HTTP on
   `[remote] media_port` (5053), and the Pi downloads what is new at each connection (platforms/pup-remote-topper.md,
   "Videos"). The same switch, `remote.enabled`, is in the bundle's settings (`scripts/package/settings.json`).

4. **Start the game.** The Pi finds it by itself (broadcast on UDP port 5052); the game's log says
   `remote PuP display 'topper' connected`.

## Tron's side in the code

- `game/tron_pup/mode.py` hands every PuP command to the platform's `RemoteServer` as well as to Godot, so the topper plays
  whether or not the cabinet has a topper window; `pupfiles.load_screens/load_playlists` read the pack's `screens.pup` and
  `playlists.pup` for it, and the platform's `media.topper_media` lists the videos to serve; `game/pup.cfg` `[remote]` holds the
  ports, listen address and discovery switch. `scripts/pup/topper_media.py` (copy and re-encode on the cabinet) is gone:
  a video the Pi's decoder cannot play would be a bundle add-on made once at build time. `tests/test_pup_remote.py` checks the
  settings option.

## Testing without a Pi

On Linux or macOS with mpv, beside the game (with `[remote] enabled=true`):

```bash
python ../MPF-Godot-Packaging/mpf_godot/pup_remote/topper/topper.py --window --media /tmp/topper-media
```

The videos are downloaded from the running game into that folder.
