"""Recording of a played game and its replay (tron/recording.py): times kept, the seed saved, the replay as long."""
import json
import os
import tempfile
from unittest import mock

from tests.tron_test import TronTestCase


class TestRecording(TronTestCase):

    def session(self, **env):
        from tron.recording import Session
        with mock.patch.dict(os.environ, env, clear=False):
            return Session(self.tron)

    def test_clock_format(self):
        from tron.recording import clock
        self.assertEqual("00:00.0", clock(0))
        self.assertEqual("01:05.5", clock(65.5))

    def test_no_recording_without_env(self):
        s = self.session(TRON_RECORD_DIR="", TRON_REPLAY="")
        self.assertIsNone(s.game_seed())

    def test_records_times_and_seed(self):
        d = tempfile.mkdtemp()
        s = self.session(TRON_RECORD_DIR=d, TRON_REPLAY="", TRON_SEED="12345")
        s._attract_started()
        self.advance_time_and_run(2)
        self.hit_and_release_switch("s_left_flipper")
        self.advance_time_and_run(1.5)
        self.hit_and_release_switch("s_right_flipper")
        self.assertEqual(12345, s.game_seed())
        s._finish()
        files = [f for f in os.listdir(d) if f.endswith(".json")]
        self.assertEqual(1, len(files))
        data = json.load(open(os.path.join(d, files[0])))
        self.assertEqual(12345, data["seed"])
        ev = [e for e in data["events"] if e[1] in ("s_left_flipper", "s_right_flipper")]
        self.assertEqual(["on", "off", "on", "off"], [e[2] for e in ev])
        self.assertGreater(ev[2][0] - ev[0][0], 1.4)           # the gap between the presses is kept
        # the same seed gives the same draws
        self.tron.random.seed(12345)
        a = [self.tron.random.random() for _ in range(3)]
        s.game_seed()
        self.assertEqual(a, [self.tron.random.random() for _ in range(3)])

    def test_no_file_without_a_game(self):
        d = tempfile.mkdtemp()
        s = self.session(TRON_RECORD_DIR=d, TRON_REPLAY="")
        s._attract_started()
        self.hit_and_release_switch("s_left_flipper")
        s._finish()
        self.assertEqual([], os.listdir(d))

    def test_replay_presses_at_the_times(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "r.json")
        json.dump({"format": 1, "seed": 7, "events": [[1.0, "s_left_flipper", "on"], [1.2, "s_left_flipper", "off"],
                                                       [3.0, "s_right_flipper", "tap"]]}, open(path, "w"))
        s = self.session(TRON_REPLAY=path, TRON_RECORD_DIR="")
        s._attract_started()
        self.advance_time_and_run(2)
        self.assertEqual(7, s.game_seed())
        self.advance_time_and_run(3)
        text = open(os.path.join(d, "r.timeline.txt")).read()
        self.assertIn("00:01.0  s_left_flipper on", text)
        self.assertIn("00:03.0  s_right_flipper tap", text)
        self.assertIn("seed 7", text)
