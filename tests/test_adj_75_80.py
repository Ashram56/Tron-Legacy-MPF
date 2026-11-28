"""adj 80 DISABLE DROP TARGETS (drop bank reset task 0x76, FUN_0100bdf4: no coil when the bank is disabled by the
adjustment, the switches are only re-read) and adj 75 ABORT ANIMATIONS (both flipper buttons, FUN_0100fb10)."""
from unittest import mock

from tests.test_adjustments import AdjCase


class TestAdj80(AdjCase):

    def _bank_down(self, adj):
        os_ = self.start_game()
        os_.adj[80] = adj
        targets = os_.features_by_name["tron_targets"]
        for sw in ("s_tron_t", "s_tron_r", "s_tron_o", "s_tron_n"):
            self.hit_switch_and_run(sw, 0.1)
        return os_, targets

    def test_80_off_pulses_the_reset_coil(self):
        os_, targets = self._bank_down(0)
        coil = self.machine.coils["c_drop_target_bank"]
        with mock.patch.object(type(coil), "pulse") as pulse:
            targets.drops_up = {1: 0, 2: 0, 3: 0, 4: 0}
            targets.bank_reset()
        self.assertTrue(pulse.called)

    def test_80_on_never_pulses_the_reset_coil(self):
        os_, targets = self._bank_down(1)
        coil = self.machine.coils["c_drop_target_bank"]
        with mock.patch.object(type(coil), "pulse") as pulse:
            targets.bank_reset()
            self.advance_time_and_run(2)
        self.assertFalse(pulse.called)


class TestAdj75(AdjCase):

    def _flip_both(self):
        self.hit_switch_and_run("s_left_flipper", 0.05)
        self.hit_switch_and_run("s_right_flipper", 0.05)

    def test_75_off_does_not_abort(self):
        os_ = self.start_game()
        os_.adj[75] = 0
        with mock.patch.object(os_.display, "show_running", return_value=True), \
                mock.patch.object(os_.display, "abort") as abort:
            self._flip_both()
        self.assertFalse(abort.called)

    def test_75_on_aborts_with_both_buttons(self):
        os_ = self.start_game()
        os_.adj[75] = 1
        with mock.patch.object(os_.display, "show_running", return_value=True), \
                mock.patch.object(os_.display, "abort") as abort:
            self._flip_both()
        abort.assert_called_with(1)

    def test_75_needs_a_show(self):
        os_ = self.start_game()
        os_.adj[75] = 2
        with mock.patch.object(os_.display, "show_running", return_value=False), \
                mock.patch.object(os_.display, "abort") as abort:
            self._flip_both()
        self.assertFalse(abort.called)
