"""The multiballs and the wizard modes against their specs (assets/rules/modes/): Quorra, Light Cycle,
Recognizer and Disc Battle, Disc Multiball, End of Line (Daft Punk), Sea of Simulation, Portal."""
from tests.bench.robot import Bench

LOOP = 10000 + 90            # one left spinner spin with its switch score


class TestQuorra(Bench):
    """quorra_multiball.md"""

    def test_five_left_loops_light_it(self):
        self.start_game(validate=True)
        for n in range(4):
            m = self.mark()
            self.shot("left_loop")
            self.assertEqual(2, self.adds(m).count(10000), "the spin and the progress, 10,000 each")
            self.assertFalse(self.tron.hook("vuk_lit_test", 2))
        self.assertEqual(4, self.pd.quorra_progress)
        m = self.mark()
        self.shot("left_loop")
        self.assertTrue(self.tron.hook("vuk_lit_test", 2))
        self.assertIn(63, self.deffs(m))
        self.assertEqual(0, self.pd.quorra_progress)
        m = self.mark()
        self.shot("left_loop")                                           # lit: no more progress
        self.assertEqual(1, self.adds(m).count(10000))

    def test_start(self):
        self.start_game(validate=True)
        self.light_quorra()
        m = self.mark()
        self.scoop()
        q = self.feature("quorra")
        self.assertEqual([(2, 625, 125)], self.mb_starts(m))
        self.assertIn(200000, self.adds(m))
        self.assertTrue(self.flag(0x29))
        self.assertEqual(1, self.audit(0x47))
        self.assertEqual((350000, 1000000, 200000), (q.jackpot, q.super, q.total))
        self.assertFalse(self.tron.hook("vuk_lit_test", 2))
        self.wait_until(lambda: self.table.pf == 2, 20, what="the second ball")
        self.assertIn(64, self.deffs(m))

    def test_jackpots_and_super(self):
        """The spec's worked example."""
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        q = self.feature("quorra")
        m = self.mark()
        self.shot("left_loop")
        self.assertIn(350000, self.adds(m))
        self.assertEqual((375000, 1350000), (q.jackpot, q.super))
        m = self.mark()
        self.shot("left_loop")
        self.assertIn(375000, self.adds(m))
        self.assertEqual((400000, 1725000), (q.jackpot, q.super))
        m = self.mark()
        self.shot("right_loop")
        self.assertIn(1725000, self.adds(m))
        self.assertEqual(1250000, q.super)
        self.assertEqual((2, 1), (self.audit(0x48), self.audit(0x49)))
        self.assertEqual(1, self.pd.items[4][1], "the Super collects the QUORRA item")

    def test_jackpot_is_capped_at_500k(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        got = []
        for _ in range(9):
            m = self.mark()
            self.shot("left_loop", settle=0.1)
            got.append(max(self.adds(m)))
        self.assertEqual([350000, 375000, 400000, 425000, 450000, 475000, 500000, 500000, 500000], got)

    def test_three_bank_hits_add_a_ball_twice(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        for added in (1, 2):
            for _ in range(2):
                m = self.mark()
                self.shot("bank_c")
                self.assertIn(50000, self.adds(m))
            m = self.mark()
            self.shot("bank_c")
            self.assertIn(500000, self.adds(m))
            self.assertEqual([(2 + added, 312, 187)], self.mb_starts(m))
            self.assertEqual(added, self.feature("quorra").aab_count)
            self.wait_until(lambda: self.table.pf == 2 + added, 20, what="the added ball")
        m = self.mark()
        self.shot("bank_c")
        self.assertNotIn(50000, self.adds(m))                             # two add-a-balls: no more

    def test_end_window_then_total(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        m = self.mark()
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x29))
        m2 = self.mark()
        self.shot("left_loop")
        self.assertIn(350000, self.adds(m2), "a late Jackpot in the end window")
        self.wait(9)
        self.assertIn(70, self.deffs(m))
        self.assertTrue(self.machine.game and self.table.pf == 1)
        m3 = self.mark()
        self.shot("left_loop")
        self.assertNotIn(375000, self.adds(m3))

    def test_add_a_ball_in_the_end_window_resumes(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.shots("bank_c", "bank_c")
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x29))
        self.shot("bank_c")
        self.assertTrue(self.flag(0x29), "Quorra resumes")
        self.wait_until(lambda: self.table.pf == 2, 20, what="the added ball")

    def test_second_quorra_jackpot_starts_higher(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.down_to_one_ball()
        self.wait(10)
        self.start_quorra()
        self.assertEqual(375000, self.feature("quorra").jackpot)
        self.wait(12)

    def test_ball_save_returns_a_drained_ball(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait_until(lambda: self.table.pf == 2, 20, what="the second ball")
        self.drain()                                                      # inside the 10 s save
        self.wait_until(lambda: self.table.pf == 2, 20, what="the saved ball")
        self.assertTrue(self.flag(0x29))

    def test_ends_with_the_ball(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        m = self.mark()
        self.end_ball()
        self.assertFalse(self.flag(0x29))
        self.assertIn(70, self.deffs(m))


class TestLightCycle(Bench):
    """light_cycle_multiball.md"""

    def test_four_different_shots_light_it(self):
        self.start_game(validate=True)
        m = self.mark()
        self.shots("left_ramp", "left_ramp", "right_ramp")
        self.assertEqual(2, self.deffs(m).count(83), "a repeated shot is no progress")
        self.assertFalse(self.tron.hook("vuk_lit_test", 4))
        self.shot("left_orbit")
        m = self.mark()
        self.shot("right_orbit")
        self.assertTrue(self.tron.hook("vuk_lit_test", 4))
        self.assertIn(84, self.deffs(m))

    def test_start(self):
        self.start_game(validate=True)
        self.light_light_cycle()
        m = self.mark()
        self.scoop()
        self.assertEqual([(2, 625, 125)], self.mb_starts(m))
        self.assertIn(150000, self.adds(m))
        self.assertTrue(self.flag(0x2b))
        self.assertEqual(1, self.audit(0x4a))
        self.wait_until(lambda: self.table.pf == 2, 20, what="the second ball")

    def _award(self, shot):
        m = self.mark()
        self.shot(shot)
        got = [p for p in self.adds(m) if p in (350000, 750000, 1500000)]
        return got[0] if got else 0

    def test_the_spec_chain(self):
        """The reference scenario: 350K, 750K, 1.5M on chain A, chain B, chain C."""
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.assertEqual(350000, self._award("left_ramp"))
        self.assertEqual(750000, self._award("left_loop"))
        self.assertEqual(1500000, self._award("right_loop"))
        self.assertEqual(350000, self._award("right_orbit"))                # chain B
        self.assertEqual(750000, self._award("right_ramp"))                 # B's Super
        self.assertEqual(350000, self._award("right_ramp"))                 # chain C: always a Jackpot
        self.assertEqual(0, self._award("right_loop"))                      # lit by no chain
        self.assertEqual((3, 2, 1), (self.audit(0x4b), self.audit(0x4c), self.audit(0x4d)))

    def test_left_orbit_super_goes_back_to_the_ramp(self):
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.assertEqual(350000, self._award("left_ramp"))
        self.assertEqual(750000, self._award("left_orbit"))
        self.assertEqual(0, self._award("left_loop"))
        self.assertEqual(350000, self._award("left_ramp"))

    def test_super_window_times_out_with_a_grace(self):
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.assertEqual(350000, self._award("left_ramp"))
        self.wait(5.6)                                                    # 315 ticks = 5.1 s, then 125 ticks grace
        self.assertEqual(750000, self._award("left_orbit"), "a grace shot still scores the Super")
        self.assertEqual(350000, self._award("left_ramp"))
        self.wait(8)
        self.assertEqual(0, self._award("left_orbit"))

    def test_six_shots_the_second_time(self):
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.down_to_one_ball()
        self.wait(10)
        for n, name in enumerate(("left_orbit", "left_ramp", "left_loop", "right_loop", "right_ramp")):
            self.shot(name)
            self.assertFalse(self.tron.hook("vuk_lit_test", 4), "lit after {} shots".format(n + 1))
        self.shot("right_orbit")
        self.assertTrue(self.tron.hook("vuk_lit_test", 4))

    def test_late_jackpot_also_counts_as_progress(self):
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x2b))
        m = self.mark()
        self.shot("right_orbit")
        self.assertIn(350000, self.adds(m))
        self.assertIn(83, self.deffs(m))
        self.wait(9)
        self.assertIn(90, self.deffs(m))

    def test_stacks_with_quorra_on_one_scoop(self):
        self.start_game(validate=True)
        self.light_quorra()
        self.light_light_cycle()
        m = self.mark()
        self.scoop()
        self.assertTrue(self.flag(0x2b) and self.flag(0x29))
        self.assertEqual([(2, 625, 125), (3, 625, 125)], self.mb_starts(m))
        self.wait_until(lambda: self.table.pf == 3, 25, what="three balls")
        both = self.mark()
        self.shot("left_loop")                                            # Quorra Jackpot (LC's chain A is on the ramp)
        self.assertIn(350000, self.adds(both))

    def test_quorra_start_resumes_a_light_cycle_in_its_end_window(self):
        self.start_game(validate=True)
        self.start_light_cycle()
        self.wait(12)
        self.light_quorra()                                               # Quorra's progress is open in Light Cycle
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x2b))
        self.scoop()
        self.assertTrue(self.flag(0x29))
        self.assertTrue(self.flag(0x2b), "Light Cycle resumes when Quorra starts in its end window")
        self.wait(12)


