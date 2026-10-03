"""The operator service menu of Tron Legacy LE 1.74 (assets/mpf_package/service_menu.md / .json), as the MPF
mode "tron_service" (game/modes/tron_service).

The coin-door buttons drive it: SELECT enters it from attract mode and opens an item, MINUS / PLUS move or
change a value, BACK leaves. The tree, item texts and visibility conditions are the ROM's own tables
(service_menu.json); every menu ends with its return item, EXIT SERVICE MENU and DISPLAY HELP SCREEN.
The screens operate the hardware through MPF (switch, coil, flash lamp, lamp, trough, knocker, sound and
motor tests), show and reset the persistent audits, edit the 88 adjustments (MPF settings, persisted),
run the install presets and resets, and set the date and time. Text goes to the DMD through the generic
service slide (game/slides/service.tscn, MediaBridge.service_show) and to the MPF event
"tron_service_display" (line0-line2), which the tests read.
"""
import datetime
import os

from mpf.core.mode import Mode

from tron.settings import service_data

BUTTONS = {"s_service_back": "back", "s_service_minus": "minus", "s_service_plus": "plus",
           "s_service_select": "select"}
# the menus' "shown_only_if" condition functions [ROM addresses]
CYCLE_SECONDS = 1.0          # cycling coil / flash lamp tests: one output per second
BLINK_SECONDS = 0.5          # lamp tests blink
CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?.,'-&"
CUSTOM_MESSAGE_LEN = 16
CUSTOM_PRICING_MAX = 10
LOCK_KEY = "service"
LIGHT_PRIORITY = 1000000


def hw_number(device):
    """Sort key: the device's SAM number (dedicated "D" numbers after the matrix)."""
    number = str(device.config.get("number", ""))
    return (1, int(number[1:])) if number[1:].isdigit() and number[0] == "D" else (
        (0, int(number)) if number.isdigit() else (2, 0))


def persist_var(machine, name, value):
    """A machine var saved to MPF's machine_vars data file."""
    machine.variables.configure_machine_var(name, persist=True)
    machine.variables.set_machine_var(name, value)


def menu_numbers():
    """{menu number: menu name}: the json lists the menus in the ROM's number order, MAIN MENU = 1."""
    return {i + 1: name for i, name in enumerate(service_data()["menus"])}


class Screen:
    """One service screen. button(name) handles a button, lines() returns the text (up to 3 lines)."""

    def __init__(self, svc, title):
        self.svc = svc
        self.os = svc.os
        self.machine = svc.machine
        self.title = title

    def enter(self):
        pass

    def leave(self):
        pass

    def button(self, name):
        if name == "back":
            self.svc.pop()

    def refresh(self):
        self.svc.render()


class MenuScreen(Screen):
    """A ROM menu: MINUS / PLUS move through the visible items, SELECT opens one, BACK goes up."""

    def __init__(self, svc, name):
        super().__init__(svc, name)
        self.pos = 0

    def items(self):
        items = [i for i in service_data()["menus"][self.title] if self.svc.visible(i)]
        # the game adds its items (GAME-SPECIFIC TESTS) at run time: the tail items stay last
        tail = [i for i in items if i["kind"] in ("back", "exit", "help")]
        return [i for i in items if i not in tail] + tail

    def lines(self):
        items = self.items()
        self.pos %= len(items)
        return [self.title, items[self.pos]["text"], "{} OF {}".format(self.pos + 1, len(items))]

    def button(self, name):
        items = self.items()
        if name == "back":
            self.svc.pop()
        elif name in ("minus", "plus"):
            self.pos = (self.pos + (1 if name == "plus" else -1)) % len(items)
            self.refresh()
        elif name == "select":
            self.svc.open_item(items[self.pos % len(items)])


class MessageScreen(Screen):
    def __init__(self, svc, title, *text):
        super().__init__(svc, title)
        self.text = list(text)

    def lines(self):
        return [self.title] + self.text


class HelpScreen(MessageScreen):
    def __init__(self, svc):
        super().__init__(svc, "HELP", "SELECT=ENTER  BACK=EXIT", "MINUS/PLUS=MOVE/CHANGE")


