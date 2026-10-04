"""MPF test base for this machine: virtual hardware that moves balls (smart_virtual), no media controller."""
import os
import subprocess
import sys

from mpf.tests.MpfTestCase import MpfTestCase

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GAME = os.path.join(ROOT, "game")
RANDOM_SEED = 1974
subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gen_config.py")], check=True)


class TronTestCase(MpfTestCase):
    FREE_PLAY = True    # unit tests start games without coins (adj 34 FREE PLAY, not persisted)

    def get_config_file(self):
        return "config.yaml"

    def get_machine_path(self):
        return GAME

    def get_absolute_machine_path(self):
        return GAME

    def get_platform(self):
        return "smart_virtual"

    def get_enable_plugins(self):
        return False

    def setUp(self):
        if GAME not in sys.path:
            sys.path.insert(0, GAME)
        super().setUp()
        self.machine.tron.random.seed(RANDOM_SEED)     # live play draws from an unseeded generator
        if self.FREE_PLAY:
            self.machine.tron.adj.override(34, 1)

    @property
    def tron(self):
        return self.machine.tron

    def fill_trough(self):
        for name in ("s_trough_1_r", "s_trough_2", "s_trough_3", "s_trough_4_l"):
            self.machine.switch_controller.process_switch(name, 1, True)
        self.advance_time_and_run(2)
