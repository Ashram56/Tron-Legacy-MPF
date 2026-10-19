"""Remote PuP screens: PinUP Player's rules in Python (screen_rules.py), the game's server (tron_pup/remote.py) and the
remote topper's agent (remote/topper/tron_topper.py), linked over the loopback with a fake mpv."""
import asyncio
import importlib.util
import json
import os
import random
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "game"))
from tron_pup import remote, screen_rules   # noqa: E402

_spec = importlib.util.spec_from_file_location("tron_topper", os.path.join(ROOT, "remote", "topper", "tron_topper.py"))
tron_topper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tron_topper)

FILES = ["Background - Topper/TronLegacyLogo.mp4", "TopperModes/CLU.mp4", "TopperModes/Gem.mp4",
         "TopperEvents/Jackpot2.mp4", "TopperEvents/Jackpot10.mp4", "TopperEvents/Jackpot1.mp4"]


class Output:
    def __init__(self):
        self.log, self.visible = [], None

    def start(self, key, loop, volume):
        self.log.append(("start", key, loop))

    def stop(self):
        self.log.append(("stop",))

    def set_visible(self, visible):
        self.visible = visible


class Timers:
    def __init__(self):
        self.pending = []

    def __call__(self, seconds, callback):
        self.pending.append((seconds, callback))

    def fire(self):
        pending, self.pending = self.pending, []
        for _s, cb in pending:
            cb()


def library(playlists=None):
    return screen_rules.Library({k: "/media/" + k for k in FILES}, playlists, rng=random.Random(1))


class TestScreenRules(unittest.TestCase):

    def screen(self, popup=False, bg=("Background - Topper", "TronLegacyLogo.mp4")):
        self.out, self.timers = Output(), Timers()
        return screen_rules.Screen(13, library(), self.out, self.timers, popup=popup, bg_playlist=bg[0],
                                   bg_file=bg[1])

    def test_background_then_priority(self):
        s = self.screen()
        s.start_background()
        self.assertEqual(("start", "Background - Topper/TronLegacyLogo.mp4", True), self.out.log[-1])
        s.command({"playlist": "TopperModes", "file": "CLU", "priority": 5, "mode": "Loop"})
        self.assertEqual(("start", "TopperModes/CLU.mp4", True), self.out.log[-1])
        s.command({"playlist": "TopperModes", "file": "Gem.mp4", "priority": 4})           # lower: dropped
        self.assertEqual("TopperModes/CLU.mp4", s.key)
        s.command({"playlist": "TopperModes", "file": "Gem", "priority": 5, "mode": "SkipSamePrty"})
        self.assertEqual("TopperModes/CLU.mp4", s.key)
        s.command({"playlist": "TopperModes", "file": "clu", "mode": "StopFile"})          # the background back
        self.assertEqual(("start", "Background - Topper/TronLegacyLogo.mp4", True), self.out.log[-1])

    def test_video_end_and_length(self):
        s = self.screen()
        s.start_background()
        s.command({"playlist": "TopperModes", "file": "Gem", "priority": 1})
        self.assertFalse(s.loop)
        s.finished()
        self.assertEqual("Background - Topper/TronLegacyLogo.mp4", s.key)
        s.command({"playlist": "TopperModes", "file": "Gem", "priority": 1, "length": 3})
        self.timers.fire()
        self.assertEqual("Background - Topper/TronLegacyLogo.mp4", s.key)

    def test_stale_length_timer(self):
        s = self.screen()
        s.command({"playlist": "TopperModes", "file": "Gem", "priority": 1, "length": 3})
        s.command({"playlist": "TopperModes", "file": "CLU", "priority": 1, "mode": "Loop"})
        self.timers.fire()                                   # Gem's timer: CLU plays on
        self.assertEqual("TopperModes/CLU.mp4", s.key)

    def test_popup_hides(self):
        s = self.screen(popup=True, bg=("", ""))
        self.assertFalse(self.out.visible)
        s.command({"playlist": "TopperEvents", "priority": 1})
        self.assertTrue(self.out.visible)
        s.finished()
        self.assertFalse(self.out.visible)
        self.assertEqual(("stop",), self.out.log[-1])
        s.command({"playlist": "TopperEvents", "priority": 1, "mode": "StopPlayer"})
        self.assertFalse(self.out.visible)

    def test_set_bg(self):
        s = self.screen()
        s.command({"playlist": "TopperModes", "file": "Gem", "mode": "SetBG"})
        self.assertEqual(("start", "TopperModes/Gem.mp4", True), self.out.log[-1])

    def test_pick(self):
        lib = library({"topperevents": {"alpha_sort": True, "volume": 50}})
        firsts = [lib.pick("TopperEvents") for _ in range(4)]
        names = ["TopperEvents/Jackpot1.mp4", "TopperEvents/Jackpot2.mp4", "TopperEvents/Jackpot10.mp4"]
        start = names.index(firsts[0])
        self.assertEqual([names[(start + i) % 3] for i in range(4)], firsts)      # natural order, wraps
        self.assertEqual(0.5, lib.volume_of({"playlist": "TopperEvents"}))
        self.assertEqual(0.8, lib.volume_of({"playlist": "TopperEvents", "volume": 80}))
        lib = library()
        picks = [lib.pick("TopperModes") for _ in range(10)]
        self.assertTrue(all(a != b for a, b in zip(picks, picks[1:])))         # random, never twice in a row
        self.assertEqual("", lib.pick("Nothing"))
        self.assertEqual("", lib.pick("TopperModes", "missing.mp4"))