class TestRecognizerAndDiscBattle(Bench):
    """recognizer_and_disc_battle.md"""

    def test_five_counts_light_the_battle(self):
        self.start_game(validate=True)
        rec = self.feature("recognizer")
        counts = 0
        hits = 0
        m0 = self.mark()
        while not self.flag(0x22):
            m = self.mark()
            self.shot("bank_l", settle=0.3)
            hits += 1
            if not self.flag(0x22):
                self.assertEqual([2500, 1080], self.adds(m))
                self.assertIn(108, self.deffs(m))
            self.assertLessEqual(hits, 5)
        self.assertGreaterEqual(hits, 3)                                  # the lit target counts 2
        self.assertIn(200000, self.adds(m0))
        self.assertIn(109, self.deffs(m0))
        self.assertEqual(1, self.audit(0x8d))
        self.assertEqual(6, self.pd.dbattle_remaining)                    # adj 67 = 1: 4 + 2 x 1
        self.wait(1.5)
        self.assertFalse(self.table.bank_up, "the 3-bank drops")
        m = self.mark()
        self.shot("bank_c")
        self.assertEqual([1000, 1080], self.adds(m))                      # the targets no longer count

    def test_seven_disc_hits_start_disc_multiball(self):
        self.start_game(validate=True)
        self.light_disc_battle()
        for left in range(6, 0, -1):
            m = self.mark()
            self.shot("disc")
            self.assertEqual([2310], self.adds(m))
            self.assertIn(111, self.deffs(m))
            self.assertEqual(left - 1, self.pd.dbattle_remaining)
        m = self.mark()
        self.shot("disc")
        self.assertEqual([2000000, 100000, 2310], self.adds(m))
        self.assertEqual([(3, 625, 187)], self.mb_starts(m))
        self.assertTrue(self.flag(0x24) and self.flag(0x25))
        self.assertFalse(self.flag(0x22))
        self.assertEqual(1, self.audit(0x41))
        self.wait_until(lambda: self.table.pf == 3, 25, what="three balls")

    def test_disc_repeat_guard(self):
        self.start_game(validate=True)
        self.light_disc_battle()
        self.shot("disc")
        m = self.mark()
        self.shot("disc", clean=False)                                    # within 2 s: sound 0x54 only
        self.assertEqual([], self.adds(m))
        self.assertEqual(5, self.pd.dbattle_remaining)
        m = self.mark()
        self.shot("disc", clean=False)                                    # the guard was cancelled by that hit
        self.assertEqual([2310], self.adds(m))

    def test_battle_stays_lit_for_the_next_ball(self):
        self.start_game(validate=True)
        self.light_disc_battle()
        self.shots("disc", "disc")
        self.end_ball()
        self.assertTrue(self.flag(0x22))
        self.assertEqual(4, self.pd.dbattle_remaining)
        self.wait(2)
        self.assertFalse(self.table.bank_up)

    def test_second_battle_needs_eight_hits(self):
        self.start_game(validate=True)
        self.start_disc_multiball()
        self.wait(14)
        self.down_to_one_ball()
        self.wait(25)                                                     # the restart window runs out
        self.light_disc_battle()
        self.assertEqual(8, self.pd.dbattle_remaining)

    def test_targets_do_not_count_in_quorra(self):
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.feature("quorra").aab_count = 2                              # no add-a-ball left: the bank is free
        m = self.mark()
        self.shot("bank_c")
        self.assertIn(1000, self.adds(m))
        self.assertNotIn(2500, self.adds(m))


