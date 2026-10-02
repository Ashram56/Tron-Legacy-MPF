"""Switch handlers, base scores and the 8 canonical shots (assets/rules/modes/switches_and_shots.md).

Each playfield switch has one handler. It applies its repeat guard, calls the feature hooks in the
ROM's fixed order (os.hook(name, ...)), then adds its base score. Hooks that no feature registered
yet do nothing. Shot indexes, bits and masks follow section 5.3 of the spec.
"""

SW = {  # SAM switch number -> MPF switch name (asset package switches.yaml)
    1: "s_tron_t", 2: "s_tron_r", 3: "s_tron_o", 4: "s_tron_n",
    7: "s_zuse_z", 8: "s_zuse_u", 48: "s_zuse_s", 13: "s_zuse_e",
    11: "s_video_game_eject", 12: "s_zen_rollover",
    14: "s_clu_l", 25: "s_clu_c", 28: "s_clu_u",
    23: "s_shooter_lane", 24: "s_left_outlane", 29: "s_right_outlane",
    26: "s_left_slingshot", 27: "s_right_slingshot",
    30: "s_left_bumper", 31: "s_right_bumper", 32: "s_bottom_bumper",
    34: "s_r_ramp_exit", 35: "s_l_ramp_entrance", 36: "s_right_orbit_spinner",
    37: "s_l_ramp_exit", 38: "s_r_ramp_entrance", 39: "s_right_inner_loop",
    41: "s_disc_opto", 43: "s_left_orbit", 44: "s_left_spinner", 46: "s_right_orbit",
    49: "s_recogniz_3_bank_l", 50: "s_recogniz_3_bank_c", 51: "s_recogniz_3_bank_r",
    52: "s_3_bank_motor_dn", 54: "s_recog_motor_pos_1", 55: "s_recog_motor_pos_2",
    56: "s_recog_motor_pos_3",
}
NUM = {name: num for num, name in SW.items()}

# shot index -> (CLU/light-cycle bit, combo/arrow mask) per section 5.3
SHOT_BIT = {0: 0x01, 1: 0x02, 2: 0x04, 3: 0x08, 4: 0x40, 5: 0x80}

TRON_LETTER = {1: (1, 4), 2: (2, 3), 3: (4, 2), 4: (8, 1)}     # sw -> (bit, letter number)
ZUSE_INDEX = {7: 0, 8: 1, 48: 2, 13: 3}
CLU_INDEX = {25: 0, 14: 1, 28: 2}
BANK_BIT = {49: 1, 50: 2, 51: 4}
BANK_LAMP = {49: 53, 50: 52, 51: 51}
POP_LAMP = {30: 46, 31: 47, 32: 48}
LANE_CHANGE_LAMPS = (32,)       # lamp list 0x040e39b4 after lamp 8 (assumed: the right outlane insert)
INSULT_COOLDOWN_TICKS = 37500   # timer 9 (0x927c)


