"""CLU lanes and the CLU hurry-up "TERMINATE CLU" (assets/rules/modes/clu_hurryup.md).

Lanes sw25 (C)LU, sw14 C(L)U, sw28 CL(U) (hook clu_letter, lane index 0-2). A completed lane set lights
the hurry-up at the VUK (lit table bit 0x10, hook clu_vuk); the VUK starts it: four CLU helmet shots
(clu_shots bits 0x001 left orbit, 0x004 left inner loop, 0x080 right orbit, 0x100 VUK; hook
clu_hurryup_awards) on a 25 s clock (task 0xc0, grace 0xc1).
"""
from tron.features import Feature
from tron.features.timed_modes import Countdown, show_total, total_wait_ticks

ORDER = 30
CLU_ITEM = 2
# lane index -> (bit, lamp, sound when newly lit, sound when already lit) [table 0x040d2ea8]
LANES = ((1, 9, 0x099, 0x096), (2, 30, 0x09a, 0x097), (4, 31, 0x09b, 0x098))
SHOT_ORDER = (0x001, 0x004, 0x080, 0x100)       # table 0x040d22dc
# the CLU insert of each shot in SHOT_ORDER (the lamp groups of table 0x040d22e0; the inserts leff 78
# draws in traces/clu_hurryup.jsonl: left orbit 13, left inner loop 61, right orbit 36, VUK eject 28)
SHOT_LAMPS = (13, 61, 36, 28)
ALL_SHOTS = 0x185
OUTLANE_LAMPS = (8, 32)                         # special inserts [table 0x040d2ecc]
MAX_AWARD = 1500000


