"""Display effect (deff) manager: priorities, the background score display and the show queue.

Model of the SAM OS deff system as the Tron rules use it:
- Background deffs (event_map.csv background_loop = yes, e.g. 19 score display, 21 tilt) loop until
  replaced. Deff 19 starts ramp tube show 10 with it.
- Foreground deffs run for their recorded length (timing.json run_seconds) unless started with
  hold=True (the caller stops them, e.g. the bonus). A deff with a lower priority than the running
  foreground deff is not shown.
- What a deff starts by itself comes from the asset package (media_table): its lamp-matrix effects
  at once, its sounds at their offsets (logged with in_deff = the deff).
- Show queue, queue_fullscreen_deff [0x0100fbb0]: "show" tasks (ids 0x81-0xa7) wait until the running
  deff's priority is below their threshold (0x9f for every caller) and they are the first show task
  in the task list, i.e. the oldest one waiting (FUN_0000c2b8 scans the list from its head; a
  re-created task goes to the end), then play their deff to the end. While a show task runs, mode
  clocks pause and the VUK holds its ball.
- After a plain foreground deff starts, and after a show ends, the deff rules re-assert the score
  display (deff rule 0x000198a8): deff 19 is restarted in the background during normal play.
"""
import csv
import os

from tron import media_table

SHOW_THRESHOLD = 0x9f
SHOW_TIMEOUT = 0xea6


class Show:
    __slots__ = ("task_id", "deff_id", "threshold", "timeout", "on_start", "on_end", "queued_at", "deff_args")

    def __init__(self, task_id, deff_id, threshold, timeout, on_start, on_end, queued_at, deff_args):
        self.task_id, self.deff_id, self.threshold, self.timeout = task_id, deff_id, threshold, timeout
        self.on_start, self.on_end, self.queued_at, self.deff_args = on_start, on_end, queued_at, deff_args


