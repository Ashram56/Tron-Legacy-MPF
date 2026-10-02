"""Text layout of the display effects, read from the decompiled ROM code.

A deff draws its text with text_draw_msg / text_printf_msg (font, flags, x, y) or with
text_draw_msg_fit / FUN_00028eb0 (a list of fonts, the first that fits max_width is used). The calls
are taken from the deff's function (event_map.csv rom_function) and from the functions it calls
(two levels). Each call: msg text (from the decompiler's msg comments), font (None for a font list),
flags (2 centre, 4 right), x, y (baseline row) and, for font lists, the list address and max width.
"""
import csv
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "assets", "code", "tron_game_decompiled_v2.c")
EVENT_MAP = os.path.join(ROOT, "assets", "mpf_package", "event_map.csv")
N = r"(-?0x[0-9a-f]+|-?\d+)"
DIRECT = re.compile(r"\b(text_draw_msg|text_printf_msg)\((0x[0-9a-f]+),[^,]+," + N + "," + N + "," + N + "," + N + ",")
FIT = re.compile(r"\b(text_draw_msg_fit|FUN_00028eb0)\((0x[0-9a-f]+),[^,]+,\(?(?:int \*\))?&DAT_([0-9a-f]+),"
                 + N + "," + N + "," + N + ",[^,]+," + N)
MSG = re.compile(r'/\* msg (0x[0-9a-f]+) "(.*?)" \*/')
CALLEE = re.compile(r"\b(FUN_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\(")


def _functions():
    funcs, names, cur = {}, {}, None
    with open(SRC) as f:
        for line in f:
            m = re.match(r"// ==== ([0-9a-f]+) (\S+)", line)
            if m:
                cur = int(m.group(1), 16)
                funcs[cur] = []
                names[m.group(2)] = cur
            elif cur is not None:
                funcs[cur].append(line)
    return funcs, names


def _messages(funcs):
    out = {}
    for lines in funcs.values():
        for line in lines:
            for mid, text in MSG.findall(line):
                out[int(mid, 16)] = text
    return out


def _calls(lines, msgs):
    out = []
    for line in lines:
        m = DIRECT.search(line)
        if m:
            text = msgs.get(int(m.group(2), 16))
            if text is not None:
                out.append({"text": text, "font": int(m.group(3), 0), "flags": int(m.group(4), 0),
                            "x": int(m.group(5), 0), "y": int(m.group(6), 0)})
            continue
        m = FIT.search(line)
        if m:
            text = msgs.get(int(m.group(2), 16))
            if text is not None:
                out.append({"text": text, "font": None, "font_list": "0x" + m.group(3),
                            "flags": int(m.group(4), 0), "x": int(m.group(5), 0), "y": int(m.group(6), 0),
                            "max_width": int(m.group(7), 0)})
    return out


def deff_calls():
    """{deff: [call, ...]} in code order (the deff's own function first, then its callees)."""
    funcs, names = _functions()
    msgs = _messages(funcs)
    out = {}
    with open(EVENT_MAP) as f:
        for row in csv.DictReader(f):
            fn = int(row["rom_function"], 16) if row["rom_function"] else None
            if fn not in funcs or fn == 0x1000000:        # 0x1000000: the generic animation player
                continue
            seen, order, todo = set(), [], [(fn, 0)]
            while todo:
                addr, depth = todo.pop(0)
                if addr in seen:
                    continue
                seen.add(addr)
                order.append(addr)
                if depth < 2:
                    for name in CALLEE.findall("".join(funcs[addr])):
                        a = names.get(name)
                        if a is not None and a >= 0x1000000:      # game code, not OS helpers
                            todo.append((a, depth + 1))
            calls = []
            for addr in order:
                calls += _calls(funcs[addr], msgs)
            out[int(row["deff"])] = calls
    return out


