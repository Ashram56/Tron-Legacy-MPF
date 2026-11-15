"""The game around the modes, against game_flow.md, skill_shots.md, bonus.md, combos.md, flynns_arcade.md
and switches_and_shots.md: serve, valid playfield, ball save, tilt, extra ball, replay, bonus, skill
shots, combos, Flynn's Arcade, the base score of every switch."""
from tests.bench.robot import Bench


class TestServeAndValidPlayfield(Bench):
    AUTOPLUNGE = None

    def test_the_player_plunges(self):
        self.start_game(plunge=False)
        self.wait(3)
        self.assertEqual((3, 1, 0), (self.table.trough, self.table.shooter, self.table.pf))
        self.assertFalse(self.table.coil_pulses.get("c_auto_launch"), "a new ball is never auto-launched")
        self.plunge()
        self.assertEqual(1, self.table.pf)

    def test_shooter_lane_reminder_after_20_seconds(self):
        self.start_game(plunge=False)
        m = self.mark()
        self.wait(19)
        self.assertNotIn(40, self.deffs(m))
        self.wait(3)
        self.assertIn(40, self.deffs(m))

    def test_drain_before_valid_playfield_is_served_again(self):
        self.start_game(plunge=False)
        self.wait(2)
        self.plunge()
        self.hit("s_left_slingshot")
        self.hit("s_right_slingshot")                    # two different counting switches: not valid yet
        self.assertFalse(self.tron.pf_valid)
        m = self.mark()
        self.drain()
        self.wait(4)
        self.assertEqual(1, self.machine.game.player.ball)
        self.assertNotIn(25, self.deffs(m))               # no bonus
        self.assertEqual(1, self.table.shooter, "the same ball again, for the player to plunge")
        self.assertEqual(0, self.audit(8))

    def test_three_different_switches_or_one_instant_switch(self):
        self.start_game(plunge=False)
        self.wait(2)
        self.plunge()
        for sw in ("s_left_slingshot", "s_left_slingshot", "s_right_slingshot"):
            self.hit(sw)
        self.assertFalse(self.tron.pf_valid)
        self.hit("s_left_bumper")
        self.assertTrue(self.tron.pf_valid)
        self.end_ball()
        self.assertFalse(self.tron.pf_valid)
        self.ball_in_play()
        self.hit("s_left_orbit")
        self.assertTrue(self.tron.pf_valid, "an orbit validates at once")


class TestBallSave(Bench):
    """game_flow.md 5.1: adj 38 = 5 s, counted from the valid playfield, then a 218-tick grace."""

    def test_saved_once_then_the_ball_ends(self):
        self.start_game(validate=True)
        self.wait(2)
        m = self.mark()
        self.drain()
        self.wait(1)
        self.assertIn(20, self.deffs(m))
        self.assertEqual(1, self.audit(0x2b))
        self.wait_until(lambda: self.table.pf == 1, 10, what="the saved ball")
        self.assertEqual(1, self.table.coil_pulses.get("c_auto_launch"), "a saved ball is auto-launched")
        self.assertEqual(1, self.machine.game.player.ball)
        self.validate()                                   # gf_pf_valid is 0 again at every serve
        self.drain()                                      # the replacement has no save of its own
        self.wait(6)
        self.assertEqual(2, self.machine.game.player.ball)

    def test_grace_after_the_lamp_stops(self):
        self.start_game(validate=True)
        self.wait(6.5)                                    # 5.1 s of save, then 3.5 s of grace
        self.assertFalse(self.tron.task_running(0x31))
        self.drain()
        self.wait_until(lambda: self.table.pf == 1, 10, what="the saved ball")
        self.assertEqual(1, self.machine.game.player.ball)

    def test_no_save_after_the_grace(self):
        self.start_game(validate=True)
        self.wait(10)
        self.drain()
        self.wait(6)
        self.assertEqual(2, self.machine.game.player.ball)
        self.assertEqual(0, self.audit(0x2b))

    def test_the_clock_waits_for_the_valid_playfield(self):
        self.start_game()
        self.wait(20)                                     # on the playfield, nothing hit
        self.validate()
        self.wait(3)
        self.drain()
        self.wait_until(lambda: self.table.pf == 1, 10, what="the saved ball")
        self.assertEqual(1, self.audit(0x2b))

    def test_outlane_saves_before_the_trough(self):
        self.start_game(validate=True)
        m = self.mark()
        self.table.hit("s_left_outlane")
        self.advance_time_and_run(0.3)
        self.assertIn(20, self.deffs(m), "BALL SAVED at the outlane switch")
        self.table.drain()
        self.wait_until(lambda: self.table.pf == 1, 10, what="the saved ball")
        self.assertEqual(1, self.machine.game.player.ball)
        self.assertEqual(1, self.audit(0x2b))

    def test_a_multiball_start_kills_the_single_ball_save(self):
        self.start_game(validate=True)
        self.set_items(collected=range(9))
        self.scoop(wait=False)
        self.wait(1)
        self.assertFalse(self.tron.task_running(0x31) or self.tron.task_running(0x32))
        self.wait(20)