class Display:

    def __init__(self, os_):
        self.os = os_
        assets = os.path.join(os_.machine.machine_path, "..", "assets")
        self.media = media_table.load(assets)
        self.prio, self.background = {}, set()
        with open(os.path.join(assets, "mpf_package", "event_map.csv")) as f:
            for row in csv.DictReader(f):
                deff_id = int(row["deff"])
                self.prio[deff_id] = int(row["priority"] or 0)
                if row["background_loop"] == "yes":
                    self.background.add(deff_id)
        self.fg = None              # running foreground deff id
        self.fg_handle = None
        self.bg = None              # running background deff id
        self.shows = []             # waiting Show entries
        self.show = None            # Show playing now
        self._sound_handles = []
        self._pump_handle = None
        # Background deff rules (lamp_rule_init type 2): [prio, cond, deff, music]. The active rule with
        # the highest priority owns the background deff and the music; without one, the score display
        # (deff 19) runs with the OS base music (os.base_music()).
        self.bg_rules = []
        self.fg_until = None        # when the foreground deff ends (None: held until stopped)
        self.hold_tail = {}         # deff id -> seconds at its end shown at priority 0x20 (set_hold_tail)
        self.music = None           # music call the background rules last played

    # ------------------------------------------------------------------ start / stop

    def start(self, deff_id, hold=False, refresh=True, **args):
        os_ = self.os
        if deff_id in self.background:
            self.bg = deff_id
            os_.trace.log("deff_start", id=deff_id)
            os_.machine.events.post("tron_deff_{}".format(deff_id), **args)
            if deff_id == 19:
                os_.tube_start(10)
            return True
        os_.trace.log("deff_start", id=deff_id)    # the ROM trace logs every start call
        if self.fg is not None and self.fg_prio() > self.prio.get(deff_id, 0):
            # a higher priority deff keeps the display; the deff rules still run and restart a mode's
            # background deff (traces/disc_multiball.jsonl: deff 48 refused behind deff 50, deff 47 again)
            if refresh and not self.show and self.bg not in (None, 19):
                os_.after(1, lambda: os_.in_play and self.bg not in (None, 19) and self.start(self.bg, refresh=False))
            return False
        self._end_fg(stopped=True)
        self.fg = deff_id
        self.bg = None
        os_.machine.events.post("tron_deff_{}".format(deff_id), **args)
        info = self.media.get(deff_id)
        if info:
            if not hold:
                # the deff's own code starts its media once it runs: nothing if it is replaced at once
                self._sound_handles.append(os_.machine.clock.schedule_once(lambda: self._media(deff_id), 0))
            seconds = info.seconds
            forced = os_.forced.get("deff_{}_seconds".format(deff_id))
            if forced:
                seconds = forced.pop(0) or seconds   # random length (e.g. the arcade reel), from a test
            if not hold and seconds:
                self.fg_handle = os_.machine.clock.schedule_once(lambda: self._ended(deff_id), seconds)
                self.fg_until = os_.now + seconds
                tail = self.hold_tail.get(deff_id)
                if tail:                             # the priority change runs the deff rules
                    self._sound_handles.append(os_.machine.clock.schedule_once(
                        lambda: self.fg == deff_id and self._hold_started(), max(0, seconds - tail)))
        if refresh and not self.show:
            os_.after(1, self.refresh)
        return True

    def _media(self, deff_id):
        if self.fg != deff_id:
            return
        os_ = self.os
        info = self.media[deff_id]
        for leff in info.leffs:
            os_.leff_start(leff)
        events = [(t, "sound", c) for t, c in info.sounds] + [(t, "tube", n) for t, n in info.tubes]
        for offset, kind, value in sorted(events, key=lambda e: e[0]):
            fire = (lambda k, v: lambda: self.fg == deff_id and (
                os_.sound(v, in_deff=deff_id) if k == "sound" else os_.tube_start(v)))(kind, value)
            if offset <= 0:
                fire()
            else:
                self._sound_handles.append(os_.machine.clock.schedule_once(fire, offset))

    def stop(self, deff_id):
        os_ = self.os
        os_.trace.log("deff_stop", id=deff_id)
        os_.machine.events.post("tron_deff_{}_stop".format(deff_id))
        if self.fg == deff_id:
            self._end_fg(stopped=True)
            self._after_fg()
        elif self.bg == deff_id:
            self.bg = None

    def set_hold_tail(self, deff_id, seconds):
        """deff_hold_frames(n, 0x20) [0x01024460]: for its last `seconds` the deff runs at priority 0x20,
        so any other deff may replace it; the priority change runs the deff rules once."""
        self.hold_tail[deff_id] = seconds

    def _hold_started(self):
        """The deff rules run at the priority drop and restart a mode's background deff behind it
        (traces/quorra_multiball: deff 65 again 2.78 s into deff 68)."""
        os_ = self.os
        if os_.in_play and not self.show and self.bg not in (None, 19):
            self.start(self.bg, refresh=False)
        os_.request_refresh()

    def fg_prio(self):
        tail = self.hold_tail.get(self.fg)
        if tail and self.fg_until is not None and self.os.now >= self.fg_until - tail:
            return 0x20
        return self.prio.get(self.fg, 0)

    def queued(self, task_id):
        """Show task task_id is waiting in the queue (not playing yet)."""
        return any(s.task_id == task_id for s in self.shows)

    def running(self, deff_id):
        return deff_id in (self.fg, self.bg)

    def _end_fg(self, stopped=False):
        info = self.media.get(self.fg) if self.fg is not None else None
        if info:
            for leff in info.leffs:                # the deff's exit handler stops its lamp effects
                if self.os.leffs.is_running(leff):
                    self.os.leff_stop(leff)
        if self.fg_handle:
            self.os.machine.clock.unschedule(self.fg_handle)
            self.fg_handle = None
        for handle in self._sound_handles:
            self.os.machine.clock.unschedule(handle)
        self._sound_handles = []
        self.fg = None
        self.fg_until = None

    def _ended(self, deff_id):
        self.fg_handle = None
        if self.fg != deff_id:
            return
        self._end_fg()
        # the deff rules restart a mode's background deff when the effect in front of it ends
        # (traces/disc_multiball.jsonl: deff 47 again as deff 48/50 end)
        if self.bg is not None and self.bg != 19 and self.os.in_play:
            self.start(self.bg, refresh=False)
            self.os.request_refresh()              # the same rules pass restarts the mode's tube show
        self._after_fg()

    def _after_fg(self):
        show = self.show
        if show:
            self.show = None
            if show.on_end:
                show.on_end()
            self.refresh()
        self._pump()

    def refresh(self):
        """Deff rules: restart the background deff (deff 19 or a mode's) behind whatever runs, in normal play."""
        os_ = self.os
        if os_.in_play and self.bg is None and not self.show:
            self.start(self.bg_select()[0])

    # ------------------------------------------------------------------ background deff rules

    def bg_rule(self, cond, deff_id, music, prio):
        """lamp_rule_init(obj, 2, cond, deff, music, ..., prio): while cond() is true, deff_id is the
        background deff and `music` the music call (0 = keep)."""
        rule = [prio, cond, deff_id, music]
        self.bg_rules.append(rule)
        self.bg_rules.sort(key=lambda r: -r[0])
        return rule

    def bg_rule_raise(self, rule):
        """A mode start re-inserts its rule before the others of its priority (e.g. FUN_0101ac74), so
        the mode started last shows its deff when several are active (stacked Light Cycle + Quorra)."""
        self.bg_rules.remove(rule)
        i = next((k for k, r in enumerate(self.bg_rules) if r[0] <= rule[0]), len(self.bg_rules))
        self.bg_rules.insert(i, rule)

    def bg_select(self):
        for _, cond, deff_id, music in self.bg_rules:
            if cond():
                return deff_id, music
        return 19, self.os.base_music()

    def bg_refresh(self):
        """Rules refresh: a change of the selected rule starts its music and its background deff."""
        os_ = self.os
        if not os_.in_play:
            return
        deff_id, music = self.bg_select()
        changed = deff_id != self.bg and (self.bg is not None or deff_id != 19)
        if changed:
            self.start(deff_id, refresh=False)
        if music and music != self.music:
            if not changed and deff_id == 19:
                self.start(19, refresh=False)       # the ROM restarts the score display with new music
            self.music = music
            os_.sound(music)

    def clear(self):
        """Ball end / game end: drop the queue and the foreground deff (no trace event)."""
        self.shows = []
        self.show = None
        self._end_fg()
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None

    # ------------------------------------------------------------------ show queue

    def queue(self, task_id, deff_id, timeout=SHOW_TIMEOUT, threshold=SHOW_THRESHOLD, on_start=None,
              on_end=None, **deff_args):
        self.shows = [s for s in self.shows if s.task_id != task_id]
        self.shows.append(Show(task_id, deff_id, threshold, timeout, on_start, on_end, self.os.now, deff_args))
        self._pump()

    def cancel(self, task_id):
        self.shows = [s for s in self.shows if s.task_id != task_id]

    def show_running(self):
        """task_running_range(0x81, 0xa7): a show task is waiting or playing."""
        return bool(self.show or self.shows)

    def _pump(self):
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None
        if self.show or not self.shows:
            return
        from tron.os_layer import TICK
        now = self.os.now
        self.shows = [s for s in self.shows if now - s.queued_at <= s.timeout * TICK]
        if not self.shows:
            return
        first = self.shows[0]
        if self.fg is None or self.prio.get(self.fg, 0) < first.threshold:
            self.shows.pop(0)
            self.show = first
            self.start(first.deff_id, refresh=False, **first.deff_args)
            if first.on_start:
                first.on_start()
            if self.fg is None:                  # deff without a recorded length
                self._after_fg()
            return
        self._pump_handle = self.os.machine.clock.schedule_once(self._pump_tick, TICK)

    def _pump_tick(self):
        self._pump_handle = None
        self._pump()