class ListScreen(Screen):
    """MINUS / PLUS scroll a list of entries; subclasses define entries() and entry_lines()."""

    def __init__(self, svc, title):
        super().__init__(svc, title)
        self.pos = 0

    def current(self):
        entries = self.entries()
        if not entries:
            return None
        self.pos %= len(entries)
        return entries[self.pos]

    def lines(self):
        entry = self.current()
        return [self.title] + (self.entry_lines(entry) if entry is not None else ["NONE"])

    def move(self, step):
        n = len(self.entries())
        if n:
            self.pos = (self.pos + step) % n
            self.moved()
        self.refresh()

    def moved(self):
        pass

    def button(self, name):
        if name == "minus":
            self.move(-1)
        elif name == "plus":
            self.move(1)
        else:
            super().button(name)


# ---------------------------------------------------------------------------------------------- switches

class SwitchTestScreen(Screen):
    """SWITCH TEST: the last switch that changed, with its number and state."""

    def __init__(self, svc):
        super().__init__(svc, "SWITCH TEST")
        self.last = None

    def enter(self):
        self.machine.switch_controller.add_monitor(self._changed)

    def leave(self):
        self.machine.switch_controller.remove_monitor(self._changed)

    def _changed(self, change):
        if change.name in BUTTONS:
            return
        self.last = (change.name, change.num, change.state)
        self.refresh()

    def lines(self):
        if not self.last:
            return [self.title, "ACTIVATE A SWITCH"]
        name, num, state = self.last
        return [self.title, "{} {}".format(num, name.upper()[2:]), "CLOSED" if state else "OPEN"]


class ActiveSwitchScreen(ListScreen):
    """ACTIVE SWITCH TEST: the switches that are closed now."""

    def __init__(self, svc):
        super().__init__(svc, "ACTIVE SWITCH TEST")

    def entries(self):
        sc = self.machine.switch_controller
        return [s for s in sorted(self.machine.switches.values(), key=lambda s: s.name)
                if sc.is_active(s) and s.name not in BUTTONS]

    def entry_lines(self, entry):
        return ["{} {}".format(entry.config["number"], entry.name.upper()[2:]),
                "{} OF {}".format(self.pos + 1, len(self.entries()))]


class SwitchAlertsScreen(ListScreen):
    """SWITCH ALERTS / TECHNICIAN ALERTS: playfield switches never seen active since power-on."""

    def __init__(self, svc, title="SWITCH ALERTS"):
        super().__init__(svc, title)

    def entries(self):
        return [s for s in sorted(self.machine.switches.values(), key=lambda s: s.name)
                if s.name.startswith("s_") and s.name not in BUTTONS and s.last_change < 0
                and not self.machine.switch_controller.is_active(s)]

    def lines(self):
        entries = self.entries()
        if not entries:
            return [self.title, "NO ALERTS"]
        return super().lines()

    def entry_lines(self, entry):
        return ["{} NOT ACTIVE".format(entry.name.upper()[2:]), "{} OF {}".format(self.pos + 1, len(self.entries()))]


# ---------------------------------------------------------------------------------------------- coils, lamps

class CoilTestScreen(ListScreen):
    """SINGLE COIL / SINGLE FLASH LAMP TEST: MINUS / PLUS pick, SELECT fires. The cycling variants fire
    each output in turn, CYCLE_SECONDS apart."""

    def __init__(self, svc, title, coils, cycling=False):
        super().__init__(svc, title)
        self.coils = coils
        self.cycling = cycling
        self.handle = None
        self.fired = []

    def entries(self):
        return self.coils

    def entry_lines(self, entry):
        return ["{} {}".format(entry.config["number"], entry.name.upper()[2:]),
                "CYCLING" if self.cycling else "PRESS SELECT TO FIRE"]

    def enter(self):
        if self.cycling:
            self._cycle()

    def leave(self):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
            self.handle = None

    def fire(self, coil):
        coil.pulse()
        self.fired.append(coil.name)

    def _cycle(self):
        self.fire(self.current())
        self.refresh()
        self.pos += 1
        self.handle = self.machine.clock.schedule_once(self._cycle, CYCLE_SECONDS)

    def button(self, name):
        if name == "select" and not self.cycling:
            self.fire(self.current())
        else:
            super().button(name)


