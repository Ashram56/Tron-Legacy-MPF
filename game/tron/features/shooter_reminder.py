"""Shooter lane reminder (game_flow.md 4.2, player_up_reminder_task [0x0100f1d0], task 0x43).

Started at every serve: after 1,250 ticks, for up to 312 more ticks, while the ball sits in the shooter
lane (FUN_0001faf0) and no show runs (FUN_000287a4), deff 40 "PLAYER n" starts (its speech 0x0f9 plays
from the deff). Validating the playfield kills the task [0x0100f25c].
"""
from tron.features import Feature

ORDER = 8
REMIND_TICKS = 0x4e2
POLL_TICKS = 0x137


class ShooterReminder(Feature):
    name = "shooter_reminder"
    HOOKS = ("ball_served", "playfield_valid", "ball_end", "tilt")

    def ball_served(self, serve_type):
        self.os.task_start(0x43, REMIND_TICKS, lambda: self._poll(0))

    def _poll(self, ticks):
        os_ = self.os
        if self.machine.switches["s_shooter_lane"].state and not os_.display.show_running():
            os_.deff_start(40, player=os_.player_num)
            return
        if ticks < POLL_TICKS:
            os_.task_start(0x43, 1, lambda: self._poll(ticks + 1))

    def playfield_valid(self):
        self.os.task_kill(0x43)

    def ball_end(self):
        self.os.task_kill(0x43)

    def tilt(self):
        self.os.task_kill(0x43)


feature = ShooterReminder
