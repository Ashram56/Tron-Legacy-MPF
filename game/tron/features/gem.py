"""GEM hurry-up "FOLLOW GEM" (assets/rules/modes/gem_hurryup.md).

The right inner loop (sw39) qualifies (hook gem_qualify: 3 loops, 5 on later starts) and, while the
mode runs, collects a growing award (hook gem_hurryup_awards, shot mask 8). Spinner spins add time
(hook gem_spin). 25 s clock: task 0xc2, end grace 0xc3.
"""
from tron.features import Feature
from tron.features.timed_modes import Countdown, show_total, total_wait_ticks

ORDER = 30
GEM_ITEM = 1


class Gem(Feature):
    name = "gem"
    HOOKS = ("player_first_ball", "ball_end", "ball_end_wait", "gem_qualify", "gem_hurryup_awards",
             "gem_spin", "timed_feature_running", "more_time", "arcade_gem_weight", "arcade_gem")

    def __init__(self, os_):
        super().__init__(os_)
        self.clock = Countdown(os_, "gem_timer", 0xc2, 0xc3, self._tick, self._show_total, intro=0x96)
        self.shots = self.total = 0
        os_.lamp_rule(self.clock.counting, leff=83, tube=18, order=0x01013b5c)
        self.rule = os_.deff_rule(self.clock.counting, 77, 0x08f, prio=5)

    def player_first_ball(self):
        """gem_player_init 0x010138f8."""
        pd = self.pd
        pd.gem_starts = pd.gem_awards = pd.gem_progress = pd.gem_snd_idx = 0

    def ball_end(self):
        self.end_now()                             # gem_on_end_of_ball 0x01013970

    def ball_end_wait(self):
        return total_wait_ticks(self.os, 0x54, 79)

    # ------------------------------------------------------------------ qualifying

    def qualify_enabled(self):
        """0x01013980: not running (incl. grace), no Sea of Simulation (0x34), no Portal (0x37)."""
        return not self.clock.running() and not self.os.flag(0x34) and not self.os.flag(0x37)

    def gem_qualify(self, silent=False):
        """gem_qualify_loop 0x01013a08 (silent: Flynn's Arcade ADV. GEM, no deff 75)."""
        os_, pd = self.os, self.pd
        if not self.qualify_enabled():
            return False
        pd.gem_progress = min(pd.gem_progress + 1, 0xff)
        needed = 5 if pd.gem_starts else 3
        if pd.gem_progress < needed:
            if not silent:
                os_.deff_start(75, more=needed - pd.gem_progress)
        else:
            self.start()
        os_.score_add(250000)
        return True

    def start(self):
        """on_gem_hurryup_started 0x01013c5c."""
        os_, pd = self.os, self.pd
        if not self.qualify_enabled():
            return False
        if not os_.hook("timed_feature_running"):
            os_.flag_clear(0x2c)
        pd.gem_progress = 0
        self.total = os_.score_add(250000)
        self.clock.start()
        self.shots = 8
        self.clock.seconds = 25
        os_.show(0x96, 76)
        pd.gem_starts = min(pd.gem_starts + 1, 0xff)
        os_.hook("item_light", GEM_ITEM)
        pd.gem_awards = pd.gem_snd_idx = 0
        os_.audit(0x50)
        os_.display.raise_rule(self.rule)
        os_.request_refresh()
        return True

    def _tick(self):
        self.clock.seconds -= 1
        return self.clock.seconds == 0

    # ------------------------------------------------------------------ while running

    def gem_hurryup_awards(self, bit):
        """on_gem_hurryup_awards 0x01013da8: the loop stays lit, the award grows."""
        os_, pd = self.os, self.pd
        if not self.clock.running() or not self.shots & bit:
            return False
        points = min(750000 + 250000 * pd.gem_awards, 2500000)
        os_.score_add(points)
        self.total += points
        pd.gem_awards = min(pd.gem_awards + 1, 0xff)
        os_.hook("item_collect", GEM_ITEM)
        os_.deff_start(78, value=points, followings=pd.gem_awards)
        os_.audit(0x51)
        os_.request_refresh()
        return True

    def gem_spin(self):
        """gem_spinner_add_time 0x01013eac: every spin adds a second (at least 5, at most 40) and
        restarts the countdown task (lead-in again); a spin in the grace revives it."""
        if not self.clock.running():
            return False
        self.clock.start()
        if self.clock.seconds < 5:
            self.clock.seconds = 5
        elif self.clock.seconds < 40:
            self.clock.seconds += 1
        self.os.request_refresh()
        return True

    # ------------------------------------------------------------------ end

    def end_now(self):
        """gem_end_now 0x01013fa0."""
        if not self.clock.running():
            return False
        self.clock.kill()
        self._show_total()
        self.os.request_refresh()
        return True

    def _show_total(self):
        """gem_end_show_total 0x01013b48: deff 79 (queued task 0x54), not in tilt or game over."""
        if self.os.state & 0x310 or not self.total:
            return
        show_total(self.os, 0x54, 79, total=self.total, followings=self.pd.gem_awards)

    # ------------------------------------------------------------------ Flynn's Arcade

    def timed_feature_running(self):
        return True if self.clock.counting() else None

    def more_time(self):
        """gem_more_time 0x01013f34."""
        if not self.clock.running():
            return None
        self.clock.start()
        self.clock.seconds = 40
        self.os.request_refresh()
        return True

    def arcade_gem_weight(self, default):
        return default if self.qualify_enabled() else 0

    def arcade_gem(self):
        """ADV. GEM = gem_qualify(1) [0x0100e008]."""
        return self.gem_qualify(silent=True)


feature = Gem
