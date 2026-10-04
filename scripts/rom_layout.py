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
# a call whose font is a variable loaded from a per-language font table (deff 80: `uVar6 =
# *(uint *)(&DAT_040d2ee8 + iVar4 * 4)`, iVar4 = FUN_0000a3b4(), the language): FONT_TABLES
VAR_FONT = re.compile(r"\b(text_draw_msg|text_printf_msg)\((0x[0-9a-f]+),[^,]+,([A-Za-z_]\w*)," + N + "," + N + ","
                      + N + ",")
TABLE_LOAD = r"\b{} = \*\(u?int \*\)\(&DAT_([0-9a-f]+) \+"
# a message picked from a table (deff 114: the stage's "SHOOT" / item lines): text "%s"
TABLE = re.compile(r"\btext_draw_msg\((?!0x)[^,]+,[^,]+," + N + "," + N + "," + N + "," + N + ",")
MSG = re.compile(r'/\* msg (0x[0-9a-f]+) "(.*?)" \*/')
CALLEE = re.compile(r"\b(FUN_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\(")


def _functions():
    funcs, names, cur = {}, {}, None
    with open(SRC, encoding="utf-8") as f:
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


def _statements(lines):
    """The lines with each call that the decompiler wrapped over several lines joined into one."""
    out, cur = [], ""
    for line in lines:
        part = line.strip()
        cur = (cur + ("" if part[:1] in ",)" or cur[-1:] in ",(" else " ") + part) if cur else line.rstrip("\n")
        if cur.count("(") <= cur.count(")"):
            out.append(cur)
            cur = ""
    return out + ([cur] if cur else [])


def _calls(lines, msgs):
    out, body = [], "".join(lines)
    for line in _statements(lines):
        m = DIRECT.search(line)
        if m:
            text = msgs.get(int(m.group(2), 16))
            if text is not None:
                out.append({"text": text, "font": int(m.group(3), 0), "flags": int(m.group(4), 0),
                            "x": int(m.group(5), 0), "y": int(m.group(6), 0)})
            continue
        m = VAR_FONT.search(line)
        if m:
            text = msgs.get(int(m.group(2), 16))
            table = re.search(TABLE_LOAD.format(re.escape(m.group(3))), body)
            font = FONT_TABLES.get("0x" + table.group(1)) if table else None
            if text is not None and font is not None:
                out.append({"text": text, "font": font, "flags": int(m.group(4), 0), "x": int(m.group(5), 0),
                            "y": int(m.group(6), 0), "font_table": "0x" + table.group(1)})
            continue
        m = FIT.search(line)
        if m:
            text = msgs.get(int(m.group(2), 16))
            if text is not None:
                out.append({"text": text, "font": None, "font_list": "0x" + m.group(3),
                            "flags": int(m.group(4), 0), "x": int(m.group(5), 0), "y": int(m.group(6), 0),
                            "max_width": int(m.group(7), 0)})
            continue
        m = TABLE.search(line)
        if m:
            out.append({"text": "%s", "font": int(m.group(1), 0), "flags": int(m.group(2), 0),
                        "x": int(m.group(3), 0), "y": int(m.group(4), 0)})
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
    with open(EVENT_MAP, encoding="utf-8") as f:
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


FILL = re.compile(r"\b(?:FUN_000274c0|dmd_fill_rect)\([^,]+," + N + "," + N + "," + N + "," + N + ",0\)")
SPAWN = re.compile(r"\btask_spawn_child\((FUN_[0-9a-f]{8})\b")


def _display_functions(fn, funcs, names):
    """_reach of the deff function, then the display tasks it spawns (one level of their callees):
    deff 96 draws the deff 95 screen from FUN_01032a30 and spawns its "%luK" pop-ups."""
    addrs = _reach(fn, funcs, names)
    for name in SPAWN.findall("".join(funcs[fn])):
        if names.get(name) in funcs:
            addrs += [a for a in _reach(names[name], funcs, names, 1) if a not in addrs]
    return addrs


def effect_fills():
    """{deff: [(x0, y0, x1, y1), ...]} the black boxes a deff clears in the effect area (x 41-127) after
    drawing its bitmap and before its text (FUN_000274c0 / dmd_fill_rect with colour 0, corners
    inclusive), e.g. deff 95's band under ALL TARGETS=. Read from the deff's function, its callees and
    the display tasks it spawns (deff 96 draws the deff 95 screen from a child task)."""
    funcs, names = _functions()
    out = {}
    for deff_id, fn in _deff_functions():
        if fn not in funcs:
            continue
        addrs = _display_functions(fn, funcs, names)
        boxes = []
        for a in addrs:
            for line in funcs[a]:
                m = FILL.search(line)
                if m:
                    box = tuple(int(v, 0) for v in m.groups())
                    if box[0] >= 0x29 and box not in boxes:
                        boxes.append(box)
        if boxes:
            out[deff_id] = boxes
    return out


