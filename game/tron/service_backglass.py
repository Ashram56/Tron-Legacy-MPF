"""The service menu on the PuP backglass: what each service screen (tron/service.py) shows there.

The DMD keeps the ROM's screens (Screen.draw()); the backglass gets a second, larger view of the same screen,
drawn by game/pup/service_backglass.gd over a still of the PuP Pack's backglass art. Each screen class has a
backglass() method returning a dictionary (JSON-able), sent by ServiceMode.render() with every DMD refresh as
the BCP trigger "service_backglass" (tron/media_bridge.py); {"show": false} when the menu closes. Without a
backglass (PuP off, a DMD-only machine) nothing listens and nothing changes.

Every description has "show", "kind", "title", "path" (where the operator is) and "hints" (the buttons and what
they do); the kinds and their own keys:
- "entry": "lines";
- "menu": "items" [{text, icon, info, children}], "sel", "main" (the main menu draws tiles);
- "rows": a page of audits, "rows" [[number, name, value]], "sel" (index in the page), "page";
- "adjust": a page of adjustments, "rows" [{number, name, value, frac, default_frac, changed, factory}], "sel",
  "editing", "page";
- "switches": "mode" (test, active, alerts), "focus" (switch name or null), "active" [names], "lines";
- "lamps": "group", "number", "lit" [names lit now], "focus" [names of the group], "on";
- "coils": "list" [names], "sel", "fired" (the last one fired), "cycling", "flashers";
- "trough": "switches" [{name, active}];
- "message": "lines".
Device views ("switches", "lamps", "coils", "trough") carry "devices" when the screen opens: every switch, lamp and coil with its SAM
number, ROM name, matrix cell, playfield position (game/monitor/monitor.yaml, fractions of
game/monitor/playfield.jpg), insert colour (game/monitor/light_colors.csv), wire colours and pulse time.
"""
import csv
import os

from tron.hw_numbers import sam_number

PAGE = 14                       # audit rows per page
ADJUST_PAGE = 12                # adjustment rows per page
MONITOR = os.path.join("monitor", "monitor.yaml")
COLORS = os.path.join("monitor", "light_colors.csv")
WHITE = "#ffffff"

# the main menu's tiles: one line on what each entry holds
MAIN_INFO = {
    "GO TO DIAGNOSTICS MENU": "Switches, coils, lamps, trough, sound",
    "GO TO AUDITS MENU": "Earnings, standard and feature audits",
    "GO TO ADJUSTMENTS MENU": "Settings and display adjustments",
    "GO TO UTILITIES MENU": "Installs, resets, message, date",
    "GO TO TOURNAMENT MENU": "Tournament play",
    "GO TO REDEMPTION MENU": "Ticket dispenser",
    "EXIT SERVICE MENU": "Back to the attract mode",
}
# a screen item's line in the menus' preview panel
SCREEN_INFO = {
    "SWITCH TEST": "Last switch hit, on the playfield and the matrix",
    "ACTIVE SWITCH TEST": "Steps through every closed switch",
    "SWITCH ALERTS": "Switches not seen since power-on",
    "TECHNICIAN ALERTS": "Switches not seen since power-on",
    "SINGLE COIL TEST": "Fire one coil, see where it is and its wires",
    "CYCLING COIL TEST": "Every coil in turn, one per second",
    "SINGLE FLASH LAMP TEST": "Fire one flasher, see where it is",
    "CYCLING FLASH LAMP TEST": "Every flasher in turn, one per second",
    "SINGLE LAMP TEST": "Blink one lamp, see it on the playfield",
    "TEST ALL LAMPS": "Every lamp blinking",
    "LAMP ROW TEST": "One matrix row at a time",
    "LAMP COLUMN TEST": "One matrix column at a time",
    "BALL TROUGH TEST": "The trough switches; SELECT ejects a ball",
    "KNOCKER TEST": "Fire the knocker",
    "SOUND/SPEAKER TEST": "Play each sound call",
    "BEGIN BURN-IN": "Lamps and coils running until BACK",
    "DOT MATRIX TEST": "Full, blank and striped DMD pages",
    "EARNINGS AUDITS": "Credits, coins and earnings",
    "STANDARD AUDITS": "Games, balls, replays, high scores",
    "FEATURE AUDITS": "Tron's modes, multiballs and awards",
    "DUMP AUDITS TO USB": "Write every audit to a file",
    "STANDARD ADJUSTMENTS": "Pricing, replays, game settings",
    "FEATURE ADJUSTMENTS": "Tron's mode and difficulty settings",
    "DISPLAY ADJUSTMENTS": "HD text glow and size, PuP DMD size",
    "ENTER CUSTOM MESSAGE": "The attract mode's message",
    "SET CUSTOM PRICING": "Coin units and units per credit",
    "SET DATE/TIME": "The game's clock",
    "RETURN TO MAIN MENU": "Back to the main menu",
    "RETURN TO PREVIOUS MENU": "Back one menu",
    "EXIT SERVICE MENU": "Back to the attract mode",
    "DISPLAY HELP SCREEN": "What the buttons do",
}

