"""TRON drop targets (sw1-4) and the TRON timed awards (assets/rules/modes/tron_targets.md).

Awards (bits): 1 DOUBLE SCORING (task 0xc6), 2 SUPER POPS / "BUMPERS" (task 199), 4 SUPER SPINNERS
(task 200). The switch layer reads tasks 199 / 200 for the x3 pop and spinner values; double scoring
doubles every score through the OS score event hook (event 0x4c). A ZEN charge (zen.py,
hook zen_use_charge) turns a new letter into a TRON completion.
"""
from tron.features import Feature

ORDER = 30
TRON_ITEM = 8
# award bit -> (task, start sound, timer adjustment)
AWARDS = {1: (0xc6, 0x0ff, 74), 2: (199, 0x101, 73), 4: (200, 0x103, 72)}
SWITCHES = (1, 2, 3, 4)
SW_NAME = {1: "s_tron_t", 2: "s_tron_r", 3: "s_tron_o", 4: "s_tron_n"}
STEPS = 10                                       # 10 x 6 ticks = one award "second"
STEP_TICKS = 6
PAUSE_SHOWS = (0xa0, 0xa2)                       # Sea of Simulation start / skip shows pause the clocks
BANK_RESET_TICKS = 15
BANK_RESET_TRIES = 3


# next lit award [table 0x040d2848, indexed running * 8 + lit]: row = running, columns lit 0, 1, 2, 4, other
ROTATE = {0: (1, 2, 4, 1, 1), 1: (2, 2, 4, 2, 2), 2: (1, 4, 1, 1, 1), 3: (4,) * 5,
          4: (1, 2, 1, 1, 1), 5: (2,) * 5, 6: (1,) * 5, 7: (0,) * 5}


def rotate(running, lit):
    return ROTATE[running & 7][{0: 0, 1: 1, 2: 2, 4: 3}.get(lit, 4)]


