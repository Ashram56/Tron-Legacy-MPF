"""The service menu's adjustments, set with the coin door buttons and then checked in a game on the
physical table: every adjustment the rules read must change what the player gets.

tests/test_adjustments.py checks the same adjustments by writing `os.adj[n]` and calling the rule's
function; here the value goes in through ADJUSTMENTS > STANDARD / FEATURE ADJUSTMENTS (or GAME OPTIONS)
and the effect is watched from the playfield. IN_PLAY | NOT_IN_PLAY must cover adjustments 1-88."""
from tests.bench.robot import Bench

MENUS = {"standard": "STANDARD ADJUSTMENTS", "feature": "FEATURE ADJUSTMENTS", "options": "GAME OPTIONS"}

# adjustment -> the test of this file that plays with it
IN_PLAY = {11, 13, 14, 15, 22, 23, 26, 30, 31, 32, 36, 38, 39, 40, 41, 42, 64, 65, 66, 67, 68, 69, 70, 72, 73,
           74, 78, 79, 82, 83, 84, 85}
# adjustment -> why it is not played here
NOT_IN_PLAY = {
    1: "coil strength: MPF's pulse times", 5: "flasher strength", 9: "sound board", 87: "sound board",
    88: "sound board", 86: "shaker: tests/test_adjustments.py (coil only)",
    2: "attract message: tests/test_credits.py", 3: "clock format (service menu)", 4: "boot", 6: "operator data",
    7: "text language: English only", 8: "operator data", 10: "language menu: not built",
    12: "dynamic replay percentage: needs many games (tests/test_adjustments.py)",
    16: "dynamic replay start (tests/test_adjustments.py)", 17: "fixed replay levels (tests/test_adjustments.py)",
    18: "as 17", 19: "as 17", 20: "as 17", 21: "replay boost: needs a second game after a replay",
    24: "special percentage: needs audits of 100 games (tests/test_adjustments.py)",
    27: "extra ball percentage: as 24", 25: "credits: tests/test_credits.py", 28: "pricing: tests/test_credits.py",
    33: "credit limit: tests/test_credits.py", 34: "free play: tests/test_credits.py",
    29: "match award: tests/test_adjustments.py (the match is random)", 35: "knocker volume: sound",
    37: "no reader in the ROM", 43: "no reader in the ROM", 44: "Q24 output: tests/test_adjustments.py",
    45: "ticket dispenser: service menu only", 46: "player competition: not built", 47: "not read by the game",
    48: "high scores: tests/test_credits.py", 49: "as 48", 50: "as 48", 51: "as 48", 52: "as 48", 53: "as 48",
    54: "as 48", 55: "as 48", 56: "as 48", 57: "as 48", 58: "as 48", 59: "as 48", 60: "as 48", 61: "as 48",
    62: "coin switch timing: tests/test_credits.py", 63: "lost ball: 5 ball searches (tests/test_adjustments.py)",
    71: "restart autofire: tests/test_adjustments.py", 75: "abort animations: not built (docs/test_bench.md)",
    76: "motor: tests/test_adjustments.py", 77: "motor: tests/test_adjustments.py",
    80: "disable drop targets: not built (docs/test_bench.md)", 81: "Recognizer head motor: not driven",
}


class Operator(Bench):
    """A Bench whose operator opens the service menu between games."""

    @property
    def svc(self):
        return self.machine.modes["tron_service"]

    def button(self, name):
        self.press("s_service_" + name, seconds=0.02, settle=0.05)

    def adjust(self, menu="standard", **values):
        """adjust(a31=1, a32=0): each adjustment set through the menu, from the attract mode."""
        self.assertIsNone(self.machine.game, "the service menu opens between games")
        self.advance_time_and_run(1)
        self.button("select")
        self.button("select")                               # entry screen, then the main menu
        self.assertTrue(self.svc.active, "the service menu did not open")
        for text in ("GO TO ADJUSTMENTS MENU", MENUS[menu]):
            screen = self.svc.stack[-1]
            texts = [i["text"] for i in screen.items()]
            self.assertIn(text, texts)
            for _ in texts:
                if texts[screen.pos % len(texts)] == text:
                    break
                self.button("plus")
            self.button("select")
        screen = self.svc.stack[-1]
        for key, value in values.items():
            num = int(key[1:])
            self.assertIn(num, screen.entries(), "adjustment {} is not in {}".format(num, MENUS[menu]))
            for _ in screen.entries():
                if screen.current() == num:
                    break
                self.button("plus")
            self.button("select")
            down = value < screen.editing
            for _ in range(400):
                if screen.editing == value:
                    break
                self.button("minus" if down else "plus")
            self.assertEqual(value, screen.editing, "adjustment {} cannot take {}".format(num, value))
            self.button("select")
            self.assertEqual(value, screen.adj[num])
        for _ in range(6):
            if not self.svc.active:
                break
            self.button("back")
        self.assertFalse(self.svc.active, "the service menu did not close")
        self.advance_time_and_run(1)


