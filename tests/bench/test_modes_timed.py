"""The timed modes and single-ball features against their specs (assets/rules/modes/): CLU hurry-up, GEM
hurry-up, ZUSE fast scoring, the TRON targets and their timed awards, ZEN, Find Flynn. Every number
below is the spec's; the robot reaches each state through the switches."""
from tests.bench.robot import Bench


class TestClu(Bench):
    """clu_hurryup.md"""

    def test_lanes_light_the_hurry_up(self):
        self.start_game(validate=True)
        m = self.mark()
        self.shots("clu_c", "clu_l")
        self.assertEqual([10000, 1090, 10000, 1090], self.adds(m))          # new lane 10,000 + switch 1,090
        m = self.mark()
        self.shot("clu_c")
        self.assertEqual([1000, 1090], self.adds(m))                       # a lit lane 1,000
        m = self.mark()
        self.shot("clu_u")
        self.assertEqual([10000, 50000, 1090], self.adds(m))               # third lane: completion 50,000
        self.assertIn(80, self.deffs(m))
        self.assertTrue(self.tron.hook("vuk_lit_test", 0x10))
        self.assertEqual(0, self.pd.clu_lane_bits)

    def test_lane_completions_grow_and_relight_every_fourth(self):
        self.start_game(validate=True)
        values = []
        for n in range(6):
            m = self.mark()
            self.shots("clu_c", "clu_l", "clu_u", settle=0.1)
            values.append(max(self.adds(m)))
            if n == 0:
                self.assertTrue(self.tron.hook("vuk_lit_test", 0x10))
                self.arcade = 0
                self.scoop()                                               # start the first one
                self.wait_until(lambda: not self.feature("clu").clock.running(), 60, what="CLU to time out")
                self.wait(4)
            elif n < 4:
                self.assertFalse(self.tron.hook("vuk_lit_test", 0x10), "relit after {} completions".format(n + 1))
        self.assertEqual([50000, 55000, 60000, 65000, 70000, 75000], values)
        self.assertTrue(self.tron.hook("vuk_lit_test", 0x10), "the 5th completion relights the hurry-up")

    def test_the_four_shots(self):
        self.start_game(validate=True)
        self.light_clu()
        m = self.mark()
        self.scoop()
        clu = self.feature("clu")
        self.assertIn(100000, self.adds(m))
        self.assertEqual(1, self.audit(0x4e) - 0)
        self.assertEqual((25, 250000, 0x185), (clu.clock.seconds, clu.base, clu.shots))
        for name, value in (("left_orbit", 250000), ("left_loop", 325000), ("right_orbit", 400000)):
            m = self.mark()
            self.shot(name)
            self.assertIn(value, self.adds(m), name)
            self.assertIn(73, self.deffs(m))
        m = self.mark()
        self.shot("left_orbit")                                            # collected: unlit
        self.assertNotIn(475000, self.adds(m))
        m = self.mark()
        self.scoop()
        self.assertIn(475000, self.adds(m))
        self.assertFalse(clu.clock.running(), "all four shots end the hurry-up")
        self.wait(8)
        self.assertIn(74, self.deffs(m))
        self.assertEqual(4, self.audit(0x4f))
        self.assertEqual(100000 + 250000 + 325000 + 400000 + 475000, clu.total)

    def test_lane_set_collects_a_shot_while_running(self):
        self.start_game(validate=True)
        self.start_clu()
        m = self.mark()
        self.shots("clu_c", "clu_l", "clu_u", settle=0.1)
        self.assertIn(55000, self.adds(m))                                 # second completion of the game
        self.assertIn(250000, self.adds(m))                                # the left orbit, collected for the player
        self.assertEqual(0x184, self.feature("clu").shots)
        self.assertFalse(self.tron.hook("vuk_lit_test", 0x10))             # and it does not count toward lighting

    def test_times_out_after_25_seconds(self):
        self.start_game(validate=True)
        self.start_clu()
        clu = self.feature("clu")
        m = self.mark()
        waited = self.wait_until(lambda: clu.clock.seconds == 0, 60, what="the CLU clock")
        self.assertTrue(20 < waited < 40, waited)                           # 25 x 1.04 s (the lead-in ran in the scoop)
        self.wait(1.0)
        self.assertTrue(clu.clock.running(), "the 2 s grace")
        m2 = self.mark()
        self.shot("left_orbit")
        self.assertIn(250000, self.adds(m2), "a shot in the grace still scores")
        self.wait(6)
        self.assertFalse(clu.clock.running())
        self.assertIn(74, self.deffs(m))

    def test_second_hurry_up_is_worth_more(self):
        self.start_game(validate=True)
        self.start_clu()
        self.wait_until(lambda: not self.feature("clu").clock.running(), 60, what="CLU to time out")
        self.wait(4)
        for _ in range(4):
            self.shots("clu_c", "clu_l", "clu_u", settle=0.1)
        self.scoop()
        self.assertEqual(325000, self.feature("clu").base)

    def test_a_multiball_blocks_the_start_not_the_light(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.light_clu()                                                   # the lanes still work in Quorra
        self.scoop()
        self.assertFalse(self.feature("clu").clock.running())
        self.assertTrue(self.tron.hook("vuk_lit_test", 0x10), "the hurry-up stays lit for a later VUK")

    def test_starts_with_quorra_on_the_same_scoop(self):
        """on_vuk tests the CLU start before the Quorra start: one entry starts both."""
        self.start_game(validate=True)
        self.light_clu()
        self.start_quorra()
        self.assertTrue(self.feature("clu").clock.running())

    def test_ends_with_the_ball(self):
        self.start_game(validate=True)
        self.start_clu()
        m = self.mark()
        self.end_ball()
        self.assertFalse(self.feature("clu").clock.running())
        self.assertIn(74, self.deffs(m))                                   # the total, before the bonus
        self.assertLess(self.deffs(m).index(74), self.deffs(m).index(25))


class TestGem(Bench):
    """gem_hurryup.md"""

    def test_three_loops_start_it(self):
        self.start_game(validate=True)
        for left in (2, 1):
            m = self.mark()
            self.shot("right_loop")
            self.assertEqual([250000, 1190], self.adds(m)[-2:])
            self.assertIn(75, self.deffs(m))
        m = self.mark()
        self.shot("right_loop")
        gem = self.feature("gem")
        self.assertTrue(gem.clock.running())
        self.assertEqual([250000, 250000, 1190], self.adds(m)[-3:])        # the start, the loop, the switch
        self.assertEqual((25, 250000), (gem.clock.seconds, gem.total))
        self.assertEqual(1, self.audit(0x50))

    def test_awards_grow_to_2_5_million(self):
        self.start_game(validate=True)
        self.start_gem()
        self.wait(6)
        got = []
        for _ in range(9):
            m = self.mark()
            self.shot("right_loop", settle=0.1)
            got.append(max(self.adds(m)))
        self.assertEqual([750000, 1000000, 1250000, 1500000, 1750000, 2000000, 2250000, 2500000, 2500000], got)
        self.assertEqual(9, self.audit(0x51))

    def test_spins_add_time(self):
        self.start_game(validate=True)
        self.start_gem()
        gem = self.feature("gem")
        self.wait_until(lambda: gem.clock.seconds <= 20, 30, what="the clock to count")
        before = gem.clock.seconds
        for _ in range(3):
            self.hit("s_right_orbit_spinner", settle=0.3)
        self.assertEqual(before + 3, gem.clock.seconds)
        for _ in range(60):
            self.hit("s_right_orbit_spinner", settle=0.05)
        self.assertEqual(40, gem.clock.seconds)                             # capped

    def test_five_loops_the_second_time(self):
        self.start_game(validate=True)
        self.start_gem()
        gem = self.feature("gem")
        self.wait_until(lambda: not gem.clock.running(), 60, what="GEM to time out")
        self.wait(4)
        for n in range(4):
            self.shot("right_loop")
            self.assertFalse(gem.clock.running(), "started after {} loops".format(n + 1))
        self.shot("right_loop")
        self.assertTrue(gem.clock.running())

    def test_times_out_with_a_total(self):
        self.start_game(validate=True)
        self.start_gem()
        gem = self.feature("gem")
        m = self.mark()
        waited = self.wait_until(lambda: not gem.clock.running(), 60, what="GEM to time out")
        self.assertTrue(26 < waited < 42, waited)
        self.wait(5)
        self.assertIn(79, self.deffs(m))

    def test_right_loop_raises_the_bonus_multiplier(self):
        self.start_game(validate=True)
        self.shots("right_loop", "right_loop", "right_loop")
        self.assertEqual(4, self.pd.bonus_x)


class TestZuse(Bench):
    """zuse_fast_scoring.md"""

    def test_letters_and_first_completion(self):
        self.start_game(validate=True)
        for name in ("zuse_z", "zuse_u", "zuse_s"):
            m = self.mark()
            self.shot(name)
            self.assertEqual([75000, 1130], self.adds(m), name)
            self.assertIn(91, self.deffs(m))
        m = self.mark()
        self.shot("zuse_z")
        self.assertEqual([10000, 1130], self.adds(m))                      # a lit letter
        m = self.mark()
        self.shot("zuse_e")
        zuse = self.feature("zuse")
        self.assertEqual([250000, 100000, 1130], self.adds(m))             # the set, then the start
        self.assertTrue(zuse.clock.running())
        self.assertEqual((25, 10000, 100000), (zuse.clock.seconds, zuse.value, zuse.total))
        self.assertEqual(1, self.audit(0x52))

    def test_every_switch_scores_and_targets_raise_the_value(self):
        self.start_game(validate=True)
        self.start_zuse()
        zuse = self.feature("zuse")
        self.wait(6)
        m = self.mark()
        self.shot("sling_l")
        self.assertEqual([10000, 440], self.adds(m))
        self.wait(2)                                                       # the hit queue (task 0x80) is idle again
        m = self.mark()
        self.shot("zuse_z")
        self.assertEqual([11000, 5000, 1130], self.adds(m))                # new target: +1,000, then the hit
        self.assertIn(97, self.deffs(m))
        m = self.mark()
        self.shot("zuse_z")                                                # queued behind the last hit
        self.assertEqual([1130, 5000, 11000], sorted(self.adds(m)))
        self.shots("zuse_u", "zuse_s")
        self.assertEqual(13000, zuse.value)
        before = zuse.clock.seconds
        m = self.mark()
        self.shot("zuse_e")
        self.assertEqual(min(before + 10, 45), zuse.clock.seconds)         # all four: +10 s, value kept
        self.assertEqual(13000, zuse.value)
        self.assertIn(98, self.deffs(m))

    def test_grace_then_total(self):
        self.start_game(validate=True)
        self.start_zuse()
        zuse = self.feature("zuse")
        m = self.mark()
        self.wait_until(lambda: zuse.clock.seconds == 0, 60, what="the ZUSE clock")
        self.wait(2)
        m2 = self.mark()
        self.shot("sling_l")
        self.assertIn(10000, self.adds(m2), "a switch in the grace still scores")
        self.wait(6)
        self.assertFalse(zuse.clock.running())
        self.assertIn(99, self.deffs(m))

    def test_next_start_needs_four_more_sets_and_is_worth_more(self):
        self.start_game(validate=True)
        self.start_zuse()
        zuse = self.feature("zuse")
        self.wait_until(lambda: not zuse.clock.running(), 80, what="ZUSE to end")
        self.wait(5)
        sets = []
        for n in range(4):
            m = self.mark()
            self.shots("zuse_z", "zuse_u", "zuse_s", "zuse_e", settle=0.1)
            sets.append(max(self.adds(m)))
            self.assertEqual(n == 3, zuse.clock.running(), "set {}".format(n + 2))
        self.assertEqual([275000, 300000, 325000, 350000], sets)
        self.assertEqual(15000, zuse.value)

    def test_tilt_ends_it(self):
        self.start_game(validate=True)
        self.start_zuse()
        self.tilt_out()
        self.assertFalse(self.feature("zuse").clock.running())

    def test_qualifying_is_closed_during_end_of_line(self):
        self.start_game(validate=True)
        self.start_end_of_line()
        self.wait(12)
        m = self.mark()
        self.shot("zuse_z")
        self.assertIn(5000, self.adds(m))
        self.assertNotIn(75000, self.adds(m))


class TestTronTargets(Bench):
    """tron_targets.md, zen_rollover.md"""

    def test_letters_then_the_lit_award(self):
        self.start_game()
        self.assertEqual(2, self.pd.tron_lit)                              # BUMPERS at every ball start
        m = self.mark()
        self.shot("tron_t")
        self.assertEqual([10000, 30], self.adds(m))
        self.assertIn(107, self.deffs(m))
        m = self.mark()
        self.shot("tron_t")                                                # the drop is down
        self.assertEqual([], self.adds(m))
        self.shots("tron_r", "tron_o")
        m = self.mark()
        self.shot("tron_n")
        self.assertEqual([22000, 100000, 30], self.adds(m))
        self.assertEqual(2, self.pd.tron_running)
        self.assertEqual(1, self.pd.tron_lit)                              # with BUMPERS running: DS is next
        self.wait(3)
        self.assertTrue(self.table.coil_pulses.get("c_drop_target_bank"))
        self.assertEqual(set(), self.table.drops_down, "the bank reset its drops")
        self.assertIn(112, self.deffs(m))
        self.assertIn(106, self.deffs(m))

    def test_pop_bumpers_rotate_the_lit_award(self):
        self.start_game()
        seen = [self.pd.tron_lit]
        for _ in range(3):
            self.shot("pop_l", settle=0.1)
            seen.append(self.pd.tron_lit)
        self.assertEqual([2, 4, 1, 2], seen)

    def test_super_pops_and_super_spinners(self):
        self.start_game()
        m = self.mark()
        self.shot("pop_l")
        self.assertEqual([10000, 170], self.adds(m))
        self.shots("pop_l", "pop_l")                                       # back to BUMPERS
        self.start_tron_award()
        self.wait(4)
        m = self.mark()
        self.shot("pop_r")
        self.assertEqual([30000, 170], self.adds(m))                       # pops x3
        self.assertEqual(4, self.pd.tron_lit)                              # that pop: DS -> SPINNERS (BUMPERS runs)
        self.start_tron_award()
        self.wait(4)
        m = self.mark()
        self.hit("s_right_orbit_spinner")
        self.assertEqual([30000, 90], self.adds(m))                        # spinners x3

    def test_double_scoring_doubles_everything(self):
        self.start_game()
        self.shots("pop_l", "pop_l")                                       # BUMPERS -> SPINNERS -> DS
        self.assertEqual(1, self.pd.tron_lit)
        self.start_tron_award()
        self.wait(4)
        self.assertEqual(440 * 2, self.scored(lambda: self.shot("sling_l")))
        self.assertEqual((250000 + 1190) * 2, self.scored(lambda: self.shot("right_loop")))

    def test_two_awards_run_down_twice_as_fast(self):
        """ROM quirk: every running award's task decrements all three counters."""
        self.start_game()
        self.start_tron_award()                                            # BUMPERS
        tron = self.feature("tron_targets")
        self.wait(8)
        self.assertEqual(1, self.pd.tron_lit)
        self.start_tron_award()                                            # DS
        self.assertEqual(3, self.pd.tron_running)
        waited = self.wait_until(lambda: not self.pd.tron_running, 40, what="the awards to end")
        self.assertLess(waited, 20, "two awards ran {} s".format(waited))  # 30 s at 2 per second

    def test_awards_end_with_the_ball_and_letters_stay(self):
        self.start_game(validate=True)
        self.shots("tron_t", "tron_r")
        self.end_ball()
        self.assertEqual(3, self.pd.tron_letters)
        self.assertEqual((2, 0), (self.pd.tron_lit, self.pd.tron_running))
        m = self.mark()
        self.shot("tron_o")
        self.assertIn(10000, self.adds(m))

    def test_all_three_running_pays_500k(self):
        self.start_game()
        for _ in range(3):
            self.start_tron_award()
            self.wait(1.5)
        self.assertEqual(7, self.pd.tron_running)
        self.assertEqual(0, self.pd.tron_lit)
        m = self.mark()
        self.start_tron_award()
        self.assertIn(500000, self.adds(m))
        self.assertEqual(self.pd.items[8][1], 1, "the TRON item is collected once all three were started")

    def test_zen_charge_completes_tron(self):
        self.start_game()
        m = self.mark()
        self.shot("zen")
        self.assertIn(42000, self.adds(m))
        self.assertIn(1090, self.adds(m))
        self.assertIn(100, self.deffs(m))
        self.assertEqual(1, self.pd.zen_charges)
        m = self.mark()
        self.shot("tron_r")
        self.assertEqual([22000, 100000, 30], self.adds(m))                # completed at once, no 10,000
        self.assertEqual((0, 0), (self.pd.zen_charges, self.pd.tron_letters))

    def test_no_zen_charge_in_a_multiball(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        m = self.mark()
        self.shot("zen")
        self.assertNotIn(42000, self.adds(m))
        self.assertEqual(0, self.pd.zen_charges)

    def test_zen_charges_stay_for_the_next_ball(self):
        self.start_game(validate=True)
        self.shot("zen")
        self.end_ball()
        self.assertEqual(1, self.pd.zen_charges)
        self.assertTrue(self.tron.task_running(0xcc))


class TestTronTargetsPro(TestTronTargets):
    """The same rules on the Pro's standup targets (they never stay down)."""
    DROP_TARGETS = False

    def test_letters_then_the_lit_award(self):
        self.start_game()
        self.shots("tron_t", "tron_r", "tron_o")
        m = self.mark()
        self.shot("tron_t")                 # docs/hardware.md: a hit standup counts once until all four are hit
        self.assertEqual([], self.adds(m))
        m = self.mark()
        self.shot("tron_n")
        self.assertEqual([22000, 100000, 30], self.adds(m))


class TestFindFlynn(Bench):
    """find_flynn_and_items.md"""

    def test_zen_starts_it_and_the_arrow_shot_finds_flynn(self):
        self.start_game(validate=True)
        m = self.mark()
        self.shot("zen")
        self.assertTrue(self.tron.task_running(0xd1))
        self.assertIn(136, self.deffs(m))
        self.assertEqual(1, self.pd.items[0][0])
        m = self.mark()
        self.shot("left_orbit")                                            # the arrow starts on the left orbit
        self.assertIn(250000, self.adds(m))
        self.assertIn(137, self.deffs(m))
        self.assertFalse(self.tron.task_running(0xd1))
        self.assertEqual(1, self.pd.items[0][1])
        self.shot("zen")
        m = self.mark()
        self.shot("left_orbit")
        self.assertIn(275000, self.adds(m))

    def test_wrong_shot_finds_nothing(self):
        self.start_game(validate=True)
        self.shot("zen")
        m = self.mark()
        self.shot("right_orbit")
        self.assertNotIn(250000, self.adds(m))
        self.assertTrue(self.tron.task_running(0xd1))

    def test_the_arrow_roves(self):
        self.start_game(validate=True)
        self.shot("zen")
        ff = self.feature("find_flynn")
        seen = set()
        for _ in range(140):
            self.wait(0.25)
            seen.add(ff.pos)
        self.assertEqual({0, 1, 2, 3, 4, 5}, seen)

    def test_ends_with_the_ball(self):
        self.start_game(validate=True)
        self.shot("zen")
        self.end_ball()
        self.assertFalse(self.tron.task_running(0xd1))
        self.validate()
        m = self.mark()
        self.shot("left_orbit")
        self.assertNotIn(250000, self.adds(m))

    def test_blocked_only_by_end_of_line_and_wizards(self):
        """FUN_0100d654 [0x0100d654] blocks it on task 0xd1, flag 0x34, Portal 0x37 and End of Line 0x27 only: a
        Quorra multiball does not block it."""
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.shot("zen")
        self.assertTrue(self.tron.task_running(0xd1))
