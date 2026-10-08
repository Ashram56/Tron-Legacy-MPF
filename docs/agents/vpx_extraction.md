# Agent B: VPX table extraction (MPF Monitor layout)

Game agnostic. From a Visual Pinball X table (`.vpx`), produce what MPF Monitor needs (the playfield picture
and every switch, lamp and flasher placed on it, named as the MPF machine config names them) and the table's
script (which the [VPX bridge agent](vpx_bridge.md) starts from). Tron Legacy is the worked example. Labels:
**verified** = done on a real table, **unverified** = reasoned, not run.

Part of the [master plan](README.md). Keep this file current: fold in anything a later table teaches.

## 1. Inputs and outputs

| In | Out (in one output folder) |
|---|---|
| The `.vpx` (never modified) | `playfield.png`, `script.vbs`, `images/`, `items.json`, `switches_all.csv`, `lights_all.csv` (every candidate) |
| The MPF config with device numbers (the asset repo's `mpf_package/config/switches.yaml`, `lights.yaml`, `coils.yaml`, or the game's) | `switches.csv`, `lights.csv` (numbered), `monitor.yaml`, `overlay.png`, `overlay_small.png` |

Deliver into the game repo: `game/monitor/playfield.jpg` (or `.png`) and `game/monitor/monitor.yaml`.

## 2. Getting at the table

- **Tables are big** (150-300 MB), too big to attach in chat. Options, in order of ease:
  1. The owner puts it in the project's files (Tron: `/mnt/project-files/Tron Legacy (Stern 2011) VPW Mod v1.1.vpx`)
     or gives a public download link; work in the cloud container. (verified)
  2. **Remote Control** on the owner's PC (`start_rc_session` on a folder they choose): the `.vpx` never
     leaves their machine. (verified) The device session reports back by cross-session message; its outputs
     stay on their disk and **do not appear in `/mnt/project-files`**: ask it to copy the small outputs (CSV,
     YAML, scripts, a downscaled overlay) into the project, or say they exist only on the PC. Put the whole
     brief in `instructions`, the device can't read the project's files. The device can go offline; the
     session waits, so don't start a second one.
- **Windows** (partly unverified): `py` or `python` rather than `python3`; install with
  `py -m pip install --user olefile pillow`; the scripts already write CSVs with `newline=""` and UTF-8 (the
  default cp1252 codec broke on some names and gave blank rows).
- **Private repos from the device**: `git clone` and web fetch return 404 without credentials there. Check
  `git` / `gh auth status` or a local clone first, or do the repo work in a cloud thread (`list_repos`,
  `add_repo`). If you fall back to a local copy, say which folder (owners can have several).

## 3. Run it

The tools are in this repo (`olefile` and `pillow`: `python scripts/setup.py --vpx`):

```
python scripts/vpx_extract.py TABLE.vpx OUT                       # any VPX 10.x table
python scripts/vpx_map.py OUT --names <switches.yaml> <lights.yaml> <coils.yaml> --mech <NUMBER:OBJECT,...>
```

Then **open `overlay_small.png` and check that the markers sit on the inserts and targets** before calling it
done. It is the only cheap check of the coordinates.