class LampTestScreen(ListScreen):
    """SINGLE LAMP TEST (one lamp), TEST ALL LAMPS, LAMP ROW / COLUMN TEST (one row or column of the SAM
    8 x 10 lamp matrix): the lamps blink at the service priority over everything else."""

    def __init__(self, svc, title, groups):
        super().__init__(svc, title)
        self.groups = groups          # [(label, [lights])]
        self.lit = []
        self.on = False
        self.handle = None

    def entries(self):
        return self.groups

    def entry_lines(self, entry):
        return [entry[0], "{} OF {}".format(self.pos + 1, len(self.groups))]

    def enter(self):
        self._blink()

    def moved(self):
        self._clear()

    def _clear(self):
        for light in self.lit:
            light.remove_from_stack_by_key(LOCK_KEY)
        self.lit = []

    def _blink(self):
        self.on = not self.on
        self._clear()
        if self.on:
            for light in self.current()[1]:
                light.color("white", key=LOCK_KEY, priority=LIGHT_PRIORITY)
                self.lit.append(light)
        self.handle = self.machine.clock.schedule_once(self._blink, BLINK_SECONDS)

    def leave(self):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
            self.handle = None
        self._clear()


class TroughTestScreen(Screen):
    """BALL TROUGH TEST: the four trough switches; SELECT ejects one ball to the shooter lane."""

    def __init__(self, svc):
        super().__init__(svc, "BALL TROUGH TEST")

    def lines(self):
        sc = self.machine.switch_controller
        names = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")
        states = " ".join("X" if sc.is_active(self.machine.switches[n]) else "-" for n in names)
        return [self.title, "TROUGH 1-4: " + states, "SELECT=EJECT"]

    def button(self, name):
        if name == "select":
            self.machine.ball_devices["bd_trough"].eject()
            self.refresh()
        else:
            super().button(name)


class ActionScreen(Screen):
    """A screen where SELECT runs one action (knocker test, installs, resets): it then shows `done`."""

    def __init__(self, svc, title, prompt, action, done="DONE"):
        super().__init__(svc, title)
        self.prompt, self.action, self.done_text = prompt, action, done
        self.done = False

    def lines(self):
        return [self.title, self.done_text if self.done else self.prompt]

    def button(self, name):
        if name == "select":
            self.action()
            self.done = True
            self.refresh()
        else:
            super().button(name)


class SoundTestScreen(ListScreen):
    """SOUND/SPEAKER TEST: MINUS / PLUS pick a sound call, SELECT plays it."""

    def __init__(self, svc):
        super().__init__(svc, "SOUND/SPEAKER TEST")
        data = self.os.media.data
        self.calls = sorted(data["pools"]) if data else list(range(0x009, 0x1d0))
        self.played = []

    def entries(self):
        return self.calls

    def entry_lines(self, entry):
        return ["SOUND {:03X}".format(entry), "PRESS SELECT TO PLAY"]

    def button(self, name):
        if name == "select":
            self.os.sound(self.current())
            self.played.append(self.current())
        else:
            super().button(name)


class BurnInScreen(Screen):
    """BEGIN BURN-IN: lamp effect 8 and every coil in turn until BACK; shows the cycles run."""

    def __init__(self, svc):
        super().__init__(svc, "BURN-IN")
        self.cycles = 0
        self.handle = None
        self.coils = svc.coils(flashers=None)

    def enter(self):
        self.os.leff_start(8)
        self._step()

    def _step(self):
        coil = self.coils[self.cycles % len(self.coils)]
        coil.pulse()
        self.cycles += 1
        self.refresh()
        self.handle = self.machine.clock.schedule_once(self._step, CYCLE_SECONDS)

    def leave(self):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
        self.os.leff_stop(8)

    def lines(self):
        return [self.title, "CYCLES {}".format(self.cycles)]