class TronTargets(Feature):
    name = "tron_targets"
    HOOKS = ("player_first_ball", "ball_start", "drop_bank_hit", "tron_letter",
             "pop_lamp_pattern", "score_event", "timed_feature_running", "more_time")

    def __init__(self, os_):
        super().__init__(os_)
        self.secs = {1: 0, 2: 0, 4: 0}          # tron_ds/bumpers/spinners_secs (global, not per player)
        self.drops_up = {sw: 1 for sw in SWITCHES}
        self.repeat_sound = 0                    # tron_repeat_sound_flag 0x3b740
        os_.lamp_rule(lambda: os_.task_running(0xc6), leff=132, order=0x0100c734)

    # ------------------------------------------------------------------ resets

    def player_first_ball(self):
        """tron_award_game_start_clear [0x0100c0bc] and FUN_0102c3b4 (letters, completions)."""
        pd = self.pd
        pd.tron_started_set = 0
        pd.tron_item_count = 0
        pd.tron_running = 0
        pd.tron_lit = 0
        pd.tron_completions = 0
        self.repeat_sound = 0
        self.letters_reset()

    def ball_start(self):
        """tron_award_ball_start [0x0100c154]: nothing running, lit = 1 then rotated (BUMPERS);
        drop_bank_ball_start_reset [0x0100b1a4]: the bank resets."""
        self.kill_awards()
        self.secs = {1: 0, 2: 0, 4: 0}
        self.pd.tron_lit = 1
        self.pd.tron_running = 0
        self.rotate_lit()
        self.bank_reset()

    def kill_awards(self):
        """The award tasks (flag 0x100) end with the ball. They still run during the bonus (a running
        DOUBLE SCORING doubles it: traces/zen_rollover.jsonl), so they are killed at the next ball start."""
        for task, _, _ in AWARDS.values():
            self.os.task_kill(task)

    def letters_reset(self):
        """tron_letters_reset [0x0102c358]: letters = the mask of disabled targets (none here)."""
        self.pd.tron_letters = 0

    # ------------------------------------------------------------------ drop bank (object 0x3b744)

    def drop_bank_hit(self, sw):
        """drop_bank_switch_handler [0x0100b4b8]: only a drop that is up counts; it is then down.
        All four down -> reset task 0x76."""
        if not self.drops_up.get(sw):
            return False
        self.drops_up[sw] = 0
        if not any(self.drops_up.values()):
            self.bank_reset()
        return True

    def bank_reset(self, tries=BANK_RESET_TRIES):
        """drop_bank_reset_task 0x76 [0x0100bcdc]: while a drop is down, pulse coil 3 (up to 3 times,
        15 ticks apart); then read the switches, an open switch = drop up [0x0100bf04]."""
        switches = self.machine.switches
        down = {sw for sw in SWITCHES if switches[SW_NAME[sw]].state}
        if down and tries:
            coil = self.machine.coils.get("c_drop_target_bank")
            if coil:
                coil.pulse()
            self.os.task_start(0x76, BANK_RESET_TICKS, lambda: self.bank_reset(tries - 1))
            return
        self.drops_up = {sw: 0 if sw in down else 1 for sw in SWITCHES}

    # ------------------------------------------------------------------ letters [0x0102c588]

    def tron_letter(self, bit, lamp):
        os_, pd = self.os, self.pd
        if os_.task_running(0x77):
            return
        letters = pd.tron_letters
        if letters & bit and letters & 0xf != 0xf:
            # letter already collected
            os_.leff_start(39)
            os_.sound(0x04b if self.repeat_sound else 0x04a)
            self.repeat_sound ^= 1
            os_.score_add(450)
            return
        new = letters | bit
        if new & 0xf != 0xf and not os_.hook("zen_use_charge"):
            pd.tron_letters = new
            os_.deff_start(107, old=letters, new=bit)
            os_.leff_start(38)
            os_.sound(0x04c)
            os_.score_add(10000)
            return
        # TRON completed (the last letter, or a new letter with a ZEN charge)
        self.letters_reset()
        award = self.start_lit()
        pd.tron_completions = min(pd.tron_completions + 1, 0xffff)
        os_.hook("item_light", TRON_ITEM)
        self._completed_show(pd.tron_completions, award, 0)
        os_.score_add(100000)
        os_.task_start(0x77, 10)

    def _completed_show(self, count, award, waited):
        """task_9f [0x0102c4c4]: wait (up to 310 ticks) for deff 107 to end, then deff 106, leff 40 and
        speech 0x04e (BUMPERS) or 0x04d."""
        os_ = self.os
        if waited == 0 or (os_.display.running(107) and waited < 0x136):
            os_.task_start(0x9f, 5 if waited else 2, lambda: self._completed_show(count, award, waited + 5))
            return
        os_.deff_start(106, count=count, award=award)
        os_.leff_start(40)
        os_.sound(0x04e if award == 2 else 0x04d)

    # ------------------------------------------------------------------ awards

    def rotate_lit(self):
        """tron_award_rotate_lit [0x0100c470] (every ball start and every pop bumper hit)."""
        if self.os.state & 0x311:
            return
        pd = self.pd
        pd.tron_lit = rotate(pd.tron_running, pd.tron_lit)

    def pop_lamp_pattern(self):
        self.rotate_lit()

    def start_lit(self):
        """tron_award_start_lit [0x0100c7bc]; returns the award started (0 when none was lit)."""
        os_, pd = self.os, self.pd
        award = pd.tron_lit
        if not award:
            os_.sound(0x105)
            os_.score_add(500000)
            return 0
        if not os_.hook("timed_feature_running"):
            os_.flag_clear(0x2c)                 # MORE TIME can be offered again
        task, call, _ = AWARDS[award]
        self._timer_start(award)
        os_.sound(call)
        os_.score_add(22000)
        os_.deff_start(112, award=award)
        pd.tron_running |= award
        os_.hook("item_light", TRON_ITEM)
        pd.tron_started_set |= award
        if pd.tron_started_set & 7 == 7:
            pd.tron_item_count = min(pd.tron_item_count + 1, 0xff)
            os_.hook("item_collect", TRON_ITEM)
            pd.tron_started_set = 0
        pd.tron_lit = 0
        self.rotate_lit()
        return award

    # ------------------------------------------------------------------ award timer [0x0100c558]

    def _timer_start(self, award):
        self.secs[award] = self.os.adj_value(AWARDS[award][2])
        self._timer_loop(award)

    def _timer_loop(self, award):
        """Each award task runs while ANY counter is nonzero and decrements EVERY nonzero counter once
        per "second" (ROM quirk: two running awards count down twice as fast)."""
        if not any(self.secs.values()):
            self._timer_end(award)
            return
        self._timer_wait(award, STEPS)

    def _timer_wait(self, award, steps):
        self.os.task_start(AWARDS[award][0], STEP_TICKS, lambda: self._timer_step(award, steps))

    def _paused(self):
        display = self.os.display
        shows = list(display.shows) + ([display.show] if display.show else [])
        return any(s.task_id in PAUSE_SHOWS for s in shows)

    def _timer_step(self, award, steps):
        steps = 9 if self._paused() else steps - 1
        if steps:
            self._timer_wait(award, steps)
            return
        for bit in self.secs:
            if self.secs[bit]:
                self.secs[bit] -= 1
        self._timer_loop(award)

    def _timer_end(self, award):
        pd = self.pd
        pd.tron_running &= ~award
        if not pd.tron_lit:
            pd.tron_lit = award
        self.os.request_refresh()

    # ------------------------------------------------------------------ OS and arcade hooks

    def score_event(self, points):
        """double_scoring_score_hook [0x0100c1c0] (event 0x4c): every score x2 while task 0xc6 runs."""
        return points * 2 if self.os.task_running(0xc6) else points

    def timed_feature_running(self):
        """The TRON part of any_timed_mode_running [0x0100f930] (None lets the other features answer)."""
        if any(self.os.task_running(task) for task, _, _ in AWARDS.values()):
            return True
        return None

    def more_time(self):
        """tron_award_refill_time_a/b/c [0x0100d35c..]: each running award back to its full time."""
        for bit, (task, _, adj) in AWARDS.items():
            if self.os.task_running(task):
                self.secs[bit] = self.os.adj_value(adj)


feature = TronTargets
