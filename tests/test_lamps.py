"""Unit tests for the lamp matrix model (game/tron/lamps.py) and the lamp comparison (scripts/lamp_state.py)."""
import json
import os
import sys
import tempfile
import unittest

from tests.test_base import BaseCase
from tests.tron_test import ROOT

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import coil_state  # noqa: E402
import lamp_state  # noqa: E402


class TestLampModel(BaseCase):

    def lamp_events(self, n):
        return [(e["t"], e["state"]) for e in self.tron.trace.of("lamp") if e["lamp"] == n]

    def test_solid_flash_and_off(self):
        self.start_game()                         # no attract leff layer over the inserts
        lamps = self.tron.lamps
        self.advance_time_and_run(3)              # game start effects over
        t0 = self.machine.clock.get_time()
        lamps.lamp_on_solid(17)
        self.advance_time_and_run(1)
        self.assertEqual([1], [s for t, s in self.lamp_events(17) if t >= t0])
        self.assertEqual(1, lamps.lamp_state(17))
        # flashing: the trace (libpinmame-like output) shows ~146 ms on, ~16 ms off
        lamps.lamp_flash(17)
        self.advance_time_and_run(1)
        events = [e for e in self.lamp_events(17) if e[0] >= t0]
        self.assertGreater(len(events), 8)
        offs = [b[0] - a[0] for a, b in zip(events, events[1:]) if a[1] == 0]
        self.assertTrue(all(0.005 < d < 0.03 for d in offs), offs)
        self.assertEqual(2, lamps.lamp_state(17))
        lamps.lamp_off_all(17)
        self.advance_time_and_run(0.5)
        self.assertEqual(0, self.lamp_events(17)[-1][1])
        self.assertNotIn(17, lamps)
        self.assertEqual(0, self.machine.lights["l_center_portal"].get_color().red)

    def test_mpf_light_follows(self):
        self.start_game()
        self.tron.lamps.lamp_on_solid(17)
        self.advance_time_and_run(0.1)
        self.assertEqual(255, self.machine.lights["l_center_portal"].get_color().red)

    def test_layers_override_by_priority(self):
        lamps = self.tron.lamps
        lamps.lamp_on_solid(7)
        low = lamps.layer_create(5, [7])          # holds lamp 7 off
        self.advance_time_and_run(0.2)
        self.assertFalse(lamps.composite(7))
        high = lamps.layer_create(9, [7])
        high.image.add(7)
        lamps.changed()
        self.advance_time_and_run(0.2)
        self.assertTrue(lamps.composite(7))
        lamps.layer_free(high)
        lamps.layer_free(low)
        self.advance_time_and_run(0.2)
        self.assertTrue(lamps.composite(7))

    def test_token_leff_plays_on_the_given_lamp(self):
        self.start_game()
        tron = self.tron
        tron.leff_start(38, lamp=4)               # TRON letter collect, captured with a stand-in lamp
        self.assertIn(38, tron.lamps.leff_players)
        layer = tron.lamps.leff_players[38][1]
        self.assertEqual({4}, layer.mask)
        self.advance_time_and_run(3)
        self.assertNotIn(38, tron.lamps.leff_players)   # played once: its layer is gone
        self.assertNotIn(layer, tron.lamps.layers)

    def test_lamp_rules_draw_the_inserts(self):
        self.start_game()
        self.validate()
        tron = self.tron
        self.advance_time_and_run(1)
        self.assertEqual(2, tron.lamps.lamp_state(1))      # TRON letters flash
        self.assertEqual(2, tron.lamps.lamp_state(27))     # FLYNN item lit at the valid playfield
        self.assertEqual(1, tron.lamps.lamp_state(46))     # pop inserts solid
        self.assertEqual(2, tron.lamps.lamp_state(11))     # Light Cycle shots to make
        self.hit("s_tron_t")
        self.advance_time_and_run(0.5)
        self.assertEqual(1, tron.lamps.lamp_state(4))      # (T)RON collected, its drop down

    def coil_events(self, n, t0):
        return [(e["t"], e["on"]) for e in self.tron.trace.of("coil") if e["coil"] == n and e["t"] >= t0]

    def test_flasher_pulses_read_as_one_flash(self):
        self.start_game()
        self.advance_time_and_run(3)
        t0 = self.machine.clock.get_time()
        lamps = self.tron.lamps
        for _ in range(3):                        # back-to-back pulses: one on / off pair, held like the ROM
            lamps.flasher("f_left_ramp", 64)
            self.advance_time_and_run(0.1)
        self.advance_time_and_run(1)
        events = self.coil_events(19, t0)
        self.assertEqual([1, 0], [on for _, on in events])
        self.assertAlmostEqual(0.2 + 0.064 + 0.24, events[1][0] - events[0][0], delta=0.03)

    def test_shaker_runs_in_game_only(self):
        tron = self.tron
        t0 = self.machine.clock.get_time()
        tron.shaker_run(2, 2)                     # attract: no shaker
        self.advance_time_and_run(1)
        self.assertEqual([], self.coil_events(8, t0))
        self.start_game()
        self.advance_time_and_run(3)
        t0 = self.machine.clock.get_time()
        tron.shaker_run(2, 2)
        self.advance_time_and_run(1)
        events = self.coil_events(8, t0)
        self.assertEqual([1, 0], [on for _, on in events])
        tron.adj[86] = 1                          # SHAKER MOTOR minimal: a min setting 2 call does nothing
        t0 = self.machine.clock.get_time()
        tron.shaker_run(2, 2)
        self.advance_time_and_run(1)
        self.assertEqual([], self.coil_events(8, t0))

    def test_clu_shot_lamps_leff(self):
        self.start_game()
        self.advance_time_and_run(3)
        clu = self.tron.features_by_name["clu"]
        clu.shots = 0x001 | 0x100                 # left orbit and VUK still to make
        self.tron.leff_start(78, loop=True)
        self.advance_time_and_run(1)
        lamps = self.tron.lamps
        layer = lamps.leff_players[78][1]
        self.assertEqual({13, 61, 36, 28}, layer.mask)
        self.assertFalse(lamps.composite(61) or lamps.composite(36))     # made: held off
        seen = set()
        for _ in range(4):                        # toggles every 3 ticks
            seen.add(lamps.composite(13))
            self.advance_time_and_run(0.05)
        self.assertEqual({True, False}, seen)


