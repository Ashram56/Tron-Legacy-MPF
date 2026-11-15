"""Stress: seeded random games on the physical table, modes started in every order, in and out of the
multiballs, with tilts, extra players and waits. The invariants (robot.Bench.check) run after every action.
`TRON_BENCH_SEEDS=200` plays more games; `TRON_BENCH_SEEDS=17,40` replays these seeds."""
import itertools
import random

from tests.bench.monkey import Monkey
from tests.bench.robot import MB_FLAGS, Bench, seeds


class TestRandomGames(Bench):
    """Whole games by a random player."""

    def _play(self, seed, **kwargs):
        if self.machine.game:                       # a seed before this one failed in the middle of its game
            self.problems = []
            self.end_game()
        self.start_game()
        Monkey(self, seed, **kwargs).play(actions=350)
        self.assertIsNone(self.machine.game)
        self.assertEqual(4, self.table.trough, "balls left out of the trough after the game")

    def test_random_games(self):
        for seed in seeds(6):
            with self.subTest(seed=seed):
                self._play(seed)

    def test_random_games_without_tilt(self):
        """No tilt: the balls live longer, so the modes go further."""
        for seed in seeds(6):
            with self.subTest(seed=seed):
                self._play(1000 + seed, tilt=False, players=False)


class TestRandomGamesPro(TestRandomGames):
    """The same on the Pro's standup TRON targets (no drop targets)."""
    DROP_TARGETS = False

    def test_random_games_without_tilt(self):
        for seed in seeds(3):
            with self.subTest(seed=seed):
                self._play(2000 + seed, tilt=False, players=False)

    def test_random_games(self):
        for seed in seeds(3):
            with self.subTest(seed=seed):
                self._play(3000 + seed)


class TestRandomAwards(Bench):
    """Flynn's Arcade left to its weighted draw (the other tests force 500K)."""
    ARCADE = None

    def test_random_games(self):
        for seed in seeds(4):
            with self.subTest(seed=seed):
                self.start_game()
                Monkey(self, 4000 + seed, tilt=False).play(actions=350)
                self.assertIsNone(self.machine.game)


class TestModesInAnyOrder(Bench):
    """The three timed modes and a multiball, started in every order on one ball."""

    STARTERS = ("start_clu", "start_gem", "start_zuse")
    MULTIBALLS = ("start_quorra", "start_light_cycle", "start_disc_multiball", "start_end_of_line")

    def test_timed_modes_in_every_order(self):
        for order in itertools.permutations(self.STARTERS):
            with self.subTest(order=order):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                for name in order:
                    getattr(self, name)()
                for name in ("clu", "gem", "zuse"):
                    self.assertTrue(self.feature(name).clock.running(), name + " stopped by a later mode")
                self.wait(60)                       # all three run out
                for name in ("clu", "gem", "zuse"):
                    self.assertFalse(self.feature(name).clock.running(), name + " never ended")

    def test_timed_modes_then_a_multiball(self):
        for mb in self.MULTIBALLS:
            for order in ((0, 1, 2), (2, 1, 0), (1, 2, 0)):
                with self.subTest(multiball=mb, order=order):
                    self.end_game() if self.machine.game else None
                    self.start_game(validate=True)
                    for i in order:
                        getattr(self, self.STARTERS[i])()
                    getattr(self, mb)()
                    self.wait(12)
                    self.assertGreaterEqual(self.table.out, 2, "the multiball put no second ball in play")
                    Monkey(self, 7, tilt=False, players=False).play(actions=60, finish=False)

    def test_a_multiball_then_the_timed_modes(self):
        for mb in self.MULTIBALLS:
            with self.subTest(multiball=mb):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                getattr(self, mb)()
                self.wait(12)
                self.start_gem()
                if mb != "start_end_of_line":       # End of Line closes the ZUSE qualifying (zuse_fast_scoring.md)
                    self.start_zuse()
                Monkey(self, 11, tilt=False, players=False).play(actions=60, finish=False)

    def test_every_multiball_after_every_other(self):
        """One multiball, down to one ball, then another: nothing of the first one is left."""
        rng = random.Random(5)
        pairs = list(itertools.permutations(self.MULTIBALLS, 2))
        rng.shuffle(pairs)
        for first, second in pairs[:8]:
            with self.subTest(first=first, second=second):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                getattr(self, first)()
                self.wait(14)
                self.down_to_one_ball()
                self.wait(26)                        # the end windows, and Disc Multiball's restart window
                self.assertFalse([f for f in MB_FLAGS if self.flag(f)], "the first multiball never ended")
                self.assertTrue(self.machine.game and self.table.pf == 1, "the ball ended with the multiball")
                getattr(self, second)()
                self.wait(12)


