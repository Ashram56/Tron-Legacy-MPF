"""Unit tests for combos (combos.md) and the TRON targets / timed awards (tron_targets.md): the parts the
reference scenarios do not reach."""
from tests.tron_test import TronTestCase

TRON = ("s_tron_t", "s_tron_r", "s_tron_o", "s_tron_n")


class GameCase(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_left_bumper")       # BUMPERS -> SPINNERS
        self.advance_time_and_run(3)

    def hit(self, name, wait=0.3):
        self.hit_and_release_switch(name)
        self.advance_time_and_run(wait)

    def spell_tron(self):
        for name in TRON:
            self.hit(name)

    @property
    def score(self):
        return self.machine.game.player.score

    @property
    def tt(self):
        return self.tron.features_by_name["tron_targets"]

    @property
    def combos(self):
        return self.tron.features_by_name["combos"]


class TestTronAwards(GameCase):

    def test_awards_items_and_nothing_lit(self):
        self.start_game()
        pd = self.tron.pd
        self.assertEqual(4, pd.tron_lit)                       # the pop rotated BUMPERS -> SPINNERS
        self.hit("s_tron_t")
        self.hit("s_tron_t")                                   # drop still down: ignored
        self.assertEqual(1, pd.tron_letters)
        self.spell_tron()                                      # T again counts: the bank was reset
        self.assertEqual(4, pd.tron_running)
        self.assertTrue(self.tron.task_running(200))
        self.assertEqual(1, pd.tron_lit)                       # rotate(running 4, lit 0) -> DS
        self.assertTrue(self.tron.hook("timed_feature_running"))
        self.spell_tron()                                      # DS: the completion itself is doubled
        self.assertEqual(5, pd.tron_running)
        self.assertEqual(2, pd.tron_lit)
        before = self.score
        self.hit("s_left_slingshot")
        self.assertEqual(880, self.score - before)             # 440 x 2
        self.spell_tron()                                      # BUMPERS: all three started
        self.assertEqual(7, pd.tron_running)
        self.assertEqual(1, self.tron.audits.get(0x79))        # TRON item collected
        self.assertEqual(0, pd.tron_started_set)
        self.assertEqual(0, pd.tron_lit)
        before = self.score
        self.spell_tron()                                      # nothing lit: 500,000 instead
        self.assertEqual(4, pd.tron_completions)
        letters = 3 * 10030 + 30
        self.assertEqual(2 * (letters + 500000 + 100000), self.score - before)
        self.advance_time_and_run(40)
        self.assertEqual(0, pd.tron_running)
        self.assertIn(pd.tron_lit, (1, 2, 4))                  # nothing lit: the first award to end

    def test_timer_quirk_more_time_and_pause(self):
        self.start_game()
        tt = self.tt
        self.spell_tron()                                      # SPINNERS
        self.advance_time_and_run(4)
        self.assertEqual(26, tt.secs[4])
        self.spell_tron()                                      # DS: both counters now drop 2 per second
        self.advance_time_and_run(5)
        self.assertEqual(20, tt.secs[1])
        self.tron.hook("more_time")
        self.assertEqual((30, 30), (tt.secs[1], tt.secs[4]))
        # a Sea of Simulation start show (task 0xa0) pauses the clocks
        self.tron.show(0xa0, 107)
        self.advance_time_and_run(1.5)
        self.assertEqual(30, tt.secs[1])
        self.advance_time_and_run(16)
        self.assertEqual(0, tt.secs[1])
        self.assertFalse(self.tron.task_running(0xc6))
        self.advance_time_and_run(1)                           # SPINNERS's task ends at its own next step
        self.assertEqual(0, self.tron.pd.tron_running)
        self.assertIsNone(self.tron.hook("timed_feature_running"))
        self.assertEqual(2, self.tron.pd.tron_lit)             # BUMPERS stays lit (rotate(5, 0) = 2)


class TestCombos(GameCase):

    def test_named_chain_multiball_block_and_jackpot(self):
        self.start_game()
        self.tron.poke(0x2111608, 600000)
        self.assertEqual(600000, self.tron.hook("eol_combo_jackpot_value"))
        sw = self.tron.switches
        before = self.score
        sw.on_left_ramp()                                      # left ramp opens 0x05
        sw.shot_left_inner_loop()                              # LAST ISO (kept)
        sw.on_right_ramp()                                     # LIGHT CYCLE (kept)
        self.advance_time_and_run(0.1)
        self.assertEqual(600000 + 400000 + 500000, self.tron.hook("eol_combo_jackpot_value"))
        self.assertEqual(3, self.combos.count)
        self.assertEqual(1, self.tron.audits.get(0x7c))
        self.assertEqual(1, self.tron.audits.get(0x7e))
        self.assertTrue(self.tron.hook("combo_lit", 5))
        self.tron.flag_set(0x27)                               # a multiball: the open window still scores
        sw.shot_right_orbit()                                  # LIGHT RUNNER, no new window
        self.assertEqual(1, self.tron.audits.get(0x7f))
        self.assertFalse(self.tron.task_running(0xcd))
        self.advance_time_and_run(0.1)
        self.assertNotIn(159, [r[1] for r in self.tron.rules if r[3]])
        combos = 250000 + 300000 + 350000
        self.assertGreaterEqual(self.score - before, combos)
        self.tron.flag_clear(0x27)
        sw.on_left_ramp()
        self.advance_time_and_run(6)                           # the window: 315 ticks, then 0xce
        self.assertFalse(self.tron.task_running(0xcd))
        self.assertTrue(self.tron.task_running(0xce))
        self.advance_time_and_run(2.1)
        self.assertFalse(self.combos.window_running())
