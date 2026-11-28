"""Deffs that pick a film clip with random_below(n) [0x0000c6b4]: Python draws it with the ROM's generator and the run lasts
that clip's ROM length (assets/rom_data/deffs/variant_runs.csv), the clip going to Godot as the show's `clip` argument."""
from tests.tron_test import TronTestCase
import os
import unittest
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


class TestVariantIdentity(unittest.TestCase):
    """The pick k of the ROM's random_below(n) is the game's clip vk: the frames the ROM draws with the pick forced
    (assets/rom_data/dmd_code/deff_NNN/variants/deff_00k, tools/gen_code_dmd.py) hold the clip vk's pictures exactly
    (columns 41-127). Checked for deffs 68 and 69; deffs 48, 49 and 111 were checked the same way on 2026-11-28."""

    def test_pick_is_the_clip_index(self):
        import glob
        try:
            import numpy as np
            from PIL import Image, ImageSequence
        except ImportError:
            self.skipTest("numpy or PIL missing")

        def arr(im):
            return np.array(im.convert("L").resize((128, 32)), dtype=float)[:, 41:] / 17

        for deff_id, n in ((68, 3), (69, 2)):
            code = os.path.join(ROOT, "assets", "rom_data", "dmd_code", "deff_%03d" % deff_id, "variants")
            gifs = sorted(glob.glob(os.path.join(ROOT, "assets", "mpf_package", "media", "dmd", "deff_%03d_*" % deff_id,
                                                 "variants", "v*.gif")))
            self.assertEqual(n, len(gifs))
            clips = [[arr(f) for f in ImageSequence.Iterator(Image.open(g))] for g in gifs]
            for k in range(n):
                frames = [arr(Image.open(f)) for f in sorted(glob.glob(os.path.join(code, "deff_%03d" % k, "frames", "*.png")))]
                dist = [sum(min(float(np.mean(np.abs(c - f))) for f in frames) for c in clip[::max(1, len(clip) // 6)])
                        for clip in clips]
                with self.subTest(deff=deff_id, pick=k):
                    self.assertEqual(k, dist.index(min(dist)))
                    self.assertAlmostEqual(0.0, min(dist), places=6)


class TestDeff108Identity(unittest.TestCase):
    """Deff 108 [0x010209b0]: pick k draws the bitmaps from the first id the code's table gives (random_parts.csv: 2683, 2713 at
    x = 0, 2623, 2653 at x = 41); the library animation of that first bitmap is frame for frame the game's clip vk."""

    def test_pick_is_the_clip_index(self):
        import glob
        try:
            import numpy as np
            from PIL import Image, ImageSequence
        except ImportError:
            self.skipTest("numpy or PIL missing")
        media = os.path.join(ROOT, "assets", "mpf_package", "media")

        def frames(path):
            return [np.array(f.convert("L").resize((128, 32))) for f in ImageSequence.Iterator(Image.open(path))]

        for k, first in enumerate((2683, 2713, 2623, 2653)):
            lib = frames(glob.glob(os.path.join(media, "dmd_library", "anim_*_img%d" % first, "animation_128x32.gif"))[0])
            clip = frames(os.path.join(media, "dmd", "deff_108_disc_access_progress", "variants", "v%02d.gif" % k))
            with self.subTest(pick=k):
                self.assertEqual(len(lib), len(clip))
                self.assertTrue(all((a == b).all() for a, b in zip(lib, clip)))