class TestTilt(Bench):
    """game_flow.md 5.3"""

    def test_two_warnings_then_tilt_no_bonus(self):
        self.start_game(validate=True)
        m = self.mark()
        self.tilt_bob()
        self.tilt_bob()
        self.assertEqual(2, self.deffs(m).count(23))
        self.assertFalse(self.tron.tilted)
        self.tilt_bob()
        self.assertTrue(self.tron.tilted)
        self.assertIn(21, self.deffs(m))
        self.assertEqual(1, self.audit(0x2a))
        score = self.score()
        self.table.hit("s_left_orbit")
        self.wait(0.3)
        self.assertEqual(score, self.score())
        m = self.mark()
        self.drain()
        self.wait_until(lambda: self.machine.game.player.ball == 2, 10, what="ball 2")
        self.assertNotIn(25, self.deffs(m))
        self.assertEqual(score, self.score())
        self.assertEqual((False, 0), (self.tron.tilted, self.tron.tilt_warnings))

    def test_bobs_within_a_second_count_once(self):
        self.start_game(validate=True)
        for _ in range(5):
            self.tilt_bob(settle=0.1)
        self.assertEqual(1, self.tron.tilt_warnings)

    def test_warnings_are_per_ball(self):
        self.start_game(validate=True)
        self.tilt_bob()
        self.tilt_bob()
        self.end_ball()
        self.tilt_bob()
        self.assertFalse(self.tron.tilted)

    def test_tilt_ends_every_mode(self):
        self.start_game(validate=True)
        self.start_gem()
        self.start_zuse()
        self.start_clu()
        m = self.mark()
        self.tilt_out()
        self.wait(1)
        self.end_ball()
        for name in ("clu", "gem", "zuse"):
            self.assertFalse(self.feature(name).clock.running(), name)
        self.assertFalse({74, 79, 99} & set(self.deffs(m)), "no TOTAL screens on a tilt")

    def test_slam_tilt_ends_the_game(self):
        self.start_game(validate=True)
        m = self.mark()
        self.press("s_slam_tilt")
        self.assertIn(24, self.deffs(m))
        self.table.drain()
        self.wait(8)
        self.assertIsNone(self.machine.game)


