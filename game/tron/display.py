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
  display (deff rule 0x000198a8): deff 19 is restarted in the background during normal play, or the
  background deff of the winning mode rule (os.deff_rule, e.g. Light Cycle Multiball deff 86).
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
        self.fg_until = None        # when it ends (None: held until stopped)
        self.hold_tail = {}         # deff id -> seconds at its end shown at priority 0x20 (set_hold_tail)
        self._bg_next = None        # background deff started during that hold
        self.fg_handle = None
        self.bg = None              # running background deff id
        self.shows = []             # waiting Show entries
        self.show = None            # Show playing now
        self._sound_handles = []
        self._pump_handle = None

    # ------------------------------------------------------------------ start / stop

    def start(self, deff_id, hold=False, refresh=True, **args):
        os_ = self.os
        if deff_id in self.background:
            # behind a foreground deff it is not running yet: the deff rules start it again when the
            # foreground deff ends (traces: D87 ... D86, then D86 again when deff 87 is over)
            self.bg = deff_id if self.fg is None else None
            if self.fg is not None and self.fg_prio() == 0x20:
                self._bg_next = deff_id              # it takes over when the holding deff ends
            os_.trace.log("deff_start", id=deff_id)
            os_.machine.events.post("tron_deff_{}".format(deff_id), **args)
            if deff_id == 19:
                os_.tube_start(10)
            return True
        os_.trace.log("deff_start", id=deff_id)    # the ROM trace logs every start call
        if self.fg is not None and self.fg_prio() > self.prio.get(deff_id, 0):
            return False                           # a higher priority deff keeps the display
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
                seconds = forced.pop(0)              # random length (e.g. the arcade reel), from a test
            if not hold and seconds:
                self.fg_handle = os_.machine.clock.schedule_once(lambda: self._ended(deff_id), seconds)
                self.fg_until = os_.now + seconds
                tail = self.hold_tail.get(deff_id)
                if tail:                             # the priority change runs the deff rules
                    self._sound_handles.append(os_.machine.clock.schedule_once(
                        lambda: self.fg == deff_id and os_.request_refresh(), max(0, seconds - tail)))
        if refresh and not self.show:
            if os_.deff_rule_winner():
                os_.request_refresh()                # the mode's deff rule re-asserts its deff (os.deff_rule)
            else:
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

    def fg_prio(self):
        tail = self.hold_tail.get(self.fg)
        if tail and self.fg_until is not None and self.os.now >= self.fg_until - tail:
            return 0x20
        return self.prio.get(self.fg, 0)

    def running(self, deff_id):
        return deff_id in (self.fg, self.bg)

    def _end_fg(self, stopped=False):
        if self.fg_handle:
            self.os.machine.clock.unschedule(self.fg_handle)
            self.fg_handle = None
        for handle in self._sound_handles:
            self.os.machine.clock.unschedule(handle)
        self._sound_handles = []
        self.fg = None
        self.fg_until = None
        self._bg_next = None

    def _ended(self, deff_id):
        self.fg_handle = None
        if self.fg != deff_id:
            return
        nxt = self._bg_next
        self._end_fg()
        if nxt is not None and self.bg is None:
            self.bg = nxt                            # already started during the hold: no new start
            self.os.machine.events.post("tron_deff_{}".format(nxt))
        self._after_fg()

    def _after_fg(self):
        show = self.show
        if show:
            self.show = None
            if show.on_end:
                show.on_end()
            self.refresh()
        self._pump()
        if not show and not self.show:
            self.refresh()                       # the deff rules re-assert the background deff

    def refresh(self):
        """Deff rule for the score display: restart deff 19 behind whatever runs, in normal play."""
        os_ = self.os
        if os_.deff_rule_winner():
            os_.request_refresh()                    # a mode's background deff rule (os.deff_rule)
        elif os_.in_play and self.bg is None and not self.show:
            self.start(19)

    def queued(self, task_id):
        """Show task task_id is waiting in the queue (not playing yet)."""
        return any(s.task_id == task_id for s in self.shows)

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
        if self.fg is None or self.fg_prio() < first.threshold:
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
