# ROM extraction feedback from the Tron MPF build (record)

Written in 2026-10 for the agent that decompiled Tron Legacy LE v1.74 (`trn_174h`) and produced
`Ashram56/Tron-Legacy-LE-ROM-Decryption`. The MPF recreation (`Ashram56/Tron-Legacy-MPF`) consumed it as a
submodule. This is the record of what the build had to reverse-engineer again or guess. Facts are as of the submodule pin `e712f62` (2026-10-04).

**This is a dated record, not instructions.** What worked and the deliverable list for the next SAM game
were folded into the ROM extraction agent's own file, [`AGENTS.md` section 14](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption/blob/main/AGENTS.md#14-deliverables-checklist-for-the-next-sam-game),
which is the one to read and update. Every gap below was then extracted into the asset repo's `rom_data/`
(its `README.md` maps each gap to its file and lists what is still open).

## 1. Missing data the build had to recover or guess

Ordered by impact. "Recovered" means rebuilt from code or captures, at real cost; "guessed" means still unverified.

| # | Missing | What the build did | Status |
|---|---|---|---|
| 1 | **Font table** (RAM 0x36f48: char ranges, per-glyph x/y offsets, height, spacing) | Fonts = image groups from image 218; offsets and spacing fitted to the captures (`scripts/gen_fonts.py`) | Recovered; 161/198 static text draws pixel-exact, rest not on screen in captures |
| 2 | **Deff text layout**: per deff, every draw call (font or font list, flags, x, baseline y, fit width), its format string, and **where each argument comes from** (RAM address/meaning, order) | Parsed out of the decompiled C two call levels deep (`scripts/rom_layout.py`); argument order and live RAM values fixed bug by bug | Recovered; some font lists guessed (`rom_layout.py` "guess") |
| 3 | **Screen selection** per deff (which screen by argument or mode phase) | Hand table `rom_layout.SCREENS` | Recovered by hand |
| 4 | **Coil table** (0xe0c00: pulse widths, hold, `desc_flags` in `io/coils.csv` undecoded) | Starting values per coil class in `hw_proc.yaml` | **Guessed** (needed for real hardware) |
| 5 | **Lamp groups** (table 0x040e3acc) | Named from `lights.yaml` tags + `lamps.csv` | Partly guessed |
| 6 | **Lamp-matrix leffs** (table 0x040e23e4, 172 effects) are only captured shows; code-drawn ones are absent | Rebuilt from code: leffs 13, 14, 45, 47, 76, 78, 94, 99, 132, 136, 157, 159 | Recovered for those |
| 7 | **Randomised deffs** captured once: deff 105 (mystery award, award id 0 only), deff 108 (4 clips) | Award reel logic rebuilt from 0x0100e8bc (decoys, slot, scroll/blink lengths, sounds) | Recovered; you have since added award parts |
| 8 | Captures with **frozen status panel** (score 00) and **two runs in one capture** (deff 115 sounds twice) | Live panel drawn over; run length from ROM | Recovered |
| 9 | **Pricing tables**: only USA 10 | Others unsupported | Missing |
| 10 | Service texts msg 0x113/0x114; audits 11, 13, 72 formulas; adj 25 reader | Inferred | Guessed |
| 11 | Coin door and aux-bus facts: tube strobe 0x10 left or right (your console vs PinMAME disagree); GI latch bit polarity at power-up; DED 22/23 Minus/Plus | Followed PinMAME's input port; tubes off on P-ROC until checked | Unverified |
| 12 | Multi-player behaviour, rare late states (Sea of Simulation stages 4-8, match odds, slam tilt) | Read from code only | Untraced |

## 2. Package defects found (fix at the source)

- Generated MPF YAML has no `#config_version=6` header (MPF refuses it); the build adds it.
- `event_map.csv` `mode_by_code_location` is often wrong.
- **Stale audit notes**: `rules/work/asset_audit.md` (W3, W5) and `developer_guide.md` section 6 still
  report two defects the package has since fixed (checked at `e712f62`): the duplicate keys in
  `switches.yaml` / `lights.yaml` (none left) and the 17 unexported audio streams (samples 0x09-0x14,
  0x16-0x19 and music 0x44d are now in `media/sounds/` and `sounds.yaml`). Mark them resolved so the
  next agent does not work around problems that are gone.
- Package `leff_NNN` are ramp **tube shows**, not lamp-matrix leffs; naming them `tube_show_NNN` would avoid the mix-up.
- Unverified in MPF: shaker gating by settings, music looping, `settings.yaml` defaults.