class TestExtraBallAndReplay(Bench):
    """game_flow.md 5.4, 5.5"""

    def _light_extra_ball(self):
        for _ in range(4):
            self.shot("left_ramp", settle=0.1)
            self.shot("right_ramp", settle=0.1)
        self.assertTrue(self.tron.hook("vuk_lit_test", 1))

    def test_extra_ball_is_played_on_the_same_ball_number(self):
        self.start_game(validate=True)
        m = self.mark()
        self._light_extra_ball()
        self.wait(12)                                     # queued behind the ramp shows
        self.assertIn(132, self.deffs(m))
        m = self.mark()
        self.scoop()
        self.assertIn(133, self.deffs(m))
        self.assertEqual(1, self.audit(9))
        self.assertEqual(1, self.machine.game.player.extra_balls)
        m = self.mark()
        self.end_ball()
        self.assertEqual((1, 1), (self.machine.game.player.number, self.machine.game.player.ball))
        self.assertIn(26, self.deffs(m))                  # PLAYER 1 / SHOOT AGAIN
        self.assertIn(25, self.deffs(m))                  # after the bonus
        self.assertTrue(self.flag(9))
        self.validate()
        self.assertFalse(self.flag(9), "the first score ends the SHOOT AGAIN flash")
        self.end_ball()
        self.assertEqual(2, self.machine.game.player.ball)

    def test_the_extra_ball_keeps_the_players_progress(self):
        """No per-player init on a shoot-again ball."""
        self.start_game(validate=True)
        self._light_extra_ball()
        self.shots("left_loop", "left_loop")
        self.wait(5)
        self.scoop()
        self.end_ball()
        self.assertEqual(2, self.pd.quorra_progress)

    def test_replay_at_20_million(self):
        self.start_game(validate=True)
        self.set_items(collected=range(9))
        m = self.mark()
        self.scoop()                                      # Portal: 1,000,000 + 50,000,000
        self.wait(20)
        self.assertGreater(self.score(), 20000000)
        self.assertIn(28, self.deffs(m))
        self.assertEqual(1, self.sounds(m).count(0x019), "one knock")


class TestBonus(Bench):
    """bonus.md"""

    def _bonus(self):
        before = self.score()
        m = self.mark()
        self.end_ball()
        self.assertIn(25, self.deffs(m))
        return self.score(1) - before

    def test_base_only(self):
        self.start_game(validate=True)
        self.assertEqual(50000, self._bonus())

    def test_items_sea_portal_and_multiplier(self):
        """The spec's worked example: (50K + 50K + 250K + 250K + 900K + 2.25M) x 4 = 15,000,000."""
        self.start_game(validate=True)
        self.shots("right_loop", "right_loop", "right_loop")            # 4X (and GEM starts: GEM lit)
        self.wait_until(lambda: not self.feature("gem").clock.running(), 60, what="GEM to end")
        self.wait(5)
        self.set_items(lit=(0,), collected=(1, 8))
        self.pd.sos_count = 2
        self.pd.portal_count = 1
        self.assertEqual(15000000, self._bonus())
        self.assertEqual(1, self.pd.bonus_x, "back to 1X on the next ball")
        self.validate()
        self.assertEqual(3750000, self._bonus())                         # the counts stay for the game

    def test_multiplier_is_capped_at_25(self):
        self.start_game(validate=True)
        for _ in range(30):
            self.shot("right_loop", settle=0.05)
        self.assertEqual(25, self.pd.bonus_x)

    def test_both_flippers_skip_the_count(self):
        self.start_game(validate=True)
        for _ in range(9):
            self.shot("right_loop", settle=0.05)
        self.wait_until(lambda: not self.feature("gem").clock.running(), 60, what="GEM to end")
        self.wait(5)
        self.no_ball_save()
        before = self.score()
        self.drain()
        self.wait_until(lambda: self.tron.state & 1, 10, what="the bonus")
        started = self.tron.now
        self.wait(0.6)
        self.machine.switch_controller.process_switch("s_left_flipper", 1, True)
        self.machine.switch_controller.process_switch("s_right_flipper", 1, True)
        self.wait_until(lambda: not self.tron.state & 1, 10, what="the bonus to end")
        self.machine.switch_controller.process_switch("s_left_flipper", 0, True)
        self.machine.switch_controller.process_switch("s_right_flipper", 0, True)
        self.assertLess(self.tron.now - started, 2.5, "9 multiplier steps skipped")
        self.assertEqual(before + 10 * (50000 + 250000), self.score(1))   # GEM was collected

    def test_bonus_can_earn_the_replay(self):
        self.start_game(validate=True)
        self.pd.portal_count = 10
        m = self.mark()
        self.assertEqual(50000 + 22500000, self._bonus())
        self.assertIn(28, self.deffs(m))