# Font lists of text_draw_msg_fit: the ROM data is not in the package; the fonts are the ones the
# reference captures show for these calls (by scripts/render_diff.py style matching).
FONT_LISTS = {"0x040d2834": [33], "0x040d2aa4": [15], "0x040d302c": [39], "0x040d31d4": [10, 6],
              "0x040d33a8": [11], "0x040d8a80": [12], "0x040d9194": [2]}
DEFAULT_LIST = [15, 12, 2]
# The score display (deff 19) picks font and row from a table by score (RAM 0x370ac, not in the
# package). Score 0 is font 26 on row 21 (reference capture); the smaller fonts for longer scores are
# a guess: the first that fits the 87 dots right of the status panel, centred on the same middle row.
SCORE_FIT = {"fit_fonts": [26, 23, 21, 19], "fit_ys": [21, 21, 18, 16], "fit_width": 87}
FALLBACK_FONT = 12
SAMPLE = {"%,02lu": "1,234,560", "%luK": "100K"}


def _sample(text):
    for k, v in SAMPLE.items():
        text = text.replace(k, v)
    return re.sub(r"%(P\d/[^%]*%|[-+ #0,]*\d*l?[dus])", "0", text)


def line_layouts(deff_id, lines, fonts, calls=None):
    """Layout of each text line of a deff: dict(font, x, y, flags[, fit_fonts, fit_ys, fit_width]
    [, alt_x, alt_y, alt_when_empty], source) or None when the line overlaps an earlier one (a later
    screen of the effect: the ROM never shows both). Lines found in the code are placed first, the
    others (fallback: font 12 centred, rows spread) only where they do not overlap them."""
    import gen_fonts
    calls = deff_calls().get(deff_id, []) if calls is None else calls
    lays = []
    for i, line in enumerate(lines):
        mine = [k for k, c in enumerate(calls) if c["text"] == line]
        if mine:
            c = calls[mine[0]]
            lay = {"x": c["x"], "y": c["y"], "flags": c["flags"], "source": "rom"}
            if c["font"] is None:
                lst = FONT_LISTS.get(c["font_list"], DEFAULT_LIST)
                lay.update(font=lst[0], fit_fonts=lst, fit_ys=[c["y"]] * len(lst), fit_width=c["max_width"])
            else:
                lay["font"] = c["font"]
            later = [k for k in mine[1:] if (calls[k]["x"], calls[k]["y"]) != (c["x"], c["y"])]
            if later:                                    # a second layout: shown when a value line is blank
                between = {calls[k]["text"] for k in range(mine[0] + 1, later[0])}
                cond = [j for j, t in enumerate(lines) if j != i and "%" in t and t in between]
                if cond:
                    lay.update(alt_x=calls[later[0]]["x"], alt_y=calls[later[0]]["y"],
                               alt_when_empty="line%d" % cond[0])
        else:
            n = len(lines)
            lay = {"font": FALLBACK_FONT, "x": 84, "flags": 2, "source": "fallback",
                   "y": round(32 * (i + 1) / n) - max(0, (32 // n - 8) // 2) - 1}
        if deff_id == 19 and "%" in line and "BALL" not in line:
            lay.update(font=SCORE_FIT["fit_fonts"][0], x=84, flags=2, y=SCORE_FIT["fit_ys"][0],
                       source="rom+table guess", **SCORE_FIT)
        lays.append(lay)
    out, boxes = [None] * len(lines), []
    order = sorted(range(len(lines)), key=lambda k: (lays[k]["source"] == "fallback", k))
    for i in order:
        lay, text = lays[i], _sample(lines[i])
        font = fonts[lay["font"]]
        left = gen_fonts.text_left(font, text, lay["x"], lay["flags"])
        box = (left, lay["y"] - font["cap"] + 1, left + gen_fonts.text_width(font, text) - 1, lay["y"])
        if not any(box[0] <= b[2] and b[0] <= box[2] and box[1] <= b[3] and b[1] <= box[3] for b in boxes):
            boxes.append(box)
            out[i] = lay
    return out
