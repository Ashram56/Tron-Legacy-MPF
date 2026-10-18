"""The service menu icons of the items this game adds (FEATURE AUDITS, DISPLAY ADJUSTMENTS, the NETWORK and
SCORBIT menus): drawn here in the ROM's icon style, as game images 9000+ (game/service_icons/NNNN.png).

    python scripts/gen_service_icons.py [--sheet PNG]

A ROM menu icon is 17 x 23 dots in four shades (0, 3, 6, 15 of 15): a bevelled tile (top and left edge 15,
bottom and right 3) on a 6 background, a picture in rows 2-14 and a label of 3 x 5 letters in rows 16-20. The
dimmed twin (the next image) drops the bevel and darkens the background to 3; the picture stays. Each icon below
is its 13 x 13 picture: '.' background, 'x' 0, '-' 3, 'o' 6 kept when dimmed, '#' 15.
"""
import argparse
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "game", "service_icons")
FIRST = 9000

FONT = {   # 3 x 5 letters, as the ROM's icon labels
    "A": ".x.x.xxxxx.xx.x", "C": ".xxx..x..x...xx", "D": "xx.x.xx.xx.xxx.", "E": "xxxx..xx.x..xxx",
    "F": "xxxx..xx.x..x..", "G": ".xxx..x.xx.x.xx", "H": "x.xx.xxxxx.xx.x", "I": "xxx.x..x..x.xxx",
    "J": "..x..x..xx.x.x.", "N": "xx.x.xx.xx.xx.x", "O": ".x.x.xx.xx.x.x.", "P": "xx.x.xxx.x..x..",
    "R": "xx.x.xxx.x.xx.x", "S": ".xxx...x...xxx.", "T": "xxx.x..x..x..x.", "U": "x.xx.xx.xx.xxxx",
    "W": "x.xx.xx.xxxxx.x", "B": "xx.x.xxx.x.xxx.", "K": "x.xx.xxx.x.xx.x", "L": "x..x..x..x..xxx",
    "M": "x.xxxxx.xx.xx.x", "Y": "x.xx.x.x..x..x.", "?": "xx...x.x.....x.",
}

WIFI = [   # the Wi-Fi arcs, shared by the network icons
    "....xxxxx....",
    "..xx#####xx..",
    ".x##xxxxx##x.",
    "x#xx.....xx#x",
    ".x..xxxxx..x.",
    "...x#####x...",
    "..x#xxxxx#x..",
    "...x.....x...",
    ".....xxx.....",
    "....x###x....",
    ".....xxx.....",
    ".............",
    ".............",
]


def with_badge(base, badge, at):
    """base with the badge rows drawn over it, top left at (row, col); '.' in the badge leaves base."""
    rows = [list(r) for r in base]
    for dy, line in enumerate(badge):
        for dx, c in enumerate(line):
            if c != ".":
                rows[at[0] + dy][at[1] + dx] = c
    return ["".join(r) for r in rows]