class TestDiscMultiball(Bench):
    """disc_multiball.md"""

    def _start(self):
        self.start_game(validate=True)
        self.start_disc_multiball()
        self.wait(14)
        return self.feature("disc_multiball")

    def test_the_spec_run(self):
        """disc_multiball.md section 10: blue shots, six disc jackpots, three Recognizer hits, the Super."""
        d = self._start()
        self.assertEqual((0, 250000, 100000, 100000), (d.phase, d.jackpot, d.super, d.total))
        for name, value in (("left_ramp", 100000), ("right_loop", 225000), ("right_ramp", 200000)):
            m = self.mark()
            self.shot(name)
            self.assertIn(value, self.adds(m), name)
        self.assertEqual(775000, d.jackpot)
        for value in (775000, 255000, 260000, 265000, 270000, 275000):
            m = self.mark()
            self.shot("disc")
            self.assertIn(value, self.adds(m))
        self.assertEqual((1, 280000, 2200000), (d.phase, d.jackpot, d.super))
        self.wait(1.5)
        self.assertTrue(self.table.bank_up, "the 3-bank rises for phase 1")
        m = self.mark()
        self.shot("disc")
        self.assertEqual([2310], self.adds(m))                            # not lit in phase 1
        for _ in range(3):
            m = self.mark()
            self.shot("bank_c")
            self.assertIn(280000, self.adds(m))
        self.assertEqual((2, 3040000), (d.phase, d.super))
        m = self.mark()
        self.shot("disc")
        self.assertIn(3040000, self.adds(m))
        self.assertEqual((0, 100000, 6605000), (d.phase, d.super, d.total))
        self.assertFalse(self.flag(0x25), "no restart window after a Super")
        m = self.mark()
        self.shot("left_ramp")
        self.assertIn(112000, self.adds(m))                               # D is kept: 100,000 + 2,000 x 6
        self.assertEqual((6, 3, 1), (self.audit(0x42), self.audit(0x44), self.audit(0x45)))
        m = self.mark()
        self.down_to_one_ball()
        self.wait(5)
        self.assertIn(51, self.deffs(m))
        self.assertFalse(self.tron.task_running(0xad))

    def test_orbits_and_left_loop_values(self):
        self._start()
        for name, value in (("left_orbit", 150000), ("left_loop", 125000), ("right_orbit", 175000)):
            m = self.mark()
            self.shot(name)
            self.assertIn(value, self.adds(m), name)

    def test_restart_window(self):
        d = self._start()
        self.shot("disc")                                                 # one jackpot, no Super
        m = self.mark()
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x24))
        self.assertTrue(self.tron.task_running(0xad), "the restart window")
        self.wait(6)
        self.assertIn(52, self.deffs(m))
        m2 = self.mark()
        self.shot("disc")
        self.assertEqual([(2, 620, 93)], self.mb_starts(m2))
        self.assertTrue(self.flag(0x24))
        self.assertEqual(255000, d.jackpot)                               # everything continues
        self.wait_until(lambda: self.table.pf == 2, 20, what="the restart's ball")
        self.down_to_one_ball()                                           # no second window: straight to the Total
        self.assertFalse(self.tron.task_running(0xad))
        self.wait(5)
        self.assertIn(51, self.deffs(m2))

    def test_missed_restart_shows_no_total(self):
        """ROM quirk (disc_multiball.md section 6)."""
        self._start()
        m = self.mark()
        self.down_to_one_ball()
        self.wait(25)
        self.assertFalse(self.tron.task_running(0xad) or self.tron.task_running(0xae) or self.tron.task_running(0xaf))
        self.assertNotIn(51, self.deffs(m))
        m = self.mark()
        self.shot("disc")
        self.assertEqual([], self.mb_starts(m))

    def test_another_multiball_cancels_the_restart_window(self):
        self.start_game(validate=True)
        self.light_light_cycle()
        self.start_disc_multiball()
        self.wait(14)
        self.down_to_one_ball()
        self.assertTrue(self.tron.task_running(0xad))
        self.scoop()                                                      # Light Cycle was lit: blocked by the window
        self.assertFalse(self.flag(0x2b), "Light Cycle may not start in the restart window")


