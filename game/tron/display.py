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
  deff's priority is below their threshold (0x9f for every caller) and they are the lowest task id
  waiting, then play their deff to the end. While a show task runs, mode clocks pause and the VUK
  holds its ball.
- After an effect ends, and after a show ends, the deff rules re-assert the background deff (deff rule
  0x000198a8): deff 19, or the deff of the true mode rule, restarts in the background during normal play.
- Mode deff rules (lamp_rule_init list 2, os.deff_rule -> add_rule): on each rules refresh the true rule
  with the highest priority starts its background deff (even behind a show) when it changed, and its
  music call when that music is not already playing. With no mode rule true the score display rule runs
  with os.base_music() (0x01a before the playfield is valid, then 0x01b; 0x029 while Disc Battle is lit)
  [0x0100f594 / 0x0100f5c8]. Every start of a rule's deff is traced with rule=1 (ROM caller 0x19944).
- A deff that ends with deff_hold_frames(n, 0x20) (HOLD_TICKS) keeps the display for its last n ticks at
  priority 0x20; a show playing it ends there. A deff's exit handler stops the ramp tube show it
  started, which re-runs the rules.
"""
import csv
import os

from tron import media_table

SHOW_THRESHOLD = 0x9f
SHOW_TIMEOUT = 0xea6
# deff_hold_frames(n, 0x20) at the end of a deff's code: its last n ticks run at priority 0x20, so a
# show task playing it ends there (queue_fullscreen_deff waits for a priority < 0x21) and the next
# show or a lower deff may start. Read from the deff code; deffs not listed hold 0 ticks.
HOLD_TICKS = {71: 10, 73: 10, 76: 1, 78: 1, 94: 1}
HOLD_PRIO = 0x20
PREVALID_PRIO = 0x10        # priority of the score display rule that runs until the playfield is valid


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
        self.fg_hold = False        # the foreground deff is in its final hold (priority 0x20)
        self.fg_handle = None
        self.bg = None              # running background deff id
        self.shows = []             # waiting Show entries
        self.show = None            # Show playing now
        self._sound_handles = []
        self._pump_handle = None
        # Background deff rules (lamp_rule_init list 2, os.deff_rule): (priority, cond, deff, music, on_start).
        # The true rule with the highest priority owns the background deff and the music; without one, the
        # score display (deff 19) runs with the OS base music (os.base_music()).
        self.rules = []
        self.music = None           # music call the background rules last played

    # ------------------------------------------------------------------ start / stop

    def start(self, deff_id, hold=False, refresh=True, run_seconds=None, **args):
        """run_seconds: the run length when this call's variant differs from the recorded one."""
        os_ = self.os
        if deff_id in self.background:
            self.bg = deff_id
            if self.is_rule_deff(deff_id):
                os_.trace.log("deff_start", id=deff_id, rule=1)   # a deff rule's deff (ROM caller 0x19944)
            else:
                os_.trace.log("deff_start", id=deff_id)
            os_.machine.events.post("tron_deff_{}".format(deff_id), **args)
            if deff_id == 19:
                os_.tube_start(10)
            return True
        os_.trace.log("deff_start", id=deff_id)    # the ROM trace logs every start call
        if self.fg is not None and self._fg_prio() > self.prio.get(deff_id, 0):
            # a higher priority deff keeps the display; the deff rules still run and restart a mode's
            # background deff (traces/disc_multiball.jsonl: deff 48 refused behind deff 50, deff 47 again)
            if refresh and not self.show and self.mode_bg():
                os_.after(1, lambda: self.mode_bg() and self.start(self.mode_bg(), refresh=False))
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
            seconds = run_seconds or info.seconds
            forced = os_.forced.get("deff_{}_seconds".format(deff_id))
            if forced:
                seconds = forced.pop(0) or seconds   # random length (e.g. the arcade reel), from a test
            if not hold and seconds:
                self.fg_handle = os_.machine.clock.schedule_once(lambda: self._ended(deff_id), seconds)
                if HOLD_TICKS.get(deff_id):
                    from tron.os_layer import TICK
                    self._sound_handles.append(os_.machine.clock.schedule_once(
                        lambda: self._hold(deff_id), max(0, seconds - HOLD_TICKS[deff_id] * TICK)))
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

    def extend(self, deff_id):
        """A running foreground deff that shows a growing value runs its full length again from now
        (no new deff_start; spinner deffs 41 / 42, see switches.SwitchLayer.sw_36)."""
        if self.fg != deff_id or not self.fg_handle:
            return
        self.os.machine.clock.unschedule(self.fg_handle)
        self.fg_handle = self.os.machine.clock.schedule_once(
            lambda: self._ended(deff_id), self.media[deff_id].seconds)

    def running(self, deff_id):
        return deff_id in (self.fg, self.bg)

    def _fg_prio(self):
        return HOLD_PRIO if self.fg_hold else self.prio.get(self.fg, 0)

    def _hold(self, deff_id):
        """deff_hold_frames(n, 0x20): the deff keeps the display at priority 0x20; a show ends here."""
        if self.fg != deff_id:
            return
        self.fg_hold = True
        if self.show and self.show.deff_id == deff_id:
            self._end_show()
            self._pump()

    def _end_fg(self, stopped=False, exit_handler=True):
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
        if exit_handler and info:
            # the deff's exit handler stops the ramp tube show it started (e.g. FUN_010022c4), and the
            # tube release re-runs the rules (traces: deff 73 end -> deff 72 / tube 23 restart)
            for _, tube in info.tubes:
                if self.os.tubes.is_running(tube):
                    self.os.tubes.stop(tube)
                    self.os.request_refresh()
        self.fg = None
        self.fg_hold = False

    def _ended(self, deff_id):
        self.fg_handle = None
        if self.fg != deff_id:
            return
        self._end_fg()
        # the deff rules restart a mode's background deff when the effect in front of it ends
        # (traces/disc_multiball.jsonl: deff 47 again as deff 48/50 end)
        if self.mode_bg():
            self.start(self.mode_bg(), refresh=False)
            self.os.request_refresh()              # the same rules pass restarts the mode's tube show
        self._after_fg()

    def _after_fg(self):
        if self.show:
            self._end_show()
        self._pump()

    def _end_show(self):
        show, self.show = self.show, None
        if show.on_end:
            show.on_end()
        self.refresh()
        self.os.request_refresh()                  # queue_fullscreen_deff: rules_refresh_request at the end

    def add_rule(self, cond, deff_id, music=None, priority=0, on_start=None):
        """lamp_rule_init(list 2): while cond() is true the background deff deff_id runs, with music
        (None/0 = keep). on_start() is called when the rule (re)starts the deff (the deff's own code).
        Returns the rule (raise_rule)."""
        rule = (priority, cond, deff_id, music, on_start)
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r[0])
        return rule

    def raise_rule(self, rule):
        """Re-insert a rule ahead of the rules of equal priority (FUN_010028dc at a mode start)."""
        self.rules.remove(rule)
        at = next((i for i, r in enumerate(self.rules) if r[0] <= rule[0]), len(self.rules))
        self.rules.insert(at, rule)

    def is_rule_deff(self, deff_id):
        return any(r[2] == deff_id for r in self.rules)

    def select(self):
        """The true rule with the highest priority: (deff, music, on_start), else the score display."""
        valid = self.os.flag(0x1c) or self.os.pf_valid
        for prio, cond, deff_id, music, on_start in self.rules:
            if prio < PREVALID_PRIO and not valid:
                break                              # the score display rule before validation [0x0100f564]
            if cond():
                return deff_id, music, on_start
        return 19, self.os.base_music(), None

    def _start_rule(self, deff_id, on_start):
        self.start(deff_id, refresh=False)
        if on_start:
            on_start()

    def refresh(self):
        """Deff rules [0x000198a8] after an effect ends: restart the background deff (deff 19 or a mode's)
        behind whatever runs, in normal play."""
        if self.os.in_play and self.bg is None and not self.show:
            deff_id, _, on_start = self.select()
            self._start_rule(deff_id, on_start)

    def mode_bg(self):
        """The mode background deff the rules select now (None: the score display)."""
        deff_id = self.select()[0] if self.os.in_play else 19
        return None if deff_id == 19 else deff_id

    def rules_refresh(self):
        """Rules refresh: a change of the selected rule starts its background deff and its music."""
        os_ = self.os
        if not os_.in_play:
            return
        deff_id, music, on_start = self.select()
        changed = deff_id != self.bg and (self.bg is not None or deff_id != 19)
        if changed:
            self._start_rule(deff_id, on_start)
        if music and music != self.music:
            if not changed and deff_id == 19:
                self.start(19, refresh=False)       # the ROM restarts the score display with new music
            self.music = music
            os_.sound(music)

    def clear(self):
        """Ball end / game end: drop the queue and the foreground deff (no trace event)."""
        self.shows = []
        self.show = None
        self.music = None
        self._end_fg(exit_handler=False)
        if self._pump_handle:
            self.os.machine.clock.unschedule(self._pump_handle)
            self._pump_handle = None

    # ------------------------------------------------------------------ show queue

    def queue(self, task_id, deff_id, timeout=SHOW_TIMEOUT, threshold=SHOW_THRESHOLD, on_start=None,
              on_end=None, **deff_args):
        self.shows = [s for s in self.shows if s.task_id != task_id]
        self.shows.append(Show(task_id, deff_id, threshold, timeout, on_start, on_end, self.os.now, deff_args))
        self.shows.sort(key=lambda s: s.task_id)
        self._pump()

    def cancel(self, task_id):
        self.shows = [s for s in self.shows if s.task_id != task_id]

    def task_running(self, task_id):
        """task_running(id) for a show task: waiting in the queue or playing."""
        return bool(self.show and self.show.task_id == task_id) or any(s.task_id == task_id for s in self.shows)

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
        if self.fg is None or self._fg_prio() < first.threshold:
            self.shows.pop(0)
            self.show = first
            self.start(first.deff_id, refresh=False, **first.deff_args)
            if first.on_start:
                first.on_start()
            self.os.request_refresh()            # rules that wait for this show's deff (e.g. a mode intro)
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
