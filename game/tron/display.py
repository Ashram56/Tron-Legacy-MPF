"""Display effect (deff) manager: priorities, the background score display and the show queue.

Model of the SAM OS deff system as the Tron rules use it:
- Background deffs (event_map.csv background_loop = yes, e.g. 19 score display, 21 tilt) loop until
  replaced. Deff 19 starts ramp tube show 10 with it.
- Foreground deffs run for their recorded length (timing.json run_seconds) unless started with
  hold=True (the caller stops them, e.g. the bonus). A deff with a lower priority than the running
  foreground deff is not shown.
- What a deff starts by itself comes from the asset package (media_table): its lamp-matrix effects
  at once, its sounds at their offsets (logged with in_deff = the deff).
- Show queue, queue_fullscreen_deff [0x0100fbb0]: "show" tasks (ids 0x81-0xa7) first run on the next
  tick, wait until the running deff's priority is below their threshold (0x9f for every caller) and
  they are the oldest show task waiting, then play their deff until its last 10 ticks (the hold at
  priority 0x20; a deff in its hold can be replaced by any other). While a show task runs, mode clocks
  pause and the VUK holds its ball.
- A deff's ramp tube shows end with it.
- Deff rules [0x000198a8], run by every full rules refresh: the winning background rule (deff 19
  score display by default, or a feature's "background_rule" with its music) is started when it is not
  on screen; while a foreground deff covers it, each pass logs a start again. When a foreground deff
  ends, the background deff resumes without a new start.
"""
import csv
import os

from tron import media_table

