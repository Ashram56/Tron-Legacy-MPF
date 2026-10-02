"""Disc Multiball with its restart window (assets/rules/modes/disc_multiball.md).

Started by Disc Battle (hook dmb_start). Shots use the spec's numbering: 0-5 blue shots, 6 Recognizer,
7 spinning disc (hook disc_mb_shot). Phase 0 blue shots grow the Jackpot and the disc collects it;
phase 1 the Recognizer scores the Jackpot; phase 2 the disc scores the Super Jackpot. An end before a
Super opens the restart window (tasks 0xad-0xaf), where a disc hit restarts it (hook
disc_restart_autofire). Other multiball starts close the window through hook dmb_cancel_restart_window.
"""
from tron.features import Feature

ORDER = 41
# shot -> (mask, base, step, max) [table 0x040d26c0]
SHOTS = (
    (0x01, 150000, 3000, 225000),      # left orbit
    (0x02, 100000, 2000, 150000),      # left ramp
    (0x04, 125000, 2500, 187500),      # left inner loop
    (0x08, 225000, 4500, 337500),      # right inner loop
    (0x10, 200000, 4000, 300000),      # right ramp
    (0x20, 175000, 3500, 262500),      # right orbit
    (0x40, 250000, 5000, 375000),      # Recognizer
    (0x80, 0, 0, 0),                   # spinning disc
)
PHASE_MASK = (0xbf, 0x40, 0x80)
END_TICKS = (156, 62)              # task 0xab, then 0xac, then the Total
COUNT_TICKS = 68                   # restart countdown, one count
WINDOW_TAIL = (187, 93)            # task 0xae, then 0xaf after the count reached 0
DISPLAY_WAIT = 0x138               # wait_display_idle(0x138) before the countdown


