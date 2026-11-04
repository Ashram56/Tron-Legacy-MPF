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
# EXTENDED ENDING (service menu, GAME OPTIONS item 1; docs/rom_differences.md): the film's last
# sequence on top of the ROM's three phases. Off by default = the ROM's rules.
GAUGE_SECONDS = 120          # act 1: the Portal closes; the gauge empties over this time (no sudden death)
GUARD_PERCENT = 50           # act 2: Clu guards one shot, which pays this percentage
WINDOW_SECONDS = 10          # act 3: Clu leaves with the disc, every shot pays for this long
COMBO_SECONDS = 6            # act 5: a different shot within this time raises the multiplier
COMBO_MAX = 5
ULTIMATE_AFTER = 8           # act 5: shots in the final wave before the disc pays the ultimate jackpot
ULTIMATE_POINTS = 10000000
# the shot lamps by shot (assets/rules/modes/portal_multiball.md 2 and 8: the last one of a group is its arrow),
# the CENTER lamps (17 PORTAL and the item lamps) and CENTER DISC
SHOT_LAMPS = {0: (13, 14, 15, 16), 1: (11, 50, 49), 2: (60, 61, 62, 63, 64), 3: (59, 58, 57),
              4: (42, 55, 56), 5: (36, 35, 34, 33)}
CENTER_LAMPS = (17, 18, 19, 20, 21, 22, 23, 24, 25, 27)
DISC_LAMP = 21
SHOT_NAMES = ("L ORBIT", "L RAMP", "L LOOP", "R LOOP", "R RAMP", "R ORBIT")