class TestEndOfLine(Bench):
    """end_of_line_multiball.md (= Daft Punk Multiball)"""

    def test_two_sets_light_it_and_the_first_lights_the_extra_ball(self):
        self.start_game(validate=True)
        for ramp in range(1, 17):
            self.shot("left_ramp" if ramp % 2 else "right_ramp", settle=0.1)
            self.assertEqual(ramp >= 8, bool(self.flag(0x28)), "extra ball after ramp {}".format(ramp))
            self.assertEqual(ramp >= 16, bool(self.flag(0x26)), "lit after ramp {}".format(ramp))
        self.assertTrue(self.tron.hook("vuk_lit_test", 1), "EJECT: EXTRA BALL")

    def test_start_and_scoring(self):
        """The reference traces' values."""
        self.start_game(validate=True)
        self.light_end_of_line()
        m = self.mark()
        self.scoop()
        e = self.feature("end_of_line")
        self.assertEqual([(2, 625, 125)], self.mb_starts(m))
        self.assertTrue(self.flag(0x27))
        self.assertFalse(self.flag(0x26))
        self.assertIn(100000, self.adds(m))
        self.assertEqual(110000, e.total)                                 # + the VUK's switch value
        self.assertEqual(1, self.audit(0x8e))
        self.wait(12)
        m = self.mark()
        self.shot("left_ramp")
        self.assertEqual([10000, 560, 10000, 500000, 1170], [p for p in self.adds(m)])
        m = self.mark()
        self.shot("left_ramp")                                            # unlit until the right ramp
        self.assertNotIn(500000, self.adds(m))
        m = self.mark()
        self.shot("right_ramp")
        self.assertIn(1000000, self.adds(m))
        m = self.mark()
        self.shot("disc")
        self.assertEqual([10000, 200000, 2310], self.adds(m))
        self.assertEqual((1, 11000, 1), (e.level, e.switch_value, e.aab_left))
        m = self.mark()
        self.shot("disc")
        self.assertEqual([11000, 200000, 2310], self.adds(m))
        self.assertEqual([(3, 312, 187)], self.mb_starts(m))
        self.assertEqual((2, 12000, 3, 1), (e.level, e.switch_value, e.aab_left, e.aab_count))
        m = self.mark()
        self.shot("left_ramp")
        self.assertIn(550000, self.adds(m))
        self.wait_until(lambda: self.table.pf == 3, 20, what="the added ball")

    def test_grace_then_total(self):
        self.start_game(validate=True)
        self.start_end_of_line()
        self.wait(12)
        m = self.mark()
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x27))
        m2 = self.mark()
        self.shot("left_ramp")
        self.assertIn(500000, self.adds(m2), "the jackpot scores in the grace")
        self.assertIn(55, self.deffs(m2), "and the letters advance again")
        self.wait(8)
        self.assertIn(61, self.deffs(m))
        m3 = self.mark()
        self.shot("sling_l")
        self.assertEqual([440], self.adds(m3))

    def test_nothing_else_starts_meanwhile(self):
        self.start_game(validate=True)
        self.light_quorra()
        self.set_items(lit=())                                            # nothing else lit
        self.pd.vuk_lit  # noqa: B018 (the scoop's lit table exists)
        self.light_end_of_line()
        self.assertTrue(self.tron.hook("vuk_lit_test", 2))
        self.scoop()
        self.wait(12)
        # on_vuk starts Quorra before End of Line: with both lit, Quorra starts and End of Line waits
        self.assertTrue(self.flag(0x29))
        self.assertFalse(self.flag(0x27))
        self.assertTrue(self.flag(0x26), "End of Line stays lit")

    def test_later_lighting_needs_eight_sets(self):
        self.start_game(validate=True)
        self.start_end_of_line()
        self.wait(12)
        self.down_to_one_ball()
        self.wait(8)
        for sets in range(1, 9):
            for _ in range(4):
                self.shot("left_ramp", settle=0.05)
                self.shot("right_ramp", settle=0.05)
            self.assertEqual(sets == 8, bool(self.flag(0x26)), "after {} sets".format(sets))