def deff_calls():
    """{deff: [call, ...]} in code order (the deff's own function first, then its callees)."""
    funcs, names = _functions()
    msgs = _messages(funcs)
    out = {}
    for deff_id, fn in _deff_functions():
        if fn in funcs:
            calls = []
            for addr in _display_functions(fn, funcs, names):
                calls += _calls(funcs[addr], msgs)
            out[deff_id] = calls
    return out


# Font lists of text_draw_msg_fit: the ROM data is not in the package; the fonts are the ones the
# reference captures show for these calls (by scripts/render_diff.py style matching).
FONT_LISTS = {"0x040d2834": [33], "0x040d2aa4": [15], "0x040d302c": [39], "0x040d31d4": [10, 6],
              "0x040d33a8": [11], "0x040d8a80": [12], "0x040d9194": [2]}
DEFAULT_LIST = [15, 12, 2]
# Per-language font tables (font = table[FUN_0000a3b4()], English = entry 0): not in the package; the
# font each reference capture shows for the call (every text dot of the capture matched, see
# tests/test_fonts.py). Without them these lines fell back to font 12 at a guessed row: the "n MORE"
# lines of deffs 66, 80 and 108 were drawn big over the effect.
FONT_TABLES = {"0x040d31bc": 2,     # deff 44 LEVEL %d COMPLETED
               "0x040d3238": 39,    # deff 63 IS LIT
               "0x040d3290": 39,    # deff 66 %d MORE TO / ADD BALL
               "0x040d2bec": 12,    # deff 78 %d FOLLOWING(S)
               "0x040d2ee8": 2,     # deff 80 TO LIGHT HURRY-UP
               "0x040d6f50": 4,     # deff 93 ZUSE / FAST SCORING
               "0x040d6f98": 34,    # deff 94 FAST SCORING (also in OVERRIDES)
               "0x040d6fdc": 39,    # deff 98 TIME / EXTENDED
               "0x040d700c": 3,     # deff 99 TOTAL:
               "0x040d39a8": 37,    # deffs 101-103 SKILL SHOT
               "0x040d32c4": 39,    # deff 108 %u MORE / TO ACCESS
               "0x040d2900": 39,    # deff 112 SUPER / POPS / DOUBLE / SCORING / SPINNERS
               "0x040d2918": 10}    # deff 112 SPINNERS SCORE
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
TICK_MS = 15.41      # ROM tick as the captures run (deff 19: 7-tick blink = 107.9 ms; deff 40: 6 ticks = 92 ms)
OVERRIDES = {38: {"MATCH": {"font": 37, "x": 127, "y": 7, "flags": 4, "source": "rom+capture",
                            "hide_after_frame": 30, "step_frames": 2,
                            "level_steps": [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15]},
                  "%,02lu": {"show_after_frame": 64}},
             # deff 40 (0x0100f604): "YOU'RE UP" drawn on every other 6-tick step
             40: {"YOU'RE UP": {"blink_ticks": 6}},
             # deff 94 (0x01032510): FAST SCORING in a font from table 0x040d6f98 (font 34 in the capture)
             # on frames where frame & 2 (frames of 4 ticks) for 24 frames, then a wipe and
             # FUN_010323d0's screen: SCORE in a fitted font (17) centred on the rows, ALL TARGETS above
             # and the points below in a font of table 0x040d6f8c (10) at palette level 4. Fonts and the
             # end of the wipe (1690 ms) read off the capture.
             94: {"FAST SCORING": {"font": 34, "x": 84, "y": 30, "flags": 2, "source": "rom+capture",
                                   "blink_ticks": 8, "show_after_ms": round(8 * TICK_MS),
                                   "hide_after_ms": round(96 * TICK_MS)},
                  "ALL TARGETS": {"font": 10, "x": 84, "y": 8, "flags": 2, "source": "rom+capture",
                                  "show_after_ms": 1690, "level_steps": [4], "step_ms": 10 ** 6},
                  "SCORE": {"font": 17, "x": 84, "y": 21, "flags": 2, "source": "rom+capture",
                            "show_after_ms": 1690},
                  "%,02lu POINTS": {"font": 10, "x": 84, "y": 30, "flags": 2, "source": "rom+capture",
                                    "show_after_ms": 1690, "level_steps": [4], "step_ms": 10 ** 6}},
             # deff 96 (0x01032bd0): each hit spawns FUN_01032900, which prints "%luK" (points / 1000) in
             # font 0x27 near the middle of the effect (random x 0x31-0x76, y 13-20) for 24 ticks while
             # it rises; drawn here centred at its middle row, without the random placement
             96: {"%luK": {"font": 39, "x": 84, "y": 17, "flags": 2, "source": "rom (position approximated)",
                           "hide_after_ms": round(24 * TICK_MS)}},
             # deffs 115-124 (deff_115, FUN_01027374 / FUN_01027478): the points are printed with the
             # palette palette_fill(0, 1, 15) every other 3-tick frame: the glyphs drawn black (blink_dark)
             **{d: {"%,02lu": {"blink_ticks": 3, "blink_dark": True}} for d in range(115, 125)},
             # deff 138 (0x01003c30): the combo count "%u" right-aligned at x 0x53, row 0x13, in font 0x2a on
             # frames where !(frame & 2), else in the outlined font 0x2b (frames of 3 ticks): two labels that
             # blink in turn
             138: {"%u": {"font": 42, "x": 83, "y": 19, "flags": 4, "source": "rom", "blink_ticks": 6,
                          "twin": {"font": 43, "show_after_ms": round(6 * TICK_MS)}}},
             # deff 55: the second rows picked into a variable (text_draw_msg(uVar8, ...) at y 0x20, font 0x21)
             55: {t: {"font": 33, "x": 84, "y": 32, "flags": 2, "source": "rom (message from the mode spec)"}
                  for t in ("ARE LIT", "LIGHT EX. BALL", "LIGHT M.B. + E.B.")}}