MOVE = ["MINUS", "PLUS", "move"]
OPEN = ["SELECT", "open"]
BACK = ["BACK", "return"]
HINTS = {
    "entry": [["SELECT", "continue"], ["BACK", "leave"]],
    "menu": [MOVE, OPEN, BACK],
    "rows": [["MINUS", "PLUS", "scroll"], BACK],
    "adjust": [["MINUS", "PLUS", "scroll"], ["SELECT", "edit"], BACK],
    "adjust_edit": [["MINUS", "PLUS", "change"], ["SELECT", "save"], ["BACK", "cancel"]],
    "switches": [["hit any switch on the playfield"], BACK],
    "switches_list": [["MINUS", "PLUS", "step"], BACK],
    "lamps": [["MINUS", "PLUS", "next"], BACK],
    "coils": [["MINUS", "PLUS", "pick"], ["SELECT", "fire"], BACK],
    "coils_cycling": [["BACK", "stop"]],
    "trough": [["SELECT", "eject a ball"], BACK],
    "message": [["SELECT", "continue"], BACK],
}

_TABLES = {}


def _monitor(machine):
    """{"switch": {name: (x, y)}, "light": ..., "coil": ...} from the MPF Monitor layout."""
    path = os.path.join(machine.machine_path, MONITOR)
    if path not in _TABLES:
        spots = {}
        if os.path.exists(path):
            from ruamel.yaml import YAML
            with open(path, encoding="utf-8") as f:
                data = YAML(typ="safe").load(f) or {}
            for section, devices in data.items():
                if isinstance(devices, dict):
                    spots[section] = {name: (float(spot["x"]), float(spot["y"])) for name, spot in devices.items()
                                      if isinstance(spot, dict) and "x" in spot and "y" in spot}
        _TABLES[path] = spots
    return _TABLES[path]


def _colors(machine):
    path = os.path.join(machine.machine_path, COLORS)
    if path not in _TABLES:
        colors = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(line for line in f if not line.startswith("#")):
                    colors[row["light"]] = row["color"]
        _TABLES[path] = colors
    return _TABLES[path]


def _wires(machine):
    """{SAM coil number: (wire colour 1, wire colour 2, ROM test pulse ms)} from the ROM's coil table, the Pro's
    on a Pro (machine var machine_variant)."""
    from tron.settings import ROOT
    pro = machine.variables.get_machine_var("machine_variant") == "pro"
    path = os.path.join(ROOT, "assets", "rom_data", *(("pro", "coils_pro.csv") if pro else ("io", "coils.csv")))
    if path not in _TABLES:
        wires = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    wires[row["coil"]] = (row.get("wire_color_1", ""), row.get("wire_color_2", ""))
        _TABLES[path] = wires
    return _TABLES[path]