class TestSeaOfSimulation(Bench):
    """sea_of_simulation.md"""

    def test_start_and_first_stages(self):
        self.start_game(validate=True)
        self.set_items(lit=range(9), collected=(2,))                      # the spec's scenario: CLU collected
        m = self.mark()
        self.scoop()
        s = self.feature("sea_of_simulation")
        self.assertIn(1000000, self.adds(m))
        self.assertTrue(self.flag(0x34) and self.flag(0x33))
        self.assertEqual(1, self.pd.sos_count)
        self.assertEqual([0] * 9, [i[0] for i in self.pd.items], "every lit byte is cleared")
        self.assertEqual(1, self.table.out, "single ball")
        m = self.mark()
        self.scoop()
        self.assertIn(100000, self.adds(m))                               # stage 0: the VUK
        m = self.mark()
        self.shot("right_loop")
        self.assertIn(200000, self.adds(m))                               # stage 1: GEM
        self.wait(6)
        self.assertIn(3000000, self.adds(m), "CLU was collected: its stage is skipped for 3,000,000")
        self.assertEqual(3, s.stage)
        for name in ("zuse_z", "zuse_u", "zuse_s", "zuse_e"):
            m = self.mark()
            self.shot(name)
            self.assertIn(400000, self.adds(m), name)
        self.assertEqual(4, s.stage)
        self.assertEqual(1000000 + 100000 + 200000 + 3000000 + 1600000, s.total)

    def test_all_nine_stages_qualify_the_portal(self):
        self.start_game(validate=True)
        self.start_sea_of_simulation()
        s = self.feature("sea_of_simulation")
        plan = ((("scoop",), 100000), (("right_loop",), 200000),
                (("scoop", "left_orbit", "left_loop", "right_orbit"), 300000),
                (("zuse_z", "zuse_u", "zuse_s", "zuse_e"), 400000), (("left_loop",), 500000),
                (("left_orbit", "left_ramp", "left_loop", "right_loop", "right_ramp", "right_orbit"), 600000),
                # stage 6 starts on right orbit, right ramp, left ramp; each made shot adds its chained ones
                (("right_orbit", "right_ramp", "left_ramp", "right_loop", "left_loop", "left_orbit"), 700000),
                (("bank_c",) * 6, 800000), (("tron_t", "tron_r", "tron_o", "tron_n"), 900000))
        for stage, (names, value) in enumerate(plan):
            self.assertEqual(stage, s.stage)
            for name in names:
                m = self.mark()
                self.scoop() if name == "scoop" else self.shot(name, settle=0.4)
                self.assertIn(value, self.adds(m), "stage {} {}".format(stage, name))
            self.wait(3)
        self.assertTrue(self.flag(0x36))
        self.assertFalse(self.flag(0x34))
        self.assertEqual([1] * 9, [1 if i[1] else 0 for i in self.pd.items])
        self.wait(6)
        m = self.mark()
        self.scoop()                                                      # all nine collected: the Portal
        self.assertTrue(self.flag(0x37))
        self.assertNotIn(50000000, self.adds(m), "a Sea of Simulation since the last Portal: no 50M bonus")
        self.wait(20)

    def test_drain_ends_it_with_a_total(self):
        self.start_game(validate=True)
        self.start_sea_of_simulation()
        m = self.mark()
        self.end_ball()
        self.assertFalse(self.flag(0x34))
        self.assertIn(126, self.deffs(m))
        self.assertEqual(1, self.pd.sos_count)

    def test_tilt_pays_the_queued_skip_bonus(self):
        """ROM: the skip bonuses not yet paid are added even on a tilt."""
        self.start_game(validate=True)
        self.set_items(lit=range(9), collected=(0,))
        self.table.to_vuk()
        self.wait(1.2)                               # the Sea starts, stage 0 (FLYNN) is skipped: 1,000,000 queued
        self.assertTrue(self.flag(0x34))
        before = self.score()
        self.CHECK = False                           # this score comes with the tilt: the rule, not a leak
        self.tilt_out()
        self.assertEqual(before + 1000000, self.score())
        self.wait_until(lambda: self.table.pf > 0, 30, what="the VUK kick")
        self._tilt_score = None
        self.CHECK = True

    def test_no_multiball_starts_in_it(self):
        self.start_game(validate=True)
        self.light_quorra()
        self.start_sea_of_simulation()
        self.assertFalse(self.flag(0x29))
        self.scoop()
        self.assertFalse(self.flag(0x29))


