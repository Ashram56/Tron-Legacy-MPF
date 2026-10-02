"""Attract mode: deff 1 pages and the leff 1 attract lamp show (assets/rules/modes/attract_and_service.md).

Started at power-up and after every game (event 0x08 [0x000015d4]): deff 1, leff 1, then the attract tube
rule (sound call 0x001 + tube show 1). Leff 1 runs in three phases [0x01017dc4]:
1. chase, 30 x 62 ticks;
2. group flash: 3 rounds x 8 groups, each 16 flashes of 3+3 ticks (96 ticks) with its own tube show
   (2..9, table 0x040d2f3a); every group change re-runs the tube rule (0x001 + tube show 1);
3. all-lamp flash, 500 ticks; the end re-runs the tube rule, then phase 1 again.
Attract ticks are 16.0 ms in the emulator (not the 16.26 ms of play): the timings below are in seconds
as measured in traces/attract_and_service.jsonl. The pages (deff 1 internals) log no rules events.
"""
from tron.features import Feature

ORDER = 6
BOOT_SECONDS = 0.992        # power-up -> deff 1 + leff 1 (traces/attract_and_service.jsonl t 0.99)
CHASE_SECONDS = 29.885      # phase 1 (1,860 ticks at 16.0 ms, plus the task start)
GROUP_SECONDS = 1.536       # one phase-2 group (96 ticks at 16.0 ms)
GROUPS = 24
FLASH_SECONDS = 8.033       # phase 3 (500 ticks)
ATTRACT_TICK = 0.016
OS_LAMPS = (65, 66)         # lamps 0x36f64 / 0x36f65 (start buttons), left to the OS


class Attract(Feature):
    name = "attract"
    HOOKS = ("attract_start",)

    def __init__(self, os_):
        super().__init__(os_)
        self.handle = None          # the one pending phase step
        self.group = 0
        self.machine.events.add_handler("init_phase_5", self._power_up)
        self.machine.events.add_handler("game_starting", self.stop, priority=2000)

    def _power_up(self, **kwargs):
        self._later(BOOT_SECONDS, self.start)

    def _later(self, seconds, fn):
        self.stop()
        self.handle = self.machine.clock.schedule_once(lambda: fn(), seconds)

    def stop(self, **kwargs):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
            self.handle = None
        self._flash_end()

    def _flash_start(self):
        """Phase 3 of leff 1: every matrix lamp but the OS-owned ones (start buttons) flashes, the
        periods slowing from 24 to 6 ticks, then 10 x 4 and 5 x 12 ticks. The captured attract show
        (lampfx_001) has only the named lamps; this layer also drives the unused matrix positions."""
        lamps = self.os.lamps
        self.flash_layer = lamps.layer_create(1, [n for n in range(1, 81) if n not in OS_LAMPS])
        self.flash_steps = list(range(24, 5, -2)) * 2 + [4] * 10 + [12] * 5
        self._flash_step()

    def _flash_step(self):
        layer = getattr(self, "flash_layer", None)
        if layer is None or not self.flash_steps:
            return
        layer.image = set() if layer.image else set(layer.mask)
        self.os.lamps.changed()
        ticks = self.flash_steps.pop(0) if len(self.flash_steps) > 1 else self.flash_steps[0]
        self.flash_handle = self.machine.clock.schedule_once(lambda: self._flash_step(), ticks * ATTRACT_TICK)

    def _flash_end(self):
        layer = getattr(self, "flash_layer", None)
        if layer is not None:
            self.machine.clock.unschedule(self.flash_handle)
            self.os.lamps.layer_free(layer)
            self.flash_layer = None

    def attract_start(self):
        self.start()

    def start(self):
        """Event 0x08: attract pages and lamp show."""
        os_ = self.os
        self.stop()
        os_.deff_start(1)
        os_.leff_start(1)
        self.tube_rule()
        self.chase()

    def tube_rule(self):
        """The attract tube rule: sound call 0x001, then tube show 1 (refused while a group show owns the tubes)."""
        self.os.sound(0x001)
        self.os.tube_start(1)

    def chase(self):
        self._flash_end()
        self.group = 0
        self._later(CHASE_SECONDS, self.next_group)

    def next_group(self):
        os_ = self.os
        if self.group:
            os_.tube_stop(2 + (self.group - 1) % 8)
        if self.group == GROUPS:
            for show in range(2, 10):
                os_.tube_stop(show)
            self.tube_rule()
            self._later(FLASH_SECONDS, self.chase)
            self._flash_start()
            return
        os_.tube_start(2 + self.group % 8)
        self.group += 1
        self.tube_rule()
        self._later(GROUP_SECONDS, self.next_group)


feature = Attract
