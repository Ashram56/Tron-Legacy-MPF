"""What each ROM display effect (deff) starts, read from the asset package.

- media/dmd/deff_NNN_*/timing.json: run length, sounds and ramp tube shows with their offsets
  (observed in emulation).
- lamp_effects.csv "started_by": lamp-matrix effects a deff starts ("effect N (deff_N_...)").
"""
import csv
import glob
import json
import os
import re

TICK = 0.01626                                     # seconds per ROM tick (os_layer.TICK)


class DeffInfo:
    __slots__ = ("id", "name", "seconds", "sounds", "tubes", "leffs")

    def __init__(self, deff_id, name):
        self.id, self.name = deff_id, name
        self.seconds = 0.0
        self.sounds = []        # (offset s, call)
        self.tubes = []         # (offset s, tube show)
        self.leffs = []         # lamp-matrix effects started with the deff


# Foreground deff lengths read from the ROM code instead of timing.json (ticks of 16.26 ms), measured by running the
# deff routine in assets/tools/deff_unicorn.py: the tick of its last task_sleep. deff 140 [0x0102faec]: 67 + 21 + 35
# frame loops and the final hold end at tick 324 (5.27 s; timing.json says 5.295 s). Deff 112 [0x0100d108], run with
# the caller's parameters injected (assets/tools/os_deff_runs.py --set, parameters 1, 2 and 4 alike): its body ends at
# tick 246 (4.00 s; timing.json says 251 ticks).
CODE_TICKS = {140: 324, 112: 246}


def load(assets_dir):
    pkg = os.path.join(assets_dir, "mpf_package")
    table = {}
    for path in glob.glob(os.path.join(pkg, "media", "dmd", "deff_*", "timing.json")):
        folder = os.path.basename(os.path.dirname(path))
        deff_id = int(folder.split("_")[1])
        info = table.setdefault(deff_id, DeffInfo(deff_id, folder))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        info.seconds = float(data.get("run_seconds") or 0)
        info.sounds = [(s["t_ms"] / 1000, int(s["call"], 16)) for s in data.get("sounds", [])]
        info.tubes = [(t["t_ms"] / 1000, int(t["leff"])) for t in data.get("light_effects", [])
                      if str(t.get("from_deff", deff_id)) == str(deff_id)]
    for deff_id, ticks in CODE_TICKS.items():
        if deff_id in table:
            table[deff_id].seconds = ticks * TICK
    with open(os.path.join(pkg, "lamp_effects.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for m in re.finditer(r"effect (\d+) \(deff_", row["started_by"]):
                deff_id = int(m.group(1))
                table.setdefault(deff_id, DeffInfo(deff_id, "deff_%03d" % deff_id)).leffs.append(int(row["leff"]))
    return table