ICONS = [   # (item text, label, picture)
    ("FEATURE AUDITS", "FAUD", [
        "x#x......xxxx",
        "###......x##x",
        "x#x......x##x",
        "......xxxx##x",
        "......x##x##x",
        "......x##x##x",
        "..xxxxx##x##x",
        "..x##xx##x##x",
        "..x##xx##x##x",
        "..x##xx##x##x",
        "xxxxxxxxxxxxx",
        "#############",
        ".............",
    ]),
    ("FEATURE ADJUSTMENTS", "FADJ", [
        "x#x..........",
        "###x...x...x.",
        "x#xx...x...x.",
        "..xxx..x...x.",
        "..x#x..x..xxx",
        "..xxx..x..x#x",
        "...x..xxx.xxx",
        "...x..x#x..x.",
        "...x..xxx..x.",
        "...x...x...x.",
        "...x...x...x.",
        "...x...x...x.",
        ".............",
    ]),
    ("DISPLAY ADJUSTMENTS", "DISP", [
        ".............",
        "xxxxxxxxxxxxx",
        "x-----------x",
        "x-#-#-#--##-x",
        "x-#-##-#-#--x",
        "x-#-#--#-##-x",
        "x-----------x",
        "xxxxxxxxxxxxx",
        "......x......",
        "....xxxxx....",
        ".............",
        ".xxxxxxxxxxx.",
        ".x###x######x",
    ]),
    ("GO TO NETWORK MENU", "NET", [
        "....xxxxx....",
        "..xx#x#x#xx..",
        ".x#x#x#x#x#x.",
        ".xxxxxxxxxxx.",
        "x#x#x#x#x#x#x",
        "x#x#x#x#x#x#x",
        "xxxxxxxxxxxxx",
        "x#x#x#x#x#x#x",
        ".xxxxxxxxxxx.",
        ".x#x#x#x#x#x.",
        "..xx#x#x#xx..",
        "....xxxxx....",
        ".............",
    ]),
    ("WI-FI STATUS", "WIFI", WIFI),
    ("SCAN WI-FI NETWORKS", "SCAN", with_badge(WIFI, [
        ".xxx..",
        "x###x.",
        "x#-#x.",
        "x###x.",
        ".xxxx.",
        "....xx",
    ], (7, 7))),
    ("JOIN HIDDEN NETWORK", "HIDE", with_badge([r.replace("#", "-") for r in WIFI], [
        "xxx.",
        "..#x",
        ".xx.",
        ".#..",
        "....",
        ".#..",
    ], (7, 9))),
    ("FORGET WI-FI NETWORK", "DROP", with_badge(WIFI, [
        "#...#",
        ".#.#.",
        "..#..",
        ".#.#.",
        "#...#",
    ], (8, 8))),
    ("GO TO SCORBIT MENU", "SCOR", [
        "...xxxxxxx...",
        "...x#####x...",
        "...x#---#x...",
        "...x#-#-#x...",
        "...x#---#x...",
        "...x#-#-#x...",
        "...x#---#x...",
        "...x#-#-#x...",
        "...x#---#x...",
        "...x#####x...",
        "...x##x##x...",
        "...x#####x...",
        "...xxxxxxx...",
    ]),
    ("SCORBIT STATUS", "STAT", [
        "...xxxxxxx...",
        "...x#####x...",
        "...x#---#x...",
        "...x#---#x...",
        "...x#--##x...",
        "...x#-##-x...",
        "...x###--x...",
        "...x##---x...",
        "...x#---#x...",
        "...x#####x...",
        "...x##x##x...",
        "...x#####x...",
        "...xxxxxxx...",
    ]),
    ("SCORBIT PAIRING", "PAIR", [
        ".............",
        ".xxxxx.......",
        "x#####x......",
        "x#xxx#x......",
        "x#x.x#xxxxx..",
        "x#xxx#####x..",
        "x###x###x##x.",
        ".xxxxx#x.x#x.",
        ".....x#xxx#x.",
        ".....x#####x.",
        "......xxxxx..",
        ".............",
        ".............",
    ]),
    ("SCORBIT UNPAIR", "UNPR", [
        ".............",
        ".xxxxx.......",
        "x#####x......",
        "x#xxx#x......",
        "x#x.x#x......",
        "x#xxx#x.#....",
        "x###xx...#...",
        ".xxx...#.....",
        ".....x#xxxx..",
        ".....x#xx##x.",
        ".....x#####x.",
        "......xxxxx..",
        ".............",
    ]),
    ("SCORBIT ADJUSTMENTS", "SADJ", [
        "...xxxxxxx...",
        "...x#####x...",
        "...x#---#x...",
        "...x#x--#x...",
        "...xx#x-#x...",
        "...x#x--#x...",
        "...x#--x#x...",
        "...x#-x#xx...",
        "...x#--x#x...",
        "...x#####x...",
        "...x##x##x...",
        "...x#####x...",
        "...xxxxxxx...",
    ]),
]

SHADE = {"x": 0, "-": 3, "o": 6, "#": 15}


def tile(picture, label, dimmed):
    bg = 3 if dimmed else 6
    img = Image.new("L", (17, 23), bg * 17)
    px = img.load()
    if not dimmed:
        for x in range(17):
            px[x, 0] = 255
            px[x, 22] = 51
        for y in range(23):
            px[0, y] = 255
            px[16, y] = 51
        px[0, 22] = 51
    assert len(picture) == 13 and all(len(r) == 13 for r in picture), label
    for y, row in enumerate(picture):
        for x, c in enumerate(row):
            if c != ".":
                px[2 + x, 2 + y] = SHADE[c] * 17
    width = 4 * len(label) - 1
    x0 = (17 - width + 1) // 2
    for i, ch in enumerate(label):
        glyph = FONT[ch]
        for k, c in enumerate(glyph):
            if c == "x":
                px[x0 + 4 * i + k % 3, 16 + k // 3] = 0
    return img


def icons():
    """{item text: game image number}, in the order written."""
    return {text: FIRST + 2 * i for i, (text, _, _) in enumerate(ICONS)}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--sheet", help="also write a picture of every icon, 8x, for checking by eye")
    args = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    tiles = []
    for (text, label, picture), n in zip(ICONS, icons().values()):
        for k in (0, 1):
            img = tile(picture, label, bool(k))
            img.save(os.path.join(OUT, "%04d.png" % (n + k)))
            tiles.append(img)
    print("{} icons in {}".format(len(ICONS), OUT))
    if args.sheet:
        sheet = Image.new("L", (len(ICONS) * 20 + 2, 50), 0)
        for i, img in enumerate(tiles):
            sheet.paste(img, (2 + (i // 2) * 20, 2 + (i % 2) * 25))
        sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(args.sheet)


if __name__ == "__main__":
    main()
