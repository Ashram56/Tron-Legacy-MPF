"""A physical model of the playfield for the bench: four real balls, moved only by the coils and by the
player robot. MPF runs on its "virtual" platform (nothing moves by itself), so every ball the rules count
must be a ball this table holds: the bench can compare the two after every action.

Where a ball can be: the trough stack, the shooter lane, the VUK (Flynn's Arcade scoop), the playfield.
- trough kicker (coil 1): trough -> shooter lane;
- auto launch (coil 2) or the player's plunge: shooter lane -> playfield;
- VUK eject (coil 4): VUK -> playfield;
- drop target reset (coil 3): the TRON drop targets come back up (their switches open);
- 3-bank motor relay (coil 6): the Recognizer bank moves to its other end (up <-> down) while it runs.
"""

TROUGH = ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l")
DROPS = ("s_tron_t", "s_tron_r", "s_tron_o", "s_tron_n")
BALLS = 4
TROUGH_TO_SHOOTER = 0.3
LAUNCH_TO_PLAYFIELD = 0.6
VUK_TO_PLAYFIELD = 0.4
BANK_TRAVEL = 0.6


class Table:

    def __init__(self, test, drop_targets=True):
        self.t = test
        self.m = test.machine
        self.trough = BALLS
        self.shooter = 0
        self.vuk = 0
        self.pf = 0
        self.flight = 0                 # balls between two places (kicked, not arrived yet)
        self.drop_targets = drop_targets
        self.drops_down = set()
        self.bank_up = True
        self.bank_moving = False
        self.coil_pulses = {}           # coil name -> pulses seen
        self.launches = 0               # auto launches (coil 2)
        self._patch("c_trough_up_kicker", self.kick_trough)
        self._patch("c_auto_launch", self.launch)
        self._patch("c_video_game_eject", self.kick_vuk)
        self._patch("c_drop_target_bank", self.reset_drops)
        motor = self.m.coils["c_recognizer_3_bank_motor_relay"].hw_driver
        motor.enable = lambda *a, **k: self._bank_motor(True)
        motor.disable = lambda *a, **k: self._bank_motor(False)
        self._motor_on = False
        self.sw("s_3_bank_motor_up", True)
        self.update()

    def _patch(self, coil, fn):
        def pulse(*a, **k):
            self.coil_pulses[coil] = self.coil_pulses.get(coil, 0) + 1
            fn()
        self.m.coils[coil].hw_driver.pulse = pulse

    # ------------------------------------------------------------------ switches

    def sw(self, name, on):
        self.m.switch_controller.process_switch(name, 1 if on else 0, True)

    def is_on(self, name):
        return bool(self.m.switches[name].state)

    def update(self):
        for i, name in enumerate(TROUGH):
            if self.is_on(name) != (i < self.trough):
                self.sw(name, i < self.trough)
        if self.is_on("s_shooter_lane") != bool(self.shooter):
            self.sw("s_shooter_lane", self.shooter)
        if self.is_on("s_video_game_eject") != bool(self.vuk):
            self.sw("s_video_game_eject", self.vuk)

    def delay(self, seconds, fn):
        self.m.clock.schedule_once(lambda *a: fn(), seconds)

    # ------------------------------------------------------------------ coils

    def kick_trough(self):
        if not self.trough:
            return
        self.trough -= 1
        self.flight += 1
        self.update()
        self.sw("s_trough_jam", True)
        self.delay(.04, lambda: self.sw("s_trough_jam", False))

        def arrive():
            self.flight -= 1
            self.shooter += 1
            self.update()
        self.delay(TROUGH_TO_SHOOTER, arrive)

    def launch(self):
        """Coil 2, or the player's plunge."""
        if not self.shooter:
            return False
        self.launches += 1
        self.shooter -= 1
        self.flight += 1
        self.update()
        self.delay(LAUNCH_TO_PLAYFIELD, self._on_playfield)
        return True

    def kick_vuk(self):
        if not self.vuk:
            return
        self.vuk -= 1
        self.flight += 1
        self.update()
        self.delay(VUK_TO_PLAYFIELD, self._on_playfield)

    def _on_playfield(self):
        self.flight -= 1
        self.pf += 1

    def reset_drops(self):
        for name in list(self.drops_down):
            self.sw(name, False)
        self.drops_down.clear()

    def _bank_motor(self, on):
        self._motor_on = on
        if on and not self.bank_moving:
            self.bank_moving = True
            self.sw("s_3_bank_motor_up", False)
            self.sw("s_3_bank_motor_dn", False)
            self.delay(BANK_TRAVEL, self._bank_arrive)

    def _bank_arrive(self):
        self.bank_moving = False
        self.bank_up = not self.bank_up
        self.sw("s_3_bank_motor_up" if self.bank_up else "s_3_bank_motor_dn", True)
        if self._motor_on:                      # still driven: it goes on to the other end
            self._bank_motor(True)

    # ------------------------------------------------------------------ the ball on the playfield

    def hit(self, name, hold=0.03):
        """A ball on the playfield closes a switch for a moment. A TRON drop target stays down."""
        if self.drop_targets and name in DROPS:
            if name in self.drops_down:
                return False                    # already down: the ball passes over it
            self.drops_down.add(name)
            self.sw(name, True)
            return True
        self.sw(name, True)
        self.delay(hold, lambda: self.sw(name, False))
        return True

    def drain(self):
        assert self.pf > 0, "no ball on the playfield to drain"
        self.pf -= 1
        self.trough += 1
        self.update()

    def to_vuk(self):
        assert self.pf > 0, "no ball on the playfield for the VUK"
        if self.vuk:
            return False                        # the scoop holds a ball: this one bounces out
        self.pf -= 1
        self.vuk += 1
        self.update()
        return True

    # ------------------------------------------------------------------ counts

    @property
    def out(self):
        """Balls out of the trough."""
        return BALLS - self.trough

    def total(self):
        return self.trough + self.shooter + self.vuk + self.pf + self.flight

    def __repr__(self):
        return "Table(trough={}, shooter={}, vuk={}, pf={}, flight={})".format(
            self.trough, self.shooter, self.vuk, self.pf, self.flight)
