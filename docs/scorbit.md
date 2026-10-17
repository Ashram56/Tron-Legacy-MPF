# Scorbit

[Scorbit](https://scorbit.io) shows a game's live scores in its app, lets players claim their scores, and
keeps leaderboards. This game talks to it through the
[Scorbit SDK](https://github.com/scorbit-io/scorbit_sdk) (version 2.0.4): it sends the scores, the active
player, the ball and the modes played and completed while a game is played, and it can pair the cabinet with a venue
from the service menu. Scorbit is an addition: the ROM has no network (docs/rom_differences.md).

The SDK's library is built for Linux only (x86_64 and arm64: a Linux PC, the Jetson cabinet). On Windows and
macOS the game runs without Scorbit and the service menu says so.

## 1. Credentials from Scorbit

Scorbit gives each game maker a **provider name**, an **encrypted provider key**, and a **machine id** for
the game (support@scorbit.io). None of them is in this repository. Put them in `game/scorbit.local.cfg`
(git-ignored), which is read after the public `game/scorbit.cfg`:

```ini
[scorbit]
provider=yourprovider
machine_id=1234
encrypted_key=AbCd...==
hostname=production
```

`hostname=staging` uses Scorbit's test server (the service menu can switch it too). `serial_number` and
`uuid` are optional; without a UUID the SDK makes one from the network card's MAC address. The SDK keeps
the cabinet's own device key in `game/data/scorbit_device_key.txt` (owner-only, git-ignored): keep that file
when you reinstall, or the cabinet registers as a new device.

The game checks the encrypted key before it starts the SDK: the SDK library stops the whole program on a key
whose text is cut short, so a key that is not valid base64 shows `KEY IS NOT BASE64` instead.

**The private key and the encrypted key.** Scorbit's private key for a provider is 64 hex characters. The
SDK does not take it as is: `encrypted_key` is that key encrypted with the provider name and a secret built
into Scorbit's ready-made library (the SDK's `encrypt_tool`, which Scorbit runs or supplies; one built from
the public source lacks the secret, so its output does not work). Ask Scorbit support for the encrypted form
(about 104 characters of letters, digits, `+` and `/`, often ending in `=`) when you only have a hex key; the game shows `KEY NOT ENCRYPTED` if the hex key is put in `encrypted_key`.
Neither form goes in git: `scorbit.local.cfg` is git-ignored, so the repository holds only the empty
`scorbit.cfg`. Check with `git status` that the file is not listed before you commit, and keep a copy of it
outside the repository (a reinstall keeps it, as it keeps every untracked file).

**Who can read it on the cabinet.** The game makes `scorbit.local.cfg` readable by its own user only (mode
600, as ssh keeps its keys) each time it starts. Anyone with root, or who logs in as the game's user, can
still read it, and so can anyone who takes the storage out: a program that uses a key must be able to read
it. What limits the harm: the key is encrypted with a secret inside Scorbit's library, so it only works
through the SDK; the SDK signs its requests to Scorbit with it (it is not your Scorbit login); if it leaks, ask Scorbit to revoke
it and issue a new one. To go further: no shared login on the cabinet (change the default `jetson`
password, ssh by key only), and an encrypted disk if the storage could be taken.

## 2. Install the SDK

```
python3 scripts/setup.py --scorbit
```

or, with the one-line Linux installer, `scripts/install/install_prereqs_linux.sh -- --scorbit`. This puts
the `scorbit` Python package in `.venv/` and the SDK's library in `tools/scorbit/lib/`, where the game finds
it (or set `SCORBIT_SDK_PATH` to the folder of another copy, such as `/opt/scorbit/lib` from Scorbit's `.deb`).
Nothing else changes: the game starts Scorbit when the SDK and the credentials are both there.
`TRON_SCORBIT=0` turns it off for one run.

## 3. Service menu

The cabinet needs a network first: UTILITIES > GO TO NETWORK MENU ([network.md](network.md)). Then
UTILITIES > **GO TO SCORBIT MENU**:

| Item | What it does |
|---|---|
| SCORBIT STATUS | Why Scorbit is off (`OFF`, `SDK NOT INSTALLED`, `NOT CONFIGURED`, a key problem), or its state: `CONNECTING`, `NOT PAIRED`, `PAIRED`, `AUTHENTICATION FAILED` (the credentials are wrong); the machine id, the server and the cabinet's Scorbit UUID. |
| SCORBIT PAIRING | Asks Scorbit for a 6-character pairing code and shows it: the venue owner enters it in the Scorbit app to add the cabinet to the venue. SELECT asks for a new code. Shows `PAIRED` once Scorbit says so. |
| SCORBIT ADJUSTMENTS | SCORBIT ON / OFF (factory ON: it only runs once installed and configured) and SCORBIT SERVER, PRODUCTION / STAGING (factory: `hostname` in the config). Kept across power cycles; a change restarts the link. RESET FACTORY SETTINGS sets both back. |
| SCORBIT UNPAIR | SELECT asks Scorbit to remove the cabinet from its venue. |

## 4. What is sent

While a game runs, every half second when something changed: each player's score, the active player, the
ball (1-9), and the modes. Scorbit keeps them in the game's history, so a player sees which modes each game
played and completed. The game start and end are sent when MPF starts and ends the game.

**Modes played** (sent while they run): `MB:Disc Multiball`, `MB:End of Line`, `MB:Quorra Multiball`,
`MB:Light Cycle Multiball`, `MB:Portal Multiball`, `NA:Sea of Simulation`, `NA:CLU Hurry-Up`,
`NA:GEM Hurry-Up`, `NA:ZUSE Fast Scoring` and `NA:Find Flynn`.

**Modes completed** (one event each time; Scorbit's achievements read them):

| Mode | Completed when |
|---|---|
| `NA:Find Flynn` | Flynn is found |
| `NA:CLU Hurry-Up` | every CLU shot is made |
| `NA:GEM Hurry-Up` | a GEM award is collected |
| `NA:ZUSE Fast Scoring` | all four ZUSE targets are hit |
| `MB:Quorra Multiball`, `MB:Disc Multiball`, `MB:Light Cycle Multiball`, `MB:Portal Multiball` | a super jackpot |
| `NA:Recognizer` | five Recognizer hits light Disc Battle |
| `NA:TRON Targets` | the T, R and O awards have all been started |
| `NA:Sea of Simulation` | its last stage is won (its stages, which also collect items, do not count on their own) |

These are the moments the ROM counts as an item collected (the Find Flynn insert), plus Portal and Sea of
Simulation. Scorbit's completed modes (`set_mode_completed`) came after SDK 2.0.4: with 2.0.4 the modes
played are sent and the completions are skipped (the log says so once); a later SDK sends them with no
change to the game. When Scorbit asks for diagnostics, the newest MPF logs (`game/logs/`,
at most five) are uploaded. The cabinet does not take game starts or credits from the Scorbit app.

## 5. For developers

- `game/tron/scorbit.py`: the link (`os.scorbit`), the settings and the credential checks. The SDK's
  callbacks run in its threads and only store values; the MPF clock does the rest.
- `game/tron/service.py`: the SCORBIT menu (`GAME_MENUS`), `ScorbitStatusScreen`, `ScorbitPairScreen`,
  `ScorbitUnpairScreen`.
- `tests/test_network.py`: a fake SDK for the game flow, the screens and the settings; `TestScorbitSdk` runs
  a game with the real SDK when `setup.py --scorbit` installed it (no network needed).
- The pairing deeplink (a QR code on Scorbit's own displays) is about 230 characters: its QR code is larger
  than the 32 dots of the DMD, so the 6-character code is used instead.
