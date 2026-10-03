"""The desktop / MPF Monitor overlay (config.yaml + hw_virtual.yaml): smart_virtual with a full trough at
power-on, trough ejects that reach the shooter lane, and trough switches that shift like the real trough."""
from tests.tron_test import TronTestCase

TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")


class TestHwVirtual(TronTestCase):

    def get_config_file(self):
        return "../../tests/machine_virtual.yaml"     # relative to game/config

    def get_platform(self):
        return False                                  # the overlay's own platform

    def trough(self):
        return [self.machine.switches[name].state for name in TROUGH]

    def test_trough_eject_and_shift(self):
        self.assertEqual("<Platform.SmartVirtual>", repr(self.machine.default_platform))
        self.advance_time_and_run(1)
        self.assertEqual([1, 1, 1, 1], self.trough())                 # starts full
        self.assertEqual(4, self.machine.ball_devices["bd_trough"].balls)
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.assertModeRunning("game")
        self.assertSwitchState("s_shooter_lane", 1)
        self.assertEqual([1, 1, 1, 0], self.trough())                 # the balls rolled down
        self.assertEqual(3, self.machine.ball_devices["bd_trough"].balls)
