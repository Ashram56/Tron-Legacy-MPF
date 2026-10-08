#!/usr/bin/env python3
"""Pull the playfield picture, every object's position and the table script out of a Visual Pinball X table.

    python scripts/vpx_extract.py TABLE.vpx OUTDIR [--image NAME]

Game agnostic (VPX 10.x tables). The .vpx is only read. OUTDIR gets:

    playfield.png       the playfield image (GameData IMAG, else the largest "playfield"/"pf*" image, or --image)
    script.vbs          the table script, byte for byte
    images/             every embedded image, as its original file (PNG, JPG, WebP ...)
    items.json          every object: type, name, x/y in table units, nx/ny as fractions of the playfield;
                        collections: {name: [member names]} (vpmMapLights reads one)
    switches_all.csv    switch candidates: triggers, targets, kickers, bumpers, spinners, gates, flippers,
                        plungers, and walls/rubbers/primitives with hit events
    lights_all.csv      lights and flashers (timer_interval is the lamp number on vpmMapLights tables)
    monitor_draft.yaml  an MPF Monitor layout with VPX names (rename to the machine config's devices)
    overlay.png         markers and names drawn on the playfield: look at it before trusting any position

The numbers (switch 23, lamp 45) are not in the objects: they live in the table script. Mapping them is the
second step, per table (docs/agents/vpx_extraction.md). Needs olefile and Pillow (`python scripts/setup.py
--vpx`, or `pip install olefile pillow`).

Format (docs/agents/vpx_extraction.md, "The .vpx format"): an OLE compound file; streams GameStg/GameData,
GameStg/GameItemN, GameStg/ImageN, GameStg/CollectionN hold BIFF records (int32 length counting the 4-byte tag, tag, payload).
CODE is the exception: its length is 4 and the script's own int32 length follows the tag.
"""
import argparse
import csv
import json
import os
import re
import struct
import sys

ITEM_TYPES = ["Wall", "Flipper", "Timer", "Plunger", "Textbox", "Bumper", "Trigger", "Light", "Kicker", "Decal",
              "Gate", "Spinner", "Ramp", "Table", "LightCenter", "DragPoint", "Collection", "DispReel", "LightSeq",
              "Primitive", "Flasher", "Rubber", "HitTarget"]
SWITCH_TYPES = {"Trigger", "HitTarget", "Kicker", "Bumper", "Spinner", "Gate", "Flipper", "Plunger"}
HIT_EVENT_TYPES = {"Wall", "Rubber", "Primitive"}      # switches only when "has hit event" is set
LIGHT_TYPES = {"Light", "Flasher"}
IMAGE_MAGIC = [(b"\x89PNG", ".png"), (b"\xff\xd8", ".jpg"), (b"RIFF", ".webp"), (b"BM", ".bmp"),
               (b"#?", ".hdr"), (b"\x76\x2f\x31\x01", ".exr"), (b"GIF8", ".gif")]


def records(data, start=0):
    """Yield (tag, payload, offset) for each BIFF record; CODE carries the script as its payload."""
    i = start
    while i + 8 <= len(data):
        length, = struct.unpack_from("<i", data, i)
        if length < 4:
            return
        tag = data[i + 4:i + 8].decode("latin-1")
        if tag == "CODE":
            size, = struct.unpack_from("<i", data, i + 8)
            yield tag, data[i + 12:i + 12 + size], i
            i += 12 + size
            continue
        yield tag, data[i + 8:i + 4 + length], i
        i += 4 + length


def astr(p):
    """An ANSI string record, or "" when the length is out of range or the text is not printable ASCII (some
    records hold binary data: on the Tron table that put garbage in the CSV until this guard was added)."""
    if len(p) < 4:
        return ""
    n, = struct.unpack_from("<i", p)
    if n < 0 or n > len(p) - 4:
        return ""
    s = p[4:4 + n]
    if any(b < 32 or b > 126 for b in s):
        return ""
    return s.decode("ascii")


def wstr(p):
    """Item NAME: int32 byte length, then UTF-16LE (ANSI on very old tables)."""
    if len(p) < 4:
        return ""
    n, = struct.unpack_from("<i", p)
    s = p[4:4 + max(0, min(n, len(p) - 4))]
    if len(s) % 2 == 0 and b"\x00" in s:
        return s.decode("utf-16-le", errors="replace").rstrip("\x00")
    return s.decode("latin-1").rstrip("\x00")


def f32(p, k=0):
    return struct.unpack_from("<f", p, 4 * k)[0]


def i32(p):
    return struct.unpack_from("<i", p)[0]