class TestMultiballEdges(Bench):

    def test_all_balls_drain_at_once(self):
        for mb in TestModesInAnyOrder.MULTIBALLS:
            with self.subTest(multiball=mb):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                ball = self.machine.game.player.ball
                getattr(self, mb)()
                self.wait(14)
                self.no_ball_save()
                while self.table.pf:                 # every ball in the same instant
                    self.table.drain()
                self.wait(0.5)
                self.end_ball()
                self.assertFalse([f for f in MB_FLAGS if self.flag(f)])
                self.assertTrue(not self.machine.game or self.machine.game.player.ball == ball + 1
                                or self.flag(9) is not None)

    def test_tilt_in_every_multiball(self):
        for mb in TestModesInAnyOrder.MULTIBALLS + ("start_sea_of_simulation", "start_portal"):
            with self.subTest(multiball=mb):
                self.end_game() if self.machine.game else None
                self.start_game(validate=True)
                getattr(self, mb)()
                self.wait(8)
                self.tilt_out()
                self.assertTrue(self.tron.tilted)
                score = self.score()
                self.wait_until(lambda: self.table.pf > 0 or not self.tron.tilted, 20, what="a ball to drain")
                while self.tron.tilted and self.machine.game:
                    if self.table.pf:
                        self.table.hit("s_left_orbit")       # a tilted ball scores nothing
                        self.drain()
                    self.wait(0.3)
                    self.assertLessEqual(self.score(1) if self.machine.game else score, score + 0)
                self.assertFalse([f for f in MB_FLAGS if self.flag(f)], "a multiball survived the tilt")

    def test_scoop_while_another_ball_is_held(self):
        """Two balls for one scoop: the second bounces out and the game goes on."""
        self.start_game(validate=True)
        self.start_quorra()
        self.wait(12)
        self.wait_until(lambda: self.table.pf >= 2, 20, what="two balls")
        self.scoop(wait=False)
        self.assertFalse(self.table.to_vuk())
        self.wait_until(lambda: self.table.vuk == 0, 30, what="the VUK kick")
        self.wait(2)


class TestPlayers(Bench):

    def test_four_players_take_turns(self):
        self.start_game(players=4, validate=True)
        seen = []
        for _ in range(12):
            if not self.machine.game:
                break
            seen.append(self.machine.game.player.number)
            self.shots("left_ramp", "right_ramp")
            self.end_ball()
        self.assertEqual([1, 2, 3, 4] * 3, seen)
        self.assertIsNone(self.machine.game)

    def test_progress_is_per_player(self):
        self.start_game(players=2, validate=True)
        self.light_quorra()                                  # player 1 lights Quorra
        self.assertTrue(self.tron.hook("vuk_lit_test", 2))
        self.end_ball()
        self.assertEqual(2, self.machine.game.player.number)
        self.validate()
        self.assertFalse(self.tron.hook("vuk_lit_test", 2), "player 2 got player 1's lit Quorra")
        self.end_ball()
        self.assertEqual(1, self.machine.game.player.number)
        self.assertTrue(self.tron.hook("vuk_lit_test", 2), "player 1 lost the lit Quorra")

    def test_start_during_the_game(self):
        """START adds players on ball 1 only."""
        self.start_game(validate=True)
        self.press("s_start_button")
        self.assertEqual(2, len(self.machine.game.player_list))
        self.end_ball()
        self.end_ball()
        self.assertEqual(2, self.machine.game.player.ball)
        self.press("s_start_button")
        self.assertEqual(2, len(self.machine.game.player_list))
