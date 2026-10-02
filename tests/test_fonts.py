"""ROM fonts (scripts/gen_fonts.py) and the text layout of the display effects (scripts/rom_layout.py)."""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "game"))
import gen_fonts  # noqa: E402
import rom_layout  # noqa: E402
import render_diff  # noqa: E402


class TestFontDecoding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        index, get, cls.fonts = gen_fonts.decode_all()
        cls.get = staticmethod(get)

    def test_font_table(self):
        self.assertEqual(44, len(self.fonts))
        self.assertEqual(218, self.fonts[0]["group"])            # first font: 5 px, images 218-276
        self.assertEqual(928, self.fonts[12]["group"])
        self.assertEqual(2241, self.fonts[33]["group"])           # the most used font in the deffs

    def test_known_glyphs(self):
        e = self.fonts[12]["glyphs"]["E"]                         # 8 px plain font: E is 6x8, advance 7
        self.assertEqual((6, 8, 0), (e["w"], e["h"], e["below"]))
        self.assertEqual(1, self.fonts[12]["spacing"])
        self.assertEqual(-1, self.fonts[13]["spacing"])           # outlined twin of font 12
        self.assertEqual(-1, self.fonts[15]["glyphs"][","]["xoff"])
        self.assertEqual(1, self.fonts[15]["glyphs"][","]["below"])
        self.assertNotIn("$", self.fonts[0]["glyphs"])            # font 0 has no dollar sign
        self.assertNotIn("#", self.fonts[4]["glyphs"])
        self.assertEqual(list(",0123456789"), list(self.fonts[26]["glyphs"]))
        self.assertEqual(42, gen_fonts.text_width(self.fonts[15], "50,000") + 1)

    def test_bmfont(self):
        out = os.path.join(ROOT, "captures", "test_fonts")
        os.makedirs(out, exist_ok=True)
        name = gen_fonts.write_bmfont(self.fonts[12], self.get, out)
        with open(os.path.join(out, name + ".fnt")) as f:
            body = f.read()
        self.assertIn("common lineHeight=9 base=8", body)        # 8 rows above the baseline, comma 1 below
        self.assertIn("char id=69 ", body)
        self.assertIn("xadvance=7 page=0", [l for l in body.splitlines() if l.startswith("char id=69 ")][0])

    def test_rom_text_matches_reference(self):
        """TOTAL BONUS / 50,000 drawn like the ROM equals the emulator capture of deff 25."""
        ref, _ = render_diff.reference(25)
        lines = ["TOTAL BONUS", "%,02lu"]
        dots = render_diff.text_dots(25, lines, render_diff.line_values(25, lines), self.fonts, self.get)
        best = max(sum(r[y][x] == v for (x, y), v in dots.items()) for r in ref)
        self.assertEqual(len(dots), best)


class TestLayout(unittest.TestCase):

    def test_draw_calls(self):
        calls = rom_layout.deff_calls()
        self.assertIn({"text": "EXTRA", "font": 13, "flags": 4, "x": 127, "y": 10}, calls[133])
        fit = [c for c in calls[40] if c["text"] == "YOU'RE UP"][0]
        self.assertEqual(("0x040d2aa4", 85), (fit["font_list"], fit["max_width"]))

    def test_alternate_layout(self):
        fonts = gen_fonts.decode_all()[2]
        lays = rom_layout.line_layouts(133, ["EXTRA", "BALL", "%,02lu"], fonts)
        self.assertEqual((127, 14, "line2"), (lays[0]["alt_x"], lays[0]["alt_y"], lays[0]["alt_when_empty"]))

    def test_dynamic_slides_use_rom_fonts(self):
        path = os.path.join(ROOT, "game", "tron", "media_data.json")
        if not os.path.exists(path):
            self.skipTest("media data not generated (scripts/gen_media.py)")
        deffs = json.load(open(path))["deffs"]
        dynamic = {d: i for d, i in deffs.items() if i["text"] and i["source"] != "reference"}
        self.assertGreater(len(dynamic), 70)
        for d, info in dynamic.items():
            self.assertTrue(any(f is not None for f in info["fonts"]), d)
            slide = os.path.join(ROOT, "game", "slides", "deffs", info["slide"] + ".tscn")
            if os.path.exists(slide):
                with open(slide) as f:
                    body = f.read()
                self.assertIn("res://tron/rom_text.gd", body, d)
                self.assertNotIn("font_sizes/font_size", body, d)