Tron (verified 2026-10-08 on the VPW Mod v1.1 table, the same one the owner's first run used):

```
python scripts/vpx_extract.py "Tron Legacy (Stern 2011) VPW Mod v1.1.vpx" out
python scripts/vpx_map.py out --names assets/mpf_package/config/{switches,lights,coils}.yaml \
    --mech 52:motorbank,53:motorbank,54:recognizer,55:recognizer,56:recognizer,22:ballrelease
```

### Checking a run (Tron values)

- Bounds 0, 0, 952, 2115; playfield `Tron_Playfield` 2048x4096 (GameData IMAG); 207 image streams (2 legacy
  BITS, not decoded); 1,032 items; `script.vbs` 4,913 lines.
- `switches_all.csv` 308 rows, `lights_all.csv` 380.
- `switches.csv` 44 switches: 1-4, 7, 8, 11-14, 18-32, 34-39, 41, 43, 44, 46, 48-56.
- `lights.csv` 72 rows: 64 lamps (1-66 without 41 and 44, which have no object; 65 and 66 are `l01`/`l02`
  below the playfield, the start and tournament button lamps) and 8 flashers (solenoids 17, 18, 21, 26, 27, 29, 31, 32).
- First rows: `1,s_tron_t,sw01,Wall,81.0,1140.1,0.0851,0.5391,drop target` and
  `1,l_tron_n,l1,lamp,Light,180.0,970.5,0.189,0.4589,also: l1a`.
- With `--names`, every device gets its config name.

Transformers Pro (verified 2026-10-08 on `Transformers Pro (Stern 2011) v.2.4.vpx`, VR-Hybrid mod, ROM
`tf_180`; outputs in Ashram56/Transformers-MPF `docs/vpx/`):

```
python scripts/vpx_extract.py "Transformers Pro (Stern 2011) v.2.4.vpx" out
python scripts/vpx_map.py out --names rom/mpf_package/config/{switches,lights,coils}.yaml --mech 43:opr,44:opr
```

- With the ROM extraction's config (`rom/mpf_package/config/` in the game repo) every placed device is named;
  the ROM confirms 15/16 are the tournament/start buttons, lamps 1/2 their lamps, lamp 56 unused, 43/44
  Optimus Prime up/down. The ROM's "slingshot left" flasher (26) is the table's right-side dome.
- Bounds 0, 0, 952, 2164; playfield `pf` 3608x8192 (GameData IMAG); 386 images; 1,106 items; 31 collections;
  `script.vbs` 4,891 lines; `switches_all.csv` 529 rows, `lights_all.csv` 251.
- 42 switches: 1-8, 10-14, 18-32, 34, 35, 37-41, 43-46, 49-51 (trough 18-21 cvpmTrough at `BallRelease`,
  Megatron lock 38-41 at `KickerMegaTron`, saucer 3, VPW standups 2/37/46/49/50, Optimus ramp 43/44 by `--mech`).
- 61 lamps (1-62 without 56; 1 and 2 below the playfield), 12 flashers (17-21, 23, 25-28, 31, 32; six Flupper domes).
- Before the collection filter, `vpmMapLights` turned 90 GI and flasher lights (TimerInterval 100) into a lamp 100. The committed `game/monitor/monitor.yaml` came from this
  pipeline: 116 devices match it at the same position (median difference 0); the rest were moved by hand.

## 4. The `.vpx` format (what `vpx_extract.py` relies on)

- An **OLE compound file**. Streams: `GameStg/GameData` (table record and script), `GameStg/GameItemN` (one per
  object, sort by N), `GameStg/ImageN` (one per texture); also `SoundN`, `FontN`, `CollectionN`.
- Each stream is **BIFF records**: `int32` length that counts the 4-byte tag, the tag, `length - 4` bytes of
  payload; stop when the length is under 4. **`CODE`** (the script, in GameData) is the exception: its length
  is 4, then the script's own `int32` length and that many bytes. Write it out byte for byte.
- **GameData**: bounds `LEFT`, `TOPX`, `RGHT`, `BOTM` (float32); `IMAG` the playfield image name.
- **Item stream**: first `int32` is the type. VPX 10.x: 0 Wall, 1 Flipper, 2 Timer, 3 Plunger, 4 Textbox,
  5 Bumper, 6 Trigger, 7 Light, 8 Kicker, 9 Decal, 10 Gate, 11 Spinner, 12 Ramp, 13 Table, 14 LightCenter,
  15 DragPoint, 16 Collection, 17 DispReel, 18 LightSeq, 19 Primitive, 20 Flasher, 21 Rubber, 22 HitTarget.
  Records start at offset 4. Keep the first occurrence of each tag. **Drag points** (`DPNT` ... `ENDB`) are
  nested: their `VCEN` must not overwrite the item's own; an item with no `VCEN`/`VPOS` uses their average.
  Position: `VCEN` (most), `VPOS` (primitives, targets), `FLAX`/`FLAY` (flashers). `HTEV` = has hit event;
  `TMIN` = timer interval (the lamp number on `vpmMapLights` tables). Wrap field parsing in `try/except struct.error`.
- **Collection stream**: `NAME` then one `ITEM` per member (both UTF-16LE), `EVNT`, `SSNG`, `GREL`, `ENDB`.
  `items.json` lists them under `collections`. `vpmMapLights AllLamps` maps only that collection's members:
  GI bulbs and flasher lights also carry a TimerInterval (100 on Transformers) and must not become lamps.
- **Strings**: item `NAME` is length-prefixed **UTF-16LE**; image names, paths, `IMAG`, `SURF` are **ANSI**.
  Some ANSI records hold binary data or a bad length: return `""` unless the text is printable ASCII (one of
  the two bugs fixed on the first real run).
- **Images**: `NAME`, `PATH`, `WDTH`, `HGHT`, then a nested `JPEG` block whose `DATA` is the original file
  (PNG, JPG, WebP, sometimes HDR/EXR; pick the extension from the magic bytes). `BITS` is a legacy LZW
  bitmap, not decoded.
- **Coordinates**: `nx = (x-LEFT)/(RGHT-LEFT)`, `ny = (y-TOPX)/(BOTM-TOPX)`. The playfield image is stretched
  over exactly these bounds, so they map straight onto it, no flip or offset (verified, 2048x4096).
- **Playfield image**: `--image NAME`, else GameData `IMAG`, else the largest image named "playfield" or
  "pf*". Modern tables may draw the playfield as a Primitive mesh texture and leave `IMAG` empty or a
  placeholder: then pass `--image` and say which you chose.

## 5. Mapping objects to numbers (`vpx_map.py`)

VPX object names are arbitrary; the numbers live in the table script. **Read `script.vbs` first** and check
that the patterns it uses are the ones `vpx_map.py` reads (comments are stripped before matching):

| Device | Script pattern | Result |
|---|---|---|
| Switch | `Sub <obj>_Hit / _Spin / _Slingshot ... End Sub` (one-line subs too) containing `Controller.Switch(n) = 1`, `PulseSw n`, or VPW's `STHit n` / `DTHit n` | obj → n (mod 100) |
| VPW targets | `(new StandupTarget)(obj, prim, n, ...)`, `(new DropTarget)(obj, objb, prim, n, ...)` | obj → n mod 100 |
| Drop targets | `.InitDrop Array(objs), Array(nums)` | zipped pairwise |
| Kickers, trough | `Set X = New cvpmBallStack` ... `.InitSw a,b,...` ... `.InitKick obj` | first slot is the entry switch, zeros dropped; one number left = the kick object; several = the trough, stacked at the kick object (`ny` + 0.006 per ball) |
| Saucer | `.InitSaucer obj, n, ...` | obj → n |
| Trough (cvpmTrough) | `Set X = New cvpmTrough` ... `.InitSwitches Array(a,b,...)` ... `.InitExit obj` | every number, stacked at the exit object |
| Lamps | `Lampz.MassAssign(n) = obj` (several objects per lamp) | main object `l<n>`/`l0<n>`, else the first Light; others in `note` |
| Lamps (older tables) | `vpmMapLights <collection>` | the Light's TimerInterval is its lamp number, members of that collection only |
| Flashers | `ModLampz.MassAssign(n) = obj` | **solenoid** numbers |
| Flashers | `SolModCallback(n)` / `SolCallback(n)` = `"vpmFlasher obj,"` (or `Array(...)`) | solenoid n → obj |
| Flupper domes | `SolModCallback(n) = "<sub>"`, the sub calls `ModFlashFlasher k` / `FlashFlasher k` | solenoid n → `Flasherlight<k>` (else `Flasherflash<k>`, `Flasherbase<k>`) |

Not handled yet (add them when a table uses them): `SolCallback(n)` objects for coils,
`Controller.Switch(n)` set from a sub named after another object or from a timer (Transformers' Optimus ramp
43/44: use `--mech`), GI strings (`GiCallback`; usually leave out). Script comments next to `SolModCallback`
can be wrong (Transformers' "Slingshot (Left)" dome sits on the right): trust the object, say so.

**Mechanism switches have no object of their own**: pass them with `--mech NUMBER:OBJECT`, per table. Tron:
52/53 (3-bank up/down) at `motorbank`, 54-56 (Recognizer position) at `recognizer`, 22 (trough jam) at
`ballrelease`; each only if still unmapped.

Expected gaps: the **trough** has no playfield objects (simulated ball stacks), so its switches sit stacked
at the ball release; **cabinet buttons** (start, flippers, launch) are not on the playfield; some **lamp
objects sit below the playfield** (apron, buttons): flag them; some manual lamp numbers have no object
(`vpx_map.py` prints them). Cross-check numbers against the manual's matrix where you can.

## 6. MPF Monitor's `monitor.yaml`

- Verified on MPF Monitor 1.0.0 (the file it saves, `game/monitor/monitor.yaml`): **singular** section keys
  `switch:`, `light:`, `coil:` (flashers go here), `flipper:`, `autofire:`, `ball_device:`, each device
  `x`/`y` as fractions of the playfield picture, optional `size`; top-level `playfield:`, `device_size`,
  `device_alpha`, `device_outline`. MPF Monitor rewrites the file when a spot is dragged.
- **Names must be the machine config's** (`switches:`, `lights:`, `coils:` names), never VPX names:
  `--names` joins on the number. Without a config, placeholders `s_NN_<vpx>`, `l_NN_<vpx>`, `f_NN_<vpx>`
  carry the number for the recreation agent to rename.
- Devices with no VPX object (flippers, autofires, ball devices, coils such as the drop target reset,
  motors, coin door, ramp tubes) are added by hand near their parts (Tron did this once; they keep their
  place in the committed file).
- Tron's monitor runs with `python scripts/run.py --monitor` (docs/hardware.md). `scripts/gen_monitor.py`
  draws a labelled grid instead and overwrites the layout: only for a game without a table.

## 7. Report

Paths, counts, the playfield image name and size, the missing lamp numbers, which `--mech` placements you
made, and the overlay verdict. List what needs the owner's eye as a short numbered list.

## History

- 2026-10-01: first written blind in a cloud session, debugged on the owner's PC by Remote Control
  (`D:\Documents\Antigravity\Tron VPX`, scripts `vpx_extract.py` 9,298 bytes and `tron_map.py` 7,635 bytes).
  Two fixes on the real run: the ANSI string guard and the CSV writing. The owner supplied the resulting
  layout; it became `game/monitor/` (2026-10-03).
- 2026-10-08: rebuilt into this repo from those notes as `scripts/vpx_extract.py` and the generic
  `scripts/vpx_map.py` (Tron's hand-placed mechanisms became `--mech`, names from the config by number);
  reproduces the first run's counts exactly. `tests/test_vpx_extract.py`.
- 2026-10-08: second table, Transformers Pro v2.4 (cloud, from the project's files). Added collections to
  `items.json` and to `vpmMapLights`, cvpmTrough, `InitSaucer`, VPW `StandupTarget`/`DropTarget`/`STHit`/`DTHit`,
  and `SolModCallback` flashers (vpmFlasher and Flupper domes). Not re-run on the Tron table (not in that
  project): Tron uses `Lampz`/`ModLampz`, so only a `vpmFlasher` callback in its script could add rows.

Last updated 2026-10-08.
