"""ZUSE targets and ZUSE fast scoring (assets/rules/modes/zuse_fast_scoring.md).

Targets sw7 (Z)USE, sw8 Z(U)SE, sw48 ZU(S)E, sw13 ZUS(E) (index 0-3). Completing Z-U-S-E qualifies
(hook zuse_letter); the 1st completion, then every 4th, starts fast scoring: nearly every playfield
switch (hook zuse_target_hit, index 4 = "any switch") scores the fast-scoring value. Clock: task 0x59
(adj 66 seconds), end grace 0x5b; hit queue task 0x80; reminder speech task 0x5a.
"""
from tron.features import Feature
from tron.features.timed_modes import Countdown, show_total, total_wait_ticks
from tron.os_layer import TICK

ORDER = 30
ZUSE_ITEM = 3
ANY = 0x10                      # zfs_targets marker bit, table 0x040d6ef0
ALL = 0x1f
QUEUE_IDLE = 0x5d               # task_80 exits after 93 idle ticks
REMIND_TICKS = 0x271            # task 0x5a sleeps 625 ticks between reminders
REMIND_PLAY_TICKS = 11          # call 0xb5 plays ~11 ticks (traces/zuse_fast_scoring.jsonl: 636-tick period)


class Zuse(Feature):
    name = "zuse"
    HOOKS = ("player_first_ball", "ball_start", "ball_end", "tilt", "ball_end_wait", "zuse_letter",
             "zuse_target_hit", "timed_feature_running", "more_time", "arcade_zuse_weight", "arcade_zuse")

    def __init__(self, os_):
        super().__init__(os_)
        self.clock = Countdown(os_, "zfs_timer", 0x59, 0x5b, self._tick, self._show_total, lead_in=0, step=6, steps=11,
                               restart_on_pause=True, tail=0, grace_ticks=250)
        self.value = self.total = self.queue = 0
        self.targets = ANY
        self._last_drain = -1.0
        # leff rules are tried newest registration first (equal priority): leff 125, then leff 124
        os_.lamp_rule(self.clock.counting, leff=125, order=0x01031b5c)
        os_.lamp_rule(self.clock.counting, leff=124, tube=30, order=0x01031b5d)
        self.rule = os_.display.bg_rule(self._background, 95, 0x0aa, 5)

    def player_first_ball(self):
        """zfs_player_init 0x010315d8 and zuse_player_init 0x01033680."""
        pd = self.pd
        pd.zfs_starts = pd.zfs_time_ext = 0
        self.os.flag_clear(0x31)
        pd.zuse_completions = 0
        pd.zuse_needed = 1
        pd.zuse_letters = 0                        # zuse_letters_reset: no ZUSE switch disabled
        pd.zfs_switch_hits = 0

    def ball_start(self):
        self.pd.zfs_switch_hits = 0                # zfs_ball_init 0x01031624

    def ball_end(self):
        self.end_now()                             # zfs_on_end_of_ball 0x01031664

    def tilt(self):
        self.end_now()                             # zfs_on_tilt 0x01031654

    def ball_end_wait(self):
        return total_wait_ticks(self.os, 0x55, 99)

    # ------------------------------------------------------------------ qualifying (Z-U-S-E letters)

    def qualify_enabled(self):
        """0x01033744: FS not running, no Sea of Simulation, Portal or End of Line."""
        return not self.clock.running() and not any(self.os.flag(f) for f in (0x34, 0x37, 0x27))

    def zuse_letter(self, idx):
        """zuse_letter_hit 0x01033790."""
        os_, pd = self.os, self.pd
        bit = 1 << idx
        if not self.qualify_enabled():
            os_.leff_start(119)
            os_.sound(0x0a4)
            os_.score_add(5000)
            return True
        if os_.task_running(0x4c):
            return False
        letters = pd.zuse_letters
        if not bit & letters or letters & 0xf == 0xf:
            if (letters | bit) & 0xf == 0xf:
                self._complete(silent=False)
                os_.task_start(0x4c, 10)
            else:
                pd.zuse_letters = letters | bit
                os_.leff_start(120)
                os_.sound(0x0a6)
                os_.task_start(0x4a, 62)
                os_.deff_start(91, lit=letters, new=bit)
                os_.score_add(75000)
        else:
            os_.leff_start(121)
            os_.sound(0x0a5)
            os_.score_add(10000)
        os_.request_refresh()
        return True

    def _complete(self, silent):
        """A completed Z-U-S-E set [0x01033790 / zuse_complete_set_adv 0x010339fc]."""
        os_, pd = self.os, self.pd
        before = pd.zuse_completions
        pd.zuse_completions = min(pd.zuse_completions + 1, 0xff)
        pd.zuse_letters = 0
        if not silent:
            os_.leff_start(122)
            os_.sound(0x0a8)
        os_.score_add(min(250000 + 25000 * before, 750000))
        if pd.zuse_completions < pd.zuse_needed:
            if not silent:
                os_.deff_start(92, more=pd.zuse_needed - pd.zuse_completions)
        else:
            self.start()
            pd.zuse_needed = min(pd.zuse_needed + 4, 0xff)

    # ------------------------------------------------------------------ fast scoring

    def start(self):
        """on_zuse_fastscoring_started 0x010318ac."""
        os_, pd = self.os, self.pd
        if not os_.hook("timed_feature_running"):
            os_.flag_clear(0x2c)
        self.clock.kill()
        self.clock.seconds = os_.adj_value(66)
        self.total = os_.score_add(100000)
        self.clock.start()
        self.targets = ANY
        self.value = min(10000 + 5000 * pd.zfs_starts, 50000)
        # task 0x9b runs FUN_0100f9d8, which plays the intro without waiting for the display priority
        os_.show(0x9b, 94, threshold=0x100, value=self.value)
        self._remind_start()
        os_.flag_clear(0x31)
        pd.zfs_starts = min(pd.zfs_starts + 1, 0xff)
        os_.hook("item_light", ZUSE_ITEM)
        os_.audit(0x52)
        os_.display.bg_raise(self.rule)
        os_.request_refresh()
        return True

    def _background(self):
        """zfs_background_rule_cond 0x01031fe0."""
        os_ = self.os
        return self.clock.counting() and not (
            os_.display.show_task_running(0x9b) and not os_.display.running(94))

    def _tick(self):
        if not self.clock.seconds:
            return True
        self.clock.seconds -= 1
        return False

    def zuse_target_hit(self, target):
        """zuse_target_hit 0x01031d0c: target 0-3 = a ZUSE target, 4 = any other switch."""
        os_ = self.os
        if not self.clock.running():
            return 0
        bit = 1 << target if target < 4 else ANY
        if bit != ANY:
            if not bit & self.targets:
                self.targets |= bit
                if self.targets & ALL == ALL:
                    self.targets = ANY
                    self.pd.zfs_time_ext = min(self.pd.zfs_time_ext + 1, 0xff)
                    os_.hook("item_collect", ZUSE_ITEM)
                    self.add_time(10)
                else:
                    self.value_raise()
                    os_.leff_start(120)
            else:
                os_.leff_start(121)
        if not os_.task_running(0x80):
            self.queue = 0
            self.score_hit()
            self._queue_task(0)
        else:
            # task 0x80 scores one queued hit per tick; it runs after the switch task in the same tick
            self.queue += 1
            os_.after(0, self._drain_now)
        os_.request_refresh()
        return 1

    def value_raise(self):
        """zfs_value_raise 0x01031a5c: +1,000 per new target (max 50,000), deff 97 when it rose."""
        if not self.clock.counting():
            return 0
        raised = min(self.value + 1000, 50000) - self.value
        self.value += raised
        if raised:
            self.os.deff_start(97, value=self.value)
        return raised

    def add_time(self, seconds):
        """zfs_add_time 0x01031ab8: all four targets add 10 s (max 45) and restart the countdown."""
        os_ = self.os
        if not self.clock.running():
            return 0
        old = self.clock.seconds
        self.clock.seconds = min(old + (seconds or os_.adj_value(66)), 45)
        self.clock.start()
        os_.deff_start(98, timer=self.clock.seconds, value=self.value)
        os_.request_refresh()
        return max(0, self.clock.seconds - old)

    def score_hit(self):
        """zfs_score_hit 0x01031b88."""
        os_, pd = self.os, self.pd
        points = os_.score_add(self.value)
        self.total += points
        pd.zfs_switch_hits = min(pd.zfs_switch_hits + 1, 0xffff)
        if os_.display.running(94) or os_.display.show_task_running(0x9b):
            return
        if not os_.display.running(96) and not os_.any_multiball():
            os_.deff_start(96, value=points)
        os_.sound(0x0b1)
        os_.leff_start(129)

    def _queue_task(self, idle):
        """task_80_zfs_hit_queue 0x01031cc0."""
        def tick():
            n = idle + 1
            if self.queue:
                self._drain()
                n = 0
            if n < QUEUE_IDLE:
                self._queue_task(n)
        self.os.task_start(0x80, 1, tick)

    def _drain(self):
        self._last_drain = self.os.now
        self.queue -= 1
        self.score_hit()

    def _drain_now(self):
        if self.queue and self.os.task_running(0x80) and self.os.now - self._last_drain > TICK / 2:
            self._drain()
            self._queue_task(0)

    # ------------------------------------------------------------------ reminder speech

    def _remind_start(self):
        """task 0x5a [0x0103167c]: every ~10 s while the countdown runs and no multiball runs."""
        self.os.task_start(0x5a, REMIND_TICKS, self._remind)

    def _remind(self):
        os_ = self.os
        if not self.clock.counting():
            return
        if not os_.any_multiball():
            os_.sound(0x0b5)
        os_.task_start(0x5a, REMIND_PLAY_TICKS + REMIND_TICKS, self._remind)

    # ------------------------------------------------------------------ end

    def end_now(self):
        """zfs_end_now 0x01031f8c (end of ball, tilt)."""
        if not self.clock.running():
            return False
        self.clock.kill()
        self._show_total()
        return True

    def _show_total(self):
        """zfs_end_show_total 0x0103171c: deff 99 (queued task 0x55), not in tilt or game over."""
        if self.os.state & 0x310 or not self.total:
            return
        show_total(self.os, 0x55, 99, total=self.total)

    # ------------------------------------------------------------------ Flynn's Arcade

    def timed_feature_running(self):
        return True if self.clock.counting() else None

    def more_time(self):
        """zfs_more_time 0x01031f08: 45 s, countdown and reminder restarted."""
        if not self.clock.running():
            return None
        self.clock.start()
        self.clock.seconds = 45
        self._remind_start()
        self.os.request_refresh()
        return True

    def arcade_zuse_weight(self, default):
        """FUN_01031804: FS not running, no multiball, no Sea of Simulation, flag 0x31 clear."""
        os_ = self.os
        ok = not self.clock.running() and not os_.any_multiball() and not os_.flag(0x34) and not os_.flag(0x31)
        return default if ok else 0

    def arcade_zuse(self):
        """ADV. ZUSE = zuse_complete_set_adv(1) [0x010339fc]: one silent completion."""
        if not self.qualify_enabled():
            return False
        self._complete(silent=True)
        self.os.request_refresh()
        return True


feature = Zuse
