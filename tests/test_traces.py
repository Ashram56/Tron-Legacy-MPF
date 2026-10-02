"""Regression: replay ROM reference scenarios and compare with the ROM traces.

TRACES lists, per scenario, the event kinds that already match the ROM. A feature that makes more
kinds match adds them here.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

TRACES = {
    "game_flow": "score,deff_start,sound,audit,mark",
    "combos": "audit,multiball_start,mark",
    "combos_eol_jackpot": "multiball_start,mark",
    "tron_targets": "multiball_start,mark",
    "zen_rollover": "score,deff_start,audit,multiball_start,mark",
}


class TestTraces(unittest.TestCase):

    def test_scenarios(self):
        for name, kinds in TRACES.items():
            with self.subTest(scenario=name):
                run = subprocess.run([sys.executable, "-m", "tests.scenario", name], cwd=ROOT,
                                     capture_output=True, text=True)
                self.assertEqual(0, run.returncode, run.stderr[-2000:])
                cmp = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "trace_check.py"), name,
                                      "--events", kinds], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(0, cmp.returncode, cmp.stdout)
