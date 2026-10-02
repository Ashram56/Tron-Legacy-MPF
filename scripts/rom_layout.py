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


def _reach(fn, funcs, names, depth=2):
    """The deff function and the game functions it calls, `depth` levels deep, in call order."""
    seen, order, todo = set(), [], [(fn, 0)]
    while todo:
        addr, d = todo.pop(0)
        if addr in seen:
            continue
        seen.add(addr)
        order.append(addr)
        if d < depth:
            for name in CALLEE.findall("".join(funcs[addr])):
                a = names.get(name)
                if a is not None and a >= 0x1000000:          # game code, not OS helpers
                    todo.append((a, d + 1))
    return order


def _deff_functions():
    with open(EVENT_MAP) as f:
        for row in csv.DictReader(f):
            fn = int(row["rom_function"], 16) if row["rom_function"] else None
            if fn and fn != 0x1000000:                        # 0x1000000: the generic animation player
                yield int(row["deff"]), fn


def status_panel_deffs():
    """{deff: kind} of the deffs whose code draws a panel left of x 41 under the effect: "status"
    (deff_draw_status_panel 0x010230ec: player scores, separator, timer bars) or "match"
    (FUN_0102cc48: the player scores dim, the separator bright)."""
    funcs, names = _functions()
    out = {}
    for d, fn in _deff_functions():
        if fn in funcs:
            body = "".join("".join(funcs[a]) for a in _reach(fn, funcs, names))
            if "deff_draw_status_panel(" in body:
                out[d] = "status"
            elif "FUN_0102cc48(" in body:
                out[d] = "match"
    return out


def deff_calls():
    """{deff: [call, ...]} in code order (the deff's own function first, then its callees)."""
    funcs, names = _functions()
    msgs = _messages(funcs)
    out = {}
    for deff_id, fn in _deff_functions():
        if fn in funcs:
            calls = []
            for addr in _reach(fn, funcs, names):
                calls += _calls(funcs[addr], msgs)
            out[deff_id] = calls
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
# Draw calls whose font or row come from ROM tables: values read off the reference capture.
# deff 38 match: "MATCH" in the font of table 0x40d3ce0 (font 37 in the capture), right-aligned at
# x 127, y = font_height - 2 = 7, for loop frames 0-29 with the brightness of table 0x40d3cf8
# (one step per two frames; capture levels 0..15); the match number only at loop frame 0x40, when
# the loop has stopped drawing its 64 bitmaps (GRAPHICS_END: the screen has no animation frame).
OVERRIDES = {38: {"MATCH": {"font": 37, "x": 127, "y": 7, "flags": 4, "source": "rom+capture",
                            "hide_after_frame": 30, "step_frames": 2,
                            "level_steps": [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15]},
                  "%,02lu": {"show_after_frame": 64}},
             # deff 40 (0x0100f604): "YOU'RE UP" drawn on every other 6-tick step
             40: {"YOU'RE UP": {"blink_ticks": 6}}}
GRAPHICS_END = {38: 64}
TICK_MS = 15.41      # ROM tick as the captures run (deff 19: 7-tick blink = 107.9 ms; deff 40: 6 ticks = 92 ms)


# deff 19 text beyond its two lines (deff_019 0x01023a98, deff_draw_status_panel 0x010230ec), all font 0:
# name, event arg, x, baseline y, flags. The panel rows move with the player count (score_display.gd).
SCORE_PANEL = [("Credits", "credits", 127, 30, 4), ("Replay", "replay", 84, 30, 2),
               ("P1", "p1", 38, 5, 4), ("P2", "p2", 38, 13, 4), ("P3", "p3", 38, 21, 4),
               ("P4", "p4", 38, 29, 4), ("Award", "award", 38, 13, 4)]


def frame_ms(deff_id, k):
    """Start of graphics frame k of a deff (timing.json; past the last frame: one more frame time)."""
    import glob
    import json
    path = glob.glob(os.path.join(ROOT, "assets", "mpf_package", "media", "dmd", "deff_%03d_*" % deff_id,
                                  "timing.json"))
    frames = json.load(open(path[0]))["graphics_frames"] if path else []
    if not frames:
        return 0
    t0 = frames[0]["t_ms"]
    if k < len(frames):
        return frames[k]["t_ms"] - t0
    step = frames[-2]["duration_ms"] if len(frames) > 1 else frames[-1]["duration_ms"]
    return frames[-1]["t_ms"] - t0 + step * (k - len(frames) + 1)
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
        over = OVERRIDES.get(deff_id, {}).get(line)
        if over:
            lay.update({k: v for k, v in over.items() if not k.endswith(("_frame", "_frames", "_ticks"))})
            if "blink_ticks" in over:
                lay["blink_ms"] = round(over["blink_ticks"] * TICK_MS)
            if "show_after_frame" in over:
                lay["show_after_ms"] = frame_ms(deff_id, over["show_after_frame"])
            if "hide_after_frame" in over:
                lay["hide_after_ms"] = frame_ms(deff_id, over["hide_after_frame"])
            if "step_frames" in over:
                lay["step_ms"] = frame_ms(deff_id, over["step_frames"])
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
        box = (left, lay["y"] - font["cap"] + 1, left + gen_fonts.text_width(font, text) - 1, lay["y"],
               lay.get("show_after_ms", 0), lay.get("hide_after_ms") or 10 ** 9)
        if not any(box[0] <= b[2] and b[0] <= box[2] and box[1] <= b[3] and b[1] <= box[3]
                   and box[4] < b[5] and b[4] < box[5] for b in boxes):
            boxes.append(box)
            out[i] = lay
    return out
