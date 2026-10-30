"""scripts/dmd_out.py: the RGB DMD output is the platform's (MPF-Godot-Packaging); this game only installs it."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import dmd_out  # noqa: E402


class TestDmdOut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.plat = os.path.join(self.tmp, "plat")
        os.makedirs(os.path.join(self.plat, "addons", "dmd_out"))
        os.makedirs(os.path.join(self.plat, "examples", "dmd_devices"))
        open(os.path.join(self.plat, "addons", "dmd_out", "dmd_out.gd"), "w").write("extends Node\n")
        open(os.path.join(self.plat, "addons", "dmd_out", "dmd_out.gd.uid"), "w").write("uid://x\n")
        for n in ("pin2dmd.yaml", "zedmd.yaml", "zedmd_feed.yaml"):
            open(os.path.join(self.plat, "examples", "dmd_devices", n), "w").write("#config_version=6\n")
        self.game = os.path.join(self.tmp, "game")
        os.makedirs(os.path.join(self.game, "config"))
        self.saved = {k: os.environ.pop(k, None) for k in ("MPF_GODOT_PACKAGING", "MPF_PLATFORM_DIR")}
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) for k, v in self.saved.items() if v])

    def test_found_by_environment(self):
        os.environ["MPF_GODOT_PACKAGING"] = self.plat
        self.assertEqual(dmd_out.platform_dir(), self.plat)

    def test_prepare_installs_the_addon_and_the_device_overlays_only(self):
        os.environ["MPF_GODOT_PACKAGING"] = self.plat
        env = dmd_out.prepare("pin2dmd", self.game)
        self.assertTrue(os.path.isfile(os.path.join(self.game, "addons", "dmd_out", "dmd_out.gd")))
        self.assertFalse(os.path.exists(os.path.join(self.game, "addons", "dmd_out", "dmd_out.gd.uid")))
        self.assertEqual(sorted(os.listdir(os.path.join(self.game, "config"))), ["pin2dmd.yaml"])
        self.assertTrue(env["PYTHONPATH"].startswith(self.plat))
        dmd_out.prepare("zedmd", self.game)
        self.assertEqual(sorted(os.listdir(os.path.join(self.game, "config"))),
                         ["pin2dmd.yaml", "zedmd.yaml", "zedmd_feed.yaml"])

    def test_without_the_platform_the_error_names_it(self):
        os.environ["MPF_GODOT_PACKAGING"] = os.path.join(self.tmp, "nothing")
        if dmd_out.platform_dir():
            self.skipTest("a platform checkout sits beside this repository")
        with self.assertRaises(SystemExit) as e:
            dmd_out.prepare("pin2dmd", self.game)
        self.assertIn("MPF-Godot-Packaging", str(e.exception))
        self.assertEqual(dmd_out.detect(), "")


    def test_serum_args(self):
        """--zedmd-serum: the feeder gets shades, the colourisation's folder and ROM name, and Tron blue for unknown frames."""
        feed, shades = dmd_out.serum_args("/x/altcolor", "#2a6cff")
        self.assertEqual("--zedmd-shades", shades)
        self.assertEqual("--zedmd-feed-args=--shades|--serum|/x/altcolor|--rom|trn_174h|--color|2a6cff", feed)

if __name__ == "__main__":
    unittest.main()
