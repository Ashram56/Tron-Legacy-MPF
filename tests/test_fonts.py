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
        with open(os.path.join(out, name + ".fnt"), encoding="utf-8") as f:
            body = f.read()
        self.assertIn("common lineHeight=9 base=8", body)        # 8 rows above the baseline, comma 1 below
        self.assertIn("char id=69 ", body)
        self.assertIn("xadvance=7 page=0", [l for l in body.splitlines() if l.startswith("char id=69 ")][0])

    def test_rom_text_matches_reference(self):
        """TOTAL BONUS / 50,000 drawn like the ROM equals the emulator capture of deff 25."""
        ref, _ = render_diff.reference(25)
        canvas = [[None] * 128 for _ in range(32)]
        gen_fonts.render(self.get, self.fonts[12], "TOTAL BONUS", 84, 12, 2, canvas)
        gen_fonts.render(self.get, self.fonts[15], "50,000", 84, 26, 2, canvas)
        dots = {(x, y): v for y in range(32) for x in range(128) if (v := canvas[y][x]) is not None}
        best = max(sum(r[y][x] == v for (x, y), v in dots.items()) for r in ref)
        self.assertEqual(len(dots), best)

    def test_font0_comma(self):
        """Score display replay line: font 0's comma also sits one dot left (deff 19 capture)."""
        ref, _ = render_diff.reference(19)
        canvas = [[None] * 128 for _ in range(32)]
        gen_fonts.render(self.get, self.fonts[0], "REPLAY AT 20,000,000", 84, 30, 2, canvas)
        dots = {(x, y): v for y in range(32) for x in range(128) if (v := canvas[y][x]) is not None}
        self.assertEqual(len(dots), max(sum(r[y][x] == v for (x, y), v in dots.items()) for r in ref))


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

    def test_timed_lines(self):
        fonts = gen_fonts.decode_all()[2]
        match = rom_layout.line_layouts(38, ["MATCH", "%,02lu", "%,02lu"], fonts)
        self.assertEqual((37, 0, 15), (match[0]["font"], match[0]["level_steps"][0], match[0]["level_steps"][-1]))
        self.assertEqual(rom_layout.frame_ms(38, 64), match[1]["show_after_ms"])   # number at loop frame 0x40
        self.assertGreater(match[1]["show_after_ms"], match[0]["hide_after_ms"])
        up = rom_layout.line_layouts(40, ["PLAYER %d", "YOU'RE UP"], fonts)
        self.assertEqual(round(6 * rom_layout.TICK_MS), up[1]["blink_ms"])

    def test_panels(self):
        panels = rom_layout.status_panel_deffs()
        self.assertEqual("status", panels[19])
        self.assertEqual("status", panels[133])
        self.assertEqual("match", panels[38])

    def test_dynamic_slides_use_rom_fonts(self):
        path = os.path.join(ROOT, "game", "tron", "media_data.json")
        if not os.path.exists(path):
            self.skipTest("media data not generated (scripts/gen_media.py)")
        deffs = json.load(open(path, encoding="utf-8"))["deffs"]
        dynamic = {d: i for d, i in deffs.items() if i["text"] and i["source"] != "reference"}
        self.assertGreater(len(dynamic), 70)
        for d, info in dynamic.items():
            self.assertTrue(any(f is not None for f in info["fonts"]), d)
            slide = os.path.join(ROOT, "game", "slides", "deffs", info["slide"] + ".tscn")
            if os.path.exists(slide):
                with open(slide, encoding="utf-8") as f:
                    body = f.read()
                self.assertIn("res://tron/rom_text.gd", body, d)
                self.assertNotIn("font_sizes/font_size", body, d)
        with open(os.path.join(ROOT, "game", "slides", "deffs", "deff_019.tscn"), encoding="utf-8") as f:
            body = f.read()
        for node in ("Credits", "Replay", "P1", "P4", "Award", "Separator", "BarGem", "ScoreDisplay"):
            self.assertIn('[node name="%s"' % node, body)
        self.assertIn("score_lines = true", body)