class TestCoverage(Operator):

    def test_every_adjustment_is_played_or_listed(self):
        self.assertEqual(set(range(1, 89)), IN_PLAY | set(NOT_IN_PLAY))
        self.assertFalse(IN_PLAY & set(NOT_IN_PLAY))

    def test_the_menu_value_is_kept_for_the_next_games(self):
        self.adjust(a31=1)
        for _ in range(2):
            self.start_game(validate=True)
            self.end_ball()
            self.assertIsNone(self.machine.game)


class TestGameAdjustments(Operator):

    def test_31_balls_per_game(self):
        for balls in (1, 5):
            with self.subTest(balls=balls):
                self.adjust(a31=balls)
                self.start_game(validate=True)
                played = 0
                while self.machine.game:
                    played += 1
                    self.end_ball()
                self.assertEqual(balls, played)

    def test_32_tilt_warnings(self):
        for warnings in (0, 3):
            with self.subTest(warnings=warnings):
                self.adjust(a32=warnings)
                self.start_game(validate=True)
                m = self.mark()
                for _ in range(warnings):
                    self.tilt_bob()
                    self.assertFalse(self.tron.tilted)
                self.assertEqual(warnings, self.deffs(m).count(23))
                self.tilt_bob()
                self.assertTrue(self.tron.tilted)
                self.end_game()

    def test_38_ball_save_time_off(self):
        self.adjust(a38=0)
        self.start_game(validate=True)
        m = self.mark()
        self.drain()
        self.wait(8)
        self.assertNotIn(20, self.deffs(m))
        self.assertEqual(2, self.machine.game.player.ball)

    def test_38_ball_save_time_long(self):
        """16 s: a drain 12 s after the valid playfield is saved (factory 5 s: test_game_flow)."""
        self.adjust(a38=16)
        self.start_game(validate=True)
        self.wait(12)
        m = self.mark()
        self.drain()
        self.wait(1.5)
        self.assertIn(20, self.deffs(m))
        self.assertEqual(1, self.machine.game.player.ball)

    def test_41_coindoor_ball_saver(self):
        self.adjust(a41=1)
        self.start_game(validate=True)
        self.no_ball_save()
        self.machine.switch_controller.process_switch("s_coin_door_open", 1, True)
        self.wait(0.5)
        self.machine.switch_controller.process_switch("s_coin_door_open", 0, True)
        self.drain()
        self.wait_until(lambda: self.table.pf == 1, 15, what="the ball given back")
        self.assertEqual(1, self.machine.game.player.ball)

    def test_64_coin_door_disable_tilt(self):
        self.adjust(a64=1)
        self.start_game(validate=True)
        self.machine.switch_controller.process_switch("s_coin_door_open", 1, True)
        self.wait(0.2)
        for _ in range(4):
            self.tilt_bob()
        self.assertEqual(0, self.tron.tilt_warnings)
        self.machine.switch_controller.process_switch("s_coin_door_open", 0, True)
        self.wait(0.2)
        self.tilt_bob()
        self.assertEqual(1, self.tron.tilt_warnings)

    def test_36_game_restart(self):
        """START held on ball 2 starts a new game; with GAME RESTART = NO it does nothing."""
        for restart in (1, 0):
            with self.subTest(restart=restart):
                self.adjust(a36=restart)
                self.start_game(validate=True)
                self.end_ball()
                self.assertEqual(2, self.machine.game.player.ball)
                self.press("s_start_button", seconds=3, settle=1)
                self.assertIsNotNone(self.machine.game)
                if restart:
                    self.assertFalse(self.tron.in_play)      # the new game waits for the ball in play
                    self.hit("s_left_bumper")                # ... which still closes switches
                    self.table.drain()
                    self.wait(8, check=False)
                self.ball_in_play()
                self.assertEqual(1 if restart else 2, self.machine.game.player.ball)
                self.end_game()

    def test_26_extra_ball_limit(self):
        """Limit 0: a collected extra ball pays 3,000,000 and the ball number goes on."""
        self.adjust(a26=0)
        self.start_game(validate=True)
        for _ in range(4):
            self.shot("left_ramp", settle=0.1)
            self.shot("right_ramp", settle=0.1)
        self.assertTrue(self.tron.hook("vuk_lit_test", 1))
        self.wait(12)
        m = self.mark()
        self.scoop()
        self.assertIn(3000000, self.adds(m))
        self.assertFalse(self.flag(9))
        self.end_ball()
        self.assertEqual(2, self.machine.game.player.ball)

    def _replay_score(self):
        """Six Flynn's Arcade 500K awards: over 3,000,000... the replay level set below is 5,000,000."""
        for _ in range(11):
            self.scoop()
            self.shot("right_orbit")
            self.wait(3)

    def test_11_14_15_replay_level_and_13_award(self):
        """AUTO at 5,000,000, award EXTRA BALL: the replay comes at that score."""
        self.adjust(a15=5000000, a13=3)
        self.start_game(validate=True)
        self._replay_score()
        self.assertGreaterEqual(self.score(), 5000000)
        self.assertEqual(1, self.audit(10))
        self.assertEqual(1, self.machine.game.player.extra_balls, "the replay's extra ball")

    def test_11_replay_type_none(self):
        self.adjust(a15=5000000, a11=0)
        self.start_game(validate=True)
        self._replay_score()
        self.assertGreaterEqual(self.score(), 5000000)
        self.assertFalse(self.audit(10))

    def test_22_special_limit_and_23_award(self):
        """SPECIAL AWARD = EXTRA BALL (the special is lit by hand: Flynn's Arcade gives it 1 time in 352)."""
        self.adjust(a23=4, a22=2)
        self.start_game(validate=True)
        self.tron.light_special()
        self.tron.special_collect()
        self.wait(1)
        self.assertEqual(1, self.machine.game.player.extra_balls)

    def test_30_match_off(self):
        """OFF: no match number at the game's end."""
        for value, shown in ((11, False), (9, True)):
            with self.subTest(match=value):
                self.adjust(a30=value, a31=1)
                self.start_game(validate=True)
                m = self.mark()
                self.end_ball()
                self.wait(12)
                self.assertEqual(shown, 38 in self.deffs(m))

    def test_30_no_match_once_the_percentage_is_reached(self):
        """The machine matched too often (1 match in 1 game > 9 %): the number shown is never a player's."""
        self.adjust(a31=1)
        self.tron.audit(0x0f)
        self.tron.audit(0x11)
        numbers, ends = [], []
        deff_start = self.tron.deff_start

        def spy(deff_id, **args):
            if deff_id == 38:
                numbers.append(args["number"])
                ends.append(self.machine.game.player.score % 100)
            return deff_start(deff_id, **args)
        self.tron.deff_start = spy
        for game in range(8):
            self.start_game(validate=True)
            for _ in range(game):
                self.hit("s_left_slingshot")                  # scores with different endings
            self.end_ball()
            self.wait(12)
        self.assertEqual(8, len(numbers))
        self.assertFalse([pair for pair in zip(numbers, ends) if pair[0] == pair[1]])
        self.assertGreater(len(set(ends)), 2, ends)

    def test_42_competition_mode(self):
        """The weighted draw always gives 500K."""
        self.arcade = None
        self.adjust(a42=1)
        self.start_game(validate=True)
        for _ in range(6):
            m = self.mark()
            self.scoop()
            self.assertIn(500000, self.adds(m))
            self.shot("right_orbit")
            self.wait(3)