class TestCoilCompare(unittest.TestCase):

    def test_bursts_and_match(self):
        pwm = [(1.0 + i * 0.016, i % 2 == 0) for i in range(40)]           # a PWM train: one burst
        self.assertEqual(1, len(coil_state.bursts([(t, int(on)) for t, on in pwm])))
        two = [(1.0, 1), (1.3, 0), (1.5, 1), (1.8, 0)]                       # 0.2 s apart: two flashes
        self.assertEqual(2, len(coil_state.bursts(two)))
        ref = [(1.0, 1.3), (5.0, 5.3), (9.0, 9.2)]
        cand = [(1.1, 1.4), (5.6, 5.9), (9.0, 9.1)]
        matched, lost, extra = coil_state.match(ref, cand)
        self.assertEqual(2, matched)
        self.assertEqual([5.0], lost)
        self.assertEqual([5.6], extra)


class TestLampCompare(unittest.TestCase):

    def write(self, path, events):
        with open(path, "w") as f:
            f.write(json.dumps({"t": 0.0, "ev": "ready"}) + "\n")
            for e in events:
                f.write(json.dumps(e) + "\n")

    def test_states(self):
        flash = []
        t = 1.0
        while t < 3.0:
            flash += [{"t": t, "ev": "lamp", "lamp": 1, "state": 1}, {"t": t + 0.146, "ev": "lamp", "lamp": 1,
                                                                      "state": 0}]
            t += 0.163
        blip = [{"t": 1.0, "ev": "lamp", "lamp": 2, "state": 1}, {"t": 2.0, "ev": "lamp", "lamp": 2, "state": 0},
                {"t": 2.015, "ev": "lamp", "lamp": 2, "state": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.jsonl")
            self.write(path, flash + blip + [{"t": 3.5, "ev": "mark", "text": "x"}])
            _, _, lm = lamp_state.load(path)
            self.assertIn(lamp_state.state(lm, 1, 2.5), "Ff")
            self.assertEqual("1", lamp_state.state(lm, 2, 2.3))     # one-frame blip: still steady on
            self.assertEqual("0", lamp_state.state(lm, 3, 2.3))
            good, total, diffs = lamp_state.compare(path, path, verbose=False)
            self.assertEqual(good, total)
            self.assertFalse(diffs)


if __name__ == "__main__":
    unittest.main()
