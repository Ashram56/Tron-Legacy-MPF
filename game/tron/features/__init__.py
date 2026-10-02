"""Rules features. Each module defines one Feature subclass; load_features() builds them all.

A feature registers its functions under the ROM hook names the switch layer and the OS call
(see tron/switches.py), and keeps per-player state in os.pd (reset on "player_first_ball").
"""
import importlib
import pkgutil


def feature_modules():
    """Every module in this package, sorted by its ORDER (default 50), then by name."""
    mods = [importlib.import_module("tron.features." + m.name) for m in pkgutil.iter_modules(__path__)]
    return sorted(mods, key=lambda m: (getattr(m, "ORDER", 50), m.__name__))


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
    return [mod.feature(os_) for mod in feature_modules() if hasattr(mod, "feature")]
