"""Recognizer 3-bank and Disc Battle (assets/rules/modes/recognizer_and_disc_battle.md).

Five Recognizer counts (the moving lit target counts 2) light DISC BATTLE (game flag 0x22); then
min(4 + 2k, 10) disc hits count down and the next one starts Disc Multiball (hook dmb_start).
The switch layer calls recognizer_bank(bit, lamp) for sw49-51 and disc_battle(type, silent) for sw41.
Target masks: L = 1, C = 2, R = 4 (table 0x040d32a8). No target switch is ever marked bad here, so
the "disabled targets" mask of the ROM is always 0.
"""
from tron.features import Feature

ORDER = 40
# moving lit target steps (table 0x040d32b4): target mask per step, L C R C
STEP_MASK = (1, 2, 4, 2)
TARGET_LAMPS = {1: 53, 2: 52, 4: 51}   # the step table lamps (L C R = RECOGNIZER POS. 3, 2, 1; traces)
STEP_TICKS = 93           # task 0x7d: one step
PREV_TICKS = 11           # the previous lit target still counts until here
NEXT_TICKS = 47           # the next step is chosen here (head motor target)
ITEM = 7                  # Find Flynn item RECOGNIZER


class Recognizer(Feature):
    name = "recognizer"
    HOOKS = ("player_first_ball", "ball_end", "recognizer_bank", "disc_battle", "dbattle_is_lit",
             "dbattle_can_progress", "recog_targets_count_active", "arcade_disc_weight", "arcade_disc",
             "arcade_recognizer_weight", "arcade_recognizer")

    def __init__(self, os_):
        super().__init__(os_)
        self.lit = self.prev = self.next = 0
        self.bank_up = True
        os_.lamp_rule(self.moving_target_rule, order=0x010200f4)
        os_.lamp_rule(lambda: self.recog_targets_count_active() and os_.task_running(0x7d), leff=99,
                      order=0x010201b4)
        os_.lamp_rule(self.dbattle_can_progress, leff=106, order=0x01020b4c)
        os_.lamp_rule(lambda: self.dbattle_ready() and self.dbattle_can_progress(), leff=107, tube=61,
                      order=0x01020bf4)
        os_.lamp_rule(self.bank_motor_rule, order=0x0102227c)
        os_.lamp_rule(lambda: (self.dbattle_can_progress() or bool(os_.hook("dmb_disc_is_target"))
                               or bool(os_.hook("portal_mb_super_lit"))), leff=76, order=0x01006610)
        os_.lamps.leff_code(76, self._leff_disc_flasher)
        os_.lamps.leff_code(99, self._leff_moving_target)

    def _leff_moving_target(self, task):
        """leff_099 [0x01020ff8]: over the recognizer target inserts, the moving lit target blinks every
        3 ticks, the previous one stays on (plane 1) and the others are off. No target is ever disabled
        here (module docstring), so the disabled-target branch (always on) does not occur."""
        phase = task.data.setdefault("phase", True)
        lit, prev = STEP_MASK[self.lit], STEP_MASK[self.prev]
        for mask, lamp in TARGET_LAMPS.items():
            if mask == lit:
                task.set(lamp, phase)
            else:
                task.set(lamp, mask == prev)
        task.data["phase"] = not phase
        task.sleep(3, self._leff_moving_target)

    def _leff_disc_flasher(self, task):
        """leff_076 [0x01006660]: coil_pulse(31 red disc, or 32 blue disc while a multiball runs
        [0x01006648], 64 ms) every 12 ticks."""
        os_ = self.os
        os_.lamps.flasher("f_blue_disc" if os_.any_multiball() else "f_red_disc", 64)   # direct coil_pulse: no leff ownership
        task.sleep(12, self._leff_disc_flasher)

    # ------------------------------------------------------------------ state

    def player_first_ball(self):
        """Event 0x26 [0x0101fd94]."""
        pd = self.pd
        pd.dbattle_award_level = 0
        pd.dbattle_k = self.os.adj_value(67)
        pd.dbattle_need = pd.dbattle_remaining = 255
        pd.rec_hits = 0
        pd.rec_hits_stat = pd.rec_battles = 0

    def ball_end(self):
        self.os.task_kill(0x7d)

    def dbattle_is_lit(self):
        return self.os.flag(0x22)

    def dbattle_ready(self):
        return self.dbattle_is_lit() and self.pd.dbattle_remaining == 0

    def recog_targets_count_active(self):
        """0x0101ffd8: battle not lit and none of Disc, Light Cycle, Quorra MB, Sea of Simulation, Portal."""
        os_ = self.os
        return not any(os_.flag(f) for f in (0x22, 0x24, 0x2b, 0x29, 0x34, 0x37))

    def dbattle_can_progress(self):
        """0x01020b4c: battle lit and no Portal, Sea of Simulation or multiball running."""
        os_ = self.os
        return self.dbattle_is_lit() and not any(os_.flag(f) for f in (0x37, 0x34, 0x24, 0x29, 0x2b, 0x27))

    # ------------------------------------------------------------------ moving lit target (task 0x7d)

    def moving_target_rule(self):
        """Rule 0x010200f4: the task runs while the targets count."""
        os_ = self.os
        if self.recog_targets_count_active():
            if not os_.task_running(0x7d):
                self.lit = self.prev = self.next = 0
                os_.task_start(0x7d, PREV_TICKS, self._step_prev)
        else:
            os_.task_kill(0x7d)
        return False

    @staticmethod
    def next_index(cur):
        """0x0101fe20: the next step, skipping disabled targets and steps that light the same target
        (neither happens with the L C R C table and no bad switch)."""
        return (cur + 1) % 4

    def _step_prev(self):
        self.prev = self.lit
        self.os.task_start(0x7d, NEXT_TICKS - PREV_TICKS, self._step_next)

    def _step_next(self):
        self.next = self.next_index(self.lit)
        self.os.task_start(0x7d, STEP_TICKS - NEXT_TICKS, self._step_move)

    def _step_move(self):
        self.prev = self.lit
        self.lit = self.next_index(self.lit)
        self.os.task_start(0x7d, PREV_TICKS, self._step_prev)

    # ------------------------------------------------------------------ 3-bank motor [0x0102227c]

    def bank_motor_rule(self):
        """The bank is up unless the battle can progress or a mode wants it down; the first move after
        the battle is lit (flag 0x2e) plays 0x0d3 [0x01022308]."""
        os_ = self.os
        want_up = self.bank_wants_up()
        if want_up != self.bank_up:
            self.bank_up = want_up
            if os_.flag(0x2e) and not os_.state & 0x312:
                os_.sound(0x0d3)
        if os_.flag(0x2e):
            os_.flag_clear(0x2e)
        return False

    def bank_wants_up(self):
        os_ = self.os
        if os_.hook("portal_mb_flag37_set") or os_.hook("eol_running_or_grace"):
            return False
        for name in ("sos_bank_state", "quorra_add_ball_state", "dmb_bank_state"):
            state = os_.hook(name)
            if state:
                return state == 1
        return not self.dbattle_can_progress()

    # ------------------------------------------------------------------ targets [0x010201e4]

    def recognizer_bank(self, bit, lamp, silent=False):
        os_, pd = self.os, self.pd
        if not self.recog_targets_count_active():
            if not silent:
                os_.leff_start(100, lamp=lamp)
                os_.sound(0x0ce)
            os_.score_add(1000)
            return False
        lit = STEP_MASK[self.lit] & bit or STEP_MASK[self.prev] & bit
        hits = min(pd.rec_hits + (2 if lit else 1), 0xff)
        pd.rec_hits = hits
        if hits < 5:
            os_.score_add(2500)
            if not silent:
                os_.deff_start(108, left=5 - hits)
                os_.leff_start(101)
                os_.sound(0x0d0)
            pd.rec_hits_stat = min(pd.rec_hits_stat + 1, 0xff)
            os_.hook("item_light", ITEM)
        else:
            pd.rec_battles = min(pd.rec_battles + 1, 0xff)
            os_.hook("item_collect", ITEM)
            self.dbattle_light(silent)
            pd.rec_hits = 0
            os_.flag_set(0x2e)
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ Disc Battle

    def dbattle_light(self, silent):
        """0x01020d1c."""
        os_, pd = self.os, self.pd
        if self.dbattle_is_lit():
            return False
        os_.flag_set(0x22)
        pd.dbattle_need = pd.dbattle_remaining = min(4 + 2 * pd.dbattle_k, 10)
        os_.audit(0x8d)
        os_.score_add(200000)
        if silent:
            os_.show(0x9d, 109)
        else:
            os_.deff_start(109)
        os_.request_refresh()
        return True

    def disc_battle(self, kind=2, silent=False):
        """0x01020da8(type, silent): sw41 (2, 0) and the arcade ADVANCE DISC award (2, 1)."""
        os_, pd = self.os, self.pd
        if not self.dbattle_can_progress():
            return False
        remaining = pd.dbattle_remaining
        if remaining == 0:
            if not kind & 2:
                return False
            os_.score_add(min(2000000 + 1000000 * pd.dbattle_award_level, 4000000))
            self.dbattle_clear()
            pd.dbattle_k = min(pd.dbattle_k + 1, 0xff)
            os_.hook("dmb_start")
            os_.request_refresh()
            return True
        pd.dbattle_remaining = remaining - min(2 if kind == 1 else 1, remaining)
        if not silent:
            os_.deff_start(111, left=pd.dbattle_remaining + 1)
            os_.leff_start(108)
            os_.sound(0x0d7)
        os_.request_refresh()
        return True

    def dbattle_clear(self):
        """0x01020f10."""
        if self.dbattle_is_lit():
            self.os.flag_clear(0x22)
            self.pd.rec_hits = 0
            self.os.request_refresh()

    # ------------------------------------------------------------------ Flynn's Arcade awards

    def arcade_disc_weight(self, default):
        return default if self.dbattle_can_progress() else 0

    def arcade_disc(self):
        return self.disc_battle(2, True)

    def arcade_recognizer_weight(self, default):
        return default if self.recog_targets_count_active() else 0

    def arcade_recognizer(self):
        return self.recognizer_bank(0x32, 0x36, True)


feature = Recognizer
