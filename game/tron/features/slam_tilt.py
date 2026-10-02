"""Slam tilt (game_flow.md 5.3, slam_tilt [0x00023e40], slam_reset_task [0x00023e18]).

The slam switch in a game: the game is lost. Flippers off, every mode stops (event 0x54), deff 24
"SLAM TILT", leff 12, sound 0x018; task 0x39 then resets the machine after 218 + 93 ticks. The reset is
modelled as the end of the game without the game-over sequence (no bonus, no match), back to attract.
"""
from tron.features import Feature
from tron.os_layer import ST_TILT

ORDER = 7
SLAM_RESET_TICKS = 0xda + 0x5d


class SlamTilt(Feature):
    name = "slam_tilt"
    HOOKS = ("slammed",)

    def __init__(self, os_):
        super().__init__(os_)
        self.slam = False
        if "s_slam_tilt" in self.machine.switches:
            self.machine.switch_controller.add_switch_handler("s_slam_tilt", self.slam_tilt, state=1)
        self.machine.events.add_handler("game_starting", self._reset_flag)

    def _reset_flag(self, **kwargs):
        self.slam = False

    def slammed(self):
        return self.slam

    def slam_tilt(self):
        os_ = self.os
        if not os_.game or os_.task_running(0x39):
            return
        self.slam = True
        os_.state |= ST_TILT                         # no scores, no rules, no bonus
        for flipper in self.machine.flippers.values():
            flipper.disable()
        os_.kill_ball_save()
        os_.hook("tilt")                             # event 0x54: every mode stops
        os_.task_start(0x39, SLAM_RESET_TICKS, self.reset)
        os_.deff_start(24)
        os_.leff_start(12)
        os_.sound(0x018)
        os_.ball_search_reload(15)

    def reset(self):
        """thunk_FUN_00010ce8(0): the machine resets; the game in progress is gone."""
        if self.machine.game:
            self.machine.game.end_game()


feature = SlamTilt
