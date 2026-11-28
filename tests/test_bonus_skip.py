"""Bonus skip (bonus.md 5.4, deff 25 [0x01001374]): the deff polls both flipper inputs every tick, so both
buttons down break the count at once, not at the next line boundary."""
from tests.test_combos_tron import GameCase


class TestBonusSkip(GameCase):

    def run_bonus(self, hold_after_ticks):
        self.start_game()
        bonus = self.tron.features_by_name["bonus"]
        self.tron.pd.bonus_x = 10
        done = []
        bonus.run(done.append)
        self.advance_time_and_run(hold_after_ticks * 0.0163)
        self.hit_switch_and_run("s_left_flipper", 0)
        self.hit_switch_and_run("s_right_flipper", 0)
        self.advance_time_and_run(0.05)                       # 3 ticks
        return bonus, done

    def test_both_flippers_skip_mid_line(self):
        bonus, done = self.run_bonus(30)                      # 9 ticks into line 2 (lines are 21 ticks)
        self.assertEqual(3, bonus.shown["screen"])            # TOTAL BONUS already, not at the next boundary
        self.advance_time_and_run(1.5)
        self.assertEqual(1, len(done))
        self.assertEqual(50000 * 10, done[0])

    def test_no_skip_with_one_flipper(self):
        self.start_game()
        bonus = self.tron.features_by_name["bonus"]
        self.tron.pd.bonus_x = 10
        done = []
        bonus.run(done.append)
        self.hit_switch_and_run("s_left_flipper", 0)
        self.advance_time_and_run(0.5)
        self.assertNotEqual(3, bonus.shown["screen"])
