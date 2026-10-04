"""Light Cycle and Portal Multiball driven from the switches, with the text each screen puts on the DMD
(assets/rules/modes/light_cycle_multiball.md, portal_multiball.md; the draw code of deffs 83-90 and 140-145).
"""
import os
from unittest import mock

import sys
from tests.tron_test import TronTestCase, GAME
if GAME not in sys.path:
    sys.path.insert(0, GAME)
from tron.media_bridge import MediaBridge   # noqa: E402

HAS_MEDIA = os.path.exists(os.path.join(GAME, "tron", "media_data.json"))


class ScreenTestCase(TronTestCase):

    def setUp(self):
        super().setUp()
        if not HAS_MEDIA:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        self.sent = []

        def send(bridge, name, settings, priority=0, need_data=True, **kwargs):
            if name == "slides_play":
                (slide, s), = settings.items()
                if s["action"] in ("play", "update"):
                    self.sent.append((slide, s["action"], kwargs))
        for patch in (mock.patch.object(MediaBridge, "connected", lambda self, need_data=True: True),
                      mock.patch.object(MediaBridge, "_send", send)):
            patch.start()
            self.addCleanup(patch.stop)

    def start_play(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)      # plunge
        self.hit_and_release_switch("s_zen_rollover")         # playfield valid
        self.advance_time_and_run(1)
        self.tron.features_by_name["skill_shots"].kill_all()  # no skill shot on the first shots

    def shoot(self, switch, wait=4):
        if switch == "s_disc_opto":                           # an opto: the ball breaks the beam
            self.release_switch_and_run(switch, 0.06)
            self.hit_switch_and_run(switch, wait)
            return
        self.hit_and_release_switch(switch)
        self.advance_time_and_run(wait)

    def vuk(self, wait=12):
        self.hit_switch_and_run("s_video_game_eject", 1)
        self.release_switch_and_run("s_video_game_eject", wait)

    def screens(self, deff_id):
        """The lines of every play of deff_id since the last call, as the DMD shows them (blank lines and
        the lines of the other screens of a multi-screen effect left out)."""
        import json
        with open(os.path.join(GAME, "tron", "media_data.json"), encoding="utf-8") as f:
            info = json.load(f)["deffs"][str(deff_id)]
        import sys
        sys.path.insert(0, os.path.join(GAME, "..", "scripts"))
        import rom_layout
        screens = rom_layout.SCREENS.get(deff_id, {})
        out = []
        for slide, action, kw in self.sent:
            if slide != "deff_%03d" % deff_id or action != "play":
                continue
            shown = kw.get("screen", 0)
            out.append(tuple(kw["line%d" % i] for i in range(len(info["text"]))
                             if kw.get("line%d" % i) and shown in screens.get(i, (shown,))))
        self.sent = [s for s in self.sent if s[0] != "deff_%03d" % deff_id]
        return out

    def status(self, deff_id):
        """The lines of the latest play or refresh of a background status screen."""
        import json
        with open(os.path.join(GAME, "tron", "media_data.json"), encoding="utf-8") as f:
            info = json.load(f)["deffs"][str(deff_id)]
        import sys
        sys.path.insert(0, os.path.join(GAME, "..", "scripts"))
        import rom_layout
        screens = rom_layout.SCREENS.get(deff_id, {})
        kw = [k for slide, _, k in self.sent if slide == "deff_%03d" % deff_id and "line0" in k][-1]
        shown = kw.get("screen", 0)
        return tuple(kw["line%d" % i] for i in range(len(info["text"]))
                     if kw.get("line%d" % i) and shown in screens.get(i, (shown,)))


