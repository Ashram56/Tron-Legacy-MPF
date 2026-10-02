"""CLU / GEM hurry-up and ZUSE fast scoring paths the reference scenarios do not reach."""
from tests.tron_test import TronTestCase

TICK = 0.01626


class TestHurryUps(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")         # force switch: playfield valid
        self.advance_time_and_run(1)
        return self.tron

    def feature(self, name):
        return self.tron.features_by_name[name]

    def run_out(self, clock, limit=120):
        """Advance until the countdown and its grace are over."""
        for _ in range(limit):
            if not clock.running():
                return
            self.advance_time_and_run(1)
        self.fail("countdown still running")

    # ------------------------------------------------------------------ CLU

    def test_clu_lanes_rotate_and_light_the_vuk(self):
        os_ = self.start_game()
        clu = self.feature("clu")
        self.assertTrue(os_.hook("clu_letter", 0))
        self.assertTrue(os_.hook("clu_letter", 0))            # already lit: 1,000
        self.assertEqual(1, os_.pd.clu_lane_bits)
        self.hit_and_release_switch("s_right_flipper")        # toward U: C -> L
        self.assertEqual(2, os_.pd.clu_lane_bits)
        self.hit_and_release_switch("s_left_flipper")         # toward C: L -> C
        self.assertEqual(1, os_.pd.clu_lane_bits)
        os_.pd.clu_lane_bits = 4
        clu.rotate_toward_u()                                 # U wraps to C
        self.assertEqual(1, os_.pd.clu_lane_bits)
        clu.rotate_toward_c()                                 # C wraps to U
        self.assertEqual(4, os_.pd.clu_lane_bits)
        os_.hook("clu_letter", 0)
        os_.hook("clu_letter", 1)                             # set complete: lights the VUK
        self.assertTrue(os_.hook("vuk_lit_test", 0x10))
        self.assertEqual(1, os_.pd.clu_lights)
        os_.flag_set(0x34)                                    # Sea of Simulation: lanes off
        self.assertFalse(clu.lanes_active())
        self.assertFalse(os_.hook("clu_letter", 2))
        self.assertFalse(os_.hook("arcade_clu"))
        clu.rotate_toward_c()                                 # ignored
        self.assertEqual(0, os_.hook("arcade_clu_weight", 50))
        os_.flag_clear(0x34)
        self.assertEqual(50, os_.hook("arcade_clu_weight", 50))
        self.assertTrue(os_.hook("arcade_clu"))               # one silent completion
        self.assertEqual(2, os_.pd.clu_lane_completions)

    def test_clu_hurryup_all_shots_more_time_and_total(self):
        os_ = self.start_game()
        clu = self.feature("clu")
        os_.flag_set(0x27)                                    # a multiball: no start
        self.assertFalse(clu.start())
        os_.flag_clear(0x27)
        os_.task_start(0xad, 100)                             # the Disc restart window keeps the wizard modes off
        self.assertTrue(clu.start_allowed(True, True))
        os_.task_kill(0xad)
        self.assertFalse(clu.start_allowed(True, False))
        self.assertFalse(os_.hook("clu_vuk"))                 # not lit at the VUK
        os_.hook("vuk_lit_add", 0x10, False)
        self.assertTrue(os_.hook("clu_vuk"))
        self.assertFalse(os_.hook("vuk_lit_test", 0x10))
        self.advance_time_and_run(8)
        self.assertTrue(os_.hook("timed_feature_running"))
        self.assertTrue(os_.hook("more_time"))
        self.assertEqual(40, clu.clock.seconds)
        self.assertTrue(os_.hook("clu_hurryup_awards", 0x001))
        self.assertFalse(os_.hook("clu_hurryup_awards", 0x001))   # collected already
        os_.hook("clu_letter", 0)
        os_.hook("clu_letter", 1)
        os_.hook("clu_letter", 2)                             # a lane set collects the next lit shot (0x004)
        self.assertEqual(0x180, clu.shots)
        os_.hook("clu_hurryup_awards", 0x080)
        os_.hook("clu_hurryup_awards", 0x100)                 # all four: ends with the total
        self.assertFalse(clu.clock.running())
        self.assertEqual(1, os_.pd.clu_completed_count)
        self.assertGreater(clu.ball_end_wait(), 2)
        self.advance_time_and_run(4)
        self.assertIsNone(clu.ball_end_wait())
        self.assertFalse(clu.end_now())
        self.assertIsNone(clu.more_time())

    def test_clu_ends_at_ball_end_and_times_out(self):
        os_ = self.start_game()
        clu = self.feature("clu")
        self.assertTrue(clu.start())
        self.run_out(clu.clock)
        self.assertEqual(0, clu.clock.seconds)
        self.assertTrue(clu.start())
        clu.total = 0                                         # nothing scored: no total
        os_.hook("ball_end")
        self.assertFalse(os_.task_running(0x53))

    # ------------------------------------------------------------------ GEM

    def test_gem_qualify_spin_more_time_ball_end(self):
        os_ = self.start_game()
        gem = self.feature("gem")
        self.assertEqual(20, os_.hook("arcade_gem_weight", 20))
        self.assertTrue(os_.hook("arcade_gem"))               # ADV. GEM: a silent loop
        os_.hook("gem_qualify")
        os_.hook("gem_qualify")                               # third loop starts it
        self.assertTrue(gem.clock.running())
        self.assertFalse(gem.start())                         # already running
        self.assertFalse(os_.hook("gem_qualify"))
        self.assertEqual(0, os_.hook("arcade_gem_weight", 20))
        gem.clock.seconds = 3
        self.assertTrue(os_.hook("gem_spin"))                 # at least 5
        self.assertEqual(5, gem.clock.seconds)
        self.assertTrue(gem.more_time())
        self.assertEqual(40, gem.clock.seconds)
        os_.hook("ball_end")
        self.assertFalse(gem.clock.running())
        self.assertTrue(os_.task_running(0x54))
        self.assertGreater(gem.ball_end_wait(), 2)
        self.assertFalse(os_.hook("gem_spin"))
        self.assertFalse(gem.end_now())
        self.assertIsNone(gem.more_time())

    def test_gem_tilt_state_shows_no_total(self):
        os_ = self.start_game()
        gem = self.feature("gem")
        os_.pd.gem_progress = 2
        os_.hook("gem_qualify")
        os_.state |= 0x200
        gem.end_now()
        self.assertFalse(os_.task_running(0x54))

    # ------------------------------------------------------------------ ZUSE

    def test_zuse_letters_lockout_and_start(self):
        os_ = self.start_game()
        zuse = self.feature("zuse")
        self.assertEqual(30, os_.hook("arcade_zuse_weight", 30))
        os_.hook("zuse_letter", 0)
        score = os_.game.player.score
        self.assertTrue(os_.hook("zuse_letter", 0))           # repeat letter: 10,000
        self.advance_time_and_run(0.1)
        self.assertEqual(score + 10000, os_.game.player.score)
        os_.task_start(0x4c, 10)
        self.assertFalse(os_.hook("zuse_letter", 1))          # lockout after a completion
        os_.task_kill(0x4c)
        os_.hook("zuse_letter", 1)
        os_.hook("zuse_letter", 2)
        os_.hook("zuse_letter", 3)                            # completes the set: fast scoring
        self.assertTrue(zuse.clock.running())
        self.assertEqual(0, os_.hook("arcade_zuse_weight", 30))
        self.assertFalse(os_.hook("arcade_zuse"))
        self.assertTrue(os_.hook("zuse_letter", 0))           # blocked while running: 5,000
        os_.hook("zuse_target_hit", 4)                        # during the intro: no pop-up deff
        self.assertFalse(os_.display.running(96))
        self.assertTrue(os_.hook("more_time"))
        self.assertEqual(45, zuse.clock.seconds)
        os_.hook("tilt")
        self.assertFalse(zuse.clock.running())
        self.assertFalse(zuse.end_now())
        self.assertIsNone(zuse.more_time())
        self.assertEqual(0, zuse.value_raise())
        self.assertEqual(0, zuse.add_time(10))

    def test_zuse_queue_pause_grace_and_total(self):
        os_ = self.start_game()
        zuse = self.feature("zuse")
        self.assertTrue(os_.hook("arcade_zuse"))              # 1st completion starts it
        self.assertTrue(zuse.clock.running())
        self.advance_time_and_run(6)
        zuse.zuse_target_hit(4)
        zuse.zuse_target_hit(4)
        zuse.zuse_target_hit(4)                               # two queued in one tick: one waits for task 0x80
        self.advance_time_and_run(0.1)
        self.assertEqual(0, zuse.queue)
        os_.task_start(0x40, 156)                             # a pop bumper pauses the count
        self.advance_time_and_run(1)
        zuse._show_total()
        zuse._show_total()                                    # queued once (task 0x55)
        os_.display.cancel(0x55)
        os_.task_kill(0x55)
        zuse.clock.seconds = 1                                # the pause ends ~1.5 s from now, then 0, then the grace
        self.advance_time_and_run(4.5)
        self.assertTrue(os_.task_running(0x5b))               # grace
        self.assertEqual(0, zuse.value_raise())
        self.run_out(zuse.clock)
        self.assertTrue(os_.display.running(99))              # the total once the grace is over
        self.assertIsNone(zuse.ball_end_wait())               # task 0x55 is done
        os_.hook("ball_end")

    def test_zuse_no_total_in_tilt(self):
        os_ = self.start_game()
        zuse = self.feature("zuse")
        os_.hook("arcade_zuse")
        os_.state |= 0x200
        zuse.end_now()
        self.assertFalse(os_.task_running(0x55))

    # ------------------------------------------------------------------ shared display / spinner pieces

    def test_spinner_deff_stays_up_after_the_last_spin(self):
        os_ = self.start_game()
        self.hit_and_release_switch("s_left_spinner")
        self.advance_time_and_run(0.5)
        self.hit_and_release_switch("s_left_spinner")         # a later spin of the session extends deff 41
        self.advance_time_and_run(3)
        os_.deff_start(42)
        self.advance_time_and_run(1.0)
        os_.display.extend(42)                                # deff 42 (1.68 s) runs its length again from here
        self.advance_time_and_run(1.4)
        self.assertTrue(os_.display.running(42))
        self.advance_time_and_run(0.5)
        self.assertFalse(os_.display.running(42))
        os_.display.extend(42)                                # not running: nothing to extend
        self.assertFalse(os_.display.running(42))

    def test_hold_of_a_replaced_deff_does_nothing(self):
        os_ = self.start_game()
        os_.deff_start(73)
        os_.deff_start(74)                                    # higher priority: 73 is gone before its hold
        self.advance_time_and_run(3)
        self.assertFalse(os_.display.fg_hold)
