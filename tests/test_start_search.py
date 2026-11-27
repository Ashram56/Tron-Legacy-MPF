"""START with a ball missing: the ROM's start ball search (task_ball_search [0x0001f4a0], FUN_0001f6fc [0x0001f6fc])."""
from tests.tron_test import TronTestCase


class StartSearchTest(TronTestCase):
    def three_balls(self):
        for name in ("s_trough_1_r", "s_trough_2", "s_trough_3"):
            self.machine.switch_controller.process_switch(name, 1, True)
        self.advance_time_and_run(2)

    def test_full_trough_starts_at_once(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(1)
        self.assertIsNotNone(self.machine.game)

    def test_missing_ball_runs_the_search_then_starts(self):
        self.three_balls()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(1)
        self.assertIsNone(self.machine.game)                      # refused: FUN_0001f6fc
        self.assertTrue(self.tron.task_running(0x2b))
        self.assertTrue(self.tron.display.running(11))         # deff 11 LOCATING PINBALLS
        self.advance_time_and_run(30)                             # 4 rounds of 52 x 6 ticks
        self.assertFalse(self.tron.task_running(0x2b))
        self.assertFalse(self.tron.display.running(11))
        self.assertTrue(self.tron.flag(0xb))                   # fewer balls than recorded
        self.assertEqual(self.tron.audits[0x25], 4)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(1)
        self.assertIsNotNone(self.machine.game)                   # recorded count = 3: the start goes ahead
        self.assertFalse(self.tron.flag(0xb))
        self.assertEqual(self.tron.audits[0x27], 1)


    def test_held_start_during_the_search_asks_for_deff_39_but_deff_11_keeps_the_display(self):
        """FUN_00019f20 calls deff_start(0x27) after 62 held ticks; deff 11 (priority 224) is on screen for the whole search and deff 39 has
        priority 80 (assets/rom_data/deffs/deffs.json), so the ROM's own display rule refuses it."""
        self.tron.adj.override(46, 1)
        self.three_balls()
        self.hit_switch_and_run("s_start_button", 0.5)
        self.assertTrue(self.tron.task_running(0x3b))               # task 0x3b times the hold while the search runs
        self.advance_time_and_run(0.6)                              # 62 ticks (1.008 s) held
        self.assertFalse(self.tron.task_running(0x3b))
        self.assertTrue(self.tron.display.running(11))
        self.assertFalse(self.tron.display.running(39))
        self.release_switch_and_run("s_start_button", 0.1)
        self.advance_time_and_run(30)                               # the search ends
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(0.1)
        self.assertIsNotNone(self.machine.game)
        self.assertFalse(self.tron.flag(0xf))                       # no deff 39 was running
        self.advance_time_and_run(3)

    def test_full_trough_start_never_shows_competition_ready(self):
        self.tron.adj.override(46, 1)
        self.fill_trough()
        self.hit_switch_and_run("s_start_button", 1.5)
        self.assertFalse(self.tron.display.running(39))
