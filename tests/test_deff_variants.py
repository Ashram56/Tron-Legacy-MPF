"""Deffs that pick a film clip with random_below(n) [0x0000c6b4]: Python draws it with the ROM's generator and the run lasts
that clip's ROM length (assets/rom_data/deffs/variant_runs.csv), the clip going to Godot as the show's `clip` argument."""
from tests.tron_test import TronTestCase
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.01626


class TestDeffVariants(TronTestCase):

    def test_table_has_every_pick(self):
        from tron import media_table
        table = media_table.load_variants(os.path.join(ROOT, "assets"))
        self.assertEqual({48: 12, 49: 12, 68: 3, 69: 2, 97: 2, 108: 4, 111: 11}, {d: len(t) for d, t in table.items()})
        self.assertEqual(129, table[48][0])            # 131 ticks start to end, minus the 2 of the task's start
        self.assertEqual(280, table[48][7])

    def test_pick_is_the_roms_draw_and_sets_the_length(self):
        for deff_id in (48, 111, 108):
            with self.subTest(deff=deff_id):
                seen = []
                self.tron.media.deff_start = lambda d, prio, **args: seen.append((d, args))
                state = self.tron.random.state
                n = len(self.tron.display.variant_ticks[deff_id])
                expect = (n * ((state * 0x19660d + 1) & 0xffffffff)) >> 32
                self.assertTrue(self.tron.display.start(deff_id))
                self.assertEqual(expect, seen[-1][1]["clip"])
                self.assertAlmostEqual(self.tron.display.variant_ticks[deff_id][expect] * TICK,
                                       self.tron.display.fg_end - self.tron.now, places=3)
                self.tron.display._end_fg(stopped=True)