class Tubes:
    """Ramp light tube shows (tube_show_start 0x0101b824, table 0x040e3c88 via io/light_effects.csv).

    Each show owns the left, right or both tubes with a priority. A start is refused when a show of
    the same or higher priority owns one of its tubes; otherwise it takes the tubes from lower shows
    (they stop). "once" shows end after their length, "loop"/"hold" shows run until stopped, and shows
    with no tube output end at once.
    """
    MASK = {"left": 1, "right": 2, "both": 3}

    def __init__(self, os_):
        self.os = os_
        self.info = {}
        path = os.path.join(os_.machine.machine_path, "..", "assets", "io", "light_effects.csv")
        with open(path) as f:
            for row in csv.DictReader(f):
                length = float(row["length_ms"] or 0) / 1000
                # shows with no tube output in emulation still hold their tubes (traces: tube 13/14)
                kind = row["kind"] if row["kind"] in ("loop", "hold", "once") else "hold"
                self.info[int(row["leff"])] = (self.MASK.get(row["tubes"], 3), int(row["priority"] or 0), kind, length)
        self.running = {}           # show id -> end handle (or None)

    def is_running(self, show_id):
        return show_id in self.running

    def start(self, show_id):
        os_ = self.os
        os_.trace.log("tube_show_start", id=show_id)
        os_.machine.events.post("tron_tube_{}".format(show_id))
        mask, prio, kind, length = self.info.get(show_id, (3, 0, "loop", 0))
        losers = []
        for other in list(self.running):
            o_mask, o_prio = self.info.get(other, (3, 0, "", 0))[:2]
            if other == show_id or not o_mask & mask:
                continue
            if o_prio >= prio:
                return False
            losers.append(other)
        for other in losers:
            self.stop(other)
        self.stop(show_id, log=False)
        handle = None
        if kind == "once" and length:
            handle = os_.machine.clock.schedule_once(lambda: self._ended(show_id), length)
        self.running[show_id] = handle
        return True

    def _ended(self, show_id):
        self.running.pop(show_id, None)
        self.os.request_refresh()

    def stop(self, show_id, log=True):
        handle = self.running.pop(show_id, "absent")
        if handle != "absent" and handle:
            self.os.machine.clock.unschedule(handle)
        if log and handle != "absent":
            self.os.trace.log("tube_show_stop", id=show_id)
            self.os.machine.events.post("tron_tube_{}_stop".format(show_id))

    def clear(self):
        for show_id in list(self.running):
            self.stop(show_id)


