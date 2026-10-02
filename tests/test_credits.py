"""Credits and pricing (tron/credits.py), game start and restart, the high-score table and initials entry
(tron/features/high_scores.py) and the attract pages (tron/features/attract_pages.py): one behaviour test per
adjustment they read (25, 28, 33, 34, 36, 48-62, 2)."""
from unittest import mock

from tests.test_adjustments import AdjCase
from tron.features.high_scores import SOUNDS

TICK_S = 0.01626
DELAY = 30 * TICK_S            # adj 62 factory COIN INPUT DELAY


class CreditCase(AdjCase):
    FREE_PLAY = False          # factory settings

    def coins(self, n, gap=0.7):
        for _ in range(n):
            self.hit_and_release_switch("s_coin")
            self.advance_time_and_run(gap)

    def deff_args(self, deff_id):
        seen = []
        self.machine.events.add_handler("tron_deff_{}".format(deff_id), lambda **kwargs: seen.append(kwargs))
        return seen

    def press_start(self, wait=0.5):
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(wait)


class TestCoins(CreditCase):

    def test_28_usa_10_pricing_and_credit_text(self):
        os_ = self.tron
        cr = os_.credit_model
        shown = self.deff_args(10)
        texts = []
        for _ in range(4):
            self.coins(1)
            texts.append(cr.text())
        self.assertEqual(["CREDITS 1/3", "CREDITS 2/3", "CREDITS 1", "CREDITS 1 1/3"], texts)
        self.assertEqual(texts, [kw["credits"] for kw in shown])            # deff 10 shows the credit text
        self.assertEqual((4, 4, 1), (os_.audits[4], os_.audits[7], os_.audits[1]))
        self.assertEqual(["0x0f0", "0x0f0", "0x0f1", "0x0f0"], [s for s in self.sounds() if s in ("0x0f0", "0x0f1")])
        self.assertEqual({"credits": 1, "counter": 0}, cr.store.written_data)
        os_.adj[28] = 0                                       # AUSTRALIA 1: not in the decompile, USA 10's table
        self.coins(2)
        self.assertEqual(2, cr.credits)

    def test_28_custom_pricing(self):
        os_ = self.tron
        for key, value in (("custom_coin_units", 2), ("custom_units_per_credit", 2)):
            self.machine.variables.set_machine_var(key, value)
        os_.adj[28] = 64                                      # CUSTOM: 2 units a coin, a credit every 2 units
        shown = self.deff_args(10)
        self.coins(1)
        self.assertEqual((1, 2, 1, 2), (os_.credit_model.credits, os_.audits[7], os_.audits[1], len(shown)))
        self.machine.variables.set_machine_var("custom_coin_units", 1)
        self.coins(1)
        self.assertEqual("CREDITS 1 1/2", os_.credit_model.text())
        self.machine.variables.set_machine_var("custom_units_per_credit", 4)
        os_.credit_model.counter = -1
        self.coins(2)                                         # 2 of 4 units: shown reduced
        self.assertEqual("CREDITS 1 1/2", os_.credit_model.text())

    def test_62_coin_input_delay(self):
        os_ = self.tron
        self.hit_and_release_switch("s_coin")
        self.advance_time_and_run(DELAY - 0.05)
        self.assertIsNone(os_.audits.get(4))                  # the coin task still waits
        self.advance_time_and_run(0.1)
        self.assertEqual(1, os_.audits.get(4))
        os_.adj[62] = 45
        self.hit_and_release_switch("s_coin")
        self.advance_time_and_run(DELAY + 0.05)
        self.assertEqual(1, os_.audits.get(4))
        self.advance_time_and_run(15 * TICK_S)
        self.assertEqual(2, os_.audits.get(4))
        os_.adj[62] = 61                                      # OFF: at once
        self.hit_and_release_switch("s_coin")
        self.advance_time_and_run(0.01)
        self.assertEqual(3, os_.audits.get(4))
        os_.adj[62] = 30                                      # a coin while the service menu runs is dropped
        self.hit_and_release_switch("s_coin")
        self.hit_and_release_switch("s_service_select")
        self.advance_time_and_run(1)
        self.assertEqual(3, os_.audits.get(4))

    def test_33_credit_limit(self):
        os_ = self.tron
        os_.adj[33] = 4
        os_.adj[62] = 61
        self.coins(15, gap=0.05)                              # 5 credits paid
        self.assertEqual((4, 5), (os_.credit_model.credits, os_.audits[1]))
        self.assertEqual(0, os_.credit_model.award(1))             # a free game cannot pass the limit either
        os_.adj[33] = 30
        self.coins(3, gap=0.05)
        self.assertEqual(5, os_.credit_model.credits)

    def test_service_credit_and_power_cycle(self):
        os_ = self.tron
        shown = self.deff_args(17)
        self.hit_and_release_switch("s_service_back")         # outside the service menu: a service credit
        self.advance_time_and_run(0.1)
        self.assertEqual((1, 1, ["CREDITS 1"]), (os_.credit_model.credits, os_.audits[0x24],
                                                 [kw["credits"] for kw in shown]))
        os_.adj[33] = 4
        os_.credit_model.add(10)
        self.hit_and_release_switch("s_service_back")         # at the limit: no audit, deff 17 still
        self.advance_time_and_run(0.1)
        self.assertEqual((4, 1, 2), (os_.credit_model.credits, os_.audits[0x24], len(shown)))
        self.hit_and_release_switch("s_service_select")       # BACK inside the menu leaves it, no credit
        self.advance_time_and_run(0.1)
        self.hit_and_release_switch("s_service_back")
        self.advance_time_and_run(0.1)
        self.assertFalse(os_.in_service)
        self.assertEqual(1, os_.audits[0x24])


