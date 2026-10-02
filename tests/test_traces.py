"""Regression: replay ROM reference scenarios and compare with the ROM traces.

TRACES lists, per scenario, the event kinds that already match the ROM. A feature that makes more
kinds match adds them here. "lamp" is the steady-state lamp comparison of scripts/lamp_state.py,
"coil" the flasher / shaker burst comparison of scripts/coil_state.py.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

TRACES = {
    "game_flow": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "game_flow_tilt": "score,deff_start,sound,tube_show_start,audit,multiball_start,mark,lamp",
    "attract_and_service": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "bonus": "audit,multiball_start,mark",
    "bonus_skip": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "skill_shots": "deff_start,leff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "skill_shots_b": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "skill_shots_c": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "switches_and_shots": "score,deff_start,sound,audit,multiball_start,mark,lamp",
    "find_flynn_and_items": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "flynns_arcade": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "sea_of_simulation": "score,deff_start,sound,audit,multiball_start,mark",
    "portal_multiball": "score,deff_start,sound,audit,multiball_start,mark,lamp",
    "portal_multiball_shots": "score,deff_start,sound,leff_start,audit,multiball_start,mark,lamp",
    "combos": "score,deff_start,sound,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "combos_eol_jackpot": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp,coil",
    "tron_targets": "audit,multiball_start,mark,lamp,coil",
    "zen_rollover": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "recognizer_and_disc_battle": "score,deff_start,leff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "disc_multiball": "score,deff_start,tube_show_start,multiball_start,mark",
    "disc_multiball_restart": "score,deff_start,audit,multiball_start,mark",
    "light_cycle_multiball": "score,deff_start,audit,multiball_start,mark",
    "light_cycle_multiball_repeat_and_stack": "score,deff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "quorra_multiball": "score,deff_start,leff_start,tube_show_start,audit,multiball_start,mark",
    # End of Line: the other kinds differ only through features not built yet (Flynn's Arcade
    # Recognizer/GEM awards at the VUK, Light Cycle progress deff 83, combo arrows leff 159)
    "end_of_line_multiball": "score,deff_start,sound,multiball_start,mark,lamp",
    "end_of_line_multiball_scoring": "score,deff_start,tube_show_start,audit,multiball_start,mark",
    "daft_punk_multiball": "score,deff_start,tube_show_start,audit,multiball_start,mark,lamp",
    "clu_hurryup": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark",
    "gem_hurryup": "score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark,coil",
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
