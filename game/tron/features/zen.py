"""ZEN rollover charges (assets/rules/modes/zen_rollover.md)."""
from tron.features import Feature

FLASH_TICKS = 35          # task 0xcc pulses coil 17 every 7 x 5 ticks


class Zen(Feature):
    name = "zen"
    HOOKS = ("player_first_ball", "ball_start", "zen_rollover", "zen_use_charge", "zen_active")

    def player_first_ball(self):
        """0x0103116c: charges cleared, flasher task killed."""
        self.pd.zen_charges = 0
        self.os.task_kill(0xcc)

    def ball_start(self):
        """0x010311ac: the flasher follows the player who is up."""
        if self.pd.zen_charges:
            self._flash_task()
        else:
            self.os.task_kill(0xcc)

    def zen_active(self):
        return self.os.task_running(0xcc)

    def zen_rollover(self):
        """0x0103129c: one charge and 42,000 per hit when no multiball runs."""
        os_ = self.os
        if os_.any_multiball():
            return
        self.pd.zen_charges = min(self.pd.zen_charges + 1, 0xffff)
        os_.score_add(42000)
        if not os_.task_running(0xcc):
            self._flash_task()
            os_.deff_start(100)
        os_.sound(0x0e5)

    def zen_use_charge(self):
        """0x01031208(1), called by a TRON standup that would light a new, non-completing letter."""
        os_ = self.os
        if not os_.task_running(0xcc):
            return False
        os_.sound(0x0e6)
        self.pd.zen_charges = max(self.pd.zen_charges - 1, 0)
        if not self.pd.zen_charges:
            os_.task_kill(0xcc)
        return True

    def _flash_task(self):
        def pulse():
            coil = self.machine.coils.get("f_zen_flasher") if hasattr(self.machine, "coils") else None
            if coil:
                coil.pulse(18)
            self._flash_task()
        self.os.task_start(0xcc, FLASH_TICKS, pulse)


feature = Zen
