#!/usr/bin/env python3
"""Give the objects vpx_extract.py found their machine numbers, from the table script, and write an MPF Monitor layout.

    python scripts/vpx_map.py OUTDIR [--names config.yaml ...] [--mech 52:motorbank,22:ballrelease ...]

OUTDIR is vpx_extract.py's output. VPX object names are arbitrary; the switch, lamp and flasher numbers live in
script.vbs. This reads the patterns most PinMAME tables use (comments stripped first):

    switch     Sub <obj>_Hit / _Spin / _Slingshot ... Controller.Switch(n) = 1 or PulseSw n ... End Sub
    drops      .InitDrop Array(objs), Array(nums)                         (zipped pairwise)
    kickers    Set X = New cvpmBallStack ... .InitSw a,b,... ... .InitKick obj
               (first slot is the entry switch, zeros dropped; one number left = the kick object,
                several = the trough, stacked at the kick object)
    lamps      Lampz.MassAssign(n) = obj   (main object: l<n> / l0<n>, else the first Light)
               vpmMapLights <collection>   (the light's TimerInterval is its lamp number)
    flashers   ModLampz.MassAssign(n) = obj   (solenoid numbers)

A table that uses other patterns (cvpmTrough, Controller.Switch set from a sub named after something else) needs
them added here: read script.vbs first. Mechanism switches have no playfield object of their own; place them
with --mech NUMBER:OBJECT (only if the number is still unmapped).

--names reads MPF config files (switches:, lights:, coils:, flashers: with number:) and names each device by its number;
without it the names are placeholders s_NN_<vpx>, l_NN_<vpx>, f_NN_<vpx>. Writes switches.csv, lights.csv,
monitor.yaml (MPF Monitor's own format: singular section keys, x/y as fractions of the picture), overlay.png
and overlay_small.png. docs/agents/vpx_extraction.md has the whole procedure.
"""
import argparse
import csv
import json
import os
import re
import sys


def strip_comments(text):
    out = []
    for line in text.splitlines():
        q = False
        for i, ch in enumerate(line):
            if ch == '"':
                q = not q
            elif ch == "'" and not q:
                line = line[:i]
                break
        if re.match(r"\s*rem\s", line, re.I):
            line = ""
        out.append(line)
    return "\n".join(out)


