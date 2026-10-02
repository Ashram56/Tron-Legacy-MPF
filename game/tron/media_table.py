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


class DeffInfo:
    __slots__ = ("id", "name", "seconds", "sounds", "tubes", "leffs")

    def __init__(self, deff_id, name):
        self.id, self.name = deff_id, name
        self.seconds = 0.0
        self.sounds = []        # (offset s, call)
        self.tubes = []         # (offset s, tube show)
        self.leffs = []         # lamp-matrix effects started with the deff


def load(assets_dir):
    pkg = os.path.join(assets_dir, "mpf_package")
    table = {}
    for path in glob.glob(os.path.join(pkg, "media", "dmd", "deff_*", "timing.json")):
        folder = os.path.basename(os.path.dirname(path))
        deff_id = int(folder.split("_")[1])
        info = table.setdefault(deff_id, DeffInfo(deff_id, folder))
        with open(path) as f:
            data = json.load(f)
        info.seconds = float(data.get("run_seconds") or 0)
        info.sounds = [(s["t_ms"] / 1000, int(s["call"], 16)) for s in data.get("sounds", [])]
        info.tubes = [(t["t_ms"] / 1000, int(t["leff"])) for t in data.get("light_effects", [])
                      if str(t.get("from_deff", deff_id)) == str(deff_id)]
    with open(os.path.join(pkg, "lamp_effects.csv")) as f:
        for row in csv.DictReader(f):
            for m in re.finditer(r"effect (\d+) \(deff_", row["started_by"]):
                deff_id = int(m.group(1))
                table.setdefault(deff_id, DeffInfo(deff_id, "deff_%03d" % deff_id)).leffs.append(int(row["leff"]))
    return table
