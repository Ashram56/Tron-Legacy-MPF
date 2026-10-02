"""Rules features. Each module defines one Feature subclass; load_features() builds them all.

A feature registers its functions under the ROM hook names the switch layer and the OS call
(see tron/switches.py), and keeps per-player state in os.pd (reset on "player_first_ball").
"""
import importlib

FEATURES = [
    "bonus",
    "game_over",
]


class Feature:
    name = ""

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        for hook in getattr(self, "HOOKS", ()):
            os_.register(hook, getattr(self, hook))

    @property
    def pd(self):
        return self.os.pd


def load_features(os_):
    out = []
    for mod_name in FEATURES:
        mod = importlib.import_module("tron.features." + mod_name)
        out.append(mod.feature(os_))
    return out
