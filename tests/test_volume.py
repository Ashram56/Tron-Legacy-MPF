"""The master volume keys (coin-door MINUS / PLUS outside the service menu, FUN_0000fc28 cases 2 and 4)."""
from tests.test_adjustments import AdjCase


class TestVolume(AdjCase):

    def press(self, name):
        self.hit_and_release_switch(name)
        self.advance_time_and_run(0.3)

    def test_first_press_shows_the_display_then_each_press_changes_the_level_by_one(self):
        os_ = self.tron
        self.assertEqual(0x28, os_.volume)
        self.press("s_service_minus")
        self.assertEqual(2, os_.display.fg)
        self.assertEqual(0x28, os_.volume)                       # the first press only shows the display
        self.press("s_service_minus")
        self.assertEqual(0x27, os_.volume)
        self.press("s_service_plus")
        self.press("s_service_plus")
        self.assertEqual(0x29, os_.volume)
        self.assertAlmostEqual(0x29 / 0x3f, self.machine.variables.get_machine_var("master_volume"))

    def test_limits(self):
        os_ = self.tron
        os_.set_volume(0x3f)
        self.press("s_service_plus")
        self.press("s_service_plus")
        self.assertEqual(0x3f, os_.volume)
        os_.set_volume(0)
        self.press("s_service_minus")
        self.assertEqual(0, os_.volume)