class TestPlunger(Operator):
    AUTOPLUNGE = None

    def test_39_timed_plunger(self):
        self.adjust(a39=4)
        self.start_game(plunge=False)
        self.wait_until(lambda: self.table.shooter == 1, 10, what="the ball in the lane")
        self.wait(2)
        self.assertEqual(1, self.table.shooter)
        self.wait(4)
        self.assertEqual((0, 1), (self.table.shooter, self.table.pf))
        self.assertEqual(1, self.table.coil_pulses.get("c_auto_launch"))

    def test_40_flipper_ball_launch(self):
        for value, side, launched in ((0, "left", False), (1, "left", True), (2, "left", False),
                                      (2, "right", True), (4, "right", False), (4, "both", True)):
            with self.subTest(value=value, side=side):
                self.adjust(a40=value)
                self.start_game(plunge=False)
                self.wait_until(lambda: self.table.shooter == 1, 10, what="the ball in the lane")
                self.wait(1)
                self.flip(side, seconds=0.2)
                self.wait(1.5)
                self.assertEqual(launched, self.table.pf == 1)
                self.end_game()

    def test_79_disable_plunge_post(self):
        """Skill shot B (right ramp) is lit at every serve; else the left flipper must be held."""
        for value in (0, 1):
            with self.subTest(value=value):
                self.adjust("feature", a79=value)
                self.start_game(plunge=False)
                self.wait_until(lambda: self.table.shooter == 1, 10, what="the ball in the lane")
                self.wait(1)
                self.assertEqual(bool(value), bool(self.feature("skill_shots").running("B")))
                self.end_game()