class Portal(Feature):
    name = "portal"
    HOOKS = ("player_first_ball", "portal_vuk", "portal_mb_shot", "portal_running", "multiball_end",
             "ball_end", "ball_end_wait", "portal_mb_super_lit")

    def __init__(self, os_):
        super().__init__(os_)
        self.counts = [0] * 7
        self.phase = 0
        self.super_value = 0
        self.total = 0
        self.end_wait = 0
        self.ext = False            # EXTENDED ENDING chosen when the Portal started
        self.started = 0.0
        self.guard = None
        self.window_end = 0.0
        self.combo, self.combo_shot, self.combo_time, self.wave_hits = 0, None, 0.0, 0
        self.ultimate_done = False
        for i in range(7):
            os_.register_poke(COUNTER_ADDR + 4 * i, (lambda i_: lambda p, v: self.counts.__setitem__(i_, v))(i),
                              players=1)
        os_.lamp_rule(self.lit_rule, leff=164, order=0x0102fa64)
        os_.lamp_rule(self.lit_rule, leff=163, tube=79, order=0x0102fa64)
        os_.lamp_rule(self.shot_lamps_rule, leff=166, order=0x01030150)
        os_.lamp_rule(self.background_rule, tube=81, order=0x01030150)
        os_.lamps.add_rule(self.ext_lamps, priority=-50)            # after the other lamp rules: it overrides
        os_.lamp_rule(self.all_shots_done, leff=167, order=0x0102f37c)
        os_.deff_rule(self.background_rule, 141, music=0x076, priority=7)
        # deff 141 [0x0102ffa0] reads pm_phase, the next award and pm_super_value on every frame
        os_.deff_text(141, self.ext_lines)
        os_.deff_live((141,), lambda: {"screen": self.phase, "next": self.award_value(),
                                       "super": self.super_value, "super_lit": self.super_value,
                                       "all_shots": 1000000})

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

    def portal_mb_super_lit(self):
        """portal_mb_super_lit [0x0102f654]: running (or grace) and all shots done (leff 76's rule)."""
        return self.all_shots_done()

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

    def shot_lamps_rule(self):
        """leff 166 (the ROM's shot lamps) unless the extended ending draws them (ext_lamps)."""
        return self.background_rule() and not self.ext

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
        self.ext_start()
        self.pd.portal_count = min(self.pd.get("portal_count", 0) + 1, 0xff)
        os_.hook("items_clear", False)
        os_.hook("sos_clear_skip_flags")
        os_.flag_clear(0x33)
        os_.audit(0x89)
        self.total = os_.score_add(1000000)
        sos_bonus = 0 if sos_played else os_.score_add(50000000)
        os_.show(0xa5, 140, total=self.total, sos_bonus=sos_bonus, screen=1 if sos_bonus else 0)
        os_.hook("dmb_cancel_restart_window")
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ shots [0x0102f6c8]

    def portal_mb_shot(self, shot):
        os_ = self.os
        if not self.running_or_grace() or not 0 <= shot < 7:
            return False
        awarded = False
        if self.ext:
            return self.ext_shot(shot)
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

    # ------------------------------------------------------------------ EXTENDED ENDING

    def ext_post(self, act, **kw):
        """Event for the display and the PuP: portal_act {act: 1..6} (the film's scenes)."""
        self.os.machine.events.post("tron_portal_act", act=act, **kw)

    def ext_start(self):
        """Act 1: the bridge, the Portal starts to close; act 2: Clu guards the first shot."""
        self.ext = bool(self.os.game_options[1])
        self.started = self.os.now
        self.guard = None
        self.window_end = 0.0
        self.combo, self.combo_shot, self.combo_time, self.wave_hits = 0, None, 0.0, 0
        self.ultimate_done = False
        if self.ext:
            self.next_guard()
            self.ext_post(1)
            self.ext_post(2, guard=self.guard)

    def gauge(self):
        """The Portal's gauge, 100 to 0 over GAUGE_SECONDS."""
        return max(0, 100 - int((self.os.now - self.started) * 100 / GAUGE_SECONDS))

    def next_guard(self):
        """Clu guards the next unfinished shot after the current guard (none when all are done)."""
        open_ = [i for i in range(6) if self.counts[i] < MAX_HITS[i]]
        if not open_:
            self.guard = None
            return
        after = [i for i in open_ if self.guard is None or i > self.guard]
        self.guard = (after or open_)[0]

    def window_open(self):
        return self.phase == 1 and self.os.now < self.window_end

    def ext_lines(self):
        """Instructions on deff 141 (lines 1, 2 = phase 0, 3 to 5 = phase 1, 6 = phase 2), 19 characters at most."""
        if not (self.ext and self.os.flag(0x37)):
            return {}
        if self.phase == 0:
            hold = ("CLU BLOCKS " + SHOT_NAMES[self.guard]) if self.guard is not None else "CROSS THE BRIDGE"
            return {1: hold, 2: "PORTAL OPEN %d%%" % self.gauge()}
        if self.phase == 1:
            if self.window_open():
                return {3: "CLU GONE: ALL PAY", 4: "SHOOT ANY SHOT", 5: "PORTAL OPEN %d%%" % self.gauge()}
            return {3: "ACTIVATE PORTAL", 4: "SHOOT DISC", 5: "SUPER=%s" % format(self.super_value, ",")}
        if self.wave_hits >= ULTIMATE_AFTER and not self.ultimate_done:
            return {6: "SHOOT DISC! 10M"}
        return {6: "COMBO x%d ALT SHOTS" % max(self.combo, 1)}

    def ext_lamps(self):
        """Lamp rule of the extended ending (replaces leff 166): solid = done or ready, flashing = shoot it,
        dark = Clu blocks it."""
        os_ = self.os
        if not (self.ext and os_.flag(0x37)):
            return
        lamps = os_.lamps
        for lamp in CENTER_LAMPS:
            lamps.lamp_set(lamp, 1)
        for shot, group in SHOT_LAMPS.items():
            done = self.counts[shot] >= MAX_HITS[shot]
            if self.phase == 0:
                if shot == self.guard:
                    states = [0] * len(group)                          # Clu is here: dark
                else:
                    states = [1 if i < self.counts[shot] else 2 if i == self.counts[shot] else 0
                              for i in range(len(group))]
            elif self.phase == 1:
                states = [2 if self.window_open() else 0] * len(group)
            else:
                states = [0 if shot == self.combo_shot else 2] * len(group)
            for lamp, state in zip(group, states):
                lamps.lamp_set(lamp, state)
        disc = self.phase == 1 and not self.window_open() or \
            self.phase == 2 and self.wave_hits >= ULTIMATE_AFTER and not self.ultimate_done
        lamps.lamp_set(DISC_LAMP, 2 if disc else 1)

    def ext_shot(self, shot):
        os_ = self.os
        awarded = False
        if self.phase == 0:
            if self.counts[shot] >= MAX_HITS[shot]:
                return False
            points = self.award_value()
            if shot == self.guard:
                points = points * GUARD_PERCENT // 100
            points = os_.score_add(points)
            self.counts[shot] += 1
            done = self.counts[shot] >= MAX_HITS[shot]
            added = done and self.add_a_ball()
            os_.deff_start(142, value=points, count=self.counts[shot], ball_added=bool(added))
            self.super_value += points
            self.total += points
            os_.audit(0x8a)
            if done:
                self.next_guard()
                self.ext_post(2, guard=self.guard)
            if self.all_shots_done():
                self.phase = 1                       # act 3: Clu takes the disc and leaves
                self.guard = None
                self.window_end = os_.now + WINDOW_SECONDS
                os_.after(round(WINDOW_SECONDS / TICK) + 1, os_.request_refresh)   # the lamps and text change
                self.ext_post(3)
            awarded = True
        elif self.phase == 1:
            if shot == 6 and self.all_shots_done():
                # act 4: Sam activates the Portal with the real disc; a fuller gauge pays more
                points = os_.score_add(self.super_value * (100 + self.gauge()) // 100)
                os_.deff_start(143, value=points)
                self.total += points
                os_.audit(0x8b)
                self.phase = 2
                self.ext_post(4, gauge=self.gauge())
                self.ext_post(5)
                awarded = True
            elif shot != 6 and os_.now < self.window_end:
                points = os_.score_add(self.award_value())    # the window of act 3
                os_.deff_start(142, value=points, count=MAX_HITS[shot], ball_added=False)
                self.total += points
                os_.audit(0x8a)
                awarded = True
        elif self.phase == 2:
            awarded = self.ext_wave(shot)
        if awarded:
            os_.request_refresh()
        return awarded

    def ext_wave(self, shot):
        """Act 5: Clu leaps, Kevin reintegrates him. Combos of different shots (1M, 2M ... 5M); after
        ULTIMATE_AFTER shots the disc pays the ultimate jackpot once (the reintegration)."""
        os_ = self.os
        if shot == 6 and self.wave_hits >= ULTIMATE_AFTER and not self.ultimate_done:
            self.ultimate_done = True
            points = os_.score_add(ULTIMATE_POINTS)
            os_.deff_start(143, value=points)
            self.total += points
            os_.audit(0x8b)
            self.ext_post(6)
            return True
        if shot == self.combo_shot or os_.now - self.combo_time > COMBO_SECONDS:
            self.combo = 0
        self.combo = min(self.combo + 1, COMBO_MAX)
        self.combo_shot, self.combo_time = shot, os_.now
        self.wave_hits += 1
        points = os_.score_add(1000000 * self.combo)
        os_.deff_start(144, value=points)
        self.total += points
        os_.audit(0x8c)
        return True

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