class TestPortal(Bench):
    """portal_multiball.md"""

    def test_start(self):
        self.start_game(validate=True)
        self.set_items(collected=range(9))
        m = self.mark()
        self.scoop()
        self.assertEqual([(4, 937, 312)], self.mb_starts(m))
        self.assertIn(1000000, self.adds(m))
        self.assertIn(50000000, self.adds(m), "no Sea of Simulation since the last Portal")
        self.assertTrue(self.flag(0x37))
        self.assertEqual(1, self.audit(0x89))
        self.assertEqual([[0, 0]] * 9, [list(i[:2]) for i in self.pd.items], "the items start again")
        self.wait_until(lambda: self.table.pf == 4, 30, what="four balls")

    def test_all_22_shots_then_the_super_then_a_million_each(self):
        self.start_game(validate=True)
        self.start_portal()
        self.wait_until(lambda: self.table.pf == 4, 30, what="four balls")
        p = self.feature("portal")
        expect = 500000
        plan = (("left_orbit", 4), ("left_ramp", 3), ("left_loop", 5), ("right_loop", 3), ("right_ramp", 3),
                ("right_orbit", 4))
        for name, count in plan:
            for _ in range(count):
                m = self.mark()
                self.shot(name, settle=0.1)
                self.assertIn(expect, self.adds(m), name)
                expect = min(expect + 50000, 1500000)
            m = self.mark()
            self.shot(name, settle=0.1)
            self.assertFalse([a for a in self.adds(m) if a >= 500000], "a completed shot scores nothing")
        self.assertEqual((1, 23500000), (p.phase, p.super_value))
        self.assertEqual(22, self.audit(0x8a))
        m = self.mark()
        self.shot("left_ramp")
        self.assertFalse([a for a in self.adds(m) if a >= 500000], "phase 1: only the disc")
        m = self.mark()
        self.shot("disc")
        self.assertIn(23500000, self.adds(m))
        self.assertEqual(2, p.phase)
        for name in ("left_ramp", "disc", "right_orbit"):
            m = self.mark()
            self.shot(name)
            self.assertIn(1000000, self.adds(m), name)
        self.assertEqual((1, 3), (self.audit(0x8b), self.audit(0x8c)))

    def test_grace_total_and_bonus(self):
        self.start_game(validate=True)
        self.start_portal()
        self.wait_until(lambda: self.table.pf == 4, 30, what="four balls")
        self.wait(16)
        m = self.mark()
        self.down_to_one_ball()
        self.assertFalse(self.flag(0x37))
        m2 = self.mark()
        self.shot("left_ramp")
        self.assertIn(500000, self.adds(m2), "a shot in the 5 s grace")
        self.wait(7)
        self.assertIn(145, self.deffs(m))
        before = self.score()
        self.end_ball()
        # bonus: base 50,000 + PORTAL 2,250,000 (the items were reset by the start)
        self.assertEqual(2300000, self.score(1) - before)

    def test_portal_before_end_of_line(self):
        self.start_game(validate=True)
        self.light_end_of_line()
        self.start_portal()
        self.assertFalse(self.flag(0x27))
        self.assertTrue(self.flag(0x26), "End of Line stays lit")
        self.wait(20)
