from tests.tron_test import TronTestCase


class TestBoot(TronTestCase):

    def test_game_start_plunge_drain(self):
        self.fill_trough()
        self.assertModeRunning("attract")
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertModeRunning("game")
        self.assertEqual(1, self.machine.game.player.ball)
        self.assertSwitchState("s_shooter_lane", 1)
        self.release_switch_and_run("s_shooter_lane", 1)      # plunge
        self.hit_and_release_switch("s_zen_rollover")         # force switch: playfield valid
        self.advance_time_and_run(1)
        self.assertTrue(self.tron.pf_valid)
        self.assertEqual(42000 + 1090, self.machine.game.player.score)    # ZEN charge + switch score