class DotMatrixScreen(ListScreen):
    """DOT MATRIX TEST: full, blank and striped pages; MINUS / PLUS step."""

    PAGES = (("ALL DOTS ON", "#" * 21), ("ALL DOTS OFF", ""), ("STRIPES", "# " * 10 + "#"))

    def __init__(self, svc):
        super().__init__(svc, "DOT MATRIX TEST")

    def entries(self):
        return list(self.PAGES)

    def entry_lines(self, entry):
        return [entry[0], entry[1]]


class MotorTestScreen(Screen):
    """GAME-SPECIFIC TESTS: SELECT starts / stops a motor coil (and MINUS / PLUS the disc direction relay);
    the position switches are shown."""

    def __init__(self, svc, title, coils, switches, direction=None):
        super().__init__(svc, title)
        self.coils = [self.machine.coils[c] for c in coils]
        self.switches = switches
        self.direction = self.machine.coils[direction] if direction else None
        self.running = False
        self.reverse = False

    def lines(self):
        sc = self.machine.switch_controller
        sw = " ".join("{}:{}".format(n.upper()[2:].replace("_MOTOR", ""), "X" if sc.is_active(
            self.machine.switches[n]) else "-") for n in self.switches)
        state = ("RUNNING" if self.running else "STOPPED") + (" REVERSE" if self.reverse else "")
        return [self.title, state, sw]

    def _set(self, on):
        self.running = on
        for coil in self.coils:
            coil.enable() if on else coil.disable()

    def button(self, name):
        if name == "select":
            self._set(not self.running)
            self.refresh()
        elif name in ("minus", "plus") and self.direction:
            self.reverse = name == "minus"
            self.direction.enable() if self.reverse else self.direction.disable()
            self.refresh()
        else:
            super().button(name)

    def leave(self):
        self._set(False)
        if self.direction:
            self.direction.disable()


class TubeTestScreen(Screen):
    """FIBER OPTIC LIGHT TUBE TEST (ROM 0x1012b50): the two ramp tubes cycle through the attract colour
    shows (tube shows 2-9), one every second."""

    SHOWS = tuple(range(2, 10))

    def __init__(self, svc):
        super().__init__(svc, "FIBER OPTIC TUBE TEST")
        self.index = 0
        self.handle = None

    def enter(self):
        self._step()

    def _step(self):
        self.os.tube_stop(self.SHOWS[self.index % len(self.SHOWS)])
        self.index += 1
        self.os.tube_start(self.SHOWS[self.index % len(self.SHOWS)])
        self.refresh()
        self.handle = self.machine.clock.schedule_once(self._step, CYCLE_SECONDS)

    def leave(self):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
        self.os.tube_stop(self.SHOWS[self.index % len(self.SHOWS)])

    def lines(self):
        return [self.title, "TUBE SHOW {}".format(self.SHOWS[self.index % len(self.SHOWS)])]


# ---------------------------------------------------------------------------------------------- audits

class AuditScreen(ListScreen):
    """EARNINGS / STANDARD / FEATURE AUDITS: one audit per page, number, ROM name and value."""

    def __init__(self, svc, title, group):
        super().__init__(svc, title)
        self.numbers = self.os.audits.menu(group)

    def entries(self):
        return self.numbers

    def entry_lines(self, number):
        audits = self.os.audits
        return ["{:02d} {}".format(number, audits.info[number]["name"]), audits.text(number)]