class TestCreditsKept(CreditCase):

    def _get_mock_data(self):
        return {"tron_credits": {"credits": 2, "counter": 1}}

    def test_credits_survive_power_cycle(self):
        cr = self.tron.credit_model
        self.assertEqual(("CREDITS 2 2/3", 2), (cr.text(), cr.credits))


class TestGameStart(CreditCase):

    def test_34_free_play_and_start_needs_a_credit(self):
        os_ = self.tron
        self.fill_trough()
        refused, shown = self.events("tron_start_refused"), self.deff_args(15)
        self.press_start()
        self.assertIsNone(self.machine.game)                  # no credit: event 0x2d, deff 15
        self.assertEqual((1, "CREDITS 0"), (len(refused), shown[0]["credits"]))
        os_.adj[34] = 1                                       # FREE PLAY
        self.assertEqual("FREE PLAY", os_.credit_model.text())
        self.press_start(2)
        self.assertIsNotNone(self.machine.game)
        self.assertEqual(1, os_.audits[0x11])

    def test_start_takes_a_credit_and_players_need_credits(self):
        os_ = self.tron
        self.fill_trough()
        os_.credit_model.add(1)
        self.press_start(2)
        self.assertEqual((0, 1), (os_.credit_model.credits, os_.audits[0x11]))
        self.press_start()                                    # ball 1, no credit: no player 2
        self.assertEqual(1, len(self.machine.game.player_list))
        os_.credit_model.add(1)
        self.press_start()
        self.assertEqual((2, 0, 2), (len(self.machine.game.player_list), os_.credit_model.credits, os_.audits[0x11]))

    def test_36_game_restart(self):
        os_ = self.tron
        os_.adj[34] = 1
        self.start_game()
        os_.adj[63] = 0
        self.hit_switch_and_run("s_start_button", 1.2)       # ball 1: START held adds a player, no restart
        self.release_switch_and_run("s_start_button", 0.1)
        self.assertEqual(2, os_.audits[0x11])
        for first in (False, True):                           # player 1 and player 2 play ball 1
            if first:
                self.release_switch_and_run("s_shooter_lane", 1)
            self.validate()
            os_.kill_ball_save()
            self.drain(10)
        game = self.machine.game
        self.assertEqual(2, game.player.ball)
        os_.adj[36] = 0                                       # NO: holding START does nothing
        self.hit_switch_and_run("s_start_button", 1.2)
        self.release_switch_and_run("s_start_button", 0.1)
        self.assertEqual(2, self.machine.game.player.ball)
        os_.adj[36] = 1
        os_.credit_model.add(1)
        self.hit_switch_and_run("s_start_button", 0.9)       # held 0.9 s: not yet
        self.assertEqual(2, self.machine.game.player.ball)
        self.advance_time_and_run(0.2)                        # 62 ticks: a new game, no game over
        self.release_switch_and_run("s_start_button", 3)
        self.assertEqual((1, 1, 3, 0), (self.machine.game.player.ball, len(self.machine.game.player_list),
                                        os_.audits[0x11], os_.credit_model.credits))
        self.assertNotIn(38, self.deffs())                    # no match


