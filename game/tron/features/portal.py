"""Portal Multiball, the wizard mode (assets/rules/modes/portal_multiball.md).

Lit when all nine items are collected, started at the VUK (on_vuk -> portal_vuk) as a 4-ball multiball.
Shots (portal_mb_shot numbering): 0 left orbit, 1 left ramp, 2 left inner loop, 3 right inner loop,
4 right ramp, 5 right orbit, 6 disc. Phase 0: make each shot its number of times (adds a ball when one
is complete); phase 1: Super Jackpot at the disc; phase 2: every shot 1,000,000.
Game flag 0x37 = running; task 0xd2 = the grace after the multiball drops to one ball.
"""
from tron.features import Feature
from tron.os_layer import TICK

ORDER = 35
MAX_HITS = (4, 3, 5, 3, 3, 4, 0)            # shot table 0x040d6e14
COUNTER_ADDR = 0x3b85c                      # pm_cnt_* bytes, 4 apart
SAVE_TICKS, GRACE_TICKS = 0x3a9, 0x138
ADD_BALL_TICKS = 0x3e


class Portal(Feature):
    name = "portal"
    HOOKS = ("player_first_ball", "portal_vuk", "portal_mb_shot", "portal_running", "multiball_end",
             "ball_end", "ball_end_wait")

    def __init__(self, os_):
        super().__init__(os_)
        self.counts = [0] * 7
        self.phase = 0
        self.super_value = 0
        self.total = 0
        self.end_wait = 0
        for i in range(7):
            os_.register_poke(COUNTER_ADDR + 4 * i, (lambda i_: lambda p, v: self.counts.__setitem__(i_, v))(i),
                              players=1)
        os_.lamp_rule(self.lit_rule, leff=164, order=0x0102fa64)
        os_.lamp_rule(self.lit_rule, leff=163, tube=79, order=0x0102fa64)
        os_.lamp_rule(self.background_rule, leff=166, tube=81, order=0x01030150)
        os_.lamp_rule(self.all_shots_done, leff=167, order=0x0102f37c)
        os_.deff_rule(self.background_rule, 141, music=0x076, priority=7)

    def player_first_ball(self):
        """Event 0x26 [0x0102f2e8]: Portals started this game (read by the bonus)."""
        self.pd.portal_count = 0

    # ------------------------------------------------------------------ state

    def portal_running(self):
        """FUN_0102f680: flag 0x37."""
        return self.os.flag(0x37)

    def running_or_grace(self):
        """FUN_0102f694."""
        return self.os.flag(0x37) or self.os.task_running(0xd2)

    def all_shots_done(self):
        """portal_mb_all_shots_done [0x0102f37c] (the disc's max is 0)."""
        return self.running_or_grace() and all(c >= m for c, m in zip(self.counts, MAX_HITS))

    def can_start(self, lit):
        """portal_mb_can_start [0x0102f434]."""
        os_ = self.os
        return bool(lit) and not os_.any_multiball() and not os_.task_running(0xad) and not os_.flag(0x34)

    def lit_rule(self):
        """portal_mb_lit_rule [0x0102fa64]."""
        return self.can_start(self.os.hook("items_all_collected"))

    def background_rule(self):
        """[0x01030150]: running, and the intro (task 0xa5) is not still waiting for the display."""
        os_ = self.os
        return os_.flag(0x37) and not (os_.display.task_running(0xa5) and not os_.display.running(140))

    def award_value(self):
        """portal_mb_award_value [0x0102f5f4]."""
        return min(500000 + 50000 * sum(self.counts), 1500000)

    # ------------------------------------------------------------------ start [0x0102f474]

    def portal_vuk(self, all_collected):
        os_ = self.os
        if not self.can_start(all_collected):
            return False
        balls = os_.rom_balls_in_play()
        if not os_.multiball_start(4 if balls == 0 else balls + 3, SAVE_TICKS, GRACE_TICKS):
            return False
        sos_played = os_.flag(0x33)
        self.counts = [0] * 7
        self.super_value = 1000000
        self.phase = 0
        if not os_.any_multiball():
            os_.flag_clear(0x32)
        os_.flag_set(0x37)
        self.pd.portal_count = min(self.pd.get("portal_count", 0) + 1, 0xff)
        os_.hook("items_clear", False)
        os_.hook("sos_clear_skip_flags")
        os_.flag_clear(0x33)
        os_.audit(0x89)
        self.total = os_.score_add(1000000)
        sos_bonus = 0 if sos_played else os_.score_add(50000000)
        os_.show(0xa5, 140, total=self.total, sos_bonus=sos_bonus)
        os_.hook("dmb_cancel_restart_window")
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ shots [0x0102f6c8]

    def portal_mb_shot(self, shot):
        os_ = self.os
        if not self.running_or_grace() or not 0 <= shot < 7:
            return False
        awarded = False
        if self.phase == 2:
            points = os_.score_add(1000000)
            os_.deff_start(144, value=points)
            self.total += points
            os_.audit(0x8c)
            awarded = True
        elif self.phase == 1:
            if shot == 6 and self.all_shots_done():
                points = os_.score_add(self.super_value)
                os_.deff_start(143, value=points)
                self.total += points
                os_.audit(0x8b)
                self.phase = 2
                awarded = True
        elif self.counts[shot] < MAX_HITS[shot]:
            points = os_.score_add(self.award_value())
            self.counts[shot] += 1
            added = self.counts[shot] >= MAX_HITS[shot] and self.add_a_ball()
            os_.deff_start(142, value=points, count=self.counts[shot], ball_added=bool(added))
            self.super_value += points
            self.total += points
            os_.audit(0x8a)
            if self.all_shots_done():
                self.phase = 1
            awarded = True
        if awarded:
            os_.request_refresh()
        return awarded

    def add_a_ball(self):
        """portal_mb_add_a_ball [0x0102f314]: multiball_add_balls(1, save 62, grace 62)."""
        os_ = self.os
        if os_.multiball_start(os_.rom_balls_in_play() + 1, ADD_BALL_TICKS, ADD_BALL_TICKS):
            if os_.task_kill(0xd2):                  # portal_mb_restart_from_grace [0x0102f8fc]
                os_.flag_set(0x37)
                os_.request_refresh()
            return True
        return False

    # ------------------------------------------------------------------ end

    def multiball_end(self):
        """portal_mb_down_to_one_ball [0x0102f8b8]: grace task 0xd2, then the total."""
        os_ = self.os
        if os_.flag(0x37):
            os_.flag_clear(0x37)
            os_.task_start(0xd2, GRACE_TICKS, self.show_total)
            os_.request_refresh()

    def show_total(self):
        """portal_mb_show_total [0x0102f94c], task 0x57: deff 145 (not when tilted or game over)."""
        os_ = self.os
        if os_.state & 0x310 or not self.total:
            return 0
        os_.deff_start(145, total=self.total)
        info = os_.display.media.get(145)
        return round(info.seconds / TICK) if info else 0

    def ball_end(self):
        """Event 0x1d [0x0102f9a4]."""
        self.end_wait = 0
        if self.running_or_grace():
            self.os.flag_clear(0x37)
            self.os.task_kill(0xd2)
            self.end_wait = self.show_total()

    def ball_end_wait(self):
        return self.end_wait or None


feature = Portal