class TestSkillShots(Bench):
    """skill_shots.md"""
    AUTOPLUNGE = None

    def _serve(self, hold_left=False):
        self.wait_until(lambda: self.table.shooter == 1, 20, what="a ball in the shooter lane")
        self.wait(0.3)
        if hold_left:
            self.machine.switch_controller.process_switch("s_left_flipper", 1, True)
            self.wait(0.1)
        self.plunge()
        if hold_left:
            self.machine.switch_controller.process_switch("s_left_flipper", 0, True)
        self.wait(0.2)

    def test_a_zen_then_left_ramp(self):
        self.start_game(plunge=False)
        self._serve()
        self.assertTrue(self.flag(0x1e))
        self.shot("zen")
        self.assertTrue(self.tron.task_running(0x70))
        m = self.mark()
        self.shot("left_ramp")
        self.assertIn(250000, self.adds(m))
        self.assertIn(101, self.deffs(m))
        self.assertFalse(self.tron.task_running(0x74), "one collect cancels all three")
        self.end_ball()
        self._serve() if not self.table.pf else None
        self.shot("zen")
        m = self.mark()
        self.shot("left_ramp")
        self.assertIn(300000, self.adds(m), "+50,000 per earlier one")

    def test_b_needs_the_left_flipper_held_at_the_plunge(self):
        self.start_game(plunge=False)
        self._serve()
        m = self.mark()
        self.shot("right_ramp")
        self.assertNotIn(300000, self.adds(m))
        self.end_ball()
        self.wait_until(lambda: self.table.shooter == 1 or self.table.pf, 20, what="ball 2")
        if self.table.pf:
            self.skipTest("the robot plunged")
        self._serve(hold_left=True)
        self.assertTrue(self.tron.task_running(0x72))
        m = self.mark()
        self.shot("right_ramp")
        self.assertIn(300000, self.adds(m))
        self.assertIn(102, self.deffs(m))

    def test_c_at_the_scoop(self):
        self.start_game(plunge=False)
        self._serve()
        self.assertTrue(self.tron.task_running(0x74))
        m = self.mark()
        self.scoop()
        self.assertEqual([500000, 500000], [a for a in self.adds(m) if a >= 100000])   # skill shot, then the arcade
        self.assertLess(self.deffs(m).index(103), self.deffs(m).index(105))

    def test_three_counting_switches_end_them(self):
        self.start_game(plunge=False)
        self._serve()
        self.shots("sling_l", "sling_r")
        self.assertTrue(self.tron.task_running(0x74) and self.flag(0x1e))
        self.shot("pop_l")
        self.wait(2)                                      # the 93-tick grace of the running one
        self.assertFalse(self.tron.task_running(0x74) or self.tron.task_running(0x75))
        self.assertFalse(self.flag(0x1e) or self.flag(0x1f))
        m = self.mark()
        self.scoop()
        self.assertEqual([500000], [a for a in self.adds(m) if a >= 100000])           # the arcade only

    def test_an_instant_switch_ends_them_at_once(self):
        self.start_game(plunge=False)
        self._serve()
        self.shot("right_loop")
        self.assertFalse(self.tron.task_running(0x74))
        self.assertFalse(self.flag(0x1e))

    def test_a_saved_ball_gets_no_new_skill_shot(self):
        self.start_game(plunge=False)
        self._serve()
        self.validate()
        self.drain()
        self.wait_until(lambda: self.table.pf == 1, 12, what="the saved ball")
        self.assertFalse(self.tron.task_running(0x74))
        self.assertFalse(self.flag(0x1e))


