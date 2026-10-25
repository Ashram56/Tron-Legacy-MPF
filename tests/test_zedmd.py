"""The ZeDMD output (game/config/zedmd.yaml): MPF boots config + hw_virtual + zedmd against a mocked libzedmd, and
Godot's "rgb_dmd_frame" BCP message reaches the device as a 128x32 RGB picture (MPF's zedmd platform renders it)."""
from unittest.mock import MagicMock, patch

from mpf.devices.rgb_dmd import RgbDmd
from mpf.platforms import zedmd

from tests.tron_test import TronTestCase

WIDTH, HEIGHT = 128, 32


class TestZeDmd(TronTestCase):
    def get_config_file(self):
        return "../../tests/machine_zedmd.yaml"

    def get_platform(self):
        return False

    def setUp(self):
        self.matrix = MagicMock()
        # the compiled libzedmd of MPF 0.80.1 only loads on the Python it was built for: its extension is mocked
        self.patches = [patch.object(zedmd, "IMPORT_LIB_FAILED", None),
                        patch.object(zedmd, "ZeDMD_ext", create=True, return_value=self.matrix)]
        for p in self.patches:
            p.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        for p in self.patches:
            p.stop()

    def device(self):
        return self.machine.rgb_dmds["default"].hw_device

    def test_device_is_the_zedmd_platform(self):
        self.assertIsInstance(self.device(), zedmd.ZeDmdDevice)
        self.assertEqual((WIDTH, HEIGHT), (self.device().config["width"], self.device().config["height"]))

    def test_bcp_frame_reaches_the_device(self):
        data = bytes((255, 0, 0)) * (WIDTH * HEIGHT)
        self.loop.run_until_complete(RgbDmd._bcp_receive_dmd_frame(self.machine, None, "default", data))
        image = self.matrix.RenderRgb888.call_args[0][0]
        self.assertEqual((WIDTH, HEIGHT), image.size)
        self.assertEqual((255, 0, 0), image.getpixel((5, 7)))

    def test_no_pin2dmd_in_the_zedmd_overlay(self):
        self.assertNotIn("pin2dmd", self.machine.config)
