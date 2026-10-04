"""Flynn's Arcade mystery award at the VUK (sw11): the pick, each award, and the deff 105 reel it shows
(assets/rules/modes/flynns_arcade.md, deff_105_arcade_award 0x0100e8bc)."""
import json
import os

from tests.tron_test import ROOT, TronTestCase

TICK = 0.01626
PARTS = os.path.join(ROOT, "assets", "mpf_package", "media", "dmd", "deff_105_flynns_arcade_award", "parts")


class TestArcade(TronTestCase):

    def setUp(self):
        super().setUp()
        self.reels = []
        self.machine.events.add_handler("tron_deff_105", lambda **kwargs: self.reels.append(kwargs))

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")         # playfield valid
        self.advance_time_and_run(3)                          # past the VUK skill shot window
        return self.tron

    @property
    def arcade(self):
        return self.tron.features_by_name["arcade"]

    def vuk(self, award=None):
        """Relight the arcade and shoot the VUK; returns the deff 105 args (None: no award)."""
        os_ = self.tron
        os_.pd.arcade_lit = 1
        if award is not None:
            os_.forced["arcade"] = [self.award_index(award)]
        before = len(self.reels)
        self.hit_switch_and_run("s_video_game_eject", 0.1)
        self.advance_time_and_run(4)                          # reel, hold, eject
        if self.machine.switches["s_video_game_eject"].state:
            self.release_switch_and_run("s_video_game_eject", 1)
        return self.reels[-1] if len(self.reels) > before else None

    @staticmethod
    def award_index(name):
        from tron.features.arcade import AWARDS
        return [a[0] for a in AWARDS].index(name)

    # ------------------------------------------------------------------ pick and reel

    def test_repeated_awards_vary(self):
        os_ = self.start_game()
        picks, slots = [], set()
        for _ in range(16):
            if os_.any_multiball():
                break
            reel = self.vuk()
            self.assertIsNotNone(reel)
            picks.append(reel["award"])
            slots.add(reel["slot"])
            self.assertFalse(os_.pd.arcade_lit)               # collected: unlit
        self.assertGreater(len(picks), 5)
        self.assertGreater(len(set(picks)), 2, picks)         # not the same award every time
        self.assertGreater(len(slots), 1)                     # the reel stops in different slots

    def test_reel_from_the_random_generator(self):
        """Live play draws from os.random (unseeded); two seeds give two different runs of picks."""
        os_ = self.start_game()
        runs = []
        for seed in (1, 2):
            os_.random.seed(seed)
            runs.append([(self.arcade.reel(8)["slot"], self.arcade.reel(8)["icon0"],
                          os_.pick("arcade", [100, 25, 25, 25, 25, 0, 25, 100, 0, 0, 1, 1]))
                         for _ in range(8)])
        self.assertNotEqual(runs[0], runs[1])

    def test_reel_layout_as_the_rom(self):
        from tron.features.arcade import blink_frames, scroll_frames
        self.assertEqual([5, 18, 30], [scroll_frames(k) for k in range(3)])   # traces: 0x0e3 at 0.24/0.88/1.47 s
        self.assertEqual(23, blink_frames(0))                 # steps 0-22: past 21, ends on an even step
        self.assertEqual(33, blink_frames(1.53))              # the capture: sample 0x0c5, 33 frames
        self.assertEqual(61, blink_frames(10))                # at most 61
        self.start_game()
        for award in range(1, 13):
            for _ in range(20):
                reel = self.arcade.reel(award)
                icons = [reel["icon%d" % i] for i in range(3)]
                self.assertEqual(award, icons[reel["slot"]])
                self.assertEqual(3, len(set(icons)))          # two different decoys
                self.assertTrue(all(1 <= i <= 12 for i in icons))
                self.assertTrue(all(0 <= reel["cab%d" % i] <= 3 for i in range(3)))
                self.assertEqual(scroll_frames(reel["slot"]), reel["scroll"])
                self.assertAlmostEqual(((reel["scroll"] + reel["blink"]) * 3 + 10) * TICK, reel["run_seconds"])

    def test_reel_sounds(self):
        """0x0e4 and the roll 0x0e1 at the start; the roll stops and 0x0e3 plays when the reel stops."""
        os_ = self.start_game()
        os_.forced["arcade_slot"] = [2]
        calls = []
        sound, stop = os_.sound, os_.sound_stop
        os_.sound = lambda call, *a, **k: calls.append((round(os_.now, 3), call)) or sound(call, *a, **k)
        os_.sound_stop = lambda call: calls.append((round(os_.now, 3), -call)) or stop(call)
        t0 = os_.now
        self.vuk("500k")
        own = [(round(t - t0, 2), c) for t, c in calls if c in (0x0e4, 0x0e1, -0x0e1, 0x0e3)]
        self.assertEqual([0x0e4, 0x0e1, -0x0e1, 0x0e3], [c for _, c in own])
        self.assertAlmostEqual(30 * 3 * TICK, own[3][0] - own[0][0], delta=0.02)

    # ------------------------------------------------------------------ each award

    def assert_award(self, name, audit):
        os_ = self.tron
        before = os_.audits.get(audit, 0)
        reel = self.vuk(name)
        self.assertIsNotNone(reel, name)
        self.assertEqual(self.award_index(name) + 1, reel["award"])
        self.assertEqual(before + 1, os_.audits.get(audit, 0), name)
        self.assertFalse(os_.pd.arcade_lit, name)
        return reel

    def test_500k(self):
        os_ = self.start_game()
        score = os_.game.player.score
        self.assert_award("500k", 0x53)
        self.assertEqual(500000 + 350, os_.game.player.score - score)   # + the VUK's own 350

    def test_score_display_back_after_the_reel(self):
        """The rules pass deferred during show 0x97 restarts deff 19 as deff 105 exits (flynns_arcade.jsonl
        19.36 s), so the screen does not go blank after the award."""
        os_ = self.start_game()
        os_.pd.arcade_lit = 1
        os_.forced["arcade"] = [self.award_index("500k")]
        os_.forced["arcade_slot"] = [0]
        self.hit_switch_and_run("s_video_game_eject", 0.01)
        for _ in range(300):
            if os_.display.fg == 105:
                break
            self.advance_time_and_run(0.01)
        reel = self.reels[-1]
        self.assertEqual(105, os_.display.fg)
        self.advance_time_and_run(((reel["scroll"] + reel["blink"]) * 3 + 10) * TICK - 0.05)
        self.assertEqual(105, os_.display.fg)
        self.advance_time_and_run(0.1)
        self.assertIsNone(os_.display.fg)
        self.assertEqual(19, os_.display.bg)

    def test_adv_gem(self):
        os_ = self.start_game()
        n = os_.pd.gem_progress
        score = os_.game.player.score
        self.assert_award("gem", 0x54)
        self.assertEqual(250000 + 350, os_.game.player.score - score)
        self.assertEqual(n + 1, os_.pd.gem_progress)                     # one of the 3 toward the hurry-up

    def test_adv_clu(self):
        os_ = self.start_game()
        score = os_.game.player.score
        self.assert_award("clu", 0x55)
        self.assertGreater(os_.game.player.score - score, 350)          # one CLU lane completion

    def test_adv_zuse(self):
        os_ = self.start_game()
        zuse = os_.features_by_name["zuse"]
        calls = []
        complete = zuse._complete
        zuse._complete = lambda silent: calls.append(silent) or complete(silent)
        self.assert_award("zuse", 0x56)
        self.assertEqual([True], calls)                                  # one silent ZUSE set

    def test_adv_quorra(self):
        os_ = self.start_game()
        score = os_.game.player.score
        self.assert_award("quorra", 0x57)
        self.assertEqual(10000 + 350, os_.game.player.score - score)

    def test_adv_light_cycle(self):
        os_ = self.start_game()
        before = os_.pd.lc_collected
        self.assert_award("light_cycle", 0x59)
        self.assertNotEqual(before, os_.pd.lc_collected)                # one Light Cycle target collected

    def test_adv_recognizer(self):
        os_ = self.start_game()
        score = os_.game.player.score
        self.assert_award("recognizer", 0x5a)
        self.assertEqual(2500 + 350, os_.game.player.score - score)

    def test_adv_disc_needs_the_battle_lit(self):
        """ADV. DISC gives nothing while the Disc Battle cannot progress: the award function returns 0, task
        0x97 is killed and the arcade stays lit [0x0100debc]."""
        os_ = self.start_game()
        self.assertFalse(os_.hook("dbattle_can_progress"))
        self.assertEqual(0, self.arcade.weights()[self.award_index("disc")])
        audit = os_.audits.get(0x58, 0)
        self.assertIsNone(self.vuk("disc"))
        self.assertTrue(os_.pd.arcade_lit)
        self.assertEqual(audit, os_.audits.get(0x58, 0))

    def test_adv_sos_only_while_it_runs(self):
        os_ = self.start_game()
        self.assertEqual(0, self.arcade.weights()[self.award_index("sos")])
        os_.flag_set(0x34)                                               # SOS running: weight 101 + 1000
        self.assertEqual(1101, self.arcade.weights()[self.award_index("sos")])
        self.assertEqual(self.award_index("sos"), os_.pick("arcade", self.arcade.weights()))
        os_.flag_clear(0x34)

    def test_more_time(self):
        os_ = self.start_game()
        zuse = os_.features_by_name["zuse"]
        zuse.start()                                                     # a timed feature runs
        self.assertEqual(100, self.arcade.weights()[self.award_index("more_time")])
        self.advance_time_and_run(3)
        left = zuse.clock.seconds
        self.assert_award("more_time", 0x5c)
        self.assertGreater(zuse.clock.seconds, left)                     # back to full
        self.assertTrue(os_.flag(0x2c))
        self.assertEqual(0, self.arcade.weights()[self.award_index("more_time")])   # not twice

    def test_light_extra_ball(self):
        os_ = self.start_game()
        self.assert_award("extra_ball", 0x5d)
        self.assertTrue(os_.features_by_name["scoop"].pd.vuk_lit[1])     # EB lit at the VUK

    def test_light_special(self):
        os_ = self.start_game()
        self.assert_award("special", 0x5e)
        self.assertEqual(1, os_.specials_lit[os_.player_num - 1])

    # ------------------------------------------------------------------ what the display shows

    def test_award_names_and_icons_match_the_rom(self):
        """Each award's name is its ROM audit text and the reel shows its own icon pair (table 0x040d29a0):
        the reel never shows an empty cabinet for the award, as the reference capture (award id 0) did."""
        from tron.features.arcade import AWARD_NAMES, AWARDS
        audits = {a["counter"]: a["name"] for a in json.load(open(
            os.path.join(ROOT, "assets", "mpf_package", "service_menu.json"), encoding="utf-8"))["audits"]}
        index = json.load(open(os.path.join(PARTS, "index.json"), encoding="utf-8"))
        icons = {a["award_id"]: a for a in index["awards"]}
        self.assertEqual(12, len(AWARD_NAMES))
        for i, ((_, _, audit), name) in enumerate(zip(AWARDS, AWARD_NAMES)):
            self.assertTrue(name)
            self.assertEqual("FLYNN'S ARCADE: " + name, audits[audit])
            self.assertEqual(name, icons[i + 1]["name"])
            for key in ("file_a", "file_b"):
                self.assertTrue(os.path.exists(os.path.join(PARTS, icons[i + 1][key])))
        self.start_game()
        for i, name in enumerate(AWARD_NAMES):
            reel = self.arcade.reel(i + 1)
            self.assertEqual(name, reel["award_name"])

    def test_reel_args_reach_the_slide(self):
        """The media bridge sends the reel's choices with the deff 105 slide (tron/arcade_reel.gd)."""
        from unittest import mock
        bridge = self.tron.media
        if not bridge.data:
            self.skipTest("media data not generated (scripts/gen_media.py)")
        self.assertEqual("arcade", bridge.data["deffs"][105]["source"])
        self.start_game()
        with mock.patch.object(bridge, "connected", return_value=True), \
                mock.patch.object(self.machine.bcp, "interface") as iface:
            reel = self.vuk("recognizer")
            plays = [c.kwargs for c in iface.bcp_trigger.call_args_list if c.kwargs["name"] == "slides_play"
                     and "deff_105" in c.kwargs["settings"]
                     and c.kwargs["settings"]["deff_105"]["action"] == "play"]
        self.assertTrue(plays)
        for key in ("award", "cab0", "cab1", "cab2", "icon0", "icon1", "icon2", "slot", "scroll", "blink"):
            self.assertEqual(reel[key], plays[-1][key], key)
        self.assertEqual(8, plays[-1]["icon%d" % plays[-1]["slot"]])