class Clu(Feature):
    name = "clu"
    HOOKS = ("player_first_ball", "ball_start", "ball_end", "ball_end_wait", "clu_letter",
             "clu_hurryup_awards", "clu_vuk", "timed_feature_running", "more_time",
             "arcade_clu_weight", "arcade_clu")

    def __init__(self, os_):
        super().__init__(os_)
        self.clock = Countdown(os_, "clu_timer", 0xc0, 0xc1, self._tick, self._show_total, intro=0x93)
        self.hits = self.shots = self.base = self.total = 0
        os_.lamp_rule(self.clock.counting, leff=78, tube=23, order=0x01001d40)
        os_.lamps.leff_code(78, self._leff_shot_lamps)
        os_.deff_rule(self._background, 72, 0x086, 5)
        os_.lamp_update(self.lane_lamps)
        sc = self.machine.switch_controller
        sc.add_switch_handler("s_left_flipper", self.rotate_toward_c)
        sc.add_switch_handler("s_right_flipper", self.rotate_toward_u)

    def _leff_shot_lamps(self, task):
        """leff_078_clu_shot_lamps [0x010028ec]: the CLU insert of each shot still to make toggles every
        3 ticks (reads solid in the traces), the others are held off."""
        for bit, lamp in zip(SHOT_ORDER, SHOT_LAMPS):
            if self.shots & bit:
                task.toggle(lamp)
            else:
                task.set(lamp, False)
        task.sleep(3, self._leff_shot_lamps)

    def player_first_ball(self):
        """clu_player_init 0x01001c2c and clu_lanes_player_init 0x010167f4."""
        pd = self.pd
        pd.clu_starts = pd.clu_awards_count = pd.clu_completed_count = 0
        pd.clu_lane_bits = pd.clu_lane_completions = pd.clu_lights = 0

    def ball_start(self):
        self.pd.clu_lane_bits = 0                  # clu_lanes_ball_reset 0x0101685c

    def ball_end(self):
        self.end_now()                             # clu_on_end_of_ball 0x01001c88

    def ball_end_wait(self):
        return total_wait_ticks(self.os, 0x53, 74)

    # ------------------------------------------------------------------ lanes

    def lanes_active(self):
        """0x0101688c: no Sea of Simulation (0x34), Portal (0x37) or End of Line (0x27)."""
        return not any(self.os.flag(f) for f in (0x34, 0x37, 0x27))

    def lane_lamps(self):
        """clu_lane_lamps_rule [0x010168d0] (lamp rule): a lit lane is solid (off while the lanes are
        inactive). Then as many outlane inserts (table 0x040d2ecc: 8, 32) are on as specials are lit
        (FUN_00023fc8): the missing ones are turned on in table order, extra ones off."""
        os_ = self.os
        active = self.lanes_active()
        bits = self.pd.get("clu_lane_bits", 0)
        for bit, lamp, _, _ in LANES:
            os_.lamps.lamp_set(lamp, 1 if active and bits & bit else 0)
        want = os_.specials_lit[os_.player_num - 1] if os_.player_num else 0
        have = sum(1 for lamp in OUTLANE_LAMPS if lamp in os_.lamps)
        for lamp in OUTLANE_LAMPS:
            if have < want and lamp not in os_.lamps:
                os_.lamps.lamp_on(lamp)
                have += 1
            elif have > want and lamp in os_.lamps:
                os_.lamps.lamp_off(lamp)
                have -= 1

    def clu_letter(self, idx):
        """clu_lane_hit 0x01016b0c."""
        os_, pd = self.os, self.pd
        if not self.lanes_active():
            return False
        bit, _lamp, snd_new, snd_lit = LANES[idx]
        if not pd.clu_lane_bits & bit:
            pd.clu_lane_bits |= bit
            os_.score_add(10000)
            os_.leff_start(86, lamp=LANES[idx][1])
            os_.sound(snd_new)
        else:
            os_.score_add(1000)
            os_.leff_start(87, lamp=LANES[idx][1])
            os_.sound(snd_lit)
        if pd.clu_lane_bits == 7:
            pd.clu_lane_bits = 0
            self._completion(silent=False)
            os_.tube_start(21)
        os_.request_refresh()
        return True

    def _completion(self, silent):
        """Lane set completed [0x01016b0c / 0x01016d14]: the value, then either a hurry-up shot
        (while it runs) or one step toward lighting it at the VUK."""
        os_, pd = self.os, self.pd
        os_.score_add(min(50000 + 5000 * pd.clu_lane_completions, 250000))
        if not self.collect_first_lit():
            pd.clu_lane_completions = min(pd.clu_lane_completions + 1, 0xffff)
            lights_before = pd.clu_lights
            lit = False
            if pd.clu_lane_completions > 4 * lights_before and os_.hook("vuk_lit_add", 0x10, False):
                pd.clu_lights = min(pd.clu_lights + 1, 0xffff)
                lit = True
            if not silent:
                os_.deff_start(80, completions=pd.clu_lane_completions, needed=4 * lights_before + 1, lit=lit)
        if not silent:
            os_.leff_start(88)
            os_.sound(0x09c)

    def _rotate(self, toward_c):
        """clu_lanes_rotate_toward_c / _u [0x01016fc0 / 0x01017074], from the flipper buttons
        (handlers 0x0102a1b4 / 0x0102a294; which button is which is inferred: left -> toward (C))."""
        os_ = self.os
        if not os_.game or os_.state & 0x311 or not self.lanes_active():
            return
        os_.leff_stop(86)
        os_.leff_stop(88)
        bits = self.pd.clu_lane_bits
        if toward_c:
            bits = (bits >> 1) | (4 if bits & 1 else 0)
        else:
            bits = (bits << 1) | (1 if bits & 4 else 0)
        self.pd.clu_lane_bits = bits & 7

    def rotate_toward_c(self):
        self._rotate(True)

    def rotate_toward_u(self):
        self._rotate(False)

    # ------------------------------------------------------------------ start at the VUK

    def start_allowed(self, all_lit, all_collected):
        """clu_start_allowed 0x01001c98: no multiball, no Sea of Simulation / Portal running or about
        to start at this VUK (FUN_010263b0 / portal_mb_can_start; the Disc restart window, task 0xad,
        keeps them from starting)."""
        os_ = self.os
        if os_.any_multiball() or os_.flag(0x34) or os_.flag(0x37):
            return False
        wizard_ready = not os_.task_running(0xad)
        return not (all_lit and wizard_ready) and not (all_collected and wizard_ready)

    def clu_vuk(self, all_lit=False, all_collected=False):
        """clu_try_start_at_vuk 0x01001cf8."""
        if self.os.hook("vuk_lit_test", 0x10) and self.start(all_lit, all_collected):
            self.os.hook("vuk_lit_take", 0x10)
            return True
        return False

    def start(self, all_lit=False, all_collected=False):
        """on_clu_hurryup_started 0x01001f38."""
        os_, pd = self.os, self.pd
        if not self.start_allowed(all_lit, all_collected):
            return False
        if not os_.hook("timed_feature_running"):
            os_.flag_clear(0x2c)
        self.clock.start()
        self.clock.seconds = 25
        self.hits = 0
        self.shots = ALL_SHOTS
        self.base = min(250000 + 75000 * pd.clu_starts, MAX_AWARD)
        self.total = os_.score_add(100000)
        os_.show(0x93, 71)
        pd.clu_starts = min(pd.clu_starts + 1, 0xff)
        os_.hook("item_light", CLU_ITEM)
        os_.audit(0x4e)
        os_.display.raise_rule(72)
        os_.request_refresh()
        return True

    def _background(self):
        """FUN_010028a4: the countdown runs, and the intro is not still waiting for its turn."""
        os_ = self.os
        return self.clock.counting() and not (
            os_.display.task_running(0x93) and not os_.display.running(71))

    def _tick(self):
        self.clock.seconds -= 1
        return self.clock.seconds == 0

    # ------------------------------------------------------------------ shots

    def clu_hurryup_awards(self, bit):
        """clu_collect_shot 0x01002098."""
        os_, pd = self.os, self.pd
        if not self.clock.running() or not self.shots & bit:
            return False
        points = os_.score_add(min(self.base + 75000 * self.hits, MAX_AWARD))
        self.shots &= ~bit
        self.total += points
        pd.clu_awards_count = min(pd.clu_awards_count + 1, 0xff)
        self.hits += 1
        os_.deff_start(73, value=points, shots_left=bin(self.shots).count("1"))
        os_.audit(0x4f)
        if not self.shots:
            pd.clu_completed_count = min(pd.clu_completed_count + 1, 0xff)
            os_.hook("item_collect", CLU_ITEM)
            self.end_now()
        os_.request_refresh()
        return True

    def collect_first_lit(self):
        """clu_collect_first_lit 0x01002268: a lane set while the hurry-up runs collects a shot."""
        if not self.clock.running():
            return False
        for bit in SHOT_ORDER:
            if self.shots & bit:
                self.clu_hurryup_awards(bit)
                break
        return True

    # ------------------------------------------------------------------ end

    def end_now(self):
        """clu_end_now 0x01002234."""
        if not self.clock.running():
            return False
        self.clock.kill()
        self._show_total()
        self.os.request_refresh()
        return True

    def _show_total(self):
        """clu_end_show_total 0x01001df4: deff 74 (queued task 0x53), not in tilt or game over."""
        if self.os.state & 0x310 or not self.total:
            return
        show_total(self.os, 0x53, 74, total=self.total, shots=self.pd.clu_awards_count)

    # ------------------------------------------------------------------ Flynn's Arcade

    def timed_feature_running(self):
        return True if self.clock.counting() else None

    def more_time(self):
        """clu_more_time 0x010021c8: the clock back to 40 and the countdown restarted."""
        if not self.clock.running():
            return None
        self.clock.start()
        self.clock.seconds = 40
        self.os.request_refresh()
        return True

    def arcade_clu_weight(self, default):
        os_ = self.os
        return default if self.start_allowed(bool(os_.hook("items_all_lit")),
                                             bool(os_.hook("items_all_collected"))) else 0

    def arcade_clu(self):
        """ADV. CLU: one silent lane completion [0x01016d14(1)]."""
        if not self.lanes_active():
            return False
        self._completion(silent=True)
        self.os.request_refresh()
        return True


feature = Clu