def dump_audits(os_, path):
    """DUMP AUDITS TO USB: every audit as "number name value" lines (the USB stick is the data folder)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for number in sorted(os_.audits.info):
            f.write("{:3d} {:34s} {}\n".format(number, os_.audits.info[number]["name"], os_.audits.text(number)))
    return path


# ---------------------------------------------------------------------------------------------- adjustments

class AdjustmentScreen(ListScreen):
    """STANDARD / FEATURE ADJUSTMENTS: MINUS / PLUS scroll; SELECT edits, MINUS / PLUS change the value by
    the ROM step, SELECT stores it (MPF setting, persisted), BACK drops the change."""

    def __init__(self, svc, title, group):
        super().__init__(svc, title)
        self.numbers = self.os.adj.menu(group)
        self.editing = None

    def entries(self):
        return self.numbers

    def entry_lines(self, num):
        adj = self.os.adj
        value = adj[num] if self.editing is None else self.editing
        mark = " (FACTORY)" if value == adj.default(num) else ""
        edit = "> " if self.editing is not None else ""      # the value being edited
        return ["{:02d} {}".format(num, adj.info[num]["name"]), edit + adj.label(num, value) + mark]

    def button(self, name):
        num = self.current()
        if self.editing is None:
            if name == "select":
                self.editing = self.os.adj[num]
                self.refresh()
            else:
                super().button(name)
            return
        if name in ("minus", "plus"):
            self.editing = self.os.adj.step(num, self.editing, 1 if name == "plus" else -1)
        elif name == "select":
            self.os.adj[num] = self.editing
            self.editing = None
        elif name == "back":
            self.editing = None
        self.refresh()


# ---------------------------------------------------------------------------------------------- utilities

class CustomMessageScreen(Screen):
    """ENTER CUSTOM MESSAGE: MINUS / PLUS change the letter, SELECT goes to the next one and stores the
    message after the last (machine var custom_message_text, persisted); BACK leaves without storing."""

    def __init__(self, svc):
        super().__init__(svc, "ENTER CUSTOM MESSAGE")
        old = self.machine.variables.get_machine_var("custom_message_text") or ""
        self.text = list(old.ljust(CUSTOM_MESSAGE_LEN)[:CUSTOM_MESSAGE_LEN])
        self.cursor = 0

    def lines(self):
        marker = " " * self.cursor + "^"
        return [self.title, "".join(self.text), marker]

    def button(self, name):
        if name in ("minus", "plus"):
            ch = self.text[self.cursor]
            i = CHARSET.index(ch) if ch in CHARSET else 0
            self.text[self.cursor] = CHARSET[(i + (1 if name == "plus" else -1)) % len(CHARSET)]
        elif name == "select":
            self.cursor += 1
            if self.cursor >= CUSTOM_MESSAGE_LEN:
                persist_var(self.machine, "custom_message_text", "".join(self.text).rstrip())
                self.svc.pop()
                return
        else:
            super().button(name)
            return
        self.refresh()


class CustomPricingScreen(Screen):
    """SET CUSTOM PRICING: the CUSTOM pricing (adj 28 = 64, tron/credits.py) as coin units of the coin slot and
    units per credit (machine vars custom_coin_units, custom_units_per_credit, persisted). SELECT steps to the
    next value and stores both after the last one and sets adj 28 to CUSTOM; MINUS / PLUS change the value.
    The ROM's own editor is not in the decompile."""

    FIELDS = (("COIN UNITS", "custom_coin_units", 1), ("UNITS PER CREDIT", "custom_units_per_credit", 3))

    def __init__(self, svc):
        super().__init__(svc, "SET CUSTOM PRICING")
        var = self.machine.variables.get_machine_var
        self.values = [int(var(key) or default) for _, key, default in self.FIELDS]
        self.field = 0

    def lines(self):
        return [self.title, self.FIELDS[self.field][0], "> {}".format(self.values[self.field])]

    def button(self, name):
        if name in ("minus", "plus"):
            v = self.values[self.field] + (1 if name == "plus" else -1)
            self.values[self.field] = min(CUSTOM_PRICING_MAX, max(1, v))
        elif name == "select":
            self.field += 1
            if self.field == len(self.FIELDS):
                for (_, key, _), value in zip(self.FIELDS, self.values):
                    persist_var(self.machine, key, value)
                self.os.adj[28] = 64
                self.svc.pop()
                return
        else:
            super().button(name)
            return
        self.refresh()


def clock_now(machine):
    """The game clock: the host clock plus the operator's SET DATE/TIME offset (machine var clock_offset)."""
    offset = machine.variables.get_machine_var("clock_offset") or 0
    return datetime.datetime.now() + datetime.timedelta(seconds=offset)