SHOW_THRESHOLD = 0x9f
SHOW_TIMEOUT = 0xea6
HOLD_TICKS = 10             # deffs end with deff_hold_frames(10, 0x20): priority 0x20 for the last 10 ticks
HOLD_PRIORITY = 0x20


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
        self.fg_prio = 0            # its priority (HOLD_PRIORITY in its last 10 ticks)
        self.fg_tubes = []          # ramp tube shows it started
        self.fg_handle = None
        self.bg = None              # running background deff id
        self.shows = []             # waiting Show entries
        self.show = None            # Show playing now
        self.music = None           # music call of the winning background rule (None: main play music)
        self.idle_waits = []        # [task_id, deff_id, deadline, on_end, deff_args] (when_idle)
        self._sound_handles = []
        self._pump_handle = None

    # ------------------------------------------------------------------ start / stop

    def start(self, deff_id, hold=False, refresh=True, **args):
        os_ = self.os
        if deff_id in self.background:
            # bg = the background deff on screen. While a foreground deff covers the display a start
            # only logs; when the foreground deff ends the winning background deff resumes silently.
            if self.fg is None:
                self.bg = deff_id
            os_.trace.log("deff_start", id=deff_id)
            os_.machine.events.post("tron_deff_{}".format(deff_id), **args)
            if deff_id == 19:
                os_.tube_start(10)
            return True
        os_.trace.log("deff_start", id=deff_id)    # the ROM trace logs every start call
        if self.fg is not None and self.fg_prio > self.prio.get(deff_id, 0):
            return False                           # a higher priority deff keeps the display
        self._end_fg(stopped=True)
        self.fg = deff_id
        self.fg_prio = self.prio.get(deff_id, 0)
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
                from tron.os_layer import TICK
                self._sound_handles.append(os_.machine.clock.schedule_once(
                    lambda: self._hold(deff_id), max(0.0, seconds - HOLD_TICKS * TICK)))
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
                os_.sound(v, in_deff=deff_id) if k == "sound" else self._deff_tube(v)))(kind, value)
            if offset <= 0:
                fire()
            else:
                self._sound_handles.append(os_.machine.clock.schedule_once(fire, offset))

    def _deff_tube(self, show_id):
        self.fg_tubes.append(show_id)
        return self.os.tube_start(show_id)

    def _hold(self, deff_id):
        """Last 10 ticks of deff_id (cancelled with it when it is replaced): its priority drops to 0x20,
        so any deff can replace it, and a show task waiting for priority < 0x21 ends here
        (queue_fullscreen_deff)."""
        self.fg_prio = HOLD_PRIORITY
        if self.show:
            self._after_fg()

    def stop(self, deff_id):
        os_ = self.os
        os_.trace.log("deff_stop", id=deff_id)
        os_.machine.events.post("tron_deff_{}_stop".format(deff_id))
        if self.fg == deff_id:
            self._end_fg(stopped=True)
            self._after_fg()
        elif self.bg == deff_id:
            self.bg = None

    def running(self, deff_id):
        return deff_id in (self.fg, self.bg)

    def _end_fg(self, stopped=False):
        if self.fg_handle:
            self.os.machine.clock.unschedule(self.fg_handle)
            self.fg_handle = None
        for handle in self._sound_handles:
            self.os.machine.clock.unschedule(handle)
        self._sound_handles = []
        for show_id in self.fg_tubes:              # the deff task's tube shows end with it
            if self.os.tubes.is_running(show_id):
                self.os.tubes.stop(show_id)
        self.fg_tubes = []
        self.fg = None

    def _ended(self, deff_id):
        self.fg_handle = None
        if self.fg != deff_id:
            return
        self._end_fg()
        self._after_fg()
        if self.os.in_play and self.fg is None:   # the background deff runs again (not logged)
            self.bg = self.background_rule()[1]

    def _after_fg(self):
        show = self.show
        if show:
            self.show = None
            if show.on_end:
                show.on_end()
            self.os.request_refresh()              # queue_fullscreen_deff: rules refresh at its end
        self._pump()

    def background_rule(self):
        """The winning deff + music rule (lamp_rule_init list 2): features answer the "background_rule"
        hook with (priority, deff, music call) while their rule is true; the score display (deff 19,
        no music of its own) is the default."""
        best = (0, 19, None)
        for fn in self.os.hooks.get("background_rule", ()):
            rule = fn()
            if rule and rule[0] > best[0]:
                best = rule
        return best

    def refresh(self):
        """Deff rule pass (FUN_000198a8), in normal play: (re)start the winning background deff when it
        is not the one on screen (a foreground deff covers it, so every pass during one logs a start);
        the score display rule is off while a show runs. Its music call is played when not already
        playing; when a rule's music ends, the main play music 0x01b comes back."""
        os_ = self.os
        if not os_.in_play:
            return
        _, deff_id, music = self.background_rule()
        if deff_id != 19 or not self.show:
            if self.bg != deff_id or self.fg is not None:
                self.start(deff_id, refresh=False)
        if music != self.music:
            if music is not None:
                os_.sound(music)
            elif os_.pf_valid:
                os_.sound(0x01b)
            self.music = music

    def clear(self):
        """Ball end / game end: drop the queue and the foreground deff (no trace event)."""
        self.shows = []
        self.show = None
        self.music = None
        self.idle_waits = []
        self._end_fg()
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None

    # ------------------------------------------------------------------ mode totals (tasks 0x4d-0x58)

    def when_idle(self, task_id, deff_id, timeout=SHOW_TIMEOUT, on_end=None, **deff_args):
        """FUN_0100fd88, used by the mode TOTAL tasks 0x4d-0x58: wait until no show task runs, no
        foreground deff is on screen and this is the oldest such task waiting, then play deff_id;
        on_end() runs when it is over (or when the wait times out)."""
        from tron.os_layer import TICK
        self.idle_waits = [w for w in self.idle_waits if w[0] != task_id]
        self.idle_waits.append([task_id, deff_id, self.os.now + timeout * TICK, on_end, deff_args])
        if len(self.idle_waits) == 1:
            self._idle_tick()

    def _idle_tick(self):
        from tron.os_layer import TICK
        now = self.os.now
        for w in [w for w in self.idle_waits if now > w[2]]:
            self.idle_waits.remove(w)
            if w[3]:
                w[3]()
        if not self.idle_waits:
            return
        if self.fg is None and not self.show_running():
            task_id, deff_id, _, on_end, args = self.idle_waits.pop(0)
            self.start(deff_id, **args)
            info = self.media.get(deff_id)
            if on_end:
                self.os.machine.clock.schedule_once(lambda: on_end(), info.seconds if info else 0)
        if self.idle_waits:
            self.os.machine.clock.schedule_once(self._idle_tick, TICK)

    # ------------------------------------------------------------------ show queue

    def queue(self, task_id, deff_id, timeout=SHOW_TIMEOUT, threshold=SHOW_THRESHOLD, on_start=None,
              on_end=None, **deff_args):
        self.shows = [s for s in self.shows if s.task_id != task_id]
        # FUN_0000c2b8 takes the first show task in the OS task list, i.e. the oldest one waiting
        # (traces/end_of_line_multiball.jsonl: task 0x87 deff 139, then 0x83 deff 133, then 0x97)
        self.shows.append(Show(task_id, deff_id, threshold, timeout, on_start, on_end, self.os.now, deff_args))
        # the show task first runs on the next tick, after the caller has finished (a deff the caller
        # starts right after queueing, e.g. deff 55 after the extra ball show 0x82, is on screen first)
        if self._pump_handle is None and not self.show:
            from tron.os_layer import TICK
            self._pump_handle = self.os.machine.clock.schedule_once(self._pump_tick, TICK)

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
        if self.fg is None or self.fg_prio < first.threshold:
            self.shows.pop(0)
            self.show = first
            self.start(first.deff_id, refresh=False, **first.deff_args)
            if first.on_start:
                first.on_start()
            self.os.request_refresh()            # queue_fullscreen_deff refreshes the rules after the start
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