def matrix_cell(number):
    """[column, row] of SAM switch or lamp `number` in its 8-row matrix (Stern's numbering: n = 8 x (column - 1) +
    row), ["D", n] for a dedicated switch, None for anything else."""
    if number.isdigit() and int(number) > 0:
        n = int(number) - 1
        return [n // 8 + 1, n % 8 + 1]
    if number[:1] == "D" and number[1:].isdigit():
        return ["D", int(number[1:])]
    return None


def devices(svc):
    """Every switch, lamp and coil of the machine for the backglass views (the coin-door buttons left out)."""
    from tron.service import BUTTONS, flasher_names, rom_label
    machine = svc.machine
    spots = _monitor(machine)
    colors = _colors(machine)
    wires = _wires(machine)
    flash = set(flasher_names())

    def place(section, name):
        spot = spots.get(section, {}).get(name)
        return list(spot) if spot else None

    out = {"switches": {}, "lamps": {}, "coils": {}}
    for switch in machine.switches.values():
        if switch.name in BUTTONS:
            continue
        number = sam_number(switch)
        out["switches"][switch.name] = {"n": number, "label": rom_label(switch), "cell": matrix_cell(number),
                                        "at": place("switch", switch.name)}
    for light in machine.lights.values():
        number = sam_number(light)
        if not number.isdigit() or light.config.get("platform"):
            continue                              # the aux bus ramp tubes are not matrix lamps
        out["lamps"][light.name] = {"n": number, "label": rom_label(light), "cell": matrix_cell(number),
                                    "at": place("light", light.name), "color": colors.get(light.name, WHITE)}
    for coil in machine.coils.values():
        number = sam_number(coil)
        pair = wires.get(number, ("", ""))
        out["coils"][coil.name] = {"n": number, "label": rom_label(coil), "at": place("coil", coil.name),
                                   "wires": [w for w in pair if w], "pulse": _pulse_ms(coil),
                                   "flasher": coil.name in flash}
    return out


def _pulse_ms(coil):
    """The coil's pulse time in ms (the ROM's, game/config/rom/coil_times.yaml), None for a held coil."""
    try:
        return int(coil.get_and_verify_pulse_ms(None))
    except (AssertionError, AttributeError, TypeError, ValueError):
        return None


def path(svc):
    """Where the operator is: SERVICE, then the menus and the screen (the last three)."""
    titles = [s.title for s in svc.stack[1:] if s.title != "MAIN MENU"]
    return (["SERVICE"] + titles)[-3:]


def describe(svc, with_devices=True):
    """The backglass description of the screen on top of the service menu's stack. The device table goes
    with the first description of a device view (with_devices); the backglass keeps it for the refreshes."""
    screen = svc.stack[-1]
    state = screen.backglass()
    state.setdefault("title", screen.title)
    state.setdefault("hints", HINTS.get(state["kind"], HINTS["message"]))
    state["show"] = True
    state["path"] = path(svc)
    if with_devices and state["kind"] in ("switches", "lamps", "coils", "trough"):
        state["devices"] = devices(svc)
    return state


def menu_state(screen, items, sel):
    """A menu: every item with its ROM icon, the main menu's line on it, and what it opens."""
    from tron.service import item_icon, menu_numbers
    from tron.settings import service_data
    menus = service_data()["menus"]
    numbers = menu_numbers()
    out = []
    for item in items:
        entry = {"text": item["text"], "icon": item_icon(item), "info": MAIN_INFO.get(item["text"], ""),
                 "children": []}
        if item["kind"] == "submenu":
            child = [i for i in menus.get(numbers.get(item["submenu"], ""), [])
                     if screen.svc.visible(i) and i["kind"] not in ("back", "exit", "help")]
            entry["children"] = [[i["text"], SCREEN_INFO.get(i["text"], "")] for i in child]
        else:
            entry["info"] = entry["info"] or SCREEN_INFO.get(item["text"], "")
        out.append(entry)
    return {"kind": "menu", "items": out, "sel": sel, "main": screen.title == "MAIN MENU"}


def page_of(pos, count, size):
    """(first index, last index + 1) of the page holding `pos`."""
    first = pos // size * size
    return first, min(count, first + size)


def active_switches(machine):
    """Names of the closed switches (the coin-door buttons left out)."""
    from tron.service import BUTTONS
    sc = machine.switch_controller
    return [s.name for s in machine.switches.values() if s.name not in BUTTONS and sc.is_active(s)]


def switches_state(screen, mode, focus, lines):
    return {"kind": "switches", "mode": mode, "focus": focus, "active": active_switches(screen.machine),
            "lines": lines[1:], "hints": HINTS["switches" if mode == "test" else "switches_list"]}


def audits_state(screen):
    """A page of audits around the one the DMD shows."""
    audits = screen.os.audits
    numbers = screen.numbers
    if not numbers:
        return {"kind": "message", "lines": ["NONE"]}
    first, last = page_of(screen.pos % len(numbers), len(numbers), PAGE)
    rows = [[n, audits.info[n]["name"], audits.text(n)] for n in numbers[first:last]]
    return {"kind": "rows", "rows": rows, "sel": screen.pos % len(numbers) - first,
            "page": [first + 1, last, len(numbers)]}


def adjust_state(screen):
    """A page of adjustments: value, where it sits in its range, the factory default, the one being edited."""
    adj = screen.adj
    numbers = screen.numbers
    pos = screen.pos % len(numbers)
    first, last = page_of(pos, len(numbers), ADJUST_PAGE)
    rows = []
    for k, num in enumerate(numbers[first:last]):
        info = adj.info[num]
        value = screen.editing if screen.editing is not None and first + k == pos else adj[num]
        lo, hi = info.get("min", 0), info.get("max", 0)

        def frac(v):
            return max(0.0, min(1.0, (v - lo) / (hi - lo))) if hi > lo else None
        rows.append({"number": num, "name": info["name"], "value": adj.label(num, value), "frac": frac(value),
                     "default_frac": frac(adj.default(num)), "changed": value != adj.default(num),
                     "factory": adj.label(num, adj.default(num))})
    editing = screen.editing is not None
    return {"kind": "adjust", "rows": rows, "sel": pos - first, "editing": editing,
            "page": [first + 1, last, len(numbers)], "hints": HINTS["adjust_edit" if editing else "adjust"]}


def coils_state(screen):
    coils = screen.coils
    return {"kind": "coils", "list": [c.name for c in coils], "sel": screen.pos % len(coils) if coils else 0,
            "fired": screen.fired[-1] if screen.fired else None, "cycling": screen.cycling,
            "flashers": "FLASH" in screen.title, "hints": HINTS["coils_cycling" if screen.cycling else "coils"]}


def lamps_state(screen):
    entry = screen.current()
    label, lights = entry[0], entry[1]
    number = entry[2] if len(entry) > 2 else ""
    return {"kind": "lamps", "group": label, "number": number, "focus": [lt.name for lt in lights],
            "lit": [lt.name for lt in screen.lit], "on": screen.on,
            "position": [screen.pos % len(screen.groups) + 1, len(screen.groups)]}


def trough_state(screen, names):
    sc = screen.machine.switch_controller
    switches = screen.machine.switches
    return {"kind": "trough", "switches": [{"name": n, "active": sc.is_active(switches[n])}
                                           for n in names if n in switches]}