class TestFreeGames(CreditCase):

    def test_25_free_game_limit(self):
        os_ = self.tron
        os_.adj[34] = 1
        self.start_game()
        os_.adj[25] = 1
        os_.replay_award(1)                                   # credit + knocker
        self.advance_time_and_run(0.1)
        os_.replay_award(2)                                   # over the limit: no credit, no knocker
        self.advance_time_and_run(0.1)
        self.assertEqual((1, 1), (os_.credit_model.credits, self.sounds().count("0x019")))
        os_.adj[25] = 0                                       # NO FREE GAMES
        self.assertEqual(0, os_.award_credit())
        os_.adj[25] = 10                                      # UNLIMITED
        self.assertEqual(3, os_.award_credit(3))


class HsCase(CreditCase):
    FREE_PLAY = True

    def play(self, *scores):
        """A one-ball game of len(scores) players ending with these scores (no match, no replays)."""
        os_ = self.tron
        os_.adj[30], os_.adj[13], os_.adj[63] = 11, 2, 0
        self.fill_trough()
        for _ in scores:
            self.hit_and_release_switch("s_start_button")
            self.advance_time_and_run(0.2)
        self.advance_time_and_run(2)
        self.machine.game.balls_per_game = 1
        for player, score in zip(self.machine.game.player_list, scores):
            player.score = score
        for _ in scores:
            self.release_switch_and_run("s_shooter_lane", 1)
            self.validate()
            os_.kill_ball_save()
            self.drain(9)
        self.advance_time_and_run(2)

    def entry(self):
        hs = self.tron.features_by_name["high_scores"]
        self.assertIsNotNone(hs.entry, "no initials entry")
        return hs.entry

    def flip(self, side, times=1):
        for _ in range(times):
            self.hit_switch_and_run("s_{}_flipper".format(side), 0.03)
            self.release_switch_and_run("s_{}_flipper".format(side), 0.03)

    def take(self):
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(0.05)


