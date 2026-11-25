# Boards inventory (step zero, STRICT RULE: DECOMPILE EVERYTHING)

States: `complet`, `partiel`, `absent`. The strict check fails while a row is not `complet`. Started 2026-11-25
from the existing decompile; states are what is evidenced today, to be confirmed in the decompile.

| Board | CPU / MCU | ROM file(s) | Decompile state | Where (decompile, notes) | Open |
|---|---|---|---|---|---|
| Main CPU board (rules, OS, DMD drawing, sound mixing) | ARM7 / AT91 | trn_174h (LE), trn_17402 (Pro) | partiel | assets `code/tron_game_decompiled_v2.c` (LE), `tron_pro_decompiled.c`; functions named where the rules use them | many routines unnamed; dead-code list and per-deff draw routines not complete |
| DMD output (FPGA / page registers on the CPU board) | none of its own (FPGA, no firmware found) | n/a | partiel | page registers 0x01100020/22, DMD pages 0x01080000 (assets `io/bus/`) | confirm there is no DMD firmware to decompile |
| Sound (sample streaming on the CPU board) | none of its own (FIQ routine 0x2b600 to 0x2d8b4) | n/a | partiel | `snd_play 0x2c8f4` etc. | confirm no separate sound CPU |
| Power driver / I/O board, ramp tube RGB board | to be confirmed | n/a | absent | `io/` tables; tube wiring open (docs/hardware.md) | check whether any board carries a MCU with firmware |
