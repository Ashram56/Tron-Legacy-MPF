"""Recognizer / Disc Battle and Disc Multiball paths the reference scenarios do not reach."""
from tests.tron_test import TronTestCase

TICK = 0.01626


class TestDiscRec(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")         # force switch: playfield valid
        self.advance_time_and_run(1)
        return self.tron

    @property
    def dmb(self):
        return self.tron.features_by_name["disc_multiball"]

    def test_arcade_awards_light_battle_and_start_multiball(self):
        os_ = self.start_game()
        self.assertEqual(100, os_.hook("arcade_recognizer_weight", 100))
        self.assertEqual(0, os_.hook("arcade_disc_weight", 25))
        for _ in range(5):                                    # silent hits, mask 0x32: 2 while C is lit
            if not os_.flag(0x22):
                self.assertTrue(os_.hook("arcade_recognizer"))
        self.assertTrue(os_.flag(0x22))
        self.assertFalse(os_.hook("recognizer_bank", 1, 53))  # battle lit: 1,000 only
        self.assertTrue(os_.display.show_running())           # deff 109 queued (task 0x9d)
        self.assertEqual(0x029, os_.base_music())
        self.assertFalse(self.tron.features_by_name["recognizer"].dbattle_light(False))   # already lit
        self.assertEqual(0, os_.hook("arcade_recognizer_weight", 100))
        self.assertEqual(25, os_.hook("arcade_disc_weight", 25))
        self.assertTrue(os_.hook("arcade_disc"))              # silent count-down
        self.assertEqual(5, os_.pd.dbattle_remaining)
        self.assertTrue(os_.hook("disc_battle", 1, True))     # type 1 counts 2
        self.assertEqual(3, os_.pd.dbattle_remaining)
        os_.pd.dbattle_remaining = 0
        self.assertFalse(os_.hook("disc_battle", 1, True))    # only a type with bit 1 starts it
        self.assertTrue(os_.hook("arcade_disc"))              # starts Disc Multiball
        self.assertTrue(os_.flag(0x24))
        self.assertFalse(os_.flag(0x22))
        self.assertEqual(2, os_.pd.dbattle_k)

    def test_end_of_ball_shows_total(self):
        os_ = self.start_game()
        self.assertTrue(os_.hook("dmb_start"))
        self.advance_time_and_run(1)
        self.dmb.ball_end()
        self.assertFalse(os_.flag(0x24))
        self.assertTrue(os_.display.running(51))
        self.assertGreater(self.dmb.ball_end_wait(), 200)

    def test_window_expires_without_total(self):
        os_ = self.start_game()
        os_.hook("dmb_start")
        self.advance_time_and_run(1)
        self.assertTrue(self.dmb.multiball_end())
        self.assertFalse(self.dmb.multiball_end())            # not running any more
        self.assertTrue(os_.task_running(0xad))
        self.advance_time_and_run(25)
        self.assertFalse(self.dmb.window_running())
        self.assertFalse(os_.display.running(51))
        self.assertFalse(self.dmb.disc_restart_autofire())

    def test_window_settings_and_cancel(self):
        os_ = self.start_game()
        os_.adj[70] = 4                                       # no window
        os_.hook("dmb_start")
        self.dmb.multiball_end()
        self.assertFalse(self.dmb.window_running())
        os_.adj[70] = 10
        os_.adj[71] = 0                                       # restart disabled
        os_.flag_set(0x24)
        os_.flag_set(0x25)
        self.dmb.multiball_end()
        self.assertTrue(self.dmb.window_running())
        self.assertFalse(self.dmb.disc_restart_autofire())
        self.assertFalse(self.dmb.window_running())
        os_.flag_set(0x24)
        os_.flag_set(0x25)
        self.dmb.multiball_end()
        os_.hook("dmb_cancel_restart_window")                 # another multiball starts
        self.assertFalse(self.dmb.window_running())

    def test_bank_follows_other_modes(self):
        os_ = self.start_game()
        rec = os_.features_by_name["recognizer"]
        self.assertTrue(rec.bank_wants_up())
        os_.register("portal_mb_flag37_set", lambda: True)    # Portal MB forces the bank down
        self.assertFalse(rec.bank_wants_up())

    def test_refused_while_tilted(self):
        os_ = self.start_game()
        os_.hook("dmb_start")
        self.dmb.multiball_end()                              # restart window open
        os_.state |= 0x200
        self.assertFalse(self.dmb.disc_restart_autofire())
        os_.flag_clear(0x24)
        self.assertFalse(os_.hook("dmb_start"))
        self.assertFalse(os_.flag(0x24))
        self.dmb.total = 100000
        self.assertFalse(self.dmb.show_total())