GRAPHICS_END = {38: 64}
# Effects that draw one of several screens on the same rows, picked by the deff's arguments (the event
# arg `screen`, tron/rom_text.gd): {deff: {line: screens it shows on}}; other lines show on every
# screen. Lines of different screens may overlap; the rules pass `screen`.
# deff 55 (0x0100461c), by its flags argument: 0 MULTIBALL + E.B. / ARE LIT, 1 EXTRA BALL / IS LIT,
#   2-4 %u MORE TO / LIGHT MULTIBALL, LIGHT EX. BALL or LIGHT M.B. + E.B., 5 MULTIBALL / IS LIT,
#   6 %u MORE TO alone
#   (messages 0x6d3, 0x6d6, 0x6d7 are picked into a variable; their text is from the mode spec)
# deff 60 (0x01005d44): 0 points / BALL ADDED (argument 0x34 = 0), 1 points higher / %u MORE FOR /
#   ADD-A-BALL
# deff 80 (0x01017230): 0 %d MORE / TO LIGHT HURRY-UP, 1 HURRY-UP / IS LIT (argument 0x38 set)
SCREENS = {55: {0: (0,), 1: (0,), 2: (1,), 3: (1,), 4: (2, 3, 4, 6), 5: (2,), 6: (3,), 7: (4,), 8: (5,), 9: (5,)},
           60: {0: (0,), 1: (0,), 2: (1,), 3: (1,), 4: (1,)},
           80: {0: (0,), 1: (0,), 2: (1,), 3: (1,)}}


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
    frames = json.load(open(path[0], encoding="utf-8"))["graphics_frames"] if path else []
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
        mine = mine[min(lines[:i].count(line), len(mine) - 1):] if mine else mine   # nth line = nth call
        if mine:
            c = calls[mine[0]]
            lay = {"x": c["x"], "y": c["y"], "flags": c["flags"], "source": "rom", "call": mine[0]}
            if c["font"] is None:
                lst = FONT_LISTS.get(c["font_list"], DEFAULT_LIST)
                lay.update(font=lst[0], fit_fonts=lst, fit_ys=[c["y"]] * len(lst), fit_width=c["max_width"])
            else:
                lay["font"] = c["font"]
            later = [k for k in mine[1:] if (calls[k]["x"], calls[k]["y"]) != (c["x"], c["y"])]
            twin = mine[0] + 1
            if later and later[0] == twin and calls[twin]["font"] == c["font"] and calls[twin]["y"] == c["y"]:
                # drawn twice in a row on the same row (deff 95's timer in both top corners): both show
                lay["twin"] = {"x": calls[twin]["x"], "flags": calls[twin]["flags"]}
                later = later[1:]
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
        if i in SCREENS.get(deff_id, {}):
            lay["screens"] = list(SCREENS[deff_id][i])
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
        call = lay.get("call")
        screens = set(lay.get("screens", ()))

        def overlaps(b):
            # an outlined font's lines drawn one after the other (LIGHT CYCLE / MULTIBALL / TOTAL:) share
            # their outline row: one dot of overlap is a stack, not a later screen of the effect
            # (also the rows of one screen of a SCREENS effect)
            e = 1 if font.get("outline") and ((call is not None and b[6] is not None and abs(call - b[6]) == 1)
                                              or (screens and b[7])) else 0
            return (box[0] + e <= b[2] and b[0] + e <= box[2] and box[1] + e <= b[3] and b[1] + e <= box[3]
                    and box[4] < b[5] and b[4] < box[5])
        if not any(overlaps(b) for b in boxes if not (screens and b[7] and not screens & b[7])):
            boxes.append(box + (call, screens))
            out[i] = lay
    return out