def clock_text(machine, when, time_format):
    """Date and time as the ROM shows them: adj 3 TIME FORMAT 0 = 12-HOUR, 1 = 24-HOUR."""
    if time_format == 1:
        clock = when.strftime("%H:%M")
    else:
        clock = "{}:{:02d} {}".format(when.hour % 12 or 12, when.minute, "PM" if when.hour >= 12 else "AM")
    return when.strftime("%Y-%m-%d"), clock


class DateTimeScreen(Screen):
    """SET DATE/TIME: SELECT steps through year, month, day, hour, minute (MINUS / PLUS change the field)
    and stores the clock offset after the minutes."""

    FIELDS = ("YEAR", "MONTH", "DAY", "HOUR", "MINUTE")

    def __init__(self, svc):
        super().__init__(svc, "SET DATE/TIME")
        self.when = clock_now(self.machine).replace(second=0, microsecond=0)
        self.field = 0

    def lines(self):
        date, clock = clock_text(self.machine, self.when, self.os.adj[3])
        return ["SET " + self.FIELDS[self.field], date, clock]

    def _change(self, step):
        w = self.when
        field = self.FIELDS[self.field]
        if field == "YEAR":
            w = w.replace(year=min(2099, max(2000, w.year + step)))
        elif field == "MONTH":
            w = w.replace(month=(w.month - 1 + step) % 12 + 1, day=min(w.day, 28))
        elif field == "DAY":
            w = w + datetime.timedelta(days=step)
        elif field == "HOUR":
            w = w + datetime.timedelta(hours=step)
        else:
            w = w + datetime.timedelta(minutes=step)
        self.when = w

    def button(self, name):
        if name in ("minus", "plus"):
            self._change(1 if name == "plus" else -1)
        elif name == "select":
            self.field += 1
            if self.field == len(self.FIELDS):
                offset = int((self.when - datetime.datetime.now()).total_seconds())
                persist_var(self.machine, "clock_offset", offset)
                self.svc.pop()
                return
        else:
            super().button(name)
            return
        self.refresh()


# ---------------------------------------------------------------------------------------------- the mode