class FakeMpv:
    def __init__(self):
        self.plays, self.path, self.position, self.on_eof = [], "", 0.0, None

    def play(self, path, loop, volume, start=0.0):
        self.path = path
        self.plays.append((os.path.basename(path), loop, round(start, 1)))

    def clear(self):
        self.path = ""
        self.plays.append(None)


SCREENS = {13: {"playlist": "Background - Topper", "file": "TronLegacyLogo.mp4", "active": "Show"},
           14: {"playlist": "", "file": "", "active": "ForcePopBack"}}


class TestDisplay(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.mpv = FakeMpv()
        self.display = tron_topper.Display(self.mpv, library())
        server = remote.RemoteServer(SCREENS, {})
        self.welcome = server.welcome([13, 14])

    def tearDown(self):
        self.loop.close()

    def test_popup_over_underlay_then_resume(self):
        self.display.setup(self.welcome["screens"], {}, [13, 14])
        self.assertEqual([("TronLegacyLogo.mp4", True, 0.0)], self.mpv.plays)
        self.mpv.position = 12.5
        self.display.command({"screen": 14, "playlist": "TopperEvents", "file": "Jackpot1", "priority": 1})
        self.assertEqual(("Jackpot1.mp4", False, 0.0), self.mpv.plays[-1])
        self.mpv.on_eof()                                    # the pop-up ends: the logo where it was
        self.assertEqual(("TronLegacyLogo.mp4", True, 12.5), self.mpv.plays[-1])

    def test_rejoin_keeps_the_loop(self):
        self.display.setup(self.welcome["screens"], {}, [13, 14])
        self.display.setup(self.welcome["screens"], {}, [13, 14])
        self.assertEqual(1, len(self.mpv.plays))
        cmd = {"screen": 13, "playlist": "TopperModes", "file": "CLU", "priority": 2, "mode": "Loop"}
        self.display.setup(self.welcome["screens"], {}, [13, 14], [cmd])       # the game says CLU runs
        self.display.setup(self.welcome["screens"], {}, [13, 14], [cmd])
        self.assertEqual([("TronLegacyLogo.mp4", True, 0.0), ("CLU.mp4", True, 0.0)], self.mpv.plays)

    def test_underlay_changes_under_popup(self):
        self.display.setup(self.welcome["screens"], {}, [13, 14])
        self.display.command({"screen": 14, "playlist": "TopperEvents", "file": "Jackpot1", "priority": 1})
        self.display.command({"screen": 13, "playlist": "TopperModes", "file": "Gem", "priority": 1,
                              "mode": "Loop"})
        self.assertEqual(("Jackpot1.mp4", False, 0.0), self.mpv.plays[-1])    # covered: nothing shown changes
        self.mpv.on_eof()
        self.assertEqual(("Gem.mp4", True, 0.0), self.mpv.plays[-1])


class TestServer(unittest.TestCase):

    def test_current_state(self):
        server = remote.RemoteServer(SCREENS, {})
        server.send({"screen": 13, "playlist": "TopperModes", "file": "Gem", "mode": "SetBG"})
        server.send({"screen": 13, "playlist": "TopperModes", "file": "CLU", "priority": 3, "mode": "Loop"})
        server.send({"screen": 13, "playlist": "TopperEvents", "priority": 1})           # lower: the loop goes on
        server.send({"screen": 14, "playlist": "TopperEvents", "priority": 9})
        self.assertEqual(["Gem", "CLU"], [c["file"] for c in server.current([13, 14])])
        server.send({"screen": 13, "playlist": "TopperModes", "file": "Gem.mp4", "mode": "StopFile"})
        self.assertEqual(2, len(server.current([13])))                                    # not the running loop
        server.send({"screen": 13, "playlist": "TopperModes", "file": "clu", "mode": "StopFile"})
        self.assertEqual(["Gem"], [c["file"] for c in server.current([13])])
        server.send({"screen": 13, "playlist": "TopperModes", "file": "CLU", "priority": 3, "mode": "Loop"})
        server.send({"screen": 13, "playlist": "TopperEvents", "priority": 3})            # replaces it
        self.assertEqual(["Gem"], [c["file"] for c in server.current([13])])
        welcome = server.welcome([13, 14])
        self.assertEqual({"bg_playlist": "Background - Topper", "bg_file": "TronLegacyLogo.mp4", "popup": False},
                         welcome["screens"]["13"])
        self.assertTrue(welcome["screens"]["14"]["popup"])
        json.dumps(welcome)

    def test_link(self):
        """Discovery, welcome with the current state, live commands to the screens asked for, then the game gone."""
        async def scenario():
            server = remote.RemoteServer(SCREENS, {"topperevents": {"alpha_sort": True, "volume": 100}},
                                         game="trn_174h", host="127.0.0.1", port=0, ping_seconds=0.2)
            await server.start()
            found = await tron_topper.discover(server.port, target="127.0.0.1")
            self.assertEqual(("127.0.0.1", server.port), found)
            server.send({"screen": 13, "playlist": "TopperModes", "file": "CLU", "priority": 3, "mode": "Loop"})
            mpv = FakeMpv()
            display = tron_topper.Display(mpv, library())
            opts = tron_topper.load_config(None, {"host": "127.0.0.1", "port": str(server.port), "timeout": "1"})
            link = asyncio.ensure_future(tron_topper.session(opts, display, [13, 14]))
            for _ in range(50):
                await asyncio.sleep(0.02)
                if server.clients:
                    break
            self.assertEqual([("CLU.mp4", True, 0.0)], mpv.plays)
            self.assertTrue(display.library.playlists["topperevents"]["alpha_sort"])
            server.send({"screen": 14, "playlist": "TopperEvents", "file": "Jackpot2", "priority": 1})
            server.send({"screen": 2, "playlist": "Drain", "priority": 1})                # not a topper screen
            await asyncio.sleep(0.5)                                                      # pings keep it up
            self.assertEqual(("Jackpot2.mp4", False, 0.0), mpv.plays[-1])
            self.assertEqual(2, len(mpv.plays))
            server.close()
            self.assertTrue(await asyncio.wait_for(link, 3))
        asyncio.run(scenario())

    def test_nobody_answers(self):
        async def scenario():
            with socket_port() as port:
                self.assertIsNone(await tron_topper.discover(port, timeout=0.2, target="127.0.0.1"))
        asyncio.run(scenario())


class socket_port:
    """A free UDP port nobody answers on."""
    def __enter__(self):
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        return self.sock.getsockname()[1]

    def __exit__(self, *exc):
        self.sock.close()


class TestAgent(unittest.TestCase):

    def test_mpv_args(self):
        opts = tron_topper.load_config(None, {})
        args = tron_topper.Mpv(opts).args()
        for arg in ("--fullscreen", "--panscan=1.0", "--aid=no", "--hwdec=v4l2m2m-copy", "--video-align-y=0.000"):
            self.assertIn(arg, args)
        args = tron_topper.Mpv(tron_topper.load_config(None, {"window": "true", "audio": "true"})).args()
        self.assertIn("--geometry=960x281", args)
        self.assertNotIn("--fullscreen", args)
        self.assertNotIn("--aid=no", args)

    def test_example_config(self):
        opts = tron_topper.load_config(os.path.join(ROOT, "remote", "topper", "tron-topper.cfg"), {})
        self.assertEqual(set(tron_topper.DEFAULTS), set(opts))

    def test_same_rules_file(self):
        # the installer copies game/tron_pup/screen_rules.py next to the agent: one file, no copy in git
        self.assertFalse(os.path.exists(os.path.join(ROOT, "remote", "topper", "screen_rules.py")))
        self.assertEqual(os.path.join(ROOT, "game", "tron_pup", "screen_rules.py"), tron_topper.screen_rules.__file__)

    def test_library_from_manifest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "manifest.json"), "w") as f:
                json.dump({"files": {"TopperModes/CLU.mp4": {"out": "TopperModes/CLU.mp4"}}}, f)
            lib = tron_topper.load_library(d)
            self.assertEqual(os.path.join(d, "TopperModes/CLU.mp4"), lib.path(lib.pick("TopperModes", "CLU")))


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
