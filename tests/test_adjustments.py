"""Phase 7 gate: every adjustment with a gameplay effect changes the behaviour its spec names.

One test per adjustment (or per group that shares one behaviour), each comparing two settings. The ROM
function that reads the adjustment is named in the code under test. Adjustments without a gameplay effect in
this rebuild are listed in NO_EFFECT with where their effect was looked for.
"""
import sys
from unittest import mock

from tests.tron_test import GAME, TronTestCase

if GAME not in sys.path:
    sys.path.insert(0, GAME)

TESTED = {3, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 29, 30, 31, 32, 35, 38, 39, 40, 41,
          42, 44, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 76, 77, 78, 79, 82, 83, 84, 85, 86}
# credits, game start / restart, high scores and attract pages: tests/test_credits.py
TESTED |= {2, 25, 28, 33, 34, 36, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62}
# adjustment -> why no behaviour test (where the effect was looked for)
NO_EFFECT = {
    1: "COIL PULSE POWER: OS coil-driver strength (read through the OS driver tables); MPF owns pulse times",
    4: "FAST BOOT: boot sequence (0x0103703c)",
    5: "FLASH LAMP POWER: OS flasher-driver strength",
    6: "GAME ID: operator data", 7: "LANGUAGE: text language (0xa2dc); English only", 8: "LOCATION ID: data",
    9: "MUSIC VOLUME: sound board master volume", 10: "PLAYER LANGUAGE SELECT: start-button language menu (0xa258)",
    37: "BILL VALIDATOR: no reader in the decompile (slot data only) and no bill acceptor switch in this machine",
    43: "CONSOLATION BALL: not read through adj_get in 1.74 (no call site found); not traced",
    45: "TICKET DISPENSER: only shows the REDEMPTION menu (tested in test_service)",
    46: "PLAYER COMPETITION: 0x00019ecc, multi-player tournament play; not modelled",
    47: "TEAM SCORES: team display, not read by the game code",
    75: "ABORT ANIMATIONS: flipper abort of queued shows (0x0100fbb0 / 0x0100fd88); not modelled in display.py",
    80: "DISABLE DROP TARGETS: tron_targets.md open question; no adj_get(80) call site (inferred only)",
    81: "DISABLE RECOGNIZER MOTOR: head motor object parameter; the rebuild does not drive the head motor",
    87: "MUSIC VOLUME (trim): sound board", 88: "SPEECH VOLUME (trim): sound board",
}


class AdjCase(TronTestCase):

    def start_game(self, plunge=True):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        if plunge:
            self.release_switch_and_run("s_shooter_lane", 1)
        return self.tron

    def validate(self):
        self.hit_and_release_switch("s_zen_rollover")
        self.advance_time_and_run(0.3)
        self.assertTrue(self.tron.pf_valid)

    def drain(self, wait=3):
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(wait)

    def events(self, name):
        seen = []
        self.machine.events.add_handler(name, lambda **kwargs: seen.append(kwargs))
        return seen

    def sounds(self):
        return [e["call"] for e in self.tron.trace.of("sound")]

    def deffs(self):
        return [e["id"] for e in self.tron.trace.of("deff_start")]


class TestCoverage(TronTestCase):

    def test_every_adjustment_is_tested_or_listed(self):
        self.assertEqual(set(range(1, 89)), TESTED | set(NO_EFFECT))
        self.assertFalse(TESTED & set(NO_EFFECT))


