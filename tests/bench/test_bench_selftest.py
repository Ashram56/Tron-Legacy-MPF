"""The bench checks itself: the table moves balls as the coils say, the robot reaches every mode by the
switches, and the invariants catch what they are meant to catch."""
from tests.bench.robot import Bench, BenchError


class TestRobot(Bench):

    def test_a_whole_ball(self):
        os_ = self.start_game()
        self.assertEqual((3, 1), (self.table.trough, self.table.pf))
        self.end_ball()
        self.assertEqual((3, 1), (self.table.trough, self.table.pf))
        self.assertEqual(2, self.machine.game.player.ball)
        self.assertEqual(1, os_.audits[8])

    def test_no_ball_no_hit(self):
        self.start_game(plunge=False)
        with self.assertRaises(BenchError):
            self.hit("s_left_orbit")

    def test_reaches_every_mode_by_the_switches(self):
        for start, check in ((self.start_clu, lambda: self.feature("clu").clock.running()),
                             (self.start_gem, lambda: self.feature("gem").clock.running()),
                             (self.start_zuse, lambda: self.feature("zuse").clock.running())):
            with self.subTest(start=start.__name__):
                if not self.machine.game:
                    self.start_game(validate=True)
                start()
                self.assertTrue(check())
                self.end_ball()

    def test_reaches_every_multiball_by_the_switches(self):
        for start, flag in ((self.start_quorra, 0x29), (self.start_light_cycle, 0x2b),
                            (self.start_disc_multiball, 0x24), (self.start_end_of_line, 0x27),
                            (self.start_sea_of_simulation, 0x34), (self.start_portal, 0x37)):
            with self.subTest(start=start.__name__):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                start()
                self.assertTrue(self.flag(flag))
                self.wait(12)
                self.end_game()


class TestInvariantsCatch(Bench):

    def test_lost_ball_is_seen(self):
        self.start_game(validate=True)
        self.table.pf -= 1                       # a ball vanishes from the table
        with self.assertRaises(BenchError):
            self.check()
        self.table.pf += 1

    def test_score_going_down_is_seen(self):
        self.start_game(validate=True)
        self.shot("sling_l")
        self.machine.game.player.score -= 10
        with self.assertRaises(BenchError):
            self.check()
        self._scores = {}

    def test_forbidden_stack_is_seen(self):
        os_ = self.start_game(validate=True)
        os_.flags.update({0x24, 0x27})
        with self.assertRaises(BenchError):
            self.check()
        os_.flags.difference_update({0x24, 0x27})
