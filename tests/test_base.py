"""Unit tests for base-game code the reference scenarios do not reach: outlane special / lane change,
the outlane ball save (early serve), the insult speech, flipper audits and INSTANT INFO."""
from tests.tron_test import TronTestCase


class BaseCase(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)

    def hit(self, name, wait=0.3):
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)

    def validate(self):
        self.hit("s_zen_rollover")                       # a force switch validates the playfield
        self.assertTrue(self.tron.pf_valid)

    def sounds(self):
        return [e["call"] for e in self.tron.trace.of("sound")]

    @property
    def score(self):
        return self.machine.game.player.score


class TestOutlanes(BaseCase):

    def test_special_lane_change_and_collect(self):
        self.start_game()
        self.validate()
        tron = self.tron
        tron.light_special()
        self.assertEqual({8}, tron.lamps)                # the special insert: left outlane
        self.hit("s_left_slingshot")                     # lane change: lamp 8 -> 32
        self.assertEqual({32}, tron.lamps)
        tron.kill_ball_save()
        tron.forced["insult"] = [1]
        before = self.score
        self.hit("s_left_outlane")                       # unlit: 0xa2 and the base 100,000
        self.assertEqual(100000, self.score - before)
        self.assertEqual("0x0a2", self.sounds()[-1])
        self.assertEqual(1, tron.specials_lit[0])
        tron.adj[23] = 3                                 # SPECIAL AWARD: points
        before = self.score
        self.hit("s_right_outlane")                      # lit: special collected
        self.assertEqual(100000 + 5000000 + 100000, self.score - before)
        self.assertIn(82, [e["id"] for e in tron.trace.of("deff_start")])
        self.assertIn("0x09e", self.sounds())
        self.assertEqual(0, tron.specials_lit[0])
        self.assertEqual(set(), tron.lamps)
        self.assertEqual(1, tron.audits.get(0x0e))
        self.assertEqual(1, tron.specials_collected[0])

    def test_lit_insert_without_special_is_silent(self):
        self.start_game()
        self.validate()
        tron = self.tron
        tron.kill_ball_save()
        tron.lamps.add(32)                                # right outlane insert lit, no special for the player
        n = len(self.sounds())
        self.hit("s_right_outlane")
        self.assertNotIn("0x0a2", self.sounds()[n:])

    def test_outlane_ball_save_serves_at_once(self):
        self.start_game()
        tron = self.tron
        self.validate()
        self.assertTrue(tron.ball_save)
        self.hit("s_left_outlane", wait=1)
        self.assertIsNone(tron.ball_save)
        self.assertEqual(1, tron.audits.get(0x2b))
        self.assertIn(20, [e["id"] for e in tron.trace.of("deff_start")])
        self.assertEqual(2, self.machine.game.balls_in_play)
        self.assertTrue(tron.task_running(0x37))

    def test_insult_and_drain_audit(self):
        self.start_game()
        tron = self.tron
        self.validate()
        tron.kill_ball_save()
        tron.forced["insult"] = [0, 0]
        self.hit("s_left_outlane")
        self.assertEqual("0x129", self.sounds()[-1])     # insult replaces the outlane sound
        self.assertNotIn("0x0a2", self.sounds())
        self.hit("s_left_outlane")                       # timer 9 still runs: no insult this time
        self.assertEqual("0x0a2", self.sounds()[-1])
        self.assertEqual(1, self.sounds().count("0x129"))
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(3)
        self.assertEqual(1, tron.audits.get(0x28))       # LEFT DRAINS: task 0x37 ran at end of ball
        self.assertIsNone(tron.audits.get(0x29))


class TestFlippers(BaseCase):

    def test_audits_and_instant_info(self):
        self.start_game()
        tron = self.tron
        self.hit_and_release_switch("s_left_flipper")
        self.advance_time_and_run(0.2)
        self.assertEqual(1, tron.audits.get(0x2c))
        self.hit_switch_and_run("s_right_flipper", 1.7)  # 93 ticks (1.51 s) held, ball not scored yet
        self.assertEqual(1, tron.audits.get(0x2d))
        self.assertIn(27, [e["id"] for e in tron.trace.of("deff_start")])
        self.release_switch_and_run("s_right_flipper", 0.2)
        self.assertFalse(tron.display.running(27))


class TestReminders(BaseCase):

    def test_shooter_lane_reminder(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertTrue(self.machine.switches["s_shooter_lane"].state)
        self.advance_time_and_run(17.5)                  # ~19.5 s after the serve
        self.assertNotIn(40, [e["id"] for e in self.tron.trace.of("deff_start")])
        self.advance_time_and_run(1.5)                   # 1,250 ticks (20.3 s) after the serve
        self.assertIn(40, [e["id"] for e in self.tron.trace.of("deff_start")])

    def test_no_reminder_after_validation(self):
        self.start_game()
        self.validate()
        self.advance_time_and_run(25)
        self.assertNotIn(40, [e["id"] for e in self.tron.trace.of("deff_start")])

    def test_extra_ball_lit_speech(self):
        self.start_game()
        self.validate()
        scoop = self.tron.features_by_name["scoop"]
        scoop.eb_light_game()
        self.advance_time_and_run(40)
        self.assertNotIn("0x118", self.sounds())
        self.advance_time_and_run(1)                     # 2,500 ticks (40.65 s) still lit
        self.assertIn("0x118", self.sounds())

    def test_no_extra_ball_speech_once_collected(self):
        self.start_game()
        self.validate()
        scoop = self.tron.features_by_name["scoop"]
        scoop.eb_light_game()
        self.advance_time_and_run(5)
        self.tron.collect_extra_ball()
        self.advance_time_and_run(40)
        self.assertNotIn("0x118", self.sounds())


class TestSlamTilt(BaseCase):

    def test_slam_ends_the_game(self):
        self.start_game()
        self.validate()
        tron = self.tron
        self.hit_and_release_switch("s_slam_tilt")
        self.advance_time_and_run(0.1)
        self.assertIn(24, [e["id"] for e in tron.trace.of("deff_start")])
        self.assertIn("0x018", self.sounds())
        before = self.score
        self.hit("s_left_slingshot")
        self.assertEqual(before, self.score)             # no scoring after a slam
        self.advance_time_and_run(6)                     # 218 + 93 ticks: reset
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(5)
        self.assertIsNone(self.machine.game)
        self.assertNotIn(38, [e["id"] for e in tron.trace.of("deff_start")])   # no match
