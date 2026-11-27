"""deff 26 SHOOT AGAIN [0x0101254c] ends with its speech: the loop (6 ticks per pass, 25 passes at most) checks every
second pass (even index) whether sound 0x11b's sample is still playing (FUN_0002cd90) and stops at the first check that
finds it ended, then deff_hold_frames(10, 0x20). The length is therefore a function of the sample length, which the ROM
run in Unicorn cannot show (no sound board): assets/tools/os_deff_runs.py gives the 25-pass limit, 25*6+10 ticks."""
import csv
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.01626


def deff26_ticks(sample_s):
    sample = sample_s / TICK
    for passes in range(1, 26):
        index = passes - 1
        if index % 2 == 0 and passes * 6 >= sample or passes == 25:
            return passes * 6 + 10
    return 25 * 6 + 10


class TestDeff26(unittest.TestCase):

    def test_length_follows_the_sample(self):
        with open(os.path.join(ROOT, "assets", "callouts", "samples_index.csv"), encoding="utf-8") as f:
            sample = [float(r["duration_s"]) for r in csv.DictReader(f) if int(r["sample_id"], 16) == 0x184][0]
        with open(os.path.join(ROOT, "assets", "mpf_package", "media", "dmd", "deff_026_shoot_again", "timing.json")) as f:
            run = json.load(f)["run_seconds"] / TICK
        self.assertLessEqual(abs(deff26_ticks(sample) - run), 3, (sample, run))


if __name__ == "__main__":
    unittest.main()
