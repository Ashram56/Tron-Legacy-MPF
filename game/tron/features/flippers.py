"""Flipper buttons in play: flipper audits and INSTANT INFO (OS code, game_flow.md; not a rules mode).

- FUN_0002dcc0: each flipper button press while the flippers are live counts audit 0x2c LEFT / 0x2d
  RIGHT FLIPPER USED and stops the score refresh deff 14 (the ROM sees the right button first when both
  close together).
- FUN_0001b144 (every tick): while a flipper button is held and gf_state & 0x211 is 0, a counter runs;
  at 93 ticks (0x5d, ball not scored yet) or 468 ticks (0x1d4, ball scored) deff 27 INSTANT INFO starts.
  Releasing every button stops deff 27 and resets the counter.
"""
from tron.features import Feature

ORDER = 5
BUTTONS = (("s_right_flipper", 0x2d), ("s_left_flipper", 0x2c))
PRESS_TICKS = 2          # switch debounce + handler task: audit 33 ms after the press (traces/skill_shots_b)
RELEASE_TICKS = 4        # deff 27 stop 65 ms after the release (traces/skill_shots_b, bonus_skip)


class Flippers(Feature):
    name = "flippers"

    def __init__(self, os_):
        super().__init__(os_)
        self.count = 0
        self.shown = False
        sc = self.machine.switch_controller
        for name, audit in BUTTONS:
            if name in self.machine.switches:
                sc.add_switch_handler(name, (lambda a: lambda: self.pressed(a))(audit), state=1)
                sc.add_switch_handler(name, self.released, state=0)

    def held(self):
        return any(self.machine.switches[n].state for n, _ in BUTTONS if n in self.machine.switches)

    def pressed(self, audit):
        os_ = self.os
        if os_.state & 0x40:                             # high-score entry owns the buttons
            return
        if not os_.game:
            os_.after(PRESS_TICKS, lambda: os_.deff_stop(14))    # attract: the button also steps the pages
            return
        flippers_live = not os_.state & 0x205            # flippers off while tilted and at end of ball
        # one switch scan handles the right button before the left one
        os_.after(PRESS_TICKS + (0.05 if audit == 0x2c else 0), lambda: self._press(audit, flippers_live))
        if not os_.task_running("instant_info"):
            os_.task_start("instant_info", 1, self._tick)

    def _press(self, audit, flippers_live):
        if flippers_live:
            self.os.audit(audit)
        self.os.deff_stop(14)

    def _tick(self):
        os_ = self.os
        if not os_.game or not self.held():
            return
        if not os_.state & 0x211 and not os_.display.running(27) and not self.shown:
            self.count += 1
            if self.count >= (468 if os_.ball_scored else 93):
                self.count = 0
                self.shown = True
                os_.deff_start(27)
        os_.task_start("instant_info", 1, self._tick)

    def released(self):
        if self.held() or not self.os.game:
            return
        self.count = 0
        self.shown = False
        self.os.after(RELEASE_TICKS, lambda: not self.os.state & 0x211 and self.os.deff_stop(27))


feature = Flippers
