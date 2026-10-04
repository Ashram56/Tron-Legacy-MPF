"""Device numbers: the SAM number a device has on this machine, and its number in the ROM's own numbering.

The rules (lamps.py, the traces) count lamps and coils as the LE 1.74 ROM does, but an overlay can renumber a
device: the P-ROC writes SAM lamp 17 as "L17" (rom/proc_numbers*.yaml) and the Pro moves it to another lamp
(machine_pro.yaml). So the rules look a device's ROM number up by name in the asset package's tables
(game/config/rom/*.yaml), and the service menu shows the number the device has on this machine.
"""
import os
import re

_ROM = {}


def sam_number(device):
    """The device's SAM number on this machine: "1", "D9", "3", "17" (P-ROC's "S01", "SD9", "C03", "L17" read back)."""
    text = str(device.config.get("number", ""))
    m = re.fullmatch(r"(SD|S|C|L)(\d+)", text)
    if m:
        return ("D" if m.group(1) == "SD" else "") + str(int(m.group(2)))
    return text


def rom_numbers(machine, section):
    """{device name: number} of the switches, coils or lights in the ROM's own (LE) numbering, for devices with a
    plain SAM number (not the aux bus tubes, not the Pro's own flashers)."""
    path = os.path.join(machine.machine_path, "config", "rom", section + ".yaml")
    if path not in _ROM:
        from ruamel.yaml import YAML
        with open(path, encoding="utf-8") as f:
            data = (YAML(typ="safe").load(f) or {}).get(section) or {}
        _ROM[path] = {name: int(cfg["number"]) for name, cfg in data.items()
                      if cfg and str(cfg.get("number", "")).isdigit()}
    return _ROM[path]