class TestGameFlowAdjustments(AdjCase):

    def _one_drain(self, balls):
        self.tron.adj[31] = balls
        os_ = self.start_game()
        self.assertEqual(balls, self.machine.game.balls_per_game)
        self.validate()
        os_.kill_ball_save()
        self.drain(15)

    def test_31_balls_per_game_one(self):
        self._one_drain(1)
        self.assertIsNone(self.machine.game)                     # game over after the only ball

    def test_31_balls_per_game_three(self):
        self._one_drain(3)
        self.assertEqual(2, self.machine.game.player.ball)

    def test_38_ball_save_time(self):
        self.tron.adj[38] = 0                                    # NO BALL SAVES
        os_ = self.start_game()
        self.assertIsNone(os_.ball_save)
        self.validate()
        self.drain()
        self.assertIsNone(os_.audits.get(0x2b))
        self.assertEqual(1, os_.audits.get(8))                   # the ball ended
        self.release_switch_and_run("s_shooter_lane", 1)
        os_.adj[38] = 2                                          # 2 s: over before 3 s of valid play
        os_._arm_ball_save()
        self.validate()
        self.assertEqual("armed", os_.ball_save)
        self.advance_time_and_run(6)
        self.assertIsNone(os_.ball_save)
        os_.adj[38] = 10
        os_._arm_ball_save()
        self.advance_time_and_run(6)
        self.assertEqual("armed", os_.ball_save)

    def test_32_tilt_warnings(self):
        self.tron.adj[32] = 0
        os_ = self.start_game()
        self.hit_and_release_switch("s_plumb_bob_tilt")
        self.advance_time_and_run(0.1)
        self.assertTrue(os_.tilted)                              # no warning at all
        self.assertNotIn(23, self.deffs())

    def test_32_tilt_warnings_two(self):
        os_ = self.start_game()
        for _ in range(2):
            self.hit_and_release_switch("s_plumb_bob_tilt")
            self.advance_time_and_run(1.2)
            self.assertFalse(os_.tilted)
        self.assertEqual(2, self.deffs().count(23))
        self.hit_and_release_switch("s_plumb_bob_tilt")
        self.advance_time_and_run(0.1)
        self.assertTrue(os_.tilted)

    def test_64_coin_door_disable_tilt(self):
        os_ = self.start_game()
        self.hit_switch_and_run("s_coin_door_open", 0.1)
        self.hit_and_release_switch("s_plumb_bob_tilt")          # adj 64 = NO: the door does not matter
        self.advance_time_and_run(1.2)
        self.assertEqual(1, os_.tilt_warnings)
        os_.adj[64] = 1
        self.hit_and_release_switch("s_plumb_bob_tilt")          # door open: ignored
        self.advance_time_and_run(1.2)
        self.assertEqual(1, os_.tilt_warnings)
        self.release_switch_and_run("s_coin_door_open", 0.1)
        self.hit_and_release_switch("s_plumb_bob_tilt")          # door closed: counts
        self.advance_time_and_run(1.2)
        self.assertEqual(2, os_.tilt_warnings)

    def test_26_extra_ball_limit(self):
        os_ = self.start_game()
        os_.adj[26] = 1
        self.assertTrue(os_.collect_extra_ball())
        before = self.machine.game.player.score
        self.assertFalse(os_.collect_extra_ball())               # over the limit: 3,000,000 points
        self.advance_time_and_run(0.1)
        self.assertEqual(3000000, self.machine.game.player.score - before)
        os_.adj[26] = 10
        self.assertTrue(os_.collect_extra_ball())

    def test_22_special_limit_and_23_special_award(self):
        os_ = self.start_game()
        credits = self.events("tron_award_credit")
        os_.light_special()
        os_.special_collect()                                    # factory: 1 special, CREDIT
        self.advance_time_and_run(0.1)
        self.assertEqual(1, len(credits))
        os_.light_special()
        before = self.machine.game.player.score
        os_.special_collect()                                    # limit 1 reached: 5,000,000 points
        self.advance_time_and_run(0.1)
        self.assertEqual(5000000, self.machine.game.player.score - before)
        os_.adj[22] = 6
        os_.adj[23] = 4                                          # EXTRA BALL
        os_.light_special()
        os_.special_collect()
        self.assertEqual(1, self.machine.game.player.extra_balls)
        os_.adj[22] = 0                                          # NO SPECIALS: always points
        os_.light_special()
        before = self.machine.game.player.score
        os_.special_collect()
        self.advance_time_and_run(0.1)
        self.assertEqual(5000000, self.machine.game.player.score - before)

    def test_13_replay_award(self):
        os_ = self.start_game()
        credits, tickets = self.events("tron_award_credit"), self.events("tron_award_ticket")
        os_.replay_award(1)                                      # CREDIT + knocker
        self.advance_time_and_run(0.1)
        self.assertEqual((1, 0), (len(credits), len(tickets)))
        self.assertEqual(1, self.sounds().count("0x019"))
        os_.adj[13] = 1                                          # TICKET: no knocker
        os_.replay_award(2)
        self.advance_time_and_run(0.1)
        self.assertEqual((1, 1), (len(credits), len(tickets)))
        self.assertEqual(1, self.sounds().count("0x019"))
        os_.adj[13] = 3                                          # EXTRA BALL
        os_.replay_award(3)
        self.assertEqual(1, self.machine.game.player.extra_balls)
        self.assertEqual([1, 1, 1], [os_.audits[c] for c in (10, 11, 12)])

    def test_11_14_15_17_20_replay_levels(self):
        os_ = self.start_game()
        adj = os_.adj
        self.assertEqual([20000000, 0, 0, 0], [os_.replay_level(n) for n in range(1, 5)])   # AUTO, 1 level
        adj[14] = 3
        adj[15] = 7000000
        self.assertEqual([7000000, 14000000, 21000000, 0], [os_.replay_level(n) for n in range(1, 5)])
        adj[11] = 1                                              # FIXED: adj 17-20
        adj[14] = 4
        adj[17], adj[18], adj[19], adj[20] = 11000000, 22000000, 33000000, 44000000
        self.assertEqual([11000000, 22000000, 33000000, 44000000], [os_.replay_level(n) for n in range(1, 5)])
        adj[11] = 0                                              # NONE
        self.assertEqual([0, 0, 0, 0], [os_.replay_level(n) for n in range(1, 5)])
        # the level is what the score is checked against
        adj[11], adj[14], adj[15] = 3, 1, 5000000
        os_.score_add(6000000)
        self.advance_time_and_run(0.5)
        self.assertEqual(1, os_.audits.get(10))

    def test_12_16_dynamic_replay(self):
        os_ = self.start_game()
        adj = os_.adj
        adj[11], adj[16], adj[12] = 2, 10000000, 10              # DYNAMIC from 10,000,000, 10 %
        self.assertEqual([10000000, 0], [os_.replay_level(1), os_.replay_level(2)])
        os_.replay_award(1)                                      # a replay raises it by adj 16
        self.assertEqual(20000000, os_.replay_level(1))
        os_.audits.extra.pop("dynamic_replay")
        os_.replayed = False
        os_._replay_statistics(1)                                # a game without a replay: -10 % of 10 M
        self.assertEqual(9000000, os_.replay_level(1))
        adj[12] = 50
        os_._replay_statistics(1)
        self.assertEqual(5000000, os_.replay_level(1))           # floor 5,000,000
        adj[16] = 20000000
        os_.replay_award(1)                                      # a replay raises it by adj 16
        self.assertEqual(25000000, os_.replay_level(1))

    def test_21_replay_boost(self):
        os_ = self.start_game()
        os_.replay_award(1)
        os_._replay_statistics(1)                                # a game with a replay: boost 1
        self.assertEqual(40000000, os_.replay_level(1))          # (1 + 1) x 20,000,000
        os_.adj[21] = 0
        self.assertEqual(20000000, os_.replay_level(1))
        os_.adj[21] = 1
        os_.replayed = False
        os_._replay_statistics(1)                                # 1 game played >= 1 replay: boost ends
        self.assertEqual(20000000, os_.replay_level(1))

    def _match(self, number=50):
        game_over = self.tron.features_by_name["match"]
        with mock.patch("tron.features.game_over.random.randrange", return_value=number):
            game_over.run(lambda: None)
        self.advance_time_and_run(5)

    def test_30_match_percentage_and_29_award(self):
        os_ = self.start_game()
        os_.score_add(1050)                                      # last two digits 50
        self.advance_time_and_run(0.1)
        credits, tickets = self.events("tron_award_credit"), self.events("tron_award_ticket")
        os_.adj[30] = 11                                         # OFF
        self._match()
        self.assertIsNone(os_.audits.get(0x0f))
        os_.adj[30] = 0                                          # 0 %: the rate (0) is never below it
        self._match()
        self.assertIsNone(os_.audits.get(0x0f))
        os_.adj[30] = 9
        self._match()
        self.assertEqual(1, os_.audits.get(0x0f))
        self.assertEqual((1, 0), (len(credits), len(tickets)))
        self.assertEqual(1, self.sounds().count("0x019"))
        os_.adj[29] = 1                                          # MATCH AWARD: TICKET
        self._match()                                            # 2 matches / 1 game: rate 200 % >= 9 %
        self.assertEqual(1, os_.audits.get(0x0f))
        os_.audit(0x11, 99)                                      # 1 match in 100 games: 1 % < 9 %
        self._match()
        self.assertEqual((2, 1, 1), (os_.audits.get(0x0f), len(credits), len(tickets)))

    def test_35_knocker_volume_and_44_q24(self):
        os_ = self.start_game()
        knocker = self.machine.coils["c_optional_coil"]
        with mock.patch.object(knocker, "pulse") as pulse:
            os_.adj[35] = 0                                      # OFF: silent
            os_.knock()
            self.assertNotIn("0x019", self.sounds())
            os_.knock(forced=True)                               # the knocker test still sounds
            self.assertEqual(1, self.sounds().count("0x019"))
            pulse.assert_not_called()
            os_.adj[35], os_.adj[44] = 1, 2                      # LOW, Q24 = KNOCKER
            os_.knock()
            self.assertEqual(2, self.sounds().count("0x019"))
            pulse.assert_called_once()

    def test_39_timed_plunger(self):
        os_ = self.start_game(plunge=False)
        lane = self.machine.ball_devices["bd_shooter_lane"]
        self.advance_time_and_run(5)
        self.assertEqual(1, lane.balls)                          # OFF: the ball waits
        os_.adj[39] = 3
        os_.serve(3)
        self.advance_time_and_run(2)
        self.assertEqual(1, lane.balls)
        self.advance_time_and_run(2)
        self.assertEqual(0, lane.balls)                          # launched after 3 s

    def test_40_flipper_ball_launch(self):
        os_ = self.start_game(plunge=False)
        lane = self.machine.ball_devices["bd_shooter_lane"]
        self.hit_and_release_switch("s_left_flipper")            # OFF
        self.advance_time_and_run(1)
        self.assertEqual(1, lane.balls)
        os_.adj[40] = 2                                          # RIGHT FLIPPER
        self.hit_and_release_switch("s_left_flipper")
        self.advance_time_and_run(1)
        self.assertEqual(1, lane.balls)
        os_.adj[40] = 4                                          # BOTH FLIPPERS
        self.hit_and_release_switch("s_right_flipper")
        self.advance_time_and_run(1)
        self.assertEqual(1, lane.balls)
        self.hit_switch_and_run("s_left_flipper", 0.1)
        self.hit_and_release_switch("s_right_flipper")
        self.advance_time_and_run(1)
        self.assertEqual(0, lane.balls)
        self.release_switch_and_run("s_left_flipper", 1)
        self.assertFalse(os_._launch_shooter_lane())             # nothing left to launch

    def test_40_flipper_ball_launch_left(self):
        os_ = self.start_game(plunge=False)
        os_.adj[40] = 1                                          # LEFT FLIPPER
        self.hit_and_release_switch("s_left_flipper")
        self.advance_time_and_run(1)
        self.assertEqual(0, self.machine.ball_devices["bd_shooter_lane"].balls)

    def test_41_coindoor_ball_saver(self):
        os_ = self.start_game()
        self.validate()
        os_.kill_ball_save()
        self.hit_switch_and_run("s_coin_door_open", 0.5)         # NO: nothing
        self.assertFalse(os_.mb_save_running())
        self.release_switch_and_run("s_coin_door_open", 0.1)
        os_.adj[41] = 1
        self.hit_switch_and_run("s_coin_door_open", 0.5)
        self.assertTrue(os_.mb_save_running())
        self.assertEqual(1, os_.trace.of("multiball_start")[-1]["balls"])
        self.drain()                                             # the drain is re-served, the ball goes on
        self.assertIsNone(os_.audits.get(8))
        self.assertEqual(1, self.machine.game.player.ball)

    def test_63_lost_ball_recovery(self):
        os_ = self.start_game()
        self.validate()
        os_.ball_search_count = 4
        searches = os_.audits.get(0x25, 0)
        os_._ball_search()                                       # 5th search, YES: a lost ball is fed
        self.assertIn(13, self.deffs())
        self.assertEqual(1, os_.audits.get(0x26))
        self.assertEqual(searches, os_.audits.get(0x25, 0))
        os_.adj[63] = 0
        self.validate()
        os_.ball_search_count = 4
        os_._ball_search()                                       # NO: an ordinary search
        self.assertEqual(searches + 1, os_.audits.get(0x25))
        self.assertEqual(1, os_.audits.get(0x26))
        self.advance_time_and_run(2)                             # search task 0x2b over
        self.hit_and_release_switch("s_left_slingshot")         # the ball was seen: the count starts over
        self.advance_time_and_run(0.1)
        self.assertEqual(0, os_.ball_search_count)