class TestFeatureAdjustments(Operator):

    def test_65_pop_bumper_difficulty(self):
        """Hits to the next bumper level: 20 (easy), 25, 30 (hard)."""
        for value, hits in ((0, 20), (2, 30)):
            with self.subTest(value=value):
                self.adjust("feature", a65=value)
                self.start_game(validate=True)
                done = self.pd.pop_levels_done
                for n in range(1, 40):
                    self.hit("s_left_bumper", settle=0.25)
                    if self.pd.pop_levels_done != done:
                        break
                self.assertEqual(hits - 1, n)                # validate() hit one bumper
                self.end_game()

    def test_66_zuse_fast_scoring_timer(self):
        """The clock starts at adj 66 and the mode lasts that much longer."""
        length = {}
        for seconds in (15, 45):
            self.adjust("feature", a66=seconds)
            self.start_game(validate=True)
            self.start_zuse()
            zuse = self.feature("zuse")
            self.assertEqual(seconds, zuse.clock.seconds)
            length[seconds] = self.wait_until(lambda: not zuse.clock.running(), 120, what="the end of ZUSE")
            self.end_game()
        self.assertGreater(length[45] - length[15], 30)

    def test_67_recognizer_difficulty(self):
        """Disc hits that start the first Disc Multiball: 4 + 2 x adj 67, and the one that starts it."""
        for value in (0, 1, 2):
            with self.subTest(value=value):
                self.adjust("feature", a67=value)
                self.start_game(validate=True)
                self.light_disc_battle()
                for n in range(1, 14):
                    self.shot("disc")
                    if self.flag(0x24):
                        break
                self.assertEqual(5 + 2 * value, n)
                self.end_game()

    def test_68_69_disc_multiball_shots(self):
        for discs, recogs in ((4, 1), (8, 5)):
            with self.subTest(discs=discs, recogs=recogs):
                self.adjust("feature", a68=discs, a69=recogs)
                self.start_game(validate=True)
                self.start_disc_multiball()
                self.wait(12)
                dmb = self.feature("disc_multiball")
                for n in range(1, 12):
                    self.shot("disc", settle=0.3)
                    if dmb.phase:
                        break
                self.assertEqual(discs, n)
                for n in range(1, 12):
                    self.shot("bank_c", settle=0.3)
                    if dmb.phase == 2:
                        break
                self.assertEqual(recogs, n)
                self.end_game()

    def test_70_disc_restart_timer(self):
        """The restart window after Disc Multiball counts adj 70 down, one count in 68 ticks; 4 = no window
        (and, as in the ROM [0x01007714], then no total either: flag 0x25 stays set)."""
        length = {}
        for seconds in (4, 6, 20):
            self.adjust("feature", a70=seconds)
            self.start_game(validate=True)
            self.start_disc_multiball()
            self.wait(14)
            m = self.mark()
            self.down_to_one_ball()
            self.wait(3)
            self.assertEqual(seconds != 4, 52 in self.deffs(m))
            if seconds != 4:
                length[seconds] = self.wait_until(lambda: not self.tron.task_running(0xad), 60,
                                                  what="the window's end")
            self.end_game()
        self.assertAlmostEqual(14 * 68 * 0.01626, length[20] - length[6], delta=2)

    def test_72_73_74_tron_award_timers(self):
        """Each T-R-O-N award runs for its own adjustment."""
        self.adjust("feature", a72=20, a73=40, a74=25)
        self.start_game(validate=True)
        targets = self.feature("tron_targets")
        want = {4: 20, 2: 40, 1: 25}
        seen = {}
        for _ in range(3):
            bit = self.start_tron_award()
            seen[bit] = targets.secs[bit]
            self.wait(3)
        self.assertEqual(set(want), set(seen))
        for bit, seconds in want.items():                    # read half a second after the start
            self.assertIn(seen[bit], (seconds, seconds - 1), bit)

    def test_78_disable_orbit_up_post(self):
        for value in (0, 1):
            with self.subTest(value=value):
                self.adjust("feature", a78=value)
                self.start_game(validate=True)
                self.assertEqual(not value, bool(self.table.coil_pulses.get("c_orbit_up_down_post")
                                                 or self.tron.switches.orbit_post))
                self.end_game()

    def test_82_insult_level(self):
        """NONE: no insult (speech 0x129) on a left outlane drain, even when the 1-in-4 draw gives it."""
        pick = self.tron.pick
        self.tron.pick = lambda name, weights: 0 if name == "insult" else pick(name, weights)
        for value in (0, 2):
            with self.subTest(value=value):
                self.adjust("feature", a82=value)
                self.start_game(validate=True)
                self.no_ball_save()
                m = self.mark()
                self.drain(outlane="left")
                self.wait(2)
                self.assertEqual(bool(value), 0x129 in self.sounds(m))
                self.end_game()

    def test_83_84_end_of_line_letters(self):
        """Sets of ramp letters that light End of Line: adj 83 the first time, adj 84 after."""
        for first, later in ((1, 4), (2, 10)):
            with self.subTest(first=first, later=later):
                self.adjust("feature", a83=first, a84=later)
                self.start_game(validate=True)
                self.assertEqual(first, self._sets_to_light())
                self.scoop()
                self.assertTrue(self.flag(0x27))
                self.wait(14)
                self.down_to_one_ball()
                self.wait(20)
                self.assertFalse(self.flag(0x27))
                self.assertEqual(later, self._sets_to_light())
                self.end_game()

    def _sets_to_light(self):
        ramps = 0
        while not self.flag(0x26) and ramps < 60:
            self.shot("left_ramp", settle=0.1)
            self.shot("right_ramp", settle=0.1)
            ramps += 1
        self.assertTrue(self.flag(0x26), "End of Line never lit")
        return ramps / 4                                     # a set: DAFT and PUNK, four ramps each

    def test_85_end_of_line_extra_ball(self):
        """The End of Line number that lights the extra ball."""
        for value in (1, 2):
            with self.subTest(value=value):
                self.adjust("feature", a85=value, a83=1, a84=4)
                self.start_game(validate=True)
                self._sets_to_light()
                self.assertEqual(value == 1, bool(self.flag(0x28)))
                self.end_game()

    def test_game_options_extended_ending(self):
        for value in (0, 1):
            with self.subTest(value=value):
                self.adjust("options", a1=value)
                self.start_game(validate=True)
                self.start_portal()
                self.assertEqual(bool(value), bool(self.feature("portal").ext))
                self.end_game()
