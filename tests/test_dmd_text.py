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
