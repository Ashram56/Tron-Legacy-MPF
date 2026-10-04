"""Every text line the rules send to the DMD, in every reference scenario (assets/rules/traces), is ROM text.

The media bridge formats each display effect's lines from the ROM's own messages (media_data.json "text",
from the decompiled draw code) and the values the rules give. Two faults put text on the DMD that the ROM
never shows: a printf line drawn without its value (a bare label such as "RIGHT SPINNER =", the values the
ROM reads from RAM not reported), and a name, event, Python value or tuple printed where the ROM prints
text (the deff 138 "CASTOR" bug). Every scenario runs with a connected media controller mocked in; every
line sent must be the ROM line, or the ROM line with its values filled in.
"""
import glob
import os
import re
import unittest
from unittest import mock

from tests.tron_test import ROOT
from tests import scenario

import sys
sys.path.insert(0, os.path.join(ROOT, "game"))
from tron.media_bridge import MediaBridge, SPEC   # noqa: E402

NUMBER = r"-?[\d,]*\d"
# what a printf spec prints: numbers ("%,02lu" with commas, "%luK" the K added by the ROM text), a %s is
# ROM text itself (upper case, digits, punctuation; never snake_case, None or a Python repr)
ROM_STRING = r"[A-Z0-9 .,:'!?+\-=/#&]*"
NOT_ROM = re.compile(r"[a-z_]|None|True|False|[\[\]{}()<>]")


def line_pattern(template):
    out, pos = "", 0
    for m in SPEC.finditer(template):
        out += re.escape(template[pos:m.start()])
        spec = m.group(1)
        out += "(?:{})".format(ROM_STRING if spec.endswith("s") else "" if spec.startswith("P") else NUMBER)
        if spec.startswith("P"):                       # %P1/a/b/c/%: one of the choices
            out = out[:-len("(?:)")] + "(?:{})".format("|".join(map(re.escape, spec[3:-1].split("/"))))
        pos = m.end()
    return re.compile(out + re.escape(template[pos:]) + "$")


def scenario_names():
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(scenario.TRACES, "*.txt")))


class TestDmdText(unittest.TestCase):

    def run_scenario(self, name):
        sent = []

        def send(bridge, name, settings, priority=0, need_data=True, **kwargs):
            if name == "slides_play":
                (slide, s), = settings.items()
                if s["action"] in ("play", "update"):
                    sent.append((slide, kwargs))
        test = scenario.ScenarioRun()
        test.scenario, test.out_path = name, os.path.join(ROOT, "captures", "traces", name + ".text.jsonl")
        with mock.patch.object(MediaBridge, "connected", lambda self, need_data=True: True), \
                mock.patch.object(MediaBridge, "_send", send):
            result = unittest.TestResult()
            test.run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        return test, sent

    def test_every_line_is_rom_text(self):
        if not os.path.exists(os.path.join(ROOT, "game", "tron", "media_data.json")):
            self.skipTest("media data not generated (scripts/gen_media.py)")
        for name in scenario_names():
            with self.subTest(scenario=name):
                missing = []
                orig = MediaBridge.__init__

                def init(bridge, os_):
                    orig(bridge, os_)
                    bridge.missing = missing
                with mock.patch.object(MediaBridge, "__init__", init):
                    test, sent = self.run_scenario(name)
                self.assertEqual([], sorted(set(missing)), "printf lines drawn without their value")
                data = None
                bad = set()
                for slide, kwargs in sent:
                    for key, value in kwargs.items():
                        if not isinstance(value, str) or not value:
                            continue
                        if NOT_ROM.search(value):
                            bad.add((slide, key, value))
                    if not slide.startswith("deff_"):
                        continue
                    if data is None:
                        import json
                        with open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8") as f:
                            data = json.load(f)["deffs"]
                    text = data[str(int(slide[5:]))]["text"]
                    for key, value in kwargs.items():
                        m = re.match(r"line(\d+)$", key)
                        if not m or value == "":
                            continue                      # blank: a None value, the ROM draws nothing there
                        i = int(m.group(1))
                        if i >= len(text) or not line_pattern(text[i]).match(value):
                            bad.add((slide, key, value))
                self.assertEqual(set(), bad, "DMD text that is not the ROM's")


if __name__ == "__main__":
    unittest.main()


# Deffs whose text the rules never draw: their fonts come from per-language tables or lists the package
# lacks (deff 3 technician alert, 12 message, 16 tournament game, 45 the Light Cycle maze video mode).
NEVER_STARTED = {3, 12, 16, 45}


