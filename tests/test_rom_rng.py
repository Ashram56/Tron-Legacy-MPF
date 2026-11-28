import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))
from tron.rom_rng import RomRandom  # noqa: E402


def test_lcg_matches_rom_formula():
    r = RomRandom(0)
    assert r.step() == 1                                   # 0 * 0x19660d + 1
    assert r.step() == 0x19660e
    r = RomRandom(5)
    st = (5 * 0x19660d + 1) & 0xffffffff
    assert r.below(13) == (13 * st) >> 32


def test_randrange_and_choice_stay_in_range():
    r = RomRandom(123)
    assert all(0 <= r.randrange(4) < 4 for _ in range(200))
    assert r.choice([7, 8, 9]) in (7, 8, 9)


def test_randrange_step_is_random_below_count_times_step():
    """The match number [0x0001b660] is random_below(10) * 10: a multiple of ten, one draw."""
    r = RomRandom(77)
    ref = RomRandom(77)
    for _ in range(100):
        n = r.randrange(0, 100, 10)
        assert n % 10 == 0 and n == ref.below(10) * 10
