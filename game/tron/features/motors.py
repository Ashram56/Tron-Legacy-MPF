"""The playfield motors the rules drive, and the operator switches that turn them off.

- Spinning disc: rule_disc_motor [0x010066c0], re-evaluated with the lamp rules. In normal play with the
  playfield valid the disc spins while the Disc Battle can progress, the Quorra add-a-ball state is 2, Disc
  Multiball wants the disc, Portal Multiball runs (flag 0x37), the Sea of Simulation state is 2 or End of Line
  runs: task 0xa8 turns on the motor relay (coil 30) and the motor power (coil 5) [0x010064c4]. Otherwise
  disc_motor_stop [0x010065ac] turns both off. Adj 77 DISABLE DISC MOTOR = YES: the motor is never driven
  (disc_motor_disabled_adj77 [0x010064a8] returns from every one of these functions).
- Recognizer 3-bank: the bank goes up or down as recognizer.bank_motor_rule decides [0x0102227c]; the OS motor
  driver runs the 3-bank motor relay (coil 6) until the bank's up / down switch (sw 53 / 52) closes. Adj 76
  DISABLE RECOGNIZER 3-BANK MOTOR = YES: the driver is off (the adjustment is the motor object's enable
  parameter, inferred from the OS motor-driver objects).
"""
from tron.features import Feature

ORDER = 90
DISC_COILS = ("c_disc_motor_relay", "c_disc_motor_power")
BANK_COIL = "c_recognizer_3_bank_motor_relay"


class Motors(Feature):
    name = "motors"
    HOOKS = ("tilt",)

    def __init__(self, os_):
        super().__init__(os_)
        self.disc_on = False
        self.bank_on = False
        self.machine.events.add_handler("tron_rules_refresh", self.refresh)
        for switch in ("s_3_bank_motor_up", "s_3_bank_motor_dn"):
            for state in (0, 1):
                self.machine.switch_controller.add_switch_handler(switch, self.bank_drive, state=state)

    # ------------------------------------------------------------------ spinning disc

    def disc_wanted(self):
        os_ = self.os
        if not os_.game or os_.state & 0x31e or not os_.pf_valid:
            return False
        return bool(os_.hook("dbattle_can_progress") or os_.hook("quorra_add_ball_state") == 2
                    or os_.hook("dmb_disc_is_target") or os_.flag(0x37) or os_.hook("sos_bank_state") == 2
                    or os_.hook("eol_running"))

    def refresh(self, **kwargs):
        if self.os.adj_value(77) != 1:
            self.set_disc(self.disc_wanted())
        self.bank_drive()

    def set_disc(self, on):
        if on == self.disc_on:
            return
        self.disc_on = on
        for name in DISC_COILS:
            coil = self.machine.coils[name]
            coil.enable() if on else coil.disable()

    def tilt(self):
        if self.os.adj_value(77) != 1:
            self.set_disc(False)

    # ------------------------------------------------------------------ recognizer 3-bank

    def bank_drive(self, **kwargs):
        """Run the 3-bank motor until the bank reaches the position the recognizer rule wants."""
        rec = self.os.features_by_name.get("recognizer")
        sc = self.machine.switch_controller
        want_up = getattr(rec, "bank_up", True)
        there = sc.is_active(self.machine.switches["s_3_bank_motor_up" if want_up else "s_3_bank_motor_dn"])
        on = bool(self.os.game) and self.os.adj_value(76) != 1 and not there
        if on != self.bank_on:
            self.bank_on = on
            coil = self.machine.coils[BANK_COIL]
            coil.enable() if on else coil.disable()


feature = Motors
