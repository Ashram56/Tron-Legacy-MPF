"""The PinMAME / Godot DMD comparison (scripts/conform/dmd_conform.py) on synthetic dumps."""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "conform"))
import dmd_conform  # noqa: E402


def dmd(path, frames):
    with open(path, "wb") as f:
        for t, shades in frames:
            f.write(struct.pack("<d3i", t, 128, 32, 4) + bytes(shades))


class TestConform(unittest.TestCase):

    def test_pair_and_load(self):
        a = [(5, 0.0), (1, 0.0), (10, 8.5)]
        b = [(1, 0.0), (10, 1.5)]
        self.assertEqual(dmd_conform.pair(a, b), [(1, 0), (2, 1)])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.dmd")
            dmd(p, [(0.5, [3] * 4096), (1.0, [4] * 4096)])
            ts, fr = dmd_conform.load_dmd(p)
            self.assertEqual(list(ts), [0.5, 1.0])
            self.assertEqual(fr[1][0], 4)
            self.assertIs(dmd_conform.at(ts, fr, 0.2), None)
            self.assertEqual(dmd_conform.at(ts, fr, 0.7)[0], 3)

    def test_identical_dumps_match_with_a_clock_offset(self):
        with tempfile.TemporaryDirectory() as d:
            rd, gd = os.path.join(d, "r.dmd"), os.path.join(d, "g.dmd")
            frames = [(k * 0.1, [k % 16] * 4096) for k in range(20)]
            dmd(rd, frames)
            dmd(gd, [(t + 1000.0, s) for t, s in frames])      # Godot's wall clock
            rt, gt = os.path.join(d, "r.jsonl"), os.path.join(d, "g.jsonl")
            open(rt, "w").write(json.dumps({"ev": "deff_start", "id": 7, "t": 0.0}) + "\n")
            open(gt, "w").write(json.dumps({"ev": "deff_start", "id": 7, "wall": 1000.0}) + "\n")
            self.assertEqual(dmd_conform.starts(rt, "t"), [(7, 0.0)])
            out = os.popen("%s %s %s %s %s %s" % (sys.executable, dmd_conform.__file__, rd, rt, gd, gt)).read()
            self.assertIn("frames found overall: 16 / 16 (100.0%)", out)


if __name__ == "__main__":
    unittest.main()