class TestHighScores(HsCase):

    def test_49_53_defaults_and_resets(self):
        os_ = self.tron
        hs = os_.features_by_name["high_scores"]
        self.assertEqual([("GRAND CHAMPION", "G S", 75000000), ("HIGH SCORE #1", "L R", 55000000)], hs.table()[:2])
        self.assertEqual([30000000, 25000000], [e["score"] for e in hs.entries[3:]])
        for num in range(49, 54):
            os_.adj[num] = 1000000 * num
        hs.entries[0]["name"] = hs.entries[1]["name"] = "XYZ"
        hs.reset(2)                                           # RESET HIGH SCORES: #1-#4 only
        self.assertEqual([("XYZ", 75000000), ("L R", 50000000)],
                         [(e["name"], e["score"]) for e in hs.entries[:2]])
        hs.reset(1)                                           # RESET GRAND CHAMPION
        self.assertEqual(("G S", 49000000), (hs.entries[0]["name"], hs.entries[0]["score"]))
        self.assertEqual(hs.entries, hs.store.written_data["entries"])

    def test_48_allow_high_scores_off(self):
        os_ = self.tron
        os_.adj[48] = 0
        self.play(90000000)
        self.assertNotIn(31, self.deffs())
        self.assertIn(38, self.deffs())                       # straight to the match
        self.assertEqual([], os_.features_by_name["high_scores"].table())

    def test_entry_initials_award_and_table(self):
        os_ = self.tron
        stages = self.events("tron_high_score")
        os_.adj[56] = 1                                       # HIGH SCORE #1 AWARDS: 1 credit (factory)
        self.play(60000000)
        self.assertEqual([31, 32], [d for d in self.deffs() if d in (31, 32, 33, 38)])
        entry = self.entry()
        self.assertEqual(0x40, os_.state & 0x40)
        self.flip("right", 2)                                 # C
        self.take()
        self.flip("left", 2)                                  # A
        self.take()
        self.flip("left")                                     # from A it wraps to the specials: SPACE
        self.assertEqual("SPACE", entry.letter())
        self.take()
        self.assertEqual(("CA ", "END"), (entry.name, entry.letter()))
        self.flip("right")                                    # a full name: BACK <-> END
        self.assertEqual("BACK", entry.letter())
        self.take()
        self.flip("left", 3)                                  # B ... Z, Y, X
        self.take()
        self.assertEqual("CAX", entry.name)
        with mock.patch.dict(SOUNDS, {"select": 0x00c}):     # the entry sounds are ROM data (not decompiled)
            self.take()                                       # END
        self.assertIn("0x00c", self.sounds())
        self.advance_time_and_run(3)
        hs = os_.features_by_name["high_scores"]
        self.assertEqual(("CAX", hs.scores[0]), (hs.entries[1]["name"], hs.entries[1]["score"]))
        self.assertEqual(("L R", 55000000), (hs.entries[2]["name"], hs.entries[2]["score"]))
        self.assertEqual([0x33, 0x34, 0x35, 0x36, 0x37, 0x38], [s["stage"] for s in stages])
        self.assertEqual((1, 1), (os_.credit_model.credits, os_.audits[0x10]))
        self.assertIn("0x019", self.sounds())                 # credit award: knocker
        self.assertEqual([31, 32, 33, 38], [d for d in self.deffs() if d in (31, 32, 33, 38)])
        self.assertEqual(0, os_.audits.get(0x2c, 0))          # the flipper buttons were not flipper audits
        self.assertFalse(os_.state & 0x40)

    def test_55_54_two_players_grand_champion_and_tickets(self):
        os_ = self.tron
        os_.adj[54], os_.adj[55] = 1, 2                       # TICKET, 2 for the grand champion
        tickets = self.events("tron_award_ticket")
        self.play(60000000, 80000000)
        names = []
        for name in ("B", "A"):                               # player 2 first (the grand champion), then 1
            entry = self.entry()
            names.append(entry.player)
            self.flip("right", ord(name) - ord("A"))
            for _ in range(3):
                self.take()
            self.take()
            self.advance_time_and_run(5)                      # deff 33, then deff 31 of the next player
        hs = os_.features_by_name["high_scores"]
        p1, p2 = hs.scores
        self.assertEqual([2, 1], names)
        self.assertEqual([("BBB", p2), ("G S", 75000000), ("AAA", p1), ("L R", 55000000)],
                         [(e["name"], e["score"]) for e in hs.entries[:4]])
        self.assertEqual((2, 2, 0), (len(tickets), os_.audits[0x10], os_.credit_model.credits))   # #2: adj 57 = 0

    def test_60_ten_letters_timeout_and_57_59_awards(self):
        os_ = self.tron
        os_.adj[60] = 1                                       # 10 LETTER NAME
        os_.adj[54], os_.adj[57] = 2, 0                       # TOKEN
        self.play(45000000)                                   # HIGH SCORE #2
        entry = self.entry()
        self.assertEqual(10, entry.size)
        self.hit_switch_and_run("s_right_flipper", 33 * 0.01626)   # held: repeats after 31 frames
        self.assertEqual("C", entry.letter())
        self.advance_time_and_run(8 * 0.01626)                # then every 7
        self.release_switch_and_run("s_right_flipper", 0.05)
        self.assertEqual("D", entry.letter())
        self.hit_switch_and_run("s_left_flipper", 0.05)       # C
        self.hit_switch_and_run("s_right_flipper", 0.3)       # both buttons held: no step
        self.release_switch_and_run("s_left_flipper", 0)
        self.release_switch_and_run("s_right_flipper", 0.05)
        self.assertEqual("C", entry.letter())
        self.take()
        self.advance_time_and_run(31 * 63 * 0.01626 + 1)     # 30 s, then the last 15 shown
        self.assertTrue(entry.counting)
        self.advance_time_and_run(16 * 63 * 0.01626 + 3)
        hs = os_.features_by_name["high_scores"]
        self.assertEqual("CC", hs.entries[2]["name"])         # the letter under the cursor is kept
        self.assertEqual(0, os_.audits.get(0x10, 0))          # no award on #2 at factory (adj 57 = 0)

    def test_58_59_lower_awards(self):
        os_ = self.tron
        os_.adj[58], os_.adj[59] = 1, 0
        self.play(35000000, 32000000)                         # HIGH SCORE #3 and #4 (the old #3 moved down)
        for _ in range(2):
            self.take()                                       # A
            self.take()
            self.take()
            self.take()                                       # END
            self.advance_time_and_run(5)
        hs = os_.features_by_name["high_scores"]
        self.assertEqual(["AAA", "AAA"], [e["name"] for e in hs.entries[3:]])
        self.assertEqual((1, 1), (os_.credit_model.credits, os_.audits[0x10]))   # #3 pays 1, #4 nothing (adj 59 = 0)

    def test_61_reset_count(self):
        os_ = self.tron
        hs = os_.features_by_name["high_scores"]
        os_.adj[61] = 100
        hs.reset_all()
        hs.count = 2
        hs.entries[0]["name"] = hs.entries[1]["name"] = "XYZ"
        for _ in range(2):
            self.play(1000)
            self.assertEqual("XYZ", hs.entries[1]["name"])
        self.hit_and_release_switch("s_start_button")         # count 0: the high scores are reset
        self.advance_time_and_run(1)
        self.assertEqual(("XYZ", "L R", 100), (hs.entries[0]["name"], hs.entries[1]["name"], hs.count))
        os_.adj[61] = 0                                       # OFF
        hs.game_started()
        self.assertEqual(100, hs.count)