def read_gamedata(ole):
    gd = ole.openstream("GameStg/GameData").read()
    out = {}
    for tag, p, _ in records(gd):
        if tag in out:
            continue
        try:
            if tag in ("LEFT", "TOPX", "RGHT", "BOTM"):
                out[tag] = f32(p)
            elif tag == "IMAG":
                out[tag] = astr(p)
            elif tag == "CODE":
                out[tag] = p
        except struct.error:
            pass
    return out


def numbered(ole, prefix):
    names = []
    for entry in ole.listdir():
        if len(entry) == 2 and entry[0] == "GameStg":
            m = re.fullmatch(prefix + r"(\d+)", entry[1])
            if m:
                names.append((int(m.group(1)), "/".join(entry)))
    return [n for _, n in sorted(names)]


def read_images(ole):
    images = []
    for stream in numbered(ole, "Image"):
        data = ole.openstream(stream).read()
        rec = {}
        for tag, p, _ in records(data):
            if tag in rec:
                continue                        # first occurrence wins (the JPEG block repeats NAME/PATH)
            try:
                if tag in ("NAME", "PATH"):
                    rec[tag] = astr(p)
                elif tag in ("WDTH", "HGHT"):
                    rec[tag] = i32(p)
                elif tag in ("DATA", "BITS"):
                    rec[tag] = p
            except struct.error:
                pass
        images.append(rec)
    return images


def image_ext(blob):
    for magic, ext in IMAGE_MAGIC:
        if blob.startswith(magic):
            return ext
    return ".bin"


def read_item(data):
    """One GameItem stream: its type and the fields the extractor uses."""
    kind, = struct.unpack_from("<i", data)
    item = {"type": ITEM_TYPES[kind] if 0 <= kind < len(ITEM_TYPES) else "Type{}".format(kind)}
    drag = []
    in_drag = False
    for tag, p, _ in records(data, 4):
        try:
            if tag == "DPNT":
                in_drag = True                  # drag point block: its VCEN must not replace the item's
                continue
            if in_drag:
                if tag == "VCEN":
                    drag.append((f32(p, 0), f32(p, 1)))
                elif tag == "ENDB":
                    in_drag = False
                continue
            if tag == "ENDB":
                break
            if tag in item:
                continue
            if tag == "NAME":
                item["name"] = wstr(p)
            elif tag == "VCEN":
                item["VCEN"] = (f32(p, 0), f32(p, 1))
            elif tag == "VPOS":
                item["VPOS"] = (f32(p, 0), f32(p, 1))
            elif tag in ("FLAX", "FLAY"):       # flasher centre
                item[tag] = f32(p)
            elif tag == "HTEV":
                item["hit_event"] = i32(p) != 0
            elif tag == "TMIN":
                item["timer_interval"] = i32(p)
            elif tag in ("IMAG", "SURF"):
                item[tag.lower()] = astr(p)
        except struct.error:
            pass
    if "VCEN" in item:
        x, y = item.pop("VCEN")
    elif "VPOS" in item:
        x, y = item.pop("VPOS")
    elif "FLAX" in item and "FLAY" in item:
        x, y = item["FLAX"], item["FLAY"]
    elif drag:
        x = sum(d[0] for d in drag) / len(drag)
        y = sum(d[1] for d in drag) / len(drag)
    else:
        x = y = None
    item.pop("FLAX", None)
    item.pop("FLAY", None)
    item.pop("VPOS", None)
    item["x"], item["y"] = x, y
    if drag:
        item["drag_points"] = len(drag)
    return item


def read_collection(data):
    """One Collection stream: its NAME and the names of its ITEMs (both UTF-16LE, like item names)."""
    name, members = "", []
    for tag, p, _ in records(data):
        try:
            if tag == "NAME" and not name:
                name = wstr(p)
            elif tag == "ITEM":
                members.append(wstr(p))
        except struct.error:
            pass
    return name, members


def pick_playfield(images, wanted, imag):
    by_name = {im.get("NAME", "").lower(): im for im in images if im.get("DATA")}
    for name in (wanted, imag):
        if name and name.lower() in by_name:
            return by_name[name.lower()], "--image" if name == wanted else "GameData IMAG"
    cands = [im for im in by_name.values() if "playfield" in im["NAME"].lower() or im["NAME"].lower().startswith("pf")]
    if cands:
        return max(cands, key=lambda im: im.get("WDTH", 0) * im.get("HGHT", 0)), "largest playfield-named image"
    return None, "none found"


def safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "unnamed"


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:     # newline="": no blank rows on Windows
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def draw_overlay(pf_path, out_path, switches, lights):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(pf_path).convert("RGB")
    d = ImageDraw.Draw(img)
    size = max(12, img.width // 110)
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    r = max(4, img.width // 200)
    for rows, colour in ((lights, (255, 220, 0)), (switches, (0, 255, 255))):
        for row in rows:
            x, y = row["nx"] * img.width, row["ny"] * img.height
            d.ellipse([x - r, y - r, x + r, y + r], outline=colour, width=2)
            d.text((x + r + 2, y - size // 2), row["vpx"], fill=colour, font=font)
    img.save(out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("table")
    ap.add_argument("outdir")
    ap.add_argument("--image", help="the playfield image's name, when GameData IMAG is not the playfield")
    args = ap.parse_args(argv)
    try:
        import olefile
    except ImportError:
        raise SystemExit("olefile and Pillow are needed: python scripts/setup.py --vpx (or pip install olefile pillow)")
    os.makedirs(os.path.join(args.outdir, "images"), exist_ok=True)

    with olefile.OleFileIO(args.table) as ole:
        gd = read_gamedata(ole)
        images = read_images(ole)
        items = [read_item(ole.openstream(s).read()) for s in numbered(ole, "GameItem")]
        collections = dict(read_collection(ole.openstream(s).read()) for s in numbered(ole, "Collection"))

    left, top = gd.get("LEFT", 0.0), gd.get("TOPX", 0.0)
    w, h = gd.get("RGHT", 1.0) - left, gd.get("BOTM", 1.0) - top
    for it in items:
        if it["x"] is not None:
            it["nx"] = round((it["x"] - left) / w, 4)
            it["ny"] = round((it["y"] - top) / h, 4)

    if "CODE" in gd:
        with open(os.path.join(args.outdir, "script.vbs"), "wb") as f:
            f.write(gd["CODE"])
    seen = set()
    for im in images:
        if im.get("DATA"):
            base = safe(im.get("NAME", "image"))
            name = base
            k = 2
            while name.lower() in seen:
                name = "{}_{}".format(base, k)
                k += 1
            seen.add(name.lower())
            with open(os.path.join(args.outdir, "images", name + image_ext(im["DATA"])), "wb") as f:
                f.write(im["DATA"])
    legacy = sum(1 for im in images if "BITS" in im and not im.get("DATA"))

    pf, why = pick_playfield(images, args.image, gd.get("IMAG"))
    pf_path = os.path.join(args.outdir, "playfield.png")
    if pf:
        import io
        from PIL import Image
        Image.open(io.BytesIO(pf["DATA"])).convert("RGB").save(pf_path)

    placed = [it for it in items if it.get("nx") is not None and it.get("name")]
    sw = [it for it in placed if it["type"] in SWITCH_TYPES or (it["type"] in HIT_EVENT_TYPES and it.get("hit_event"))]
    li = [it for it in placed if it["type"] in LIGHT_TYPES]
    cols = ["vpx", "type", "x", "y", "nx", "ny", "timer_interval", "surf", "imag"]
    sw_rows = [dict(it, vpx=it["name"], x=round(it["x"], 1), y=round(it["y"], 1)) for it in sw]
    li_rows = [dict(it, vpx=it["name"], x=round(it["x"], 1), y=round(it["y"], 1)) for it in li]
    write_csv(os.path.join(args.outdir, "switches_all.csv"), sw_rows, cols)
    write_csv(os.path.join(args.outdir, "lights_all.csv"), li_rows, cols)
    with open(os.path.join(args.outdir, "items.json"), "w", encoding="utf-8") as f:
        json.dump({"bounds": [left, top, left + w, top + h], "playfield_image": pf and pf.get("NAME"),
                   "items": items, "collections": collections}, f, indent=1)

    # MPF Monitor's own file uses singular section keys (switch:, light:, coil: ...) with x/y fractions of
    # the playfield picture; the names must become the machine config's device names before use.
    with open(os.path.join(args.outdir, "monitor_draft.yaml"), "w", encoding="utf-8") as f:
        f.write("# Draft MPF Monitor layout from {} (VPX names: rename to the machine config's devices)\n"
                .format(os.path.basename(args.table)))
        for key, rows in (("light", li_rows), ("switch", sw_rows)):
            f.write(key + ":\n")
            for r in rows:
                f.write("  {}:   # {}\n    x: {}\n    y: {}\n".format(
                    safe(r["vpx"]).lower(), r["type"], r["nx"], r["ny"]))
    if pf:
        draw_overlay(pf_path, os.path.join(args.outdir, "overlay.png"), sw_rows, li_rows)

    script_lines = gd["CODE"].count(b"\n") + 1 if "CODE" in gd else 0
    print("table bounds {:g},{:g} .. {:g},{:g}".format(left, top, left + w, top + h))
    print("playfield: {} ({}x{}, {})".format(pf and pf.get("NAME"), pf and pf.get("WDTH"), pf and pf.get("HGHT"), why))
    print("{} images ({} legacy BITS not decoded), {} items, {} collections, script {} lines".format(
        len(images), legacy, len(items), len(collections), script_lines))
    print("{} switch candidates, {} lights/flashers -> {}".format(len(sw_rows), len(li_rows), args.outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
