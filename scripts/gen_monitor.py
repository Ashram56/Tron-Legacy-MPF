#!/usr/bin/env python3
"""Generate game/monitor/monitor.yaml and game/monitor/playfield.jpg for MPF Monitor.

The assets have no playfield image, so this draws a labelled grid: every switch (matrix by SAM number, then
the dedicated ones) and every lamp (by SAM number, then the two ramp tubes), each at a spot with its name
printed next to it. Click a spot in MPF Monitor to toggle the switch. Positions are fractions of the image
(MPF Monitor's x/y). MPF Monitor rewrites monitor.yaml when spots are dragged, so re-running this script
discards a hand-made layout: run it only to start over (or after switches or lights are added).

Usage: .venv/bin/python scripts/gen_monitor.py   (after scripts/gen_config.py)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from ruamel.yaml import YAML

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG = os.path.join(ROOT, "game", "config")
OUT = os.path.join(ROOT, "game", "monitor")
WIDTH, HEIGHT = 1040, 1500
SWITCH_COLUMNS, LIGHT_COLUMNS = 4, 4
# DejaVu Sans (Linux) draws the committed playfield.jpg; other OSes use a font of their own, then Pillow's.
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf", "Arial.ttf", "arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]


def load_font(size):
    for name in FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def devices(section, files):
    yaml = YAML(typ="safe")
    found = []
    for name in files:
        with open(os.path.join(CONFIG, name), encoding="utf-8") as f:
            data = yaml.load(f) or {}
        for device, cfg in (data.get(section) or {}).items():
            if cfg and "number" in cfg:
                found.append((device, str(cfg["number"])))

    def order(item):        # matrix / lamp numbers first, by number; then D<n> dedicated, then the rest
        number = item[1]
        if number.isdigit():
            return (0, int(number))
        if number[:1] == "D" and number[1:].isdigit():
            return (1, int(number[1:]))
        return (2, number)
    return sorted(found, key=order)


def place(items, columns, top, bottom):
    rows = (len(items) + columns - 1) // columns
    spots = {}
    for i, (name, number) in enumerate(items):
        col, row = i % columns, i // columns
        x = (col + 0.08) / columns
        y = top + (row + 0.5) * (bottom - top) / rows
        spots[name] = (round(x, 4), round(y, 4), number)
    return spots


def main():
    switches = devices("switches", ["rom/switches.yaml", "hardware.yaml"])
    lights = devices("lights", ["rom/lights.yaml"])
    switch_spots = place(switches, SWITCH_COLUMNS, 0.04, 0.46)
    light_spots = place(lights, LIGHT_COLUMNS, 0.52, 0.99)

    image = Image.new("RGB", (WIDTH, HEIGHT), (24, 24, 32))
    draw = ImageDraw.Draw(image)
    font = load_font(15)
    head = load_font(22)
    draw.text((12, 8), "SWITCHES (SAM number: name), click to toggle", font=head, fill=(230, 230, 230))
    draw.text((12, 0.49 * HEIGHT), "LIGHTS (SAM lamp number: name)", font=head, fill=(230, 230, 230))
    draw.line((0, 0.485 * HEIGHT, WIDTH, 0.485 * HEIGHT), fill=(90, 90, 110), width=2)
    for spots, colour in ((switch_spots, (120, 200, 255)), (light_spots, (255, 210, 120))):
        for name, (x, y, number) in spots.items():
            px, py = x * WIDTH, y * HEIGHT
            draw.ellipse((px - 9, py - 9, px + 9, py + 9), outline=(80, 80, 90), width=2)
            draw.text((px + 16, py - 9), "{}: {}".format(number if len(number) < 4 else "aux", name[2:]), font=font, fill=colour)
    os.makedirs(OUT, exist_ok=True)
    image.save(os.path.join(OUT, "playfield.jpg"), quality=90)

    lines = ["# MPF Monitor layout (scripts/gen_monitor.py): spots on game/monitor/playfield.jpg, x/y as fractions",
             "# of the image. MPF Monitor rewrites this file when spots are dragged."]
    for kind, spots in (("switch", switch_spots), ("light", light_spots)):
        lines.append("{}:".format(kind))
        for name, (x, y, _) in spots.items():
            lines.append("  {}:".format(name))
            lines.append("    x: {}".format(x))
            lines.append("    y: {}".format(y))
    with open(os.path.join(OUT, "monitor.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("monitor: {} switches, {} lights".format(len(switch_spots), len(light_spots)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