UNCLAIMED = {76}     # leff_076 [0x01006660] pulses the red/blue disc flasher itself (coil_pulse), no coil group


class Leffs:
    """Flasher ownership of lamp-matrix effects (assets/mpf_package/lamp_effects.csv: flashers, priority).

    Lamps are drawn in priority layers, so they never conflict (leff 99 starts under leff 52), but a
    leff start is refused while a running leff with a higher priority uses one of its flashers (a
    running lower one keeps running). When an effect ends or stops, the lamp rules start a refused rule
    leff that can run now (logged again; traces/recognizer_and_disc_battle.jsonl: leff 107 behind leff
    108; disc_multiball_restart.jsonl: leff 54 behind leff 52). Rule leffs run until the rule stops them.
    """

    def __init__(self, os_):
        self.os = os_
        self.info = {}
        path = os.path.join(os_.machine.machine_path, "..", "assets", "mpf_package", "lamp_effects.csv")
        with open(path) as f:
            for row in csv.DictReader(f):
                outputs = frozenset(row["flashers"].split()) if int(row["leff"]) not in UNCLAIMED else frozenset()
                length = float(row["length_ms"]) / 1000 if row["loops"] == "0" and row["length_ms"] else None
                self.info[int(row["leff"])] = (outputs, int(row["priority"] or 0), length)
        self.running = {}           # leff id -> end handle (or None)
        self.pending = []           # refused lamp-rule leffs, started when an effect ends

    def is_running(self, leff_id):
        return leff_id in self.running

    def blocked(self, leff_id):
        outputs, prio, _ = self.info.get(leff_id, (frozenset(), 0, None))
        return any(other != leff_id and o_out & outputs and o_prio > prio
                   for other in self.running for o_out, o_prio, _ in (self.info.get(other, (frozenset(), 0, None)),))

    def start(self, leff_id, loop=False):
        if self.blocked(leff_id):
            if loop and leff_id not in self.pending:
                self.pending.append(leff_id)
            return False
        self.stop(leff_id)
        length = self.info.get(leff_id, (None, None, None))[2]
        handle = None
        if length and not loop:
            handle = self.os.machine.clock.schedule_once(lambda: self._ended(leff_id), length)
        self.running[leff_id] = handle
        return True

    def _ended(self, leff_id):
        self.running.pop(leff_id, None)
        self._retry()

    def _retry(self):
        """Outputs were freed: the lamp rules run again and start a refused rule leff that can run now."""
        if any(not self.blocked(p) for p in self.pending):
            from tron.os_layer import TICK
            self.os.machine.clock.schedule_once(lambda: self.os.rules_refresh(leffs_only=True), TICK / 2)

    def retry_due(self, leff_id):
        return leff_id in self.pending and not self.blocked(leff_id)

    def stop(self, leff_id):
        if leff_id in self.pending:
            self.pending.remove(leff_id)
        if leff_id not in self.running:
            return
        handle = self.running.pop(leff_id)
        if handle:
            self.os.machine.clock.unschedule(handle)
        self._retry()
