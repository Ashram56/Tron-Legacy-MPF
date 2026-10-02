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
    "game_flow": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "game_flow_tilt": "score,deff_start,sound,tube_show_start,audit,multiball_start,mark",
    "attract_and_service": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "bonus": "multiball_start,mark",
    "bonus_skip": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "skill_shots": "leff_start,tube_show_start,audit,multiball_start,mark",
    "skill_shots_b": "score,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "skill_shots_c": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "switches_and_shots": "audit,multiball_start,mark",
    "find_flynn_and_items": "score,sound,audit,multiball_start,mark",
    "flynns_arcade": "score,sound,audit,multiball_start,mark",
    "sea_of_simulation": "deff_start,audit,multiball_start,mark",
    "portal_multiball": "multiball_start,mark",
    "portal_multiball_shots": "mark",
    "combos": "sound,audit,multiball_start,mark",
    "combos_eol_jackpot": "multiball_start,mark",
    "tron_targets": "audit,multiball_start,mark",
    "zen_rollover": "score,deff_start,sound,leff_start,audit,multiball_start,mark",
    "recognizer_and_disc_battle": "score,deff_start,leff_start,tube_show_start,audit,multiball_start,mark",
    "disc_multiball": "tube_show_start,multiball_start,mark",
    "disc_multiball_restart": "score,deff_start,audit,multiball_start,mark",
    # End of Line: the other kinds differ only through features not built yet (Flynn's Arcade
    # Recognizer/GEM awards at the VUK, Light Cycle progress deff 83, combo arrows leff 159)
    "end_of_line_multiball": "score,multiball_start,mark",
    "end_of_line_multiball_scoring": "multiball_start,mark",
    "daft_punk_multiball": "multiball_start,mark",
    "clu_hurryup": "score,sound,tube_show_start,audit,multiball_start,mark",
    "gem_hurryup": "score,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "zuse_fast_scoring": "audit,multiball_start,mark",
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
