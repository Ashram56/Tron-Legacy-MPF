"""The game's side of the remote topper: scripts/pup/topper_media.py on a small pack. The server, the PinUP rules and the
Raspberry Pi agent are the platform's (MPF-Godot-Packaging, mpf_godot/pup_remote/, tested there)."""
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mpf_platform  # noqa: E402

PLATFORM = mpf_platform.platform_dir()


def load_topper():
    spec = importlib.util.spec_from_file_location(
        "topper", os.path.join(PLATFORM, "mpf_godot", "pup_remote", "topper", "topper.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(PLATFORM and os.path.isdir(os.path.join(PLATFORM, "mpf_godot", "pup_remote")),
                     "needs the platform with pup_remote")
@unittest.skipUnless(__import__("shutil").which("ffmpeg"), "needs ffmpeg")
class TestTopperMedia(unittest.TestCase):
    """scripts/pup/topper_media.py on a small pack: the topper's playlists only, copied unless the Pi can't decode."""

    def test_build(self):
        import subprocess
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "scripts", "pup"))
        import topper_media
        with tempfile.TemporaryDirectory() as d:
            pack, out = os.path.join(d, "pack"), os.path.join(d, "out")
            for folder in ("Background - Topper", "TopperEvents", "Drain"):
                os.makedirs(os.path.join(pack, folder))
            with open(os.path.join(pack, "triggers.pup"), "w") as f:
                f.write("ID,Active,Descript,Trigger,ScreenNum,PlayList,PlayFile,Volume,Priority,Length,Counter,"
                        "RestSeconds,Loop\n1,1,x,D1,14,TopperEvents,,,1,,,0,\n2,1,x,D14,2,Drain,,,1,,,0,\n")
            with open(os.path.join(pack, "screens.pup"), "w") as f:
                f.write("ScreenNum,ScreenDes,PlayList,PlayFile,Loopit,Active\n"
                        "13,Topper,Background - Topper,Logo.mp4,1,Show\n2,Backglass,Drain,,0,Show\n")

            def video(path, *args):
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                                "testsrc=size=64x32:rate=30:duration=0.2"] + list(args) + [path], check=True)
            video(os.path.join(pack, "Background - Topper", "Logo.mp4"), "-c:v", "libx264", "-pix_fmt", "yuv420p")
            video(os.path.join(pack, "TopperEvents", "Jackpot.mp4"), "-c:v", "libx264", "-pix_fmt", "yuv444p")
            video(os.path.join(pack, "Drain", "Drain1.mp4"), "-c:v", "libx264", "-pix_fmt", "yuv420p")
            manifest = topper_media.build(pack, out)
            self.assertEqual({"Background - Topper/Logo.mp4", "TopperEvents/Jackpot.mp4"}, set(manifest))
            self.assertNotIn("reencoded", manifest["Background - Topper/Logo.mp4"])
            self.assertIn("4:4:4", manifest["TopperEvents/Jackpot.mp4"]["reencoded"])
            info = topper_media.probe("ffmpeg", os.path.join(out, "TopperEvents", "Jackpot.mp4"))
            self.assertEqual("", topper_media.why_reencode(info))
            lib = tron_topper.load_library(out)
            self.assertTrue(os.path.exists(lib.path(lib.pick("TopperEvents"))))

    def test_limits(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "pup"))
        import topper_media
        ok = {"codec": "h264", "profile": "high", "pix_fmt": "yuv420p", "w": 1920, "h": 1080, "fps": 30.0}
        self.assertEqual("", topper_media.why_reencode(ok))
        self.assertEqual("60 fps", topper_media.why_reencode(dict(ok, fps=60.0)))
        self.assertEqual("2560x1080", topper_media.why_reencode(dict(ok, w=2560)))
        self.assertEqual("codec hevc", topper_media.why_reencode(dict(ok, codec="hevc")))
        self.assertIn("yuv420p10le", topper_media.why_reencode(dict(ok, profile="", pix_fmt="yuv420p10le")))


if __name__ == "__main__":
    unittest.main()
