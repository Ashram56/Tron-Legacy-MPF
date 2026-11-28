"""The clip Python names (the deff's random_below(n) drawn with the ROM's generator) is the one Godot plays.

Runs tests/godot/variant_clip_check.gd with the pinned Godot under Xvfb (software rendering); skipped only when the
Godot executable or xvfb-run is missing (setup.py installs Godot).
"""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestGodotVariantClip(unittest.TestCase):

    def test_named_clip_is_played(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import toolchain
        godot = toolchain.godot_path()
        xvfb = shutil.which("xvfb-run")
        if not os.path.exists(godot) or not xvfb:
            self.skipTest("Godot or xvfb-run missing")
        run = subprocess.run([xvfb, "-a", godot, "--headless", "--path", os.path.join(ROOT, "game"), "--script",
                              os.path.join(ROOT, "tests", "godot", "variant_clip_check.gd")],
                             capture_output=True, text=True, timeout=240)
        out = run.stdout
        self.assertEqual(5, out.count("CLIP want="), out[-1500:])
        self.assertIn("CLIPCHECK OK", out, out[-1500:])


if __name__ == "__main__":
    unittest.main()
