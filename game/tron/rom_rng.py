"""The ROM's random number generator (decompile): FUN_0000c684 (0xc684) steps the 32-bit state at RAM 0x372c4,
state = state * 0x19660d + 1; random_below(n) FUN_0000c6b4 (0xc6b4) = (n * state) >> 32 on the new state.
With the same state, the game and the ROM code run (Unicorn: RAM 0x372c4 set) make the same draws in the same order."""
import random

MULT = 0x19660d


class RomRandom(random.Random):
    def __init__(self, seed=None):
        super().__init__()
        self.state = (seed if seed is not None else random.SystemRandom().getrandbits(32)) & 0xffffffff

    def seed(self, a=None, version=2):                      # random.Random.__init__ calls it
        if hasattr(self, "state") or a is not None:
            self.state = (a if a is not None else 0) & 0xffffffff

    def step(self):                                         # FUN_0000c684
        self.state = (self.state * MULT + 1) & 0xffffffff
        return self.state

    def below(self, n):                                     # FUN_0000c6b4
        return (n * self.step()) >> 32

    def _randbelow(self, n):
        return self.below(n)

    def randrange(self, a, b=None, step=1):
        if b is None:
            return self.below(a)
        return a + self.below(b - a)

    def random(self):
        return self.step() / 4294967296.0

    def getrandbits(self, k):
        return self.step() >> (32 - k) if k <= 32 else super().getrandbits(k)