class TestAttractPages(HsCase):

    def test_pages_flippers_and_2_custom_message(self):
        os_ = self.tron
        pages = self.events("tron_attract_page")
        self.advance_time_and_run(12)
        names = [p["page"] for p in pages]
        self.assertEqual(["GAME OVER", "CREDITS", "REPLAY", "GRAND CHAMPION", "HIGH SCORE #1"], names[:5])
        self.assertEqual(["GRAND CHAMPION", "G S", "75,000,000"], pages[3]["lines"])
        self.assertEqual(["FREE PLAY"], pages[1]["lines"])
        self.machine.variables.set_machine_var("custom_message_text", "HELLO")
        self.advance_time_and_run(46)
        names = [p["page"] for p in pages]
        self.assertIn("CUSTOM MESSAGE", names)
        self.assertEqual("CREDITS", names[names.index("CLOCK") + 1])     # wraps without GAME OVER
        os_.adj[2] = 0                                                   # CUSTOM MESSAGE OFF
        self.advance_time_and_run(60)                                    # from the next pass on
        self.assertNotIn("CUSTOM MESSAGE", [p["page"] for p in pages[-10:]])
        os_.features_by_name["attract_pages"].attract_start()
        self.hit_and_release_switch("s_left_flipper")                    # first page: back to the last one
        self.advance_time_and_run(0.01)
        self.assertEqual("CLOCK", pages[-1]["page"])
        current = pages[-1]["page"]
        self.hit_and_release_switch("s_right_flipper")
        self.hit_and_release_switch("s_left_flipper")
        self.advance_time_and_run(0.01)
        self.assertEqual(current, pages[-1]["page"])          # next, then back
        self.assertNotEqual(current, pages[-2]["page"])
        self.play(1000)                                       # the last game's scores replace REPLAY AT
        self.advance_time_and_run(15)
        after = [p["page"] for p in pages]
        last = len(after) - 1 - after[::-1].index("GAME OVER")
        self.assertEqual(["GAME OVER", "CREDITS", "PLAYER 1", "GRAND CHAMPION"], after[last:last + 4])
