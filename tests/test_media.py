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

    def test_sounds_go_to_the_gmc_client(self):
        # MPF's bcp_trigger() skips clients without a registered handler, and GMC registers none for
        # sounds_play: the bridge must address GMC (the "local_display" client) directly
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        client = mock.Mock()
        with mock.patch.object(bridge, "connected", return_value=True), \
                mock.patch.object(self.machine.bcp, "interface") as iface, \
                mock.patch.object(self.machine.bcp, "transport") as transport:
            transport.get_named_client.return_value = client
            bridge.sound(0x01b)
            iface.bcp_trigger.assert_not_called()
            kw = iface.bcp_trigger_client.call_args.kwargs
            self.assertIs(client, kw["client"])
            self.assertEqual("sounds_play", kw["name"])
            transport.get_named_client.assert_called_with("local_display")
        self.assertFalse(self.machine.bcp.transport.get_transports_for_handler("sounds_play"))   # why

    def test_score_display_args(self):
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        self.assertEqual("FREE PLAY", bridge.credits_text())           # unit tests run on free play
        self.tron.adj[34] = 0
        self.assertEqual("CREDITS 0", bridge.credits_text())
        self.tron.credit_model.counter = 0                              # one coin of USA 10's three
        self.assertEqual("CREDITS 1/3", bridge.credits_text())
        self.tron.credit_model.credits = 2
        self.assertEqual("CREDITS 2 1/3", bridge.credits_text())
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        args = bridge.deff_lines(19, {})
        self.assertEqual("BALL 1", args["line0"])
        self.assertEqual("REPLAY AT 20,000,000", args["replay"])      # auto replay, first level
        self.assertEqual((1, 1, "00", ""), (args["players"], args["player"], args["p1"], args["p2"]))
        self.machine.game.player.score += 5000
        bridge.score_changed()
        args = bridge.score_display_args()
        self.assertEqual(("5,000", 0), (args["award"], args["award_age"]))
        for key in ("bar_ds", "bar_bumpers", "bar_spinners", "bar_zfs", "bar_clu", "bar_gem"):
            self.assertEqual(0, args[key])

    def test_missing_value_is_blank(self):
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        lines = {k: v for k, v in bridge.deff_lines(133, {}).items() if k.startswith("line")}
        self.assertEqual({"line0": "EXTRA", "line1": "BALL", "line2": ""}, lines)