def safe(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "x"


def read_names(paths):
    """{section: {number: name}} from MPF YAML (indented `name:` then `number:`), without a YAML library."""
    names = {"switches": {}, "lights": {}, "coils": {}, "flashers": {}}
    for path in paths:
        section = dev = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^(\w+):\s*$", line)
                if m:
                    section, dev = m.group(1), None
                    continue
                m = re.match(r"^  (\w+):\s*(#.*)?$", line)
                if m:
                    dev = m.group(1)
                    continue
                m = re.match(r"^    number:\s*['\"]?(-?\d+)['\"]?", line)
                if m and section in names and dev:
                    names[section].setdefault(int(m.group(1)), dev)
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("outdir")
    ap.add_argument("--names", nargs="*", default=[], help="MPF config files with switches/lights/coils numbers")
    ap.add_argument("--mech", default="",
                    help="NUMBER:OBJECT,... switches placed at an object (mechanisms, trough jam)")
    args = ap.parse_args(argv)
    d = args.outdir
    with open(os.path.join(d, "items.json"), encoding="utf-8") as f:
        items = json.load(f)["items"]
    by_name = {it["name"].lower(): it for it in items if it.get("name") and it.get("nx") is not None}
    with open(os.path.join(d, "script.vbs"), "rb") as f:
        script = strip_comments(f.read().decode("cp1252", errors="replace"))
    names = read_names(args.names)

    switches = {}                                   # number -> (object, note)

    def add_sw(n, obj, note=""):
        if n > 0 and obj.lower() in by_name and n not in switches:
            switches[n] = (obj.lower(), note)

    for m in re.finditer(r"^\s*Sub\s+(\w+?)_(Hit|Spin|Slingshot)\b(.*?)\bEnd\s+Sub", script, re.I | re.M | re.S):
        body = m.group(3)
        k = re.search(r"Controller\.Switch\s*\(\s*(\d+)\s*\)\s*=\s*(1|True)|PulseSw\s*\(?\s*(\d+)", body, re.I)
        if k:
            add_sw(int(k.group(1) or k.group(3)), m.group(1), m.group(2).lower())
    for m in re.finditer(r"\.InitDrop\s+Array\(([^)]*)\)\s*,\s*Array\(([^)]*)\)", script, re.I):
        objs = [o.strip() for o in m.group(1).split(",")]
        nums = [int(n) for n in re.findall(r"\d+", m.group(2))]
        for o, n in zip(objs, nums):
            add_sw(n, o, "drop target")
    stacks = list(re.finditer(r"Set\s+(\w+)\s*=\s*New\s+cvpmBallStack", script, re.I))
    for i, m in enumerate(stacks):
        seg = script[m.end():stacks[i + 1].start() if i + 1 < len(stacks) else len(script)]
        sw = re.search(r"\.InitSw\s+([\d,\s]+)", seg)
        kick = re.search(r"\.InitKick\s+(\w+)", seg)
        if not (sw and kick):
            continue
        nums = [int(n) for n in sw.group(1).split(",")[1:] if n.strip() and int(n) != 0]
        for k, n in enumerate(nums):
            slot = " slot {}".format(k + 1) if len(nums) > 1 else ""
            add_sw(n, kick.group(1), "ball stack {}{}".format(m.group(1), slot))
    for spec in filter(None, args.mech.split(",")):
        n, obj = spec.split(":")
        add_sw(int(n), obj.strip(), "mechanism (placed by hand)")

    lamps, flashers = {}, {}
    for pattern, table in ((r"(?<!Mod)Lampz\.MassAssign\s*\(\s*(\d+)\s*\)\s*=\s*(\w+)", lamps),
                           (r"ModLampz\.MassAssign\s*\(\s*(\d+)\s*\)\s*=\s*(\w+)", flashers)):
        for m in re.finditer(pattern, script, re.I):
            table.setdefault(int(m.group(1)), []).append(m.group(2).lower())
    if re.search(r"^\s*vpmMapLights\b", script, re.I | re.M):
        for it in by_name.values():
            if it["type"] == "Light" and it.get("timer_interval", 0) > 0:
                lamps.setdefault(it["timer_interval"], []).append(it["name"].lower())

    def main_obj(n, objs, prefix):
        objs = [o for o in objs if o in by_name]
        for o in objs:
            if re.fullmatch(r"{}0?{}".format(prefix, n), o):
                return o, objs
        for o in objs:
            if by_name[o]["type"] == "Light":
                return o, objs
        return (objs[0], objs) if objs else (None, objs)

    sw_rows, li_rows = [], []
    for n in sorted(switches):
        obj, note = switches[n]
        it = by_name[obj]
        mpf = names["switches"].get(n) or "s_{:02d}_{}".format(n, safe(it["name"]))
        sw_rows.append(dict(number=n, mpf_name=mpf, vpx=it["name"], type=it["type"], x=round(it["x"], 1),
                            y=round(it["y"], 1), nx=it["nx"], ny=it["ny"], note=note))
    # a ball stack's slots share one object: spread them along the table so they don't overlap
    for obj in {r["vpx"] for r in sw_rows}:
        same = [r for r in sw_rows if r["vpx"] == obj]
        for k, r in enumerate(same[1:], 1):
            r["ny"] = round(r["ny"] + 0.006 * k, 4)
    for kind, table, prefix, section in (("lamp", lamps, "l", "lights"), ("flasher", flashers, "f", "coils")):
        for n in sorted(table):
            obj, objs = main_obj(n, table[n], prefix)
            if not obj:
                continue
            it = by_name[obj]
            mpf = (names[section].get(n) or (names["flashers"].get(n) if kind == "flasher" else None)
                   or "{}_{:02d}_{}".format(prefix, n, safe(it["name"])))
            others = [o for o in objs if o != obj]
            li_rows.append(dict(number=n, mpf_name=mpf, vpx=it["name"], kind=kind, type=it["type"],
                                x=round(it["x"], 1), y=round(it["y"], 1), nx=it["nx"], ny=it["ny"],
                                note="also: " + " ".join(others) if others else ""))

    cols = ["number", "mpf_name", "vpx", "type", "x", "y", "nx", "ny", "note"]
    for fn, rows, c in (("switches.csv", sw_rows, cols), ("lights.csv", li_rows, cols[:3] + ["kind"] + cols[3:])):
        with open(os.path.join(d, fn), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=c, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    with open(os.path.join(d, "monitor.yaml"), "w", encoding="utf-8") as f:
        f.write("# MPF Monitor layout (x/y: fractions of playfield.png) from vpx_extract.py + vpx_map.py\n")
        for key, rows in (("coil", [r for r in li_rows if r["kind"] == "flasher"]),
                          ("light", [r for r in li_rows if r["kind"] == "lamp"]), ("switch", sw_rows)):
            if not rows:
                continue
            f.write(key + ":\n")
            for r in rows:
                f.write("  {}:   # {} {} ({})\n    x: {}\n    y: {}\n".format(
                    r["mpf_name"], key, r["number"], r["vpx"], r["nx"], r["ny"]))

    pf = os.path.join(d, "playfield.png")
    if os.path.exists(pf):
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(pf).convert("RGB")
        dr = ImageDraw.Draw(img)
        size = max(12, img.width // 90)
        try:
            font = ImageFont.truetype("arial.ttf", size)
        except OSError:
            font = ImageFont.load_default()
        r = max(5, img.width // 160)
        for rows, label, colour in ((sw_rows, "S", (0, 255, 255)),
                                    ([x for x in li_rows if x["kind"] == "lamp"], "L", (255, 230, 0)),
                                    ([x for x in li_rows if x["kind"] == "flasher"], "F", (255, 0, 255))):
            for row in rows:
                x, y = row["nx"] * img.width, row["ny"] * img.height
                dr.ellipse([x - r, y - r, x + r, y + r], outline=colour, width=3)
                dr.text((x + r + 2, y - size // 2), "{}{}".format(label, row["number"]), fill=colour, font=font)
        img.save(os.path.join(d, "overlay.png"))
        img.resize((img.width // 2, img.height // 2)).save(os.path.join(d, "overlay_small.png"))

    lamp_nums = {r["number"] for r in li_rows if r["kind"] == "lamp"}
    missing = [n for n in range(1, max(lamp_nums or {0}) + 1) if n not in lamp_nums]
    print("{} switches: {}".format(len(sw_rows), " ".join(str(r["number"]) for r in sw_rows)))
    print("{} lamps, {} flashers; lamp numbers with no object: {}".format(
        len(lamp_nums), len(li_rows) - len(lamp_nums), " ".join(map(str, missing)) or "none"))
    if args.names:
        unnamed = [r["mpf_name"] for r in sw_rows + li_rows if re.match(r"[slf]_\d\d_", r["mpf_name"])]
        print("{} devices not in the config (placeholder names): {}".format(len(unnamed), " ".join(unnamed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