class TestDmdFonts(unittest.TestCase):
    """Every text line a display effect can draw is placed in a ROM font, at the ROM's position, as the
    deff's draw code (or its reference capture) gives it: no guessed fallback font (the oversized "n MORE"
    lines of deffs 66, 80 and 108 were font 12 at a guessed row), and no Godot default font on any slide."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        if not os.path.exists(os.path.join(ROOT, "game", "fonts", "fonts.json")):
            self.skipTest("fonts not generated (scripts/gen_media.py)")

    def test_no_fallback_font(self):
        import json
        import rom_layout
        with open(os.path.join(ROOT, "game", "tron", "media_data.json"), encoding="utf-8") as f:
            deffs = json.load(f)["deffs"]
        with open(os.path.join(ROOT, "game", "fonts", "fonts.json"), encoding="utf-8") as f:
            fonts = {font["id"]: font for font in json.load(f)["fonts"]}
        calls = rom_layout.deff_calls()
        bad = []
        for deff_id, info in sorted(deffs.items(), key=lambda kv: int(kv[0])):
            deff_id = int(deff_id)
            if deff_id in NEVER_STARTED or not info["text"]:
                continue
            for line, lay in zip(info["text"], rom_layout.line_layouts(deff_id, info["text"], fonts,
                                                                       calls.get(deff_id, []))):
                if lay and lay["source"] == "fallback":
                    bad.append((deff_id, line, "fallback font"))
            for call in calls.get(deff_id, []):
                if call["font"] is None and call["font_list"] not in rom_layout.FONT_LISTS \
                        and call["text"] in info["text"]:
                    bad.append((deff_id, call["text"], "unknown font list " + call["font_list"]))
        self.assertEqual([], bad)

    def test_never_started_deffs(self):
        source = ""
        for path in glob.glob(os.path.join(ROOT, "game", "tron", "**", "*.py"), recursive=True):
            with open(path, encoding="utf-8") as f:
                source += f.read()
        for deff_id in NEVER_STARTED:
            self.assertNotRegex(source, r"deff_start\({}\b".format(deff_id))

    def test_slides_draw_rom_fonts(self):
        # every text label of every slide is a tron/rom_text.gd label (a ROM font); the boot slide said
        # "TRON LEGACY / MPF + GMC BOOT OK" and the attract pages and initials used Godot's default font
        paths = glob.glob(os.path.join(ROOT, "game", "slides", "*.tscn")) + \
            glob.glob(os.path.join(ROOT, "game", "slides", "deffs", "*.tscn"))
        bad = []
        for path in paths:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            text_script = re.search(r'path="res://tron/rom_text.gd" id="([^"]+)"', text)
            for node in re.split(r"\n(?=\[node )", text):
                if 'type="Label"' in node and not (text_script and 'script = ExtResource("{}")'.format(
                        text_script.group(1)) in node):
                    bad.append((os.path.basename(path), node.splitlines()[0]))
        self.assertEqual([], bad)


class TestDmdNeverEmpty(unittest.TestCase):
    """During a game a display effect is always on the DMD. In play the score display (deff 19) comes back
    whenever no other deff runs (the deff rules [0x000198a8] re-assert the background deff as an effect
    ends; traces/flynns_arcade.jsonl 19.36 s), and between effects the DMD keeps its last frame: GMC's base
    slide (attract.tscn, below every deff) never shows. Each reference scenario is sampled every 50 ms for
    an empty slide stack during a game, and for no running deff in play."""

    SAMPLE = 0.05

    def test_no_base_slide_during_a_game(self):
        if not os.path.exists(os.path.join(ROOT, "game", "tron", "media_data.json")):
            self.skipTest("media data not generated (scripts/gen_media.py)")
        for name in scenario_names():
            with self.subTest(scenario=name):
                shown, empty, idle = set(), [], []

                def send(bridge, kind, settings, priority=0, need_data=True, **kwargs):
                    if kind == "slides_play":
                        (slide, s), = settings.items()
                        if s["action"] == "play":
                            shown.add(slide)
                        elif s["action"] == "remove":
                            shown.discard(slide)
                orig = MediaBridge.__init__

                def init(bridge, os_):
                    orig(bridge, os_)

                    def sample(dt=None):
                        game = bridge.machine.game
                        if game is not None and game.player and not shown:
                            empty.append(round(os_.now, 2))
                        if game is not None and os_.in_play and os_.display.fg is None and os_.display.bg is None:
                            idle.append(round(os_.now, 2))
                    bridge.machine.clock.schedule_interval(sample, self.SAMPLE)
                test = scenario.ScenarioRun()
                test.scenario = name
                test.out_path = os.path.join(ROOT, "captures", "traces", name + ".empty.jsonl")
                with mock.patch.object(MediaBridge, "connected", lambda self, need_data=True: True), \
                        mock.patch.object(MediaBridge, "_send", send), \
                        mock.patch.object(MediaBridge, "__init__", init):
                    result = unittest.TestResult()
                    test.run(result)
                self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
                self.assertEqual([], self.spans(empty), "seconds with no slide on the DMD (GMC's base slide)")
                self.assertEqual([], self.spans(idle), "seconds in play with no deff running (no score display)")

    def spans(self, times):
        spans = []
        for t in times:
            if spans and t - spans[-1][1] <= self.SAMPLE * 1.5:
                spans[-1][1] = t
            else:
                spans.append([t, t])
        return spans