class DiscMultiball(Feature):
    name = "disc_multiball"
    HOOKS = ("player_first_ball", "ball_end", "ball_end_wait", "dmb_start", "disc_mb_shot",
             "disc_restart_autofire", "multiball_end", "dmb_cancel_restart_window", "dmb_bank_state",
             "dmb_disc_is_target")

    def __init__(self, os_):
        super().__init__(os_)
        self.phase = 0
        self.mask = 0
        self.level = self.disc_count = self.recog_count = 0
        self.jackpot = self.super = self.total = 0
        self.variant = 0
        self.restart_secs = 0
        self.intro_waiting = False      # task 0x88 queued, deff 46 not shown yet
        self.restart_waiting = False    # task 0x89 queued, deff 52 not shown yet
        self.total_wait = 0
        os_.display.bg_rule(self.status_display_cond, 47, 0x02a, 7)
        os_.display.bg_rule(self.restart_display_cond, 53, 0x02b, 7)
        os_.lamp_rule(self.status_display_cond, leff=45, tube=43, order=0x010081c0)
        os_.lamp_rule(lambda: self.running_or_ending() and self.phase == 1, leff=47, order=0x01006e14)
        os_.lamp_rule(lambda: os_.flag(0x24) and self.phase == 2, leff=46, order=0x010083b8)
        # same condition: the ROM starts leff 54 before leff 53 (traces/disc_multiball_restart.jsonl)
        os_.lamp_rule(self.restart_display_cond, leff=54, tube=49, order=0x010097ec)
        os_.lamp_rule(self.restart_display_cond, leff=53, order=0x010097ec)

    def player_first_ball(self):
        """Event 0x26 [0x01006d84]."""
        self.pd.dmb_started = 0
        self.pd.dmb_supers = 0

    # ------------------------------------------------------------------ conditions

    def running_or_ending(self):
        return self.os.flag(0x24) or self.os.task_running(0xab)

    def running_or_end_task(self):
        os_ = self.os
        return os_.flag(0x24) or os_.task_running(0xab) or os_.task_running(0xac)

    def window_running(self, last=0xaf):
        return any(self.os.task_running(t) for t in range(0xad, last + 1))

    def status_display_cond(self):
        """0x010081c0: running, and the intro is not still waiting for the display."""
        return self.os.flag(0x24) and not self.intro_waiting

    def restart_display_cond(self):
        """0x010097ec: countdown running, and deff 52 is not still waiting for the display."""
        return self.os.task_running(0xad) and not self.restart_waiting

    def dmb_bank_state(self):
        """0x01006e48: 0 no opinion, 1 bank up (phase 1), 2 bank down."""
        if not self.running_or_ending():
            return 2 if self.window_running(0xae) else 0
        return 1 if self.phase == 1 else 2

    def dmb_disc_is_target(self):
        """0x01006e88: the disc spins in phases 0 and 2 and in the restart window."""
        if not self.os.flag(0x24):
            return self.window_running(0xae)
        return self.phase in (0, 2)

    # ------------------------------------------------------------------ start [0x01007128]

    def seed(self, earlier):
        return min(250000 + 5000 * (self.level + earlier), 375000)

    def enter_phase(self, phase):
        self.phase = phase
        self.mask = PHASE_MASK[phase]
        if phase == 0:
            self.disc_count = 0
        elif phase == 1:
            self.recog_count = 0

    def dmb_start(self):
        os_, pd = self.os, self.pd
        in_play = os_.rom_balls_in_play()
        if not os_.multiball_start(in_play + 2 if in_play else 3, 625, 187):
            return False
        self.enter_phase(0)
        self.level = 0
        self.jackpot = self.seed(pd.dmb_started)
        self.super = 100000
        self.variant = 0
        self.total = os_.score_add(100000)
        os_.flag_set(0x24)
        os_.flag_set(0x25)
        self.intro_waiting = True
        os_.show(0x88, 46, on_start=self._intro_started)
        pd.dmb_started = min(pd.dmb_started + 1, 0xff)
        os_.hook("item_light", 5)
        os_.audit(0x41)
        os_.request_refresh()
        return True

    def _intro_started(self):
        self.intro_waiting = False
        self.os.request_refresh()

    # ------------------------------------------------------------------ shots [0x01007244]

    def disc_mb_shot(self, shot):
        os_ = self.os
        if not self.running_or_end_task():
            return False
        mask, base, step, cap = SHOTS[shot]
        if not self.mask & mask:
            return False
        if self.phase == 0:
            earlier = max(self.pd.dmb_started - 1, 0)
            if mask != 0x80:
                points = os_.score_add(min(base + step * (self.level + earlier), cap))
                self.jackpot += points
                os_.audit(0x43)
            else:
                points = os_.score_add(self.jackpot)
                self.super += points
                self.level += 1
                self.jackpot = self.seed(earlier)
                self.disc_count += 1
                if self.disc_count >= os_.adj_value(68):
                    self.variant = 0
                    self.enter_phase(1)
                os_.audit(0x42)
            self._jackpot_deff(48, points, 3)
            self.total += points
        elif self.phase == 1:
            points = os_.score_add(self.jackpot)
            self._jackpot_deff(49, points, 4)
            self.super += points
            self.total += points
            os_.audit(0x44)
            self.recog_count += 1
            if self.recog_count >= os_.adj_value(69):
                self.enter_phase(2)
        else:
            points = os_.score_add(self.super)
            os_.deff_start(50, points=points)
            self.total += points
            self.pd.dmb_supers = min(self.pd.dmb_supers + 1, 0xff)
            os_.audit(0x45)
            os_.hook("item_collect", 5)
            self.enter_phase(0)
            self.super = 100000
            self.variant = 0
            os_.flag_clear(0x25)
        os_.request_refresh()
        return True

    def _jackpot_deff(self, deff_id, points, last_variant):
        if self.os.deff_start(deff_id, points=points):
            if self.variant > last_variant:
                self.variant = 0
            self.variant += 1           # clip variant: written to the deff, never read (dead)

    # ------------------------------------------------------------------ end [0x01007714]

    def multiball_end(self):
        os_ = self.os
        if not os_.flag(0x24):
            return False
        os_.flag_clear(0x24)
        if not os_.flag(0x25):
            os_.task_start(0xab, END_TICKS[0], self._end_ac)
        else:
            self.open_restart_window()
        os_.request_refresh()
        return True

    def _end_ac(self):
        self.os.request_refresh()
        self.os.task_start(0xac, END_TICKS[1], self._end_total)

    def _end_total(self):
        self.os.request_refresh()
        self.show_total()

    def show_total(self):
        """0x01007558: Total deff 51 (task 0x4e), not while tilted or after the game."""
        os_ = self.os
        if os_.state & 0x310 or not self.total:
            return False
        os_.deff_start(51, total=self.total)
        return True

    def ball_end(self):
        """Event 0x1d [0x010078ec]: a running (or ending) multiball shows its Total now."""
        os_ = self.os
        self.total_wait = 0
        self.close_window()
        if self.running_or_end_task():
            if os_.flag(0x24):
                os_.flag_clear(0x24)
            os_.task_kill(0xab)
            os_.task_kill(0xac)
            if self.show_total():
                self.total_wait = round(os_.display.media[51].seconds / 0.01626)

    def ball_end_wait(self):
        return self.total_wait or None

    # ------------------------------------------------------------------ restart window

    def open_restart_window(self):
        """0x0100769c: adj 70 = 4 means no window."""
        os_ = self.os
        secs = os_.adj_value(70)
        if secs == 4:
            return False
        self.restart_secs = secs
        os_.flag_clear(0x25)
        self.restart_waiting = True
        os_.show(0x89, 52, on_start=self._restart_deff_started)
        self._wait_display(0)
        os_.request_refresh()
        return True

    def _restart_deff_started(self):
        self.restart_waiting = False
        self.os.request_refresh()

    def _wait_display(self, waited):
        """task 0xad: wait_display_idle(0x138), then count every 68 ticks."""
        os_ = self.os
        if waited < DISPLAY_WAIT and (os_.display.fg is not None or self.restart_waiting):
            os_.task_start(0xad, 1, lambda: self._wait_display(waited + 1))
        else:
            os_.task_start(0xad, COUNT_TICKS, self._count)

    def _count(self):
        os_ = self.os
        if not self.restart_secs:
            os_.request_refresh()
            os_.task_start(0xae, WINDOW_TAIL[0], self._window_tail)
            return
        old = self.restart_secs
        self.restart_secs -= 1
        if old == 8:
            os_.sound(0x02e)
        elif 2 <= old <= 6:
            os_.sound2(0x02f, self.restart_secs)    # "five" ... "one"
        os_.task_start(0xad, COUNT_TICKS, self._count)

    def _window_tail(self):
        self.os.request_refresh()
        self.os.task_start(0xaf, WINDOW_TAIL[1], self.os.request_refresh)

    def close_window(self):
        for task in (0xad, 0xae, 0xaf):
            self.os.task_kill(task)
        self.os.display.cancel(0x89)
        self.restart_waiting = False

    def dmb_cancel_restart_window(self):
        """0x010078c8: Light Cycle, Portal, Sea of Simulation or a Quorra restart starts."""
        self.close_window()
        self.os.request_refresh()

    def disc_restart_autofire(self):
        """0x0100781c: a disc hit while the window runs restarts the multiball (adj 71 = 0: nothing)."""
        os_ = self.os
        if not self.window_running():
            return False
        self.close_window()
        autofire = os_.adj_value(71)
        if not autofire:
            return False
        in_play = os_.rom_balls_in_play()
        if not os_.multiball_start(in_play + 1 if in_play else 2, autofire * 62, 93):
            return False
        os_.task_kill(0xab)
        os_.task_kill(0xac)
        os_.flag_set(0x24)
        os_.show(0x8a, 54)
        os_.request_refresh()
        return True


feature = DiscMultiball