class TestFeatureAdjustments(AdjCase):

    def weight(self, name):
        arcade = self.tron.features_by_name["arcade"]
        from tron.features.arcade import AWARDS
        return arcade.weights()[[a[0] for a in AWARDS].index(name)]

    def test_24_27_award_percentages(self):
        os_ = self.start_game()
        self.assertEqual((1, 1), (self.weight("extra_ball"), self.weight("special")))   # fresh machine
        os_.audit(8, 100)
        os_.audit(9, 50)                                         # 50 % extra balls > adj 27 (25)
        self.assertEqual(0, self.weight("extra_ball"))
        os_.adj[27] = 50
        self.assertEqual(1, self.weight("extra_ball"))           # equal: kept
        os_.adj[27] = 52                                         # 50 + 3 >= 52: just below, dropped
        self.assertEqual(0, self.weight("extra_ball"))
        os_.audit(0x11, 99)
        os_.audit(0x0e, 9)                                       # 9 specials in 100 games
        self.assertEqual(0, self.weight("special"))              # 9 + 2 >= 10
        os_.adj[24] = 12
        self.assertEqual(1, self.weight("special"))

    def test_42_competition_mode(self):
        self.start_game()
        self.assertEqual(100, self.weight("500k"))
        self.tron.adj[42] = 1
        self.assertEqual(1100, self.weight("500k"))

    def test_65_pop_bumper_difficulty(self):
        os_ = self.start_game()
        self.assertEqual(25, os_.switches.pop_hits_needed())
        os_.adj[65] = 2
        self.assertEqual(30, os_.switches.pop_hits_needed())

    def test_66_zuse_fast_scoring_timer(self):
        os_ = self.start_game()
        zuse = os_.features_by_name["zuse"]
        os_.adj[66] = 40
        zuse.start()
        self.assertEqual(40, zuse.clock.seconds)

    def test_67_recognizer_difficulty(self):
        self.tron.adj[67] = 2
        os_ = self.start_game()
        self.assertEqual(2, os_.pd.dbattle_k)

    def test_68_69_disc_multiball_shots(self):
        os_ = self.start_game()
        self.validate()
        os_.adj[68], os_.adj[69] = 4, 1
        dmb = os_.features_by_name["disc_multiball"]
        os_.hook("dmb_start")
        self.advance_time_and_run(1)
        for _ in range(3):
            dmb.disc_mb_shot(7)
        self.assertEqual(0, dmb.phase)
        dmb.disc_mb_shot(7)                                      # 4th disc jackpot: phase 1
        self.assertEqual(1, dmb.phase)
        dmb.disc_mb_shot(6)                                      # 1 Recognizer hit: phase 2 (super)
        self.assertEqual(2, dmb.phase)

    def test_70_71_disc_restart(self):
        os_ = self.start_game()
        self.validate()
        dmb = os_.features_by_name["disc_multiball"]
        os_.adj[70] = 7
        os_.hook("dmb_start")
        self.advance_time_and_run(1)
        dmb.multiball_end()
        self.assertEqual(7, dmb.restart_secs)                    # restart countdown = adj 70
        os_.adj[71] = 3
        self.assertTrue(dmb.disc_restart_autofire())
        self.assertEqual(3 * 62, os_.trace.of("multiball_start")[-1]["save_ticks"])

    def test_72_73_74_tron_award_timers(self):
        os_ = self.start_game()
        targets = os_.features_by_name["tron_targets"]
        os_.adj[72], os_.adj[73], os_.adj[74] = 21, 33, 40
        for award, seconds in ((4, 21), (2, 33), (1, 40)):
            targets._timer_start(award)
            self.assertEqual(seconds, targets.secs[award])

    def test_78_orbit_up_post(self):
        os_ = self.start_game()
        os_.switches.raise_orbit_post()
        self.assertEqual(1, os_.switches.orbit_post)
        os_.switches.drop_orbit_post()
        os_.adj[78] = 1
        os_.switches.raise_orbit_post()
        self.assertEqual(0, os_.switches.orbit_post)

    def test_79_disable_plunge_post(self):
        os_ = self.start_game()
        skill = os_.features_by_name["skill_shots"]
        skill.ball_served(3)
        self.assertFalse(skill.running("B"))
        self.assertTrue(os_.flag(0x1f))                          # B armed for a held flipper
        os_.adj[79] = 1
        skill.ball_served(3)
        self.assertTrue(skill.running("B"))                      # lit at every serve

    def test_82_insult_level(self):
        os_ = self.start_game()
        os_.adj[82] = 0
        self.assertFalse(os_.switches.insult_speech(True))
        os_.adj[82] = 1
        self.assertTrue(os_.switches.insult_speech(True))

    def test_83_84_85_end_of_line_letters(self):
        os_ = self.start_game()
        self.validate()
        eol = os_.features_by_name["end_of_line"]
        os_.adj[83], os_.adj[84], os_.adj[85] = 1, 4, 3
        for side in (0, 1):
            for _ in range(4):
                eol.eol_letter(side)
        self.assertTrue(os_.flag(0x26))                          # 1 set lights it the first time (adj 83)
        self.assertFalse(os_.flag(0x28))                         # EB at the 3rd set (adj 85)
        os_.flag_clear(0x26)
        os_.pd.eol_sets = 0
        os_.pd.eol_left = os_.pd.eol_right = 0
        for side in (0, 1):
            for _ in range(4):
                eol.eol_letter(side)
        self.assertFalse(os_.flag(0x26))                         # later: 4 sets needed (adj 84)

    def test_86_shaker_motor(self):
        os_ = self.start_game()
        shaker = self.machine.coils["c_shaker_motor_optional"]
        os_.deff_start(71)                                       # shaker_run(2, 2), MAXIMAL USE
        self.advance_time_and_run(0.01)                          # in the deff's function, once it runs
        self.assertEqual("enabled", shaker.hw_driver.state)
        self.advance_time_and_run(1)
        self.assertEqual("disabled", shaker.hw_driver.state)
        os_.adj[86] = 1                                          # MINIMAL USE: only min-setting-1 calls
        os_.deff_start(71)
        self.advance_time_and_run(0.01)
        self.assertEqual("disabled", shaker.hw_driver.state)
        self.assertFalse(os_.shaker_run(2, 2))
        self.assertTrue(os_.shaker_run(3, 1))
        os_.adj[86] = 0                                          # NONE
        self.advance_time_and_run(2)
        self.assertFalse(os_.shaker_run(3, 1))
        self.assertEqual(2, sum(1 for e in os_.trace.of("coil") if e["coil"] == 8 and e["on"]))

    def test_77_disc_motor_and_76_bank_motor(self):
        os_ = self.start_game()
        self.validate()
        motors = os_.features_by_name["motors"]
        power = self.machine.coils["c_disc_motor_power"]
        bank = self.machine.coils["c_recognizer_3_bank_motor_relay"]
        os_.flag_set(0x37)                                       # Portal Multiball: the disc spins
        os_.request_refresh()
        self.advance_time_and_run(0.1)
        self.assertEqual("enabled", power.hw_driver.state)
        self.assertEqual("enabled", bank.hw_driver.state)        # the bank moves to the rule's position
        self.hit_switch_and_run("s_3_bank_motor_up" if os_.features_by_name["recognizer"].bank_up
                                else "s_3_bank_motor_dn", 0.1)
        self.assertEqual("disabled", bank.hw_driver.state)       # ... until its switch closes
        os_.flag_clear(0x37)
        os_.request_refresh()
        self.advance_time_and_run(0.1)
        self.assertEqual("disabled", power.hw_driver.state)
        os_.adj[77] = 1                                          # DISABLE DISC MOTOR
        os_.flag_set(0x37)
        os_.request_refresh()
        self.advance_time_and_run(0.1)
        self.assertEqual("disabled", power.hw_driver.state)
        os_.adj[77] = 0
        os_.request_refresh()
        self.advance_time_and_run(0.1)
        os_.hook("tilt")
        self.assertFalse(motors.disc_on)
        self.release_switch_and_run("s_3_bank_motor_up", 0.1)
        self.release_switch_and_run("s_3_bank_motor_dn", 0.1)
        os_.adj[76] = 1                                          # DISABLE RECOGNIZER 3-BANK MOTOR
        motors.bank_drive()
        self.assertEqual("disabled", bank.hw_driver.state)


class TestAuditsAtGameOver(AdjCase):

    def test_score_range_and_game_time_audits(self):
        os_ = self.start_game()
        os_.adj[63] = 0                                          # no lost-ball feed during the long wait
        self.validate()
        os_.score_add(5000000)
        self.advance_time_and_run(70)
        os_.kill_ball_save()
        self.machine.game.balls_per_game = 1
        self.drain(15)
        self.assertIsNone(self.machine.game)
        self.assertEqual(1, os_.audits.get(47))                  # 1 - 1.5 MINUTE GAMES
        self.assertEqual(1, os_.audits.get(21))                  # 4.0M-5.99M SCORES
        self.assertEqual(1, os_.audits.value(29))                # TOTAL PLAYS
        self.assertGreater(os_.audits.value(47), 5000000)        # AVERAGE SCORES
        self.assertEqual("1:1", os_.audits.text(4)[:3])          # AVERAGE GAME TIME 1:1x
        self.assertEqual(1, os_.audits.value(53))                # CENTER DRAINS
