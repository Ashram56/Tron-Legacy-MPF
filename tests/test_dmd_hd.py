"""The HD DMD mode: the upscaler (scripts/dmd_hd.py), the HD fonts (scripts/gen_fonts.py build_hd), the HD
frames of every display effect (scripts/gen_media.py build_hd_frames), the run.py switches, and in Godot
(game/tools/dmd_mode.gd): classic mode gives the same 128x32 frames as before HD existed, dot for dot, and
HD mode draws the text at the window's resolution."""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dmd_hd  # noqa: E402
import gen_fonts  # noqa: E402
import run  # noqa: E402
import toolchain as tc  # noqa: E402

GAME = os.path.join(ROOT, "game")


def image(rows):
    from PIL import Image
    img = Image.new("L", (len(rows[0]), len(rows)))
    img.putdata([v for row in rows for v in row])
    return img


class TestUpscaler(unittest.TestCase):
    def test_sizes_and_flat_areas(self):
        black = image([[0] * 16] * 8)
        self.assertEqual((128, 64), dmd_hd.upscale_levels(black, 8).size)
        self.assertEqual((0, 0), dmd_hd.upscale_levels(black, 8).getextrema())
        block = image([[0] * 16] * 2 + [[0] * 4 + [255] * 8 + [0] * 4] * 4 + [[0] * 16] * 2)
        big = dmd_hd.upscale_levels(block, 8)
        self.assertEqual(255, big.getpixel((64, 32)))                  # inside the block: full level
        self.assertEqual(0, big.getpixel((8, 8)))                      # far outside: dark

    def test_shades_kept_and_edges_smoothed(self):
        rows = [[0] * 12 for _ in range(12)]
        for y in range(2, 10):
            for x in range(2, 10):
                rows[y][x] = 136 if x < 6 else 255                     # two shades side by side
        big = dmd_hd.upscale_levels(image(rows), 8)
        self.assertEqual(136, big.getpixel((3 * 8 + 4, 48)))
        self.assertEqual(255, big.getpixel((8 * 8 + 4, 48)))
        values = {v for _, v in big.getcolors(256)}
        self.assertGreater(len(values), 4)                             # anti-aliased edges, not 3 flat greys

    def test_single_dot_and_thin_line_survive(self):
        rows = [[0] * 9 for _ in range(9)]
        rows[4][4] = 255
        big = dmd_hd.upscale_levels(image(rows), 8)
        self.assertEqual(255, big.getpixel((36, 36)))
        line = [[0] * 20 for _ in range(5)]
        line[2] = [255] * 20
        big = dmd_hd.upscale_levels(image(line), 8)
        width = sum(1 for y in range(40) if big.getpixel((80, y)) >= 128)
        self.assertTrue(6 <= width <= 11, width)                       # about one dot (8 px) wide

    def test_deterministic(self):
        rows = [[(x * y * 37) % 256 // 17 * 17 for x in range(16)] for y in range(8)]
        a = dmd_hd.upscale_levels(image(rows), 4).tobytes()
        self.assertEqual(a, dmd_hd.upscale_levels(image(rows), 4).tobytes())


class TestHdFonts(unittest.TestCase):
    """Every one of the 44 ROM fonts has an HD twin with the same metrics times the scale."""

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        _, get, cls.fonts = gen_fonts.decode_all()
        cls.get = staticmethod(get)
        gen_fonts.build_hd(cls.fonts, get, cls.out, 4)            # a small scale keeps the test quick

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_every_font_has_an_hd_font(self):
        self.assertEqual(44, len(self.fonts))
        info = json.load(open(os.path.join(self.out, "fonts_hd.json"), encoding="utf-8"))
        self.assertEqual(4, info["scale"])
        self.assertEqual(list(range(44)), [f["id"] for f in info["fonts"]])
        styles = {f["style"] for f in info["fonts"]}
        self.assertTrue({"plain", "outlined", "tron", "digits", "big tron digits"} <= styles, styles)
        self.assertTrue(info["fonts"][1]["outline"] and not info["fonts"][0]["outline"])
        for f in self.fonts:
            self.assertTrue(os.path.exists(os.path.join(self.out, "rom_font_%02d.png" % f["id"])))

    def test_metrics_scaled(self):
        for f in self.fonts:
            text = open(os.path.join(self.out, "rom_font_%02d.fnt" % f["id"]), encoding="utf-8").read()
            chars = {}
            for line in text.splitlines():
                if line.startswith("char "):
                    kv = dict(p.split("=") for p in line.split()[1:])
                    chars[chr(int(kv["id"]))] = kv
            self.assertEqual(set(f["glyphs"]), set(chars))
            for c, g in f["glyphs"].items():
                kv = chars[c]
                self.assertEqual(g["w"] * 4, int(kv["width"]))
                self.assertEqual(g["h"] * 4, int(kv["height"]))
                self.assertEqual((g["w"] + g["xoff"] + f["spacing"]) * 4, int(kv["xadvance"]))
                self.assertEqual((f["ascent"] - g["h"] + g["below"]) * 4, int(kv["yoffset"]))
            self.assertIn("size=%d" % ((f["ascent"] + f["descent"]) * 4), text)

    def test_glyph_cells(self):
        """Plain fonts keep their black cell (opaque rectangle); outline fonts are transparent around."""
        plain = dmd_hd.upscale_glyph(self.get(self.fonts[12]["glyphs"]["O"]["image"]), 8, False)
        self.assertEqual((255, 255), plain.split()[3].getextrema())
        outlined = dmd_hd.upscale_glyph(self.get(self.fonts[13]["glyphs"]["O"]["image"]), 8, True)
        self.assertEqual(0, outlined.split()[3].getpixel((0, 0)))
        self.assertEqual(255, outlined.split()[0].getextrema()[1])


GENERATED = os.path.exists(os.path.join(GAME, "media", "dmd_hd", "scale.json"))


@unittest.skipUnless(GENERATED, "HD media not generated (scripts/gen_media.py)")
class TestHdMedia(unittest.TestCase):
    def test_every_picture_has_an_hd_twin(self):
        from PIL import Image
        scale = json.load(open(os.path.join(GAME, "media", "dmd_hd", "scale.json")))["scale"]
        pictures = glob.glob(os.path.join(GAME, "media", "dmd", "deff_*", "*.png"))
        self.assertGreater(len(pictures), 1000)
        for src in pictures:
            rel = os.path.relpath(src, os.path.join(GAME, "media", "dmd"))
            dst = os.path.join(GAME, "media", "dmd_hd", rel)
            self.assertTrue(os.path.exists(dst), rel)
        for src in pictures[::50]:
            rel = os.path.relpath(src, os.path.join(GAME, "media", "dmd"))
            w, h = Image.open(src).size
            self.assertEqual((w * scale, h * scale), Image.open(os.path.join(GAME, "media", "dmd_hd", rel)).size)

    def test_every_deff_and_font(self):
        data = json.load(open(os.path.join(GAME, "tron", "media_data.json"), encoding="utf-8"))
        for deff in data["deffs"]:
            self.assertTrue(os.path.isdir(os.path.join(GAME, "media", "dmd_hd", "deff_%03d" % int(deff))), deff)
        for n in range(44):
            self.assertTrue(os.path.exists(os.path.join(GAME, "fonts", "hd", "rom_font_%02d.fnt" % n)))


class TestRunSwitches(unittest.TestCase):
    def test_dmd_args(self):
        self.assertEqual(["--", "--dmd=classic"], run.dmd_args([], "classic"))
        self.assertEqual(["--rendering-driver", "opengl3", "--resolution", "1920x480", "--", "--x", "--dmd=hd",
                          "--dmd-dots=2"],
                         run.dmd_args(["--rendering-driver", "opengl3", "--", "--x"], "hd", 2, "1920x480"))
        self.assertEqual([], run.dmd_args([]))                     # TRON_DMD / the project setting decide
        with self.assertRaises(SystemExit):
            run.dmd_args([], size="big")

    def test_cli(self):
        seen = {}
        with unittest.mock.patch.object(run, "run", lambda *a, **k: seen.update(k) or 0):
            run.main(["--dmd", "classic", "--seconds", "1"])
            self.assertIn("--dmd=classic", seen["godot_args"])
            run.main(["--seconds", "1"])
            self.assertEqual([], seen["godot_args"])


# Pixel hashes (sha1 of the RGBA dots, 16 hex digits) of 128x32 frames rendered before the HD mode existed
# (phase10-docker 662f0a8): classic mode must keep giving these. Times 0, 400 and 1600 ms.
CLASSIC = {
    "deff_019": ["4c202f8e88fbe459", "ceff80ed506ad992", "ceff80ed506ad992"],
    "deff_025": ["d37ed2eab53a1001", "d37ed2eab53a1001", "d37ed2eab53a1001"],
    "deff_046": ["bf7708db11dc8854", "04cca43df9dd0e4c", "3e055f3406cf6f2d"],
    "deff_091": ["5389647d8fd053ff", "5389647d8fd053ff", "0b25fcc7236c9b02"],
    "deff_143": ["6507f3260bdb28ac", "c3c251af5390289d", "2b45f48506dd629c"],
}
KWARGS = {"deff_019": {"line0": "BALL 1", "line1": "1,234,560", "credits": "FREE PLAY",
                       "replay": "REPLAY AT 20,000,000", "p1": "1,234,560", "p2": "870,050", "p3": "", "p4": "",
                       "players": 2, "player": 1, "valid": True, "award": "25,000", "award_age": 3,
                       "blink_age": 0, "bar_ds": 6, "bar_zfs": 7},
          "deff_025": {"line1": "50,000"}, "deff_046": {}, "deff_091": {"lit": 3, "new": 4},
          "deff_143": {"line2": "25,000,000"}}
CAN_RENDER = (sys.platform.startswith("linux") and GENERATED and os.path.exists(tc.godot_path())
              and (shutil.which("xvfb-run") or os.environ.get("DISPLAY"))
              and not tc.media_stale())


@unittest.skipUnless(CAN_RENDER, "needs Linux with Xvfb or a display, Godot and the imported media")
class TestGodotModes(unittest.TestCase):
    """Renders slides with game/tools/slide_capture.tscn, as scripts/render_diff.py does."""

    def render(self, user_args=(), engine_args=(), env=None):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        jobs = [{"slide": s, "kwargs": KWARGS[s], "times_ms": [0, 400, 1600], "out": os.path.join(out, s)}
                for s in CLASSIC]
        job = os.path.join(out, "job.json")
        with open(job, "w") as f:
            json.dump(jobs, f)
        cmd = run.godot_command(["--rendering-driver", "opengl3"] + list(engine_args)
                                + ["res://tools/slide_capture.tscn", "--", "--job=" + job] + list(user_args))
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
                       env=dict(os.environ, **(env or {})))
        return out

    def hashes(self, out):
        from PIL import Image
        got = {}
        for s in CLASSIC:
            got[s] = [hashlib.sha1(Image.open(p).convert("RGBA").tobytes()).hexdigest()[:16]
                      for p in sorted(glob.glob(os.path.join(out, s, "*.png")))]
        return got

    def test_classic_is_the_original_output(self):
        self.assertEqual(CLASSIC, self.hashes(self.render(["--dmd=classic"])))
        # captures without --dmd stay classic, even with TRON_DMD=hd (the ROM checks compare dots)
        self.assertEqual(CLASSIC, self.hashes(self.render(env={"TRON_DMD": "hd"})))

    def test_hd_draws_text_at_window_resolution(self):
        from PIL import Image
        out = self.render(["--dmd=hd"], ["--resolution", "1280x320"])
        frame = Image.open(os.path.join(out, "deff_025", "frame_00000.png")).convert("L")
        self.assertEqual((1280, 320), frame.size)
        box = frame.point(lambda p: 255 if p > 40 else 0).getbbox()
        # "50,000" in font 15, centred on x 84, baseline row 26 (deff 25): 42 x 11 dots in classic
        self.assertTrue(abs((box[0] + box[2]) / 2 - 84.5 * 10) < 15, box)
        self.assertTrue(380 < box[2] - box[0] < 450 and 90 < box[3] - box[1] < 130, box)
        self.assertGreater(len(frame.getcolors(256)), 20)          # smooth edges, not 10x10 blocks
        score = Image.open(os.path.join(out, "deff_019", "frame_00002.png"))
        self.assertEqual((1280, 320), score.size)


if __name__ == "__main__":
    unittest.main()
