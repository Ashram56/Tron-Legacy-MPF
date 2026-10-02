"""Shared pieces of the timed modes: CLU hurry-up, GEM hurry-up and ZUSE fast scoring.

Not a feature itself (no `feature` attribute). The modes use:
- Countdown: the ROM countdown task (task_c0 CLU [0x01001e08], task_c2 GEM [0x01013b88],
  task_59 ZUSE [0x01031730]) run as os tasks, so os.task_running(<ROM id>) works for the other rules.
- show_total(): the queued TOTAL display (flag-0x2000 tasks 0x53 / 0x54 / 0x55).

The pause rule itself is os.timed_mode_paused() [0x0100ff64]. Flynn's Arcade MORE TIME reaches the
modes through the hooks "timed_feature_running" (any_timed_mode_running 0x0100f930: a countdown task,
not the end grace) and "more_time" (more_time_refill_all 0x0100f98c). A "timed_feature_running" hook
returns True or None (never False), because os.hook() returns the last non-None result.
"""

IDLE_WAIT = 0x138          # wait_display_idle(312) [0x0100fecc]
TOTAL_WAIT = 0xea6         # the TOTAL display waits up to 3750 ticks for the display [0x0100f7f0]


class Countdown:
    """One countdown task.

    Hurry-up style (CLU, GEM): wait while the intro show task runs, wait up to 312 ticks while the
    display is busy, sleep `lead_in` (156) ticks, then count one second per 16 un-paused 4-tick steps
    (paused steps do not count, partial progress is kept). tick() is called once per second and
    returns True when the clock is done; then sleep `tail` (46) ticks, continue as the grace task for
    `grace_ticks` (125) and call on_end().

    ZUSE style (restart_on_pause): no intro wait and no lead-in; a second is 11 steps of 6 ticks and a
    paused step restarts the count; grace task 0x5b for 250 ticks, no tail.
    """

    def __init__(self, os_, var, task, grace, tick, on_end, intro=None, lead_in=156, step=4, steps=16,
                 restart_on_pause=False, tail=46, grace_ticks=125):
        self.os = os_
        self.var = var              # ROM RAM name of the seconds counter, logged as a "var" trace event
        self._seconds = 0
        self.task, self.grace, self.intro = task, grace, intro
        self.tick, self.on_end = tick, on_end
        self.lead_in, self.step, self.steps = lead_in, step, steps
        self.restart_on_pause, self.tail, self.grace_ticks = restart_on_pause, tail, grace_ticks
        self._n = 0

    @property
    def seconds(self):
        """Seconds left on the display (clu_timer / gem_timer / zfs_timer)."""
        return self._seconds

    @seconds.setter
    def seconds(self, value):
        if value != self._seconds:
            self.os.trace.log("var", name=self.var, value=value, old=self._seconds)
        self._seconds = value

    def counting(self):
        return self.os.task_running(self.task)

    def running(self):
        """The countdown or its end grace runs (task_running_range(task, grace))."""
        return self.os.task_running(self.task) or self.os.task_running(self.grace)

    def kill(self):
        self.os.task_kill(self.task)
        self.os.task_kill(self.grace)

    def start(self):
        """task_recreate: (re)start from the beginning (also ends a running grace)."""
        self.kill()
        self.os.task_start(self.task, 1, self._intro_wait)   # the new task runs after its creator

    # ------------------------------------------------------------------ lead-in

    def _intro_wait(self):
        if self.intro is not None and self.os.display.show_task_running(self.intro):
            self.os.task_start(self.task, 1, self._intro_wait)
            return
        self._n = 0
        self._idle_wait()

    def _idle_wait(self):
        if self._n < IDLE_WAIT and self.os.display_busy():
            self._n += 1
            self.os.task_start(self.task, 1, self._idle_wait)
            return
        if self.lead_in:
            self.os.task_start(self.task, self.lead_in, self._count_start)
        else:
            self._count_start()

    # ------------------------------------------------------------------ counting

    def _count_start(self):
        self._n = 0
        if self.restart_on_pause:
            self._zstep()
        else:
            self.os.task_start(self.task, self.step, self._step)

    def _step(self):
        if not self.os.timed_mode_paused():
            self._n += 1
        if self._n < self.steps:
            self.os.task_start(self.task, self.step, self._step)
            return
        self._n = 0
        if self.tick():
            self._expire()
        else:
            self.os.task_start(self.task, self.step, self._step)

    def _zstep(self):
        if self.os.timed_mode_paused():
            self._n = 0
        self.os.task_start(self.task, self.step, self._zstep_end)

    def _zstep_end(self):
        self._n += 1
        if self._n < self.steps:
            self._zstep()
            return
        self._n = 0
        if self.tick():
            self._expire()
        else:
            self._zstep()

    # ------------------------------------------------------------------ end

    def _expire(self):
        if self.tail:
            self.os.task_start(self.task, self.tail, self._grace)
        else:
            self._grace()

    def _grace(self):
        """task_set_id(grace): shots still score, the rules (display, lamps, music) already stop."""
        self.os.task_kill(self.task)
        self.os.task_start(self.grace, self.grace_ticks, self._end)
        self.os.request_refresh()

    def _end(self):
        self.on_end()
        self.os.request_refresh()


def show_total(os_, task_id, deff_id, **args):
    """task_create_unique(task_id, ..., 0x2002) running FUN_0100f7f0(deff, 3750): wait until no show
    task runs and the display is idle (at most 3750 ticks), then start the TOTAL deff."""
    if os_.task_running(task_id):
        return
    state = {"n": 0}

    def poll():
        if not os_.show_running() and not os_.display_busy():
            os_.deff_start(deff_id, **args)
            return
        state["n"] += 1
        if state["n"] < TOTAL_WAIT:
            os_.task_start(task_id, 1, poll)
    os_.task_start(task_id, 1, poll)


def total_wait_ticks(os_, task_id, deff_id):
    """ball_end_wait: ticks the end of ball waits for a TOTAL display still queued or running."""
    from tron.os_layer import TICK
    length = round(os_.display.media[deff_id].seconds / TICK)
    return 2 + length if os_.task_running(task_id) else None
