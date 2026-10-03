"""Desktop / MPF Monitor only (hw_virtual.yaml overlay): the trough's balls roll toward the eject end.

MPF's smart_virtual platform takes a ball out of the trough by clearing the first active ball switch
(s_trough_1_r, the eject end) and adds one on the first free switch, so the trough switches never show the
real trough's behaviour: after an eject the remaining balls roll down to switch 1 (R), and a drained ball
lands behind them. Here, a moment after any trough switch changes, the balls in the trough are packed onto
switches 1 (R), 2, 3, 4 (L) in that order. The ball count never changes, so MPF's trough counting is not
disturbed. The rules code is unchanged; the unit tests and scenarios do not load this overlay.
"""
from mpf.core.custom_code import CustomCode

TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")     # eject end first
ROLL_MS = 150


class VirtualTrough(CustomCode):

    def on_load(self):
        self.machine.events.add_handler("init_phase_4", self._start)

    def _start(self, **kwargs):
        del kwargs
        for name in TROUGH:
            for state in (0, 1):
                self.machine.switch_controller.add_switch_handler(name, self._changed, state=state)

    def _changed(self):
        self.delay.reset(ms=ROLL_MS, callback=self._roll, name="roll")

    def _roll(self):
        controller = self.machine.switch_controller
        switches = [self.machine.switches[name] for name in TROUGH]
        balls = sum(1 for switch in switches if controller.is_active(switch))
        for position, switch in enumerate(switches):
            wanted = position < balls
            if controller.is_active(switch) != wanted:
                controller.process_switch_obj(switch, int(wanted), logical=True)
