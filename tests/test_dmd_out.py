"""scripts/dmd_out.py: the RGB DMD output is the platform's (MPF-Godot-Packaging); this game only installs it."""
import os
import subprocess
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


    def test_serum_env(self):
        """--zedmd-serum: the colouriser gets the colourisation's folder, the ROM name, Tron blue for unknown frames and the plain
        feeder to pipe to, in the environment (the add-on cannot pass it arguments)."""
        env = dmd_out.serum_env("/x/altcolor", "/y/zedmd_feed", "#2a6cff")
        self.assertEqual({"DMD_SERUM_ARGS": "--serum|/x/altcolor|--rom|trn_174h|--color|2a6cff|--feeder|/y/zedmd_feed"}, env)

    def test_a_bundle_never_compiles_the_tools(self):
        """Without a .git folder (a bundle) the tools are only the ones built offline for this CPU; a development checkout builds."""
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, "game")
            with mock.patch.object(dmd_out.tc, "ROOT", root), mock.patch.object(dmd_out.tc, "GAME", game), \
                    mock.patch.object(dmd_out, "build_serum") as build:
                self.assertIsNone(dmd_out.prebuilt("dmd_serum"))
                self.assertIsNone(dmd_out.serum_filter())
                build.assert_not_called()                      # no .git: nothing is built here
                exe = os.path.join(game, "native", "bin", dmd_out.arch(), "dmd_serum")
                os.makedirs(os.path.dirname(exe))
                open(exe, "w").close()
                self.assertEqual(exe, dmd_out.prebuilt("dmd_serum"))
                self.assertEqual(exe, dmd_out.serum_filter())
                os.makedirs(os.path.join(root, ".git"))
                os.remove(exe)
                dmd_out.serum_filter()
                build.assert_called_once()                     # a development checkout builds on first use

    def test_the_colouriser_probes_the_feeder_and_needs_its_file(self):
        """dmd_serum (built by the bundle's build or by hand) returns the feeder's --probe code, and refuses a missing .cROMc."""
        import tempfile
        exe = dmd_out.prebuilt("dmd_serum")
        if not exe:
            self.skipTest("dmd_serum is not built (game/native/dmd_serum/build.sh OUT)")
        probe = subprocess.run([exe, "--serum", "x", "--rom", "y", "--feeder", "/bin/false", "--probe"], capture_output=True)
        self.assertEqual(1, probe.returncode)
        with tempfile.TemporaryDirectory() as empty:
            run = subprocess.run([exe, "--serum", empty, "--rom", "trn_174h", "--feeder", "/bin/cat"], input=b"", capture_output=True)
            self.assertEqual(1, run.returncode)
            self.assertIn(b"not loaded", run.stderr)


if __name__ == "__main__":
    unittest.main()
