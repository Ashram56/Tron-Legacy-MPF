"""The PIN2DMD output (game/config/pin2dmd.yaml): MPF boots config + hw_virtual + pin2dmd against a mocked pyusb,
Godot's "rgb_dmd_frame" BCP message reaches the device, and MPF's pin2dmd platform turns the 128x32 RGB frame into the
PIN2DMD's USB packet (4 header bytes 81 C3 E9 12, then 6 bit planes of 2048 bytes)."""
from unittest.mock import MagicMock, patch

from mpf.devices.rgb_dmd import RgbDmd
from mpf.platforms import pin2dmd

from tests.test_proc import ProcCase
from tests.tron_test import TronTestCase

WIDTH, HEIGHT = 128, 32
PLANE = WIDTH * HEIGHT // 2          # one bit plane: 2048 bytes, a dot of the upper half and one of the lower per byte


def frame(top=(0, 0, 0), bottom=(0, 0, 0)):
    """A 128x32 RGB frame: the upper 16 rows in one colour, the lower 16 in another."""
    return bytes(top) * (WIDTH * HEIGHT // 2) + bytes(bottom) * (WIDTH * HEIGHT // 2)


class Pin2DmdCase(TronTestCase):
    def get_config_file(self):
        return "../../tests/machine_pin2dmd.yaml"

    def get_platform(self):
        return False

    def setUp(self):
        self.usb_device = MagicMock()
        self.patches = [patch.object(pin2dmd.usb.core, "find", return_value=self.usb_device)]
        for p in self.patches:
            p.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        for p in self.patches:
            p.stop()

    def send(self, data):
        """The frame as the platform's feeder thread writes it to the device (the test loop has no executor thread)."""
        device = self.machine.rgb_dmds["default"].hw_device
        device._send_frame(bytearray(data))
        endpoint, packet = self.usb_device.write.call_args[0][:2]
        self.assertEqual(0x01, endpoint)
        return bytes(packet)


class TestPin2Dmd(Pin2DmdCase):
    def test_device_found_with_the_pin2dmd_ids(self):
        pin2dmd.usb.core.find.assert_called_with(idVendor=0x0314, idProduct=0xE457)
        self.assertEqual("128x32", self.machine.rgb_dmds["default"].hw_device.resolution)

    def test_bcp_frame_reaches_the_device(self):
        packet = self.send(frame(top=(255, 0, 0)))
        self.assertEqual([0x81, 0xC3, 0xE9, 18], list(packet[:4]))
        planes = packet[4:]
        # red in the upper half, nothing in the lower: bit 0 (red) of every byte, bit 3 (red, lower half) never
        top_bit = 0
        for plane in range(6):
            self.assertEqual(1, len({b & 0b11 for b in planes[plane * PLANE:(plane + 1) * PLANE]}))
            top_bit |= planes[plane * PLANE] & 1
        self.assertEqual(1, top_bit)
        self.assertTrue(all(b & 0b111110 == 0 for b in planes))     # green, blue and the whole lower half stay dark

    def test_lower_half_is_its_own_channel_bits(self):
        planes = self.send(frame(bottom=(255, 255, 255)))[4:]
        self.assertTrue(all(b & 0b111000 == 0b111000 for b in planes[5 * PLANE:6 * PLANE]))   # the top plane
        self.assertTrue(all(b & 0b000111 == 0 for b in planes))

    def test_rgb_dmd_frame_over_bcp(self):
        """Godot's message: MPF's rgb_dmds device hands the 12288 bytes to the platform's feeder."""
        data = frame(top=(1, 2, 3))
        self.loop.run_until_complete(RgbDmd._bcp_receive_dmd_frame(self.machine, None, "default", data))
        device = self.machine.rgb_dmds["default"].hw_device
        self.assertEqual(data, bytes(device.current_frame))
        self.assertTrue(device.new_frame_event.is_set())

    def test_black_frame_is_black(self):
        self.assertEqual(0, sum(self.send(frame())[4:]))


class TestPin2DmdOnTheProc(ProcCase):
    """The real machine: hw_proc + pin2dmd with a mocked P-ROC. The PIN2DMD takes the DMD; the P-ROC's DMD device
    goes to the virtual platform."""

    def get_config_file(self):
        return "../../tests/machine_proc_pin2dmd.yaml"

    def setUp(self):
        self.find = patch.object(pin2dmd.usb.core, "find", return_value=MagicMock())
        self.find.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.find.stop()

    def test_pin2dmd_replaces_the_proc_dmd(self):
        self.assertEqual("virtual", self.machine.dmds["dmd"].config["platform"])
        self.assertEqual("128x32", self.machine.rgb_dmds["default"].hw_device.resolution)
