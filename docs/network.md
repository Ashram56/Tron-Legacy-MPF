# Network (Wi-Fi) from the service menu

UTILITIES > **GO TO NETWORK MENU** joins the cabinet to a Wi-Fi network with the coin-door buttons, for
[Scorbit](scorbit.md) or anything else that needs the network. On Linux it drives NetworkManager (`nmcli`)
when it runs (most desktop Linux), else wpa_supplicant (`wpa_cli`), as on the Jetson image
([jetson_image.md](jetson_image.md): systemd-networkd and `wpa_supplicant@wlan0`). Elsewhere (Windows,
macOS, a Linux with neither) the items say `NOT AVAILABLE` and the network is set up with the system's own
tools. `TRON_WIFI=off` hides the network from the game; `TRON_WIFI=nmcli` or `TRON_WIFI=wpa` chooses.

| Item | What it does |
|---|---|
| WI-FI STATUS | Connected or not, the network's name, the address and the signal, read again every 2 s. |
| SCAN WI-FI NETWORKS | The networks in range, the connected one first, then the strongest. MINUS / PLUS choose one, SELECT joins it: an open one at once, a secured one after its password. A password left empty uses the one saved for that network. |
| JOIN HIDDEN NETWORK | A network that does not announce its name: type the name, then the password. |
| FORGET WI-FI NETWORK | Disconnects the connected network and deletes its saved password. |

After a join the result shows (`CONNECTED`, `WRONG PASSWORD`, `NETWORK NOT FOUND`, `NOT AUTHORIZED`,
`TIMED OUT`, or NetworkManager's own message); SELECT goes back to the menu.

## Typing a password

- MINUS / PLUS change the character (hold them to run through), SELECT adds it, BACK deletes the last one
  (BACK with nothing typed leaves).
- The flipper buttons jump to the previous / next kind of character: lower case, upper case, numbers,
  symbols, and END. SELECT on END finishes.
- The ROM's fonts have capitals only, so a lower case letter shows as a small capital and the line under the
  text names the kind being chosen (`LOWER CASE`, `UPPER CASE`, `NUMBER`, `SYMBOL`, or the symbol's name
  when the font has no picture of it, such as `UNDERSCORE`).

## Permissions

**wpa_supplicant** (the Jetson image): `wpa_cli` talks to the control socket in `/run/wpa_supplicant/`,
which the image opens to the `sudo` group (`ctrl_interface=DIR=/run/wpa_supplicant GROUP=sudo`); its user
`jetson` is in that group. `update_config=1` lets a joined network be saved to
`/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`. The game hashes the password into the network's PSK
itself, as `wpa_passphrase` does, so neither the command line nor the file holds the password. A network of
the same name is replaced; a join that fails is removed again.

**NetworkManager**: `nmcli` needs the right to change the system's network. A desktop session has it. When
the game runs from systemd, ssh or Docker, NetworkManager answers `NOT AUTHORIZED`; allow the game's user
with a polkit rule, for example `/etc/polkit-1/rules.d/50-tron-network.rules`:

```js
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 && subject.user == "tron") {
        return polkit.Result.YES;
    }
});
```

With NetworkManager the password goes to `nmcli` on its command line, so it shows in the process list while
`nmcli` runs (a few seconds at most); NetworkManager keeps it in its own connection file, readable by root
only. The game never stores a password.

## For developers

`game/tron/network.py` (the `nmcli` and `wpa_cli` backends and the worker thread each call runs in) and the screens in
`game/tron/service.py` (`WifiStatusScreen`, `WifiScanScreen`, `TextEntryScreen`, `WifiConnectScreen`,
`WifiForgetScreen`); `tests/test_network.py` uses a fake backend and canned `nmcli` and `wpa_cli` output.
Neither backend has been run against a real Wi-Fi card yet: check the menu on the cabinet.