class TestLightCycleScreens(ScreenTestCase):

    def test_lighting_starting_and_jackpots(self):
        self.start_play()
        lc = self.tron.features_by_name["light_cycle"]
        pd = self.tron.pd
        # four different Light Cycle shots light it on the first Light Cycle of the game
        self.shoot("s_l_ramp_exit")
        self.assertEqual([("3 MORE", "TO LIGHT", "LIGHT CYCLE")], self.screens(83))
        self.shoot("s_l_ramp_exit")                           # the same shot again counts nothing
        self.assertEqual([], self.screens(83))
        self.shoot("s_r_ramp_exit")
        self.shoot("s_left_orbit")
        self.assertEqual([("2 MORE", "TO LIGHT", "LIGHT CYCLE"), ("1 MORE", "TO LIGHT", "LIGHT CYCLE")],
                         self.screens(83))
        self.shoot("s_right_orbit", wait=5)
        self.assertTrue(self.tron.hook("vuk_lit_test", 4))   # lit at the VUK; deff 84 (LIGHT CYCLE IS LIT)
        self.assertIn(84, [int(s[0][5:]) for s in self.sent if s[0].startswith("deff_")])
        self.assertEqual((0xcf, 0), (pd.lc_remaining, pd.lc_collected))
        self.shoot("s_r_ramp_exit")                           # lit: no progress
        self.assertEqual([], self.screens(83))

        before = self.machine.game.player.score
        self.vuk(wait=14)
        self.assertTrue(self.tron.flag(0x2b))                 # running, 2 balls
        self.assertEqual(1, pd.lc_starts)
        self.assertGreaterEqual(self.machine.game.player.score - before, 150000)

        # chain A: left ramp Jackpot, then left inner loop Super, then right inner loop Double Super
        self.shoot("s_l_ramp_exit")
        self.assertEqual([("JACKPOT", "350,000")], self.screens(87))
        self.shoot("s_left_spinner")
        self.assertEqual([("SUPER JACKPOT", "750,000")], self.screens(88))
        self.shoot("s_right_inner_loop")
        self.assertEqual([("DOUBLE", "SUPER JACKPOT", "1,500,000")], self.screens(89))
        # chain B: right orbit Jackpot, then the right ramp Super; chain C: the right ramp is a Jackpot
        self.shoot("s_right_orbit")
        self.shoot("s_r_ramp_exit")
        self.shoot("s_r_ramp_exit")
        self.assertEqual([("JACKPOT", "350,000"), ("JACKPOT", "350,000")], self.screens(87))
        self.assertEqual([("SUPER JACKPOT", "750,000")], self.screens(88))
        self.assertEqual(150000 + 350000 + 750000 + 1500000 + 350000 + 750000 + 350000, lc.total)

        # down to one ball: the end window, then the total
        lc.multiball_end()
        self.advance_time_and_run(8)
        self.assertEqual([("LIGHT CYCLE", "MULTIBALL", "TOTAL:", "4,200,000")], self.screens(90))

    def test_second_light_cycle_needs_all_six(self):
        self.start_play()
        self.tron.pd.lc_starts = 1
        self.shoot("s_l_ramp_exit")
        self.assertEqual([("5 MORE", "TO LIGHT", "LIGHT CYCLE")], self.screens(83))


class TestPortalScreens(ScreenTestCase):

    def test_intro_status_phases_and_total(self):
        self.start_play()
        portal = self.tron.features_by_name["portal"]
        for item in self.tron.pd.items:                      # all nine items collected: Portal is lit
            item[1] = 1
        self.tron.flag_set(0x33)                              # a Sea of Simulation since the last Portal: no bonus
        self.vuk(wait=12)
        self.assertTrue(self.tron.flag(0x37))
        # intro: no bonus screen; PORTAL / MULTIBALL, then COMPLETE ALL SHOTS / FOR / SUPER JACKPOT
        self.assertEqual([("PORTAL", "MULTIBALL", "COMPLETE ALL SHOTS", "FOR", "SUPER JACKPOT")],
                         self.screens(140))
        self.assertEqual(("PORTAL MULTIBALL", "NEXT SHOT=500,000", "SUPER=1,000,000"), self.status(141))

        self.shoot("s_left_orbit")                            # 500,000; the next shot is worth 550,000
        self.assertEqual([("500,000",)], self.screens(142))
        self.advance_time_and_run(1)
        self.assertEqual(("PORTAL MULTIBALL", "NEXT SHOT=550,000", "SUPER=1,500,000"), self.status(141))

        portal.counts[:6] = [4, 3, 5, 3, 3, 3]                # every shot made but one right orbit
        self.shoot("s_right_orbit")                           # S = 21: capped at 1,500,000; all shots made
        self.assertEqual([("1,500,000",)], self.screens(142))
        self.assertEqual(1, portal.phase)
        self.advance_time_and_run(1)
        self.assertEqual(("PORTAL MULTIBALL", "SUPER JACKPOT LIT", "SHOOT DISC", "SUPER=3,000,000"),
                         self.status(141))
        self.shoot("s_l_ramp_exit")                           # the Super is lit only at the disc
        self.assertEqual([], self.screens(142))
        self.shoot("s_disc_opto", wait=10)
        self.assertEqual([("SUPER", "JACKPOT", "3,000,000")], self.screens(143))
        self.assertEqual(2, portal.phase)
        self.assertEqual(("PORTAL MULTIBALL", "ALL SHOTS=1,000,000"), self.status(141))
        self.shoot("s_l_ramp_exit")                           # every shot: 1,000,000
        self.assertEqual([("1,000,000",)], self.screens(144))

        portal.multiball_end()                                # one ball left: 5 s grace, then the total
        self.advance_time_and_run(6)
        total = 1000000 + 500000 + 1500000 + 3000000 + 1000000
        self.assertEqual(total, portal.total)
        self.assertEqual([("PORTAL MULTIBALL", "TOTAL:", "7,000,000")], self.screens(145))

    def test_sea_of_simulation_bonus_screen(self):
        self.start_play()
        for item in self.tron.pd.items:
            item[1] = 1
        self.vuk(wait=12)                                    # no Sea of Simulation since the last Portal
        # the bonus over the animation, then the PORTAL / MULTIBALL intro
        self.assertEqual([("50,000,000", "SEA OF SIMULATION", "BONUS", "PORTAL", "MULTIBALL", "COMPLETE ALL SHOTS",
                           "FOR", "SUPER JACKPOT")], self.screens(140))