class ServiceMode(Mode):
    """MPF mode tron_service: the menu stack, the coin-door buttons and the display."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stack = []
        self.handlers = []
        self.lines = []
        self.dump_path = os.path.join(self.machine.machine_path, "data", "audit_dump.txt")

    @property
    def os(self):
        return self.machine.tron

    def mode_start(self, **kwargs):
        os_ = self.os
        os_.in_service = True
        attract = os_.features_by_name.get("attract")
        if attract:
            attract.stop()                        # the ROM's attract pages and lamp show stop
        os_.deff_stop(1)
        os_.leff_stop(1)
        if self.machine.modes["attract"].active:
            self.machine.modes["attract"].stop()  # no game start from the service menu
        sc = self.machine.switch_controller
        for name, button in BUTTONS.items():
            self.handlers.append(sc.add_switch_handler(name, self._button, callback_kwargs={"name": button}))
        self.stack = []
        self.push(MenuScreen(self, "MAIN MENU"))
        self.machine.events.post("tron_service_entered")

    def mode_stop(self, **kwargs):
        while self.stack:
            self.stack.pop().leave()
        for handler in self.handlers:
            self.machine.switch_controller.remove_switch_handler_by_key(handler)
        self.handlers = []
        os_ = self.os
        os_.in_service = False
        os_.media.service_hide()
        self.machine.events.post("tron_service_exited")
        if not self.machine.modes["attract"].active:
            self.machine.modes["attract"].start()
        os_.hook("attract_start")                 # event 0x08: attract pages and lamp show again

    # ------------------------------------------------------------------ navigation

    def _button(self, name):
        if self.stack:
            self.stack[-1].button(name)

    def push(self, screen):
        self.stack.append(screen)
        screen.enter()
        self.render()

    def pop(self):
        self.stack.pop().leave()
        if not self.stack:
            self.stop()
            return
        self.render()

    def exit(self):
        self.stop()

    def render(self):
        lines = (self.stack[-1].lines() + ["", "", ""])[:3]
        self.lines = lines
        self.os.media.service_show(lines)
        self.machine.events.post("tron_service_display", line0=lines[0], line1=lines[1], line2=lines[2])

    def visible(self, item):
        """The ROM's shown_only_if conditions for the menu items."""
        cond = item.get("shown_only_if")
        if not cond:
            return True
        adj = self.os.adj
        redemption = adj[45] != 0                 # a ticket dispenser is configured
        return {
            "0x2ffc0": False,                     # tournament mode available: no tournament system here
            "0x30078": False, "0x3005c": False, "0x30034": False,
            "0x101298c": redemption,
            "0x30004": redemption, "0x2ffec": redemption, "0x2ffd4": redemption, "0x3001c": redemption,
            "0x32e7c": False,                     # DISPLAY SOFTWARE ERRORS: no errors logged
        }.get(cond, False)

    def open_item(self, item):
        kind, text = item["kind"], item["text"]
        if kind == "submenu":
            self.push(MenuScreen(self, menu_numbers()[item["submenu"]]))
        elif kind == "back":
            self.pop()
        elif kind == "exit":
            self.exit()
        elif kind == "help":
            self.push(HelpScreen(self))
        else:
            self.push(self.screen_for(text))

    # ------------------------------------------------------------------ hardware lists

    def coils(self, flashers=False):
        """The ROM's coils (flashers=False), flash lamps (True) or both (None), by driver number."""
        flash = set(flasher_names())
        coils = [c for c in self.machine.coils.values()
                 if flashers is None or (c.name in flash) == bool(flashers)]
        return sorted(coils, key=lambda c: hw_number(c))

    def lamp_groups(self, how):
        lights = sorted((light for light in self.machine.lights.values() if str(light.config.get("number", ""))
                         .isdigit()), key=lambda light: int(light.config["number"]))
        if how == "single":
            return [("{} {}".format(lt.config["number"], lt.name.upper()[2:]), [lt]) for lt in lights]
        if how == "all":
            return [("ALL LAMPS", lights)]
        groups = {}
        for light in lights:
            n = int(light.config["number"]) - 1
            key = n // 8 + 1 if how == "column" else n % 8 + 1
            groups.setdefault(key, []).append(light)
        return [("{} {}".format(how.upper(), k), v) for k, v in sorted(groups.items())]

    # ------------------------------------------------------------------ screens by item text

    def screen_for(self, text):
        os_ = self.os
        adj, audits = os_.adj, os_.audits
        if text.startswith("INSTALL ") and text in service_data()["install_presets"] or text == "INSTALL FACTORY":
            return ActionScreen(self, text, "PRESS SELECT TO INSTALL", lambda: adj.install(text), "INSTALLED")
        resets = {
            "RESET COIN AUDITS": audits.reset_coin,
            "RESET GAME AUDITS": audits.reset_game,
            "RESET GRAND CHAMPION": lambda: self.reset_high_scores(1),
            "RESET HIGH SCORES": lambda: self.reset_high_scores(2),
            "RESET CREDITS": self.reset_credits,
            "RESET FACTORY SETTINGS": self.factory_reset,
        }
        if text in resets:
            return ActionScreen(self, text, "PRESS SELECT TO RESET", resets[text])
        screens = {
            "SWITCH TEST": lambda: SwitchTestScreen(self),
            "ACTIVE SWITCH TEST": lambda: ActiveSwitchScreen(self),
            "SWITCH ALERTS": lambda: SwitchAlertsScreen(self),
            "TECHNICIAN ALERTS": lambda: SwitchAlertsScreen(self, "TECHNICIAN ALERTS"),
            "SINGLE COIL TEST": lambda: CoilTestScreen(self, text, self.coils()),
            "CYCLING COIL TEST": lambda: CoilTestScreen(self, text, self.coils(), cycling=True),
            "SINGLE FLASH LAMP TEST": lambda: CoilTestScreen(self, text, self.coils(True)),
            "CYCLING FLASH LAMP TEST": lambda: CoilTestScreen(self, text, self.coils(True), cycling=True),
            "SINGLE LAMP TEST": lambda: LampTestScreen(self, text, self.lamp_groups("single")),
            "TEST ALL LAMPS": lambda: LampTestScreen(self, text, self.lamp_groups("all")),
            "LAMP ROW TEST": lambda: LampTestScreen(self, text, self.lamp_groups("row")),
            "LAMP COLUMN TEST": lambda: LampTestScreen(self, text, self.lamp_groups("column")),
            "BALL TROUGH TEST": lambda: TroughTestScreen(self),
            "KNOCKER TEST": lambda: ActionScreen(self, text, "PRESS SELECT", lambda: os_.knock(forced=True),
                                                 "KNOCK"),
            "SOUND/SPEAKER TEST": lambda: SoundTestScreen(self),
            "BEGIN BURN-IN": lambda: BurnInScreen(self),
            "DOT MATRIX TEST": lambda: DotMatrixScreen(self),
            "3-BANK MOTOR TEST": lambda: MotorTestScreen(self, text, ["c_recognizer_3_bank_motor_relay"],
                                                         ["s_3_bank_motor_up", "s_3_bank_motor_dn"]),
            "DISC MOTOR TEST": lambda: MotorTestScreen(self, text, ["c_disc_motor_power", "c_disc_motor_relay"],
                                                       [], direction="c_disc_direction_relay"),
            "RECOGNIZER MOTOR TEST": lambda: MotorTestScreen(
                self, text, ["c_recognizer_motor_relay"],
                ["s_recog_motor_pos_1", "s_recog_motor_pos_2", "s_recog_motor_pos_3"]),
            "FIBER OPTIC LIGHT TUBE TEST": lambda: TubeTestScreen(self),
            "EARNINGS AUDITS": lambda: AuditScreen(self, text, "earnings"),
            "STANDARD AUDITS": lambda: AuditScreen(self, text, "standard"),
            "FEATURE AUDITS": lambda: AuditScreen(self, text, "feature"),
            "DUMP AUDITS TO USB": lambda: ActionScreen(self, text, "PRESS SELECT TO DUMP",
                                                       lambda: dump_audits(os_, self.dump_path), "AUDITS SAVED"),
            "STANDARD ADJUSTMENTS": lambda: AdjustmentScreen(self, text, "standard"),
            "FEATURE ADJUSTMENTS": lambda: AdjustmentScreen(self, text, "feature"),
            "ENTER CUSTOM MESSAGE": lambda: CustomMessageScreen(self),
            "SET DATE/TIME": lambda: DateTimeScreen(self),
            "SET CUSTOM PRICING": lambda: CustomPricingScreen(self),
            "UPDATE GAME CODE": lambda: MessageScreen(self, text, "NO UPDATE FOUND"),
            "BACKUP TO USB MEMORY STICK": lambda: ActionScreen(
                self, text, "PRESS SELECT TO BACKUP", lambda: dump_audits(os_, self.dump_path), "BACKUP DONE"),
        }
        return screens.get(text, lambda: MessageScreen(self, text, "NOT AVAILABLE"))()

    # ------------------------------------------------------------------ resets

    def reset_credits(self):
        self.os.credit_model.reset()

    def reset_high_scores(self, mask):
        """RESET GRAND CHAMPION (1) / RESET HIGH SCORES (2) [0x0001a9f4]; 3 = both and the reset counter."""
        hs = self.os.features_by_name.get("high_scores")
        if hs:
            hs.reset_all() if mask == 3 else hs.reset(mask)

    def factory_reset(self):
        """RESET FACTORY SETTINGS: adjustments to their defaults, audits cleared, high scores and credits."""
        self.os.adj.factory_reset()
        self.os.audits.reset_all()
        self.reset_high_scores(3)
        self.reset_credits()


_FLASHERS = None


def flasher_names():
    """The outputs listed under "flashers:" in the package's coils.yaml (MPF 0.80 has them as coils)."""
    global _FLASHERS
    if _FLASHERS is None:
        from tron.settings import ROOT
        names, inside = [], False
        with open(os.path.join(ROOT, "assets", "mpf_package", "config", "coils.yaml"), encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith((" ", "#")):
                    inside = line.startswith("flashers:")
                elif inside and line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":"):
                    names.append(line.strip()[:-1])
        _FLASHERS = names
    return _FLASHERS
