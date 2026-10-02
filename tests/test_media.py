"""Media bridge: ROM text formatting and the BCP triggers sent to the media controller."""
import unittest
from unittest import mock

from tests.tron_test import TronTestCase
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "game"))
from tron.media_bridge import format_rom_text   # noqa: E402


class TestRomText(unittest.TestCase):

    def test_printf(self):
        self.assertEqual("BALL 2", format_rom_text("BALL %d", [2]))
        self.assertEqual("1,234,560", format_rom_text("%,02lu", [1234560]))
        self.assertEqual("00", format_rom_text("%,02lu", [0]))      # score 0 as the ROM shows it
        self.assertEqual("000042", format_rom_text("%06d", [42]))
        self.assertEqual("PLAYER 3", format_rom_text("PLAYER %u", [3]))
        self.assertEqual("ZUSE", format_rom_text("%s", ["ZUSE"]))

    def test_plural_and_ordinal(self):
        self.assertEqual("1 BALL", format_rom_text("%d %P0/BALL/BALLS%", [1]))
        self.assertEqual("3 BALLS", format_rom_text("%d %P0/BALL/BALLS%", [3]))
        self.assertEqual("2ND", format_rom_text("%d%P1/ST/ND/RD/TH%", [2]))


class TestBridge(TronTestCase):

    def test_deff_and_sound_triggers(self):
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        with mock.patch.object(bridge, "connected", return_value=True), \
                mock.patch.object(self.machine.bcp, "interface") as iface:
            trig = iface.bcp_trigger
            self.tron.deff_start(25, hold=True, total=1500000)
            plays = [c.kwargs for c in trig.call_args_list if c.kwargs["name"] == "slides_play"
                     and "deff_025" in c.kwargs["settings"]
                     and c.kwargs["settings"]["deff_025"]["action"] == "play"]
            self.assertEqual("TOTAL BONUS", plays[-1]["line0"])
            self.assertEqual("1,500,000", plays[-1]["line1"])
            trig.reset_mock()
            self.tron.media.sound(0x01b)                  # main play music: looped on the music bus
            sent = trig.call_args_list[-1].kwargs["settings"]
            (key, settings), = sent.items()
            self.assertEqual("music", settings["bus"])
            self.assertEqual(-1, settings["loops"])
            self.tron.media.sound(0x001)                  # channel stop: stops the music
            self.assertEqual({"action": "stop", "key": key}, trig.call_args_list[-1].kwargs["settings"][key])

    def test_missing_value_is_blank(self):
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        self.assertEqual({"line0": "EXTRA", "line1": "BALL", "line2": ""}, bridge.deff_lines(133, {}))