class SwitchLayer:

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        self.lspin = {"pending": 0, "last": 0, "total": 0}
        self.rspin = {"pending": 0, "last": 0, "total": 0}
        self.orbit_post = 0
        sc = self.machine.switch_controller
        for num, name in SW.items():
            if name not in self.machine.switches:
                continue
            handler = getattr(self, "sw_{}".format(num), None)
            if handler:
                sc.add_switch_handler(name, self._dispatch(num, handler))
        sc.add_switch_handler("s_shooter_lane", self.shooter_close, state=1)
        sc.add_switch_handler("s_shooter_lane", self.shooter_open, state=0)
        os_.register("player_first_ball", self.player_first_ball)
        os_.register("ball_start", self.ball_start)

    def _dispatch(self, num, handler):
        """The ROM runs a playfield handler as a task about one tick after the switch closes. A handler
        does not refresh the lamp rules by itself: the hooks that change rule state call
        rules_refresh_request (os.request_refresh) as the ROM does."""
        def on_close():
            if not self.os.game or (not self.os.in_play and num != 11):
                return
            self.os.after(1, handler)
        return on_close

    # ------------------------------------------------------------------ per player / ball state

    def player_first_ball(self):
        pd = self.os.pd
        pd.lspin_value = 10000
        pd.rspin_value = 10000
        pd.pop_levels_done = 0
        pd.pop_value_level = 0
        pd.pop_hits_left = self.pop_hits_needed()

    def ball_start(self):
        pd = self.os.pd
        for flag, key in ((0x10, "lspin_value"), (0x11, "rspin_value")):
            if self.os.flag(flag):
                self.os.flag_clear(flag)
            else:
                pd[key] = 10000
        if self.os.flag(0x19):
            self.os.flag_clear(0x19)
        else:
            pd.pop_value_level = 0

    def pop_hits_needed(self):
        return min((self.os.adj_value(65) + self.os.pd.pop_levels_done) * 5 + 20, 50)

    # ------------------------------------------------------------------ helpers

    def h(self, name, *args):
        return self.os.hook(name, *args)

    def z4_eol(self):
        self.h("zuse_target_hit", 4)
        self.h("eol_shot_score")

    # ------------------------------------------------------------------ TRON targets 1-4

    def _tron(self, sw):
        os_ = self.os
        # drop_bank_switch_handler [0x0100b4b8]: a target whose drop is already down is ignored
        if self.h("drop_bank_hit", sw) is False:
            return
        if os_.state & 0x312:
            return
        bit, letter = TRON_LETTER[sw]
        # posts 0x6b; TRON targets count toward the playfield validation (traces/tron_targets.jsonl:
        # main play music 0x01b right after the third different target, T R O)
        os_.playfield_switch(sw)
        self.z4_eol()
        self.h("simulation_shot", 1 + sw)
        self.h("tron_letter", bit, letter)
        self.h("rules_refresh")
        os_.base_score(30)

    def sw_1(self):
        self._tron(1)

    def sw_2(self):
        self._tron(2)

    def sw_3(self):
        self._tron(3)

    def sw_4(self):
        self._tron(4)

    # ------------------------------------------------------------------ ZUSE 7, 8, 48, 13

    def _zuse(self, sw):
        self.os.playfield_switch(sw)
        idx = ZUSE_INDEX[sw]
        self.h("zuse_target_hit", idx)
        self.h("eol_shot_score")
        self.h("simulation_shot", 9 + idx)
        self.h("zuse_letter", idx)
        self.os.base_score(1130)

    def sw_7(self):
        self._zuse(7)

    def sw_8(self):
        self._zuse(8)

    def sw_48(self):
        self._zuse(48)

    def sw_13(self):
        self._zuse(13)

    # ------------------------------------------------------------------ VUK 11 (device settles first)

    def sw_11(self):
        os_ = self.os
        if os_.in_play:
            os_.playfield_switch(11)
        os_.ball_held = True
        # The ball device settles about 0.76 s before on_vuk runs (section 5, sw11), then the eject
        # sequence (device events 7 and 4, FUN_0101bdd0) runs.
        os_.after(47, self.vuk_settled)

    def vuk_settled(self):
        if self.os.in_play:
            self.on_vuk()
        self.vuk_kickout()

    def vuk_kickout(self):
        """Device event 7: wait for the show deffs, then 0x0fd + leff 35, 46 ticks, leff 36 + 0x0fe, eject."""
        os_ = self.os
        if not self.machine.switches[SW[11]].state:
            # the ball left the VUK without a kick: nothing to eject, and as after an unconfirmed eject
            # no ball search until a playfield switch (traces/sea_of_simulation.jsonl 7.4 -> 21.4)
            os_.ball_held = False
            os_.vuk_ejecting = True
            return
        if os_.show_running():
            os_.after(6, self.vuk_kickout)
            return
        if not os_.state & 0x310:
            os_.sound(0x0fd)
            os_.leff_start(35)
            os_.after(46, self.vuk_eject)
        else:
            self.vuk_eject()

    def vuk_eject(self):
        os_ = self.os
        if not os_.state & 0x312:
            os_.leff_start(36)
            os_.sound(0x0fe)
        os_.ball_held = False
        os_.vuk_released_at = os_.now     # the multiball task waits a fixed time after the kick
        os_.vuk_ejecting = True
        os_.ball_search_reload()
        self.machine.events.post("tron_vuk_release")

    def on_vuk(self):
        """on_vuk [0x0102eddc]: every VUK award in ROM order; lit states are read before any award."""
        os_ = self.os
        os_.audit(0x66)
        all_lit = bool(self.h("items_all_lit"))
        all_collected = bool(self.h("items_all_collected"))
        lit = {bit: bool(self.h("vuk_lit_test", bit)) for bit in (1, 2, 4, 0x10)}
        self.h("vuk_skill_shot")                      # skill shot C
        self.h("simulation_shot", 0)
        self.h("clu_hurryup_awards", 0x100)
        self.h("eol_combo_jackpot")
        if lit[1] and self.h("vuk_lit_test", 1):
            self.h("vuk_extra_ball")                  # eb_collect_game 0x01012228
        self.h("arcade_collect")
        self.h("portal_vuk", all_collected)
        self.h("sos_vuk", all_lit)
        if lit[0x10] and self.h("vuk_lit_test", 0x10):
            self.h("clu_vuk", all_lit, all_collected)
        if lit[4] and self.h("vuk_lit_test", 4):
            self.h("light_cycle_vuk", all_lit, all_collected)
        if lit[2] and self.h("vuk_lit_test", 2):
            self.h("quorra_vuk", all_lit, all_collected)
        self.h("eol_vuk")
        self.z4_eol()
        os_.base_score(350)
        os_.request_refresh()

    # ------------------------------------------------------------------ ZEN 12

    def sw_12(self):
        os_ = self.os
        os_.playfield_switch(12)
        self.h("left_ramp_skill_shot_start")
        self.z4_eol()
        self.h("find_flynn_started")
        self.h("zen_rollover")
        os_.base_score(1090)

    # ------------------------------------------------------------------ CLU 25, 14, 28

    def _clu(self, sw):
        self.os.playfield_switch(sw)
        self.z4_eol()
        self.h("simulation_shot", {25: 6, 14: 7, 28: 8}[sw])
        self.h("clu_letter", CLU_INDEX[sw])
        self.os.base_score(1090)

    def sw_14(self):
        self._clu(14)

    def sw_25(self):
        self._clu(25)

    def sw_28(self):
        self._clu(28)

    # ------------------------------------------------------------------ shooter lane 23

    def shooter_close(self):
        self.os.task_start(0x3d, 6)

    def shooter_open(self):
        os_ = self.os
        if not os_.game:
            return
        os_.task_start(0x3e, 125)
        if self.machine.switches["s_left_flipper"].state:
            self.h("right_ramp_skill_shot")
        if os_.task_running(0x3d) or not os_.in_play:
            return
        os_.sound(0x0ea)
        os_.task_start(0x68, 187)
        if (os_.adj_value(79) == 0 and not os_.task_running(0x3c)
                and not self.h("right_ramp_skill_shot_running")):
            self.raise_orbit_post()
        if not self.orbit_post:
            os_.task_start(0x66, 187)

    def raise_orbit_post(self):
        if self.os.adj_value(78):
            return
        self.orbit_post = 1
        coil = self.machine.coils.get("c_orbit_up_down_post")
        if coil:
            coil.enable()
        self.os.task_start("orbit_post", 125, self.drop_orbit_post)

    def drop_orbit_post(self):
        self.orbit_post = 0
        coil = self.machine.coils.get("c_orbit_up_down_post")
        if coil:
            coil.disable()

    # ------------------------------------------------------------------ outlanes 24, 29

    def _outlane(self, sw, lamp):
        """sw24_left_outlane / sw29_right_outlane: ball save try, insult speech (left only), special
        collect at a lit outlane insert, z4, eol, then 100,000."""
        os_ = self.os
        os_.playfield_switch(sw)
        # FUN_0000c6d4(0x19), drawn at every left outlane hit so a reference run's picks line up
        lucky = sw == 24 and os_.pick("insult", [1, 3]) == 0
        save_running = bool(os_.ball_save)                     # FUN_00019b1c
        saved = os_.ball_save_try(1 if sw == 24 else 2)
        insult = False
        # FUN_0001e454 (balls still being served) is covered by the ball count: a served ball counts
        if (sw == 24 and not save_running and not saved and os_.pf_valid
                and os_.rom_balls_in_play() == 1):
            insult = self.insult_speech(lucky)
        self.outlane_special(lamp, insult)
        self.z4_eol()
        os_.base_score(100000)

    def insult_speech(self, lucky):
        """outlane_insult_speech [0x010127c0]: speech 0x129 (25 %) with no multiball, adj 82 INSULT LEVEL
        above 0 and timer 9 idle; timer 9 then runs 37,500 ticks."""
        os_ = self.os
        if os_.any_multiball() or os_.adj_value(82) <= 0 or not lucky or os_.task_running("timer_9"):
            return False
        os_.sound(0x129)
        os_.task_start("timer_9", INSULT_COOLDOWN_TICKS)
        return True

    def outlane_special(self, lamp, insult):
        """outlane_special_collect [0x01016e58]: at a lit outlane insert with a special lit, collect it
        (the insert goes off while fewer than 2 remain): deff 82, leff 90, sound 0x9e unless the insult
        played, 100,000. Otherwise sound 0xa2 unless the insult played."""
        os_ = self.os
        if lamp not in os_.lamps or not os_.special_collect():
            if lamp not in os_.lamps and not insult:
                os_.sound(0x0a2)
            return False
        if os_.specials_lit[os_.player_num - 1] < 2:
            os_.lamps.discard(lamp)
        os_.deff_start(82)
        os_.leff_start(90)
        if not insult:
            os_.sound(0x09e)
        os_.score_add(100000)
        os_.request_refresh()
        return True

    def lane_change(self):
        """sling_lamp_rotate [0x01017128]: stops leffs 89 / 90 and rotates the lamp 8 state through the
        lamp list 0x040e39b4 and back to lamp 8 (assumed (32,), the other outlane insert: the list is not
        in the decompile)."""
        os_ = self.os
        if os_.state & 0x311:
            return
        os_.leff_stop(90)
        os_.leff_stop(89)
        carry = 8 in os_.lamps
        for lamp in LANE_CHANGE_LAMPS:
            carry, lit = lamp in os_.lamps, carry
            (os_.lamps.add if lit else os_.lamps.discard)(lamp)
        (os_.lamps.add if carry else os_.lamps.discard)(8)

    def sw_24(self):
        self._outlane(24, 8)

    def sw_29(self):
        self._outlane(29, 32)

    # ------------------------------------------------------------------ slings 26, 27

    def _sling(self, sw):
        self.os.playfield_switch(sw)                  # posts 0x6b itself
        self.z4_eol()
        self.lane_change()
        self.os.sound(0x0e8 if sw == 26 else 0x0e9)
        self.os.base_score(440)

    def sw_26(self):
        self._sling(26)

    def sw_27(self):
        self._sling(27)

    # ------------------------------------------------------------------ pop bumpers 30-32 (5.2)

    def _pop(self, sw):
        os_ = self.os
        os_.task_start(0x40, 156)                     # bumper_busy
        os_.playfield_switch(sw)
        self.z4_eol()
        self.pop_value(sw)
        os_.base_score(170)

    def pop_value(self, sw):
        """pop_bumper_hit [0x0101c3a4]."""
        os_, pd = self.os, self.os.pd
        mult = 3 if os_.task_running(199) else 1
        level = pd.pop_value_level
        self.h("pop_lamp_pattern")
        if os_.task_running(0xcb):
            self.h("big_bumps_hit")
        hits_left = pd.pop_hits_left
        if hits_left not in (0, 1):
            value = min(10000 + 2500 * level, 50000)
            points = os_.score_add(value * mult)
            if os_.display.running(43):               # a running deff 43 takes the new values
                os_.display.extend(43)
            else:
                os_.deff_start(43, hits_left=hits_left - 1, value=value, mult=mult, points=points)
            os_.leff_start(41, lamp=POP_LAMP[sw])
            os_.sound(0x50 if mult == 1 else 0x51)
            pd.pop_hits_left = hits_left - 1
        else:
            value = min(100000 + 25000 * level, 500000)
            pd.pop_levels_done = min(pd.pop_levels_done + 1, 0xff)
            pd.pop_value_level = min(pd.pop_value_level + 1, 0xff)
            points = os_.score_add(value * mult)
            if os_.deff_start(44, level=pd.pop_levels_done, value=value, mult=mult, points=points):
                os_.leff_start(42)
            os_.sound(0x50)
            pd.pop_hits_left = self.pop_hits_needed()

    def sw_30(self):
        self._pop(30)

    def sw_31(self):
        self._pop(31)

    def sw_32(self):
        self._pop(32)

    # ------------------------------------------------------------------ ramps 34-38

    def sw_34(self):
        self.os.playfield_switch(34)
        self.on_right_ramp()

    def sw_37(self):
        self.os.playfield_switch(37)
        self.on_left_ramp()

    def sw_35(self):
        self.os.playfield_switch(35)
        self.os.sound(0x0eb)
        self.z4_eol()
        self.os.base_score(560)

    def sw_38(self):
        self.os.playfield_switch(38)
        self.os.sound(0x0eb)
        self.z4_eol()
        self.os.base_score(560)

    def on_left_ramp(self):
        """Shot 1 [on_left_ramp 0x0102a940]."""
        os_ = self.os
        os_.audit(0x62)
        self.h("portal_mb_shot", 1)
        self.h("simulation_shot", 0x0f)
        self.h("left_ramp_skill_shot")
        self.h("disc_mb_shot", 1)
        self.h("light_cycle_mb_shot", 2)
        self.h("light_cycle_target", 2)
        self.h("combo_awards", 1)
        self.h("find_flynn_completed", 1)
        self.z4_eol()
        self.h("eol_ramp_jackpot", 0)
        self.h("eol_letter", 0)
        os_.sound(0x0eb)
        os_.base_score(1170)

    def on_right_ramp(self):
        """Shot 4 [on_right_ramp 0x0102aa50]."""
        os_ = self.os
        os_.audit(0x63)
        self.h("portal_mb_shot", 4)
        self.h("simulation_shot", 0x12)
        self.h("right_ramp_skill_shot_collect")
        self.h("clu_hurryup_awards", 0x40)
        self.h("disc_mb_shot", 4)
        self.h("light_cycle_mb_shot", 0x40)
        self.h("light_cycle_target", 0x40)
        self.h("combo_awards", 4)
        self.h("find_flynn_completed", 4)
        self.z4_eol()
        self.h("eol_ramp_jackpot", 1)
        self.h("eol_letter", 1)
        self.h("eol_combo_jackpot_light")
        os_.sound(0x0eb)
        os_.base_score(1170)

    # ------------------------------------------------------------------ spinners 44, 36 (5.1)

    def _spin_value(self, key):
        return self.os.pd[key] * (3 if self.os.task_running(200) else 1)

    def sw_44(self):
        os_ = self.os
        os_.playfield_switch(44)
        if os_.task_running(0x64):
            self.lspin["pending"] += 1                # scored by the session task
            os_.display.extend(41)                    # the spinner deff stays up (see sw_36)
        else:
            self.lspin.update(total=0, pending=0)
            self._score_lspin()
            os_.deff_start(41)
            self._lspin_task()
            os_.audit(0x64)
            self.shot_left_inner_loop()
        self.z4_eol()
        self.h("gem_spin")
        os_.base_score(90)

    def _lspin_task(self):
        """Task 0x64: scores one pending spin per tick, ends after 62 idle ticks."""
        os_ = self.os
        state = {"idle": 0}

        def tick():
            if self.lspin["pending"]:
                self.lspin["pending"] -= 1
                self._score_lspin()
                state["idle"] = 0
            else:
                state["idle"] += 1
            if state["idle"] < 62:
                os_.task_start(0x64, 1, tick)
        os_.task_start(0x64, 1, tick)

    def _score_lspin(self):
        value = self._spin_value("lspin_value")
        self.os.score_add(value)
        self.lspin["last"] = value
        self.lspin["total"] += value
        self.os.leff_start(33)
        self.os.sound(0x0ec)

    def shot_left_inner_loop(self):
        """Shot 2 hooks [on_l_inner_loop 0x01029ba4] (after the first spin is scored)."""
        self.h("portal_mb_shot", 2)
        self.h("simulation_shot", 0x10)
        self.h("clu_hurryup_awards", 4)
        self.h("disc_mb_shot", 2)
        self.h("quorra_super_jackpots", 4)
        self.h("light_cycle_mb_shot", 4)
        self.h("light_cycle_target", 4)
        self.h("quorra_to_light", 4)
        self.h("combo_awards", 2)
        self.h("find_flynn_completed", 2)

    def sw_36(self):
        os_ = self.os
        os_.playfield_switch(36)
        if os_.task_running(0x65):
            self.rspin["pending"] += 1
            # the spinner deff stays up for its length after the last spin (inferred from
            # traces/gem_hurryup.jsonl: the GEM countdown restarted by the last spin waits for the
            # display until 1.68 s, deff 42's length, after that spin)
            os_.display.extend(42)
            os_.after(0, self._rspin_now)
        else:
            self.rspin.update(total=0, pending=0)
            self._score_rspin()
            os_.deff_start(42)
            self._rspin_task()
            if (os_.task_running(199) and not os_.any_multiball()
                    and not self.h("combo_lit", 5)):
                self.raise_orbit_post()
            if self.orbit_post == 1:
                self.shot_right_orbit()
        self.z4_eol()
        self.h("gem_spin")
        os_.base_score(90)

    def _rspin_task(self):
        os_ = self.os
        state = {"idle": 0}

        def tick():
            if self.rspin["pending"]:
                self.rspin["pending"] -= 1
                self._score_rspin()
                state["idle"] = 0
            else:
                state["idle"] += 1
            if state["idle"] < 93:
                os_.task_start(0x65, 1, tick)
        os_.task_start(0x65, 1, tick)

    def _rspin_now(self):
        """Task 0x65 runs after the switch task in the same tick, so a pending spin scores at once
        (traces/gem_hurryup.jsonl: one 10,090 score per repeated spin)."""
        if self.rspin["pending"] and self.os.task_running(0x65):
            self.rspin["pending"] -= 1
            self._score_rspin()
            self._rspin_task()

    def _score_rspin(self):
        value = self._spin_value("rspin_value")
        self.os.score_add(value)
        self.rspin["last"] = value
        self.rspin["total"] += value
        self.os.leff_start(34)
        self.os.sound(0x0ee)

    # ------------------------------------------------------------------ right inner loop 39

    def sw_39(self):
        """Shot 3 [0x0102ae3c]."""
        os_ = self.os
        os_.playfield_switch(39)
        os_.audit(0x65)
        self.h("portal_mb_shot", 3)
        self.h("simulation_shot", 0x11)
        self.h("combo_awards", 3)
        self.h("find_flynn_completed", 3)
        self.h("disc_mb_shot", 3)
        self.h("quorra_super_jackpots", 8)
        self.h("light_cycle_mb_shot", 8)
        self.h("light_cycle_target", 8)
        self.z4_eol()
        self.h("bonus_x_add")
        self.h("gem_hurryup_awards", 8)
        self.h("gem_qualify")
        os_.base_score(1190)

    # ------------------------------------------------------------------ disc 41

    def sw_41(self):
        os_ = self.os
        os_.playfield_switch(41)
        if os_.task_running(0x3f):
            os_.task_kill(0x3f)
            os_.sound(0x54)
            return
        os_.task_start(0x3f, 125)
        self.h("portal_mb_shot", 6)
        self.h("simulation_shot", 1)
        self.h("disc_mb_shot", 7)
        self.h("disc_restart_autofire")
        self.z4_eol()
        self.h("eol_disc_jackpot", 2)
        self.h("disc_battle", 2, 0)
        os_.leff_start(75)
        os_.sound_chain(0x53, os_.sound(0x52))       # 0x53 plays when the 0x52 sample ends
        os_.base_score(2310)

    # ------------------------------------------------------------------ orbits 43, 46

    def sw_43(self):
        os_ = self.os
        os_.playfield_switch(43)
        if os_.task_kill(0x67):
            pass
        elif os_.task_running(0x66):
            os_.task_kill(0x66)
            os_.task_kill(0x69)
        else:
            os_.audit(0x60)
            self.shot_left_orbit()
            os_.task_start(0x67, 125)
            os_.task_start(0x68, 187)
            os_.sound(0x0ed)
        os_.base_score(1220)

    def shot_left_orbit(self):
        """FUN_0102a728."""
        if self.os.task_running(0x3c):
            return
        self.h("portal_mb_shot", 0)
        self.h("simulation_shot", 0x0e)
        self.h("clu_hurryup_awards", 1)
        self.h("disc_mb_shot", 0)
        self.h("light_cycle_mb_shot", 1)
        self.h("light_cycle_target", 1)
        self.h("combo_awards", 0)
        self.h("find_flynn_completed", 0)
        self.z4_eol()

    def sw_46(self):
        os_ = self.os
        os_.playfield_switch(46)
        if os_.task_kill(0x69):
            pass
        elif os_.task_running(0x68):
            os_.task_kill(0x68)
            os_.task_kill(0x67)
        else:
            os_.audit(0x61)
            self.shot_right_orbit()
            os_.task_start(0x69, 125)
            os_.task_start(0x66, 187)
            os_.sound(0x0ef)
        os_.base_score(1220)

    def shot_right_orbit(self):
        """FUN_0102a794."""
        if self.os.task_running(0x3c):
            return
        self.h("portal_mb_shot", 5)
        self.h("simulation_shot", 0x13)
        self.h("clu_hurryup_awards", 0x80)
        self.h("disc_mb_shot", 5)
        self.h("light_cycle_mb_shot", 0x80)
        self.h("light_cycle_target", 0x80)
        self.h("combo_awards", 5)
        self.h("find_flynn_completed", 5)
        self.z4_eol()
        self.h("arcade_light", 1)

    # ------------------------------------------------------------------ recognizer 3-bank 49-51

    def _bank(self, sw):
        os_ = self.os
        os_.playfield_switch(sw)
        if not os_.task_running(0x7b):
            self.h("quorra_super_jackpots", 0x10)
            self.h("disc_mb_shot", 6)
            self.z4_eol()
            self.h("simulation_shot", 0x0d)
            self.h("recognizer_bank", BANK_BIT[sw], BANK_LAMP[sw])
            os_.base_score(1080)
        os_.task_start(0x7b, 10)

    def sw_49(self):
        self._bank(49)

    def sw_50(self):
        self._bank(50)

    def sw_51(self):
        self._bank(51)
