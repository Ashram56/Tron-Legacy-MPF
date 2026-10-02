"""Light Cycle and Quorra Multiball paths the reference scenarios do not reach."""
from tests.tron_test import TronTestCase

TICK = 0.01626


class TestLightCycleQuorra(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")         # force switch: playfield valid
        self.advance_time_and_run(1)
        return self.tron

    @property
    def lc(self):
        return self.tron.features_by_name["light_cycle"]

    @property
    def quorra(self):
        return self.tron.features_by_name["quorra"]

    def test_lc_arcade_refusals_and_grace(self):
        os_ = self.start_game()
        self.assertEqual(100, self.lc.arcade_light_cycle_weight(100))
        self.assertTrue(self.lc.arcade_light_cycle())          # first open shot: left orbit
        self.assertEqual(0x01, os_.pd.lc_collected)
        os_.flag_set(0x24)                                    # Disc Multiball running: no progress, no start
        self.assertFalse(self.lc.arcade_light_cycle())
        self.assertEqual(0, self.lc.arcade_light_cycle_weight(100))
        os_.flag_clear(0x24)
        self.assertFalse(self.lc.light_cycle_vuk())           # VUK not lit
        multiball_start = os_.multiball_start
        os_.multiball_start = lambda *args: False             # refused (e.g. tilted)
        self.assertFalse(self.lc.mb_start(False, False))
        os_.multiball_start = multiball_start
        self.assertTrue(self.lc.mb_start(False, False))
        self.assertFalse(self.lc.mb_start(False, False))      # already running
        self.assertFalse(self.lc.light_cycle_mb_shot(0x10))   # no chain lights this shot
        self.assertTrue(self.lc.light_cycle_mb_shot(0x80))    # chain B Jackpot: Super lit on 0x48
        self.advance_time_and_run(316 * TICK)                 # timer out: B home, 0x48 in its grace
        self.assertEqual((0x80, 0x48), (self.lc.b.lit, self.lc.b.prev))
        self.assertTrue(self.lc.light_cycle_mb_shot(0x08))    # Super from the grace
        self.assertEqual(750000 + 350000 + 150000, self.lc.total)

    def test_lc_resume_end_window_and_end_of_ball(self):
        os_ = self.start_game()
        self.assertTrue(self.lc.mb_start(False, False))
        self.advance_time_and_run(1)
        self.assertFalse(self.lc.lc_mb_resume_in_end_window())   # not in the end window
        self.lc.multiball_end()
        self.assertFalse(os_.flag(0x2b))
        self.assertTrue(os_.task_running(0xb8))
        self.assertTrue(os_.hook("lc_mb_resume_in_end_window"))  # Quorra start / add-a-ball
        self.assertTrue(os_.flag(0x2b))
        self.lc.ball_end()
        self.assertFalse(os_.flag(0x2b))
        self.assertTrue(os_.display.running(90))
        self.assertGreater(self.lc.ball_end_wait(), 0)
        self.lc.total = 0
        os_.task_kill(0x52)
        self.lc.show_total()                                  # nothing scored: no total
        self.assertIsNone(self.lc.ball_end_wait())

    def test_quorra_arcade_refusals_resume_and_end_of_ball(self):
        os_ = self.start_game()
        self.assertEqual(50, self.quorra.arcade_quorra_weight(50))
        self.assertTrue(self.quorra.arcade_quorra())
        self.assertEqual(1, os_.pd.quorra_progress)
        self.assertFalse(self.quorra.quorra_vuk())            # VUK not lit
        multiball_start = os_.multiball_start
        os_.multiball_start = lambda *args: False
        self.assertFalse(self.quorra.mb_start(False, False))
        os_.multiball_start = multiball_start
        self.assertTrue(self.quorra.mb_start(False, False))
        self.assertFalse(self.quorra.mb_start(False, False))  # already running
        self.assertFalse(self.quorra.quorra_vuk())            # running: the VUK does nothing
        self.assertEqual(0, self.quorra.arcade_quorra_weight(50))
        self.assertFalse(self.quorra.quorra_super_jackpots(0x01))
        self.advance_time_and_run(1)
        self.quorra.multiball_end()
        self.assertTrue(os_.task_running(0xb3))
        self.assertTrue(os_.hook("quorra_mb_resume_in_end_window"))
        self.assertTrue(os_.flag(0x29))
        self.assertFalse(os_.task_running(0xb3))
        self.quorra.ball_end()
        self.assertFalse(os_.flag(0x29))
        self.assertTrue(os_.display.running(70))
        self.quorra.total = 0
        os_.task_kill(0x50)
        self.quorra.show_total()
        self.assertIsNone(self.quorra.ball_end_wait())