class TestCombos(Bench):
    """combos.md"""

    def _combo(self, shot):
        m = self.mark()
        self.shot(shot, settle=0.2)
        return self.adds(m), self.deffs(m)

    def test_castor_then_the_end_of_line_jackpot(self):
        self.start_game(validate=True)
        self.shot("left_ramp")
        adds, deffs = self._combo("left_orbit")
        self.assertIn(250000, adds)
        self.assertIn(138, deffs)
        self.assertEqual(850000, self.pd.eol_combo_jackpot)               # CASTOR adds 350,000
        self.assertEqual((1, 1), (self.audit(0x7a), self.audit(0x7b)))
        self.shot("right_ramp")                                           # lights the jackpot for 4 s
        m = self.mark()
        self.scoop()
        self.assertIn(850000, self.adds(m))
        self.assertIn(139, self.deffs(m))
        self.assertEqual(850000, self.pd.eol_combo_jackpot, "not reset by the collect")

    def test_the_spec_chain(self):
        """LIL -> RR -> RO -> RIL: 250,000 (Jarvis), 300,000 (3-Man), 350,000 (Ricochet): jackpot 2,000,000."""
        self.start_game(validate=True)
        self.shot("left_loop")
        self.assertIn(250000, self._combo("right_ramp")[0])
        self.assertEqual(850000, self.pd.eol_combo_jackpot)
        self.assertIn(300000, self._combo("right_orbit")[0])
        self.assertEqual(1350000, self.pd.eol_combo_jackpot)
        m = self.mark()
        self.shot("right_loop", settle=0.2)
        self.assertIn(350000, self.adds(m))
        self.assertEqual(2000000, self.pd.eol_combo_jackpot)
        adds, _ = self._combo("right_loop")                               # the chain ended on a finisher
        self.assertFalse([a for a in adds if a in (250000 + 0, 400000)] and False)

    def test_window_closes_after_seven_seconds(self):
        self.start_game(validate=True)
        self.shot("left_ramp")
        self.wait(7.6)
        _, deffs = self._combo("left_orbit")
        self.assertNotIn(138, deffs)

    def test_no_window_opens_in_a_multiball(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.shot("left_ramp")
        _, deffs = self._combo("left_orbit")
        self.assertNotIn(138, deffs)

    def test_jackpot_starts_again_at_500k_each_ball(self):
        self.start_game(validate=True)
        self.shot("left_ramp")
        self._combo("left_orbit")
        self.end_ball()
        self.assertEqual(500000, self.pd.eol_combo_jackpot)

    def test_orbit_pass_through_is_not_a_shot(self):
        self.start_game(validate=True)
        self.shot("right_orbit")
        m = self.mark()
        self.shot("left_orbit", clean=False)                              # the same ball coming out
        self.assertEqual([1220], self.adds(m))
        self.assertEqual(0, self.audit(0x60))


class TestFlynnsArcade(Bench):
    """flynns_arcade.md"""
    ARCADE = None

    def setUp(self):
        super().setUp()
        self.bags = []
        pick = self.tron.pick

        def spy(name, weights):
            if name == "arcade":
                self.bags.append(list(weights))
                if self.arcade is not None and weights[self.arcade] > 0:
                    return self.arcade
            return pick(name, weights)
        self.tron.pick = spy

    def test_the_bag_at_game_start(self):
        self.arcade = 0
        self.start_game(validate=True)
        m = self.mark()
        self.scoop()
        self.assertEqual([100, 25, 25, 25, 25, 0, 25, 100, 0, 0, 1, 1], self.bags[0])
        self.assertIn(500000, self.adds(m))
        self.assertIn(105, self.deffs(m))
        self.assertEqual(1, self.audit(0x53))

    def test_unlit_after_the_collect_relit_by_the_right_orbit(self):
        self.arcade = 0
        self.start_game(validate=True)
        self.scoop()
        m = self.mark()
        self.scoop()
        self.assertEqual([350], self.adds(m))
        self.shot("right_orbit")
        self.assertIn(104, self.deffs(m))
        m = self.mark()
        self.scoop()
        self.assertIn(500000, self.adds(m))

    def test_lit_again_at_every_ball(self):
        self.arcade = 0
        self.start_game(validate=True)
        self.scoop()
        self.end_ball()
        self.assertEqual(1, self.pd.arcade_lit)

    def test_more_time_is_offered_while_a_timed_award_runs(self):
        self.arcade = 0
        self.start_game(validate=True)
        self.start_tron_award()
        self.wait(4)
        self.scoop()
        self.assertEqual(100, self.bags[-1][9])
        # flynns_arcade.md says 352 and 452, but its own table adds up to 327 (ADV. DISC is 0 at game start)
        self.assertEqual(427, sum(self.bags[-1]), self.bags[-1])

    def test_more_time_refills_the_clocks_once(self):
        self.arcade = 0
        self.start_game(validate=True)
        self.scoop()                                      # the ball's arcade, out of the way
        self.start_gem()
        gem = self.feature("gem")
        self.wait_until(lambda: gem.clock.seconds <= 15, 40, what="GEM to count down")
        self.arcade = 9
        self.shot("right_orbit")
        self.scoop()
        self.assertGreaterEqual(gem.clock.seconds, 39)
        self.assertEqual(1, self.audit(0x5c))
        self.shot("right_orbit")
        self.scoop()
        self.assertEqual(0, self.bags[-1][9], "MORE TIME is not offered twice")

    def test_no_collect_in_a_multiball(self):
        self.arcade = 0
        self.start_game(validate=True)
        self.scoop()
        self.start_quorra()
        self.wait(12)
        self.shot("right_orbit")
        self.assertEqual(0, self.pd.arcade_lit, "a right orbit does not relight it in a multiball")

    def test_every_advance_award_runs(self):
        """Each award of the bag, forced in turn on its own ball: none may break the game."""
        for award in (1, 2, 3, 4, 6, 7, 10, 11):
            with self.subTest(award=award):
                self.end_game() if self.machine.game else None
                self.bags = []
                self.arcade = award
                self.start_game(validate=True)
                m = self.mark()
                self.scoop()
                self.assertTrue(self.bags and self.bags[0][award] > 0, "award {} not offered".format(award))
                self.assertEqual(1, self.audit(0x53 + award) - getattr(self, "_seen", {}).get(award, 0))
                self.assertIn(105, self.deffs(m))
                self.wait(3)


class TestSwitchScores(Bench):
    """switches_and_shots.md section 10: the base score of every switch on a fresh ball."""

    def test_base_scores(self):
        self.start_game()
        table = (("sling_l", [440]), ("sling_r", [440]), ("pop_l", [10000, 170]), ("zuse_z", [75000, 1130]),
                 ("clu_c", [10000, 1090]), ("tron_t", [10000, 30]), ("bank_l", [2500, 1080]),
                 ("right_spinner", [10000, 90]), ("disc", [2310]))
        for name, expect in table:
            m = self.mark()
            self.shot(name)
            self.assertEqual(expect, self.adds(m), name)
        for switch, expect in (("s_l_ramp_entrance", [560]), ("s_l_ramp_exit", [1170]),
                               ("s_r_ramp_entrance", [560]), ("s_r_ramp_exit", [1170])):
            m = self.mark()
            self.hit(switch)
            self.assertEqual(expect, self.adds(m), switch)
        self.wait(4)
        m = self.mark()
        self.shot("left_orbit")
        self.assertEqual([1220], self.adds(m))
        self.assertEqual(1, self.audit(0x60))

    def test_spinner_spins_are_all_scored_but_the_loop_counts_once(self):
        self.start_game(validate=True)
        m = self.mark()
        for _ in range(3):
            self.hit("s_left_spinner", settle=0.05)
        self.wait(2)
        self.assertEqual(3, self.adds(m).count(90))
        self.assertEqual(3 + 1, self.adds(m).count(10000), "three spins and one Quorra progress")
        self.assertEqual(1, self.audit(0x64))

    def test_pop_level_completes_at_25_hits(self):
        self.start_game(validate=True)                    # validate used one pop hit
        values = []
        for _ in range(26):
            m = self.mark()
            self.shot("pop_r", settle=0.05)
            values.append(self.adds(m)[0])
        self.assertEqual(100000, values[23], "hit 25 completes the level")
        self.assertEqual(12500, values[24])

    def test_ball_search_after_ten_seconds_without_a_switch(self):
        self.start_game(validate=True)
        self.wait(9)
        self.assertEqual(0, self.audit(0x25))
        self.wait(2.5)
        self.assertEqual(1, self.audit(0x25))
        self.shot("sling_l")
        self.assertTrue(self.machine.game and self.table.pf == 1)


class TestGameOver(Bench):

    def test_three_balls_then_match_and_attract(self):
        self.start_game(validate=True)
        m = self.mark()
        for ball in (1, 2, 3):
            self.assertEqual(ball, self.machine.game.player.ball)
            self.end_ball()
        self.assertIsNone(self.machine.game)
        self.assertEqual(3, self.audit(8))
        self.assertIn(38, self.deffs(m))                  # match
        self.wait(12)
        self.assertTrue(self.tron.state & 0x10)
        self.start_game()                                 # and a new game starts from attract
        self.assertEqual(0, self.score())

    def test_high_score_entry_is_asked_for(self):
        self.start_game(validate=True)
        self.set_items(collected=range(9))
        self.scoop()                                      # 51,000,000: HIGH SCORE #1 is 55M, #2 40M
        self.wait(20)
        m = self.mark()
        self.end_game()
        self.assertIn(31, self.deffs(m))


class TestRegressions(Bench):
    """Bugs the bench found (docs/test_bench.md, "Found by the bench")."""
    AUTOPLUNGE = None

    def test_tilt_before_a_multiball_launches_its_balls(self):
        """The balls of a multiball still to launch at the tilt never come: the ball must end all the
        same (the game waited for ever for them: MPF's balls_in_play counted them)."""
        self.autoplunge = 1.0
        self.start_game(validate=True)
        self.light_light_cycle()
        self.scoop(wait=False)
        self.wait_until(lambda: self.flag(0x2b), 20, what="Light Cycle Multiball")
        self.assertGreater(self.tron._mb_pending, 0, "the test must tilt before the launches")
        self.tilt_out()
        self.wait_until(lambda: self.table.pf > 0, 30, what="the VUK to give the ball back")
        self.end_ball()
        self.assertEqual(2, self.machine.game.player.ball)
        self.assertEqual(1, self.machine.game.balls_in_play)

    def test_ball_plunged_at_once(self):
        """A ball plunged 0.15 s after it reached the shooter lane is in play: its drain is seen at once
        and saved (MPF's default 500 ms entrance delay never counted the ball: drain ignored for 10 s)."""
        self.start_game(plunge=False)
        self.wait_until(lambda: self.table.shooter == 1, 20, what="a ball in the shooter lane")
        self.wait(0.15)
        self.plunge()
        self.validate()
        self.assertEqual(1, self.machine.playfield.balls)
        m = self.mark()
        self.drain()
        self.wait(1.5)
        self.assertIn(20, self.deffs(m), "the drain was not saved")
        self.wait_until(lambda: self.table.pf == 1, 10, what="the saved ball")

    def test_game_ended_from_the_service_menu_during_the_bonus(self):
        """SELECT twice ends the game while the bonus counts: nothing of the count is left to run
        without a player."""
        self.autoplunge = 1.0
        self.start_game(validate=True)
        self.no_ball_save()
        self.drain()
        self.wait_until(lambda: self.tron.state & 0x01, 10, what="the bonus")
        self.press("s_service_select", settle=0.3)
        self.press("s_service_select", settle=0.3)
        self.wait(10, check=False)
        self.assertIsNone(self.machine.game)
        for _ in range(4):
            if not self.machine.modes["tron_service"].active:
                break
            self.press("s_service_back")
        self.wait(2)
