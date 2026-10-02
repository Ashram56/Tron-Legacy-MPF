"""End of Line (Daft Punk) multiball and the End of Line combo jackpot: the paths the reference
scenarios do not reach (deff 55 texts, grace restart, ball end total, tilt, combo jackpot hooks)."""
from tests.tron_test import TronTestCase

TICK = 0.01626


class TestEndOfLine(TronTestCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")         # playfield valid
        self.advance_time_and_run(1)
        return self.tron.features_by_name["end_of_line"]

    def last(self, ev, **match):
        found = [e for e in self.tron.trace.events if e["ev"] == ev
                 and all(e.get(k) == v for k, v in match.items())]
        return found[-1] if found else None

    def test_letters_more_to_texts_and_extra_ball_once(self):
        eol = self.start_game()
        os_ = self.tron
        os_.adj[83], os_.adj[85] = 2, 1
        calls = []
        start = os_.display.start
        os_.display.start = lambda deff_id, **kw: (calls.append((deff_id, kw)), start(deff_id, **kw))[1]
        self.assertTrue(eol.eol_letter(0))
        self.assertEqual(self.tron.pd.eol_left, 1)
        # 2 sets to light the MB, 1 to light the EB: "1 MORE TO / LIGHT EX. BALL"
        self.assertEqual(calls[-1], (55, dict(before=(0, 0), after=(1, 0), flags=4, more=1)))
        for _ in range(3):
            eol.eol_letter(0)
        for _ in range(4):
            eol.eol_letter(1)
        self.assertTrue(os_.flag(0x28))                       # set 1 lit the extra ball
        self.assertEqual(calls[-1][1]["flags"], 1 | 8)        # EB lit; "1 MORE TO LIGHT MULTIBALL"
        self.assertEqual(os_.pd.eol_sets, 1)
        # the extra ball is lit once per game: same set count again does not relight it
        self.assertFalse(eol.extra_ball_check(1))
        os_.adj[85] = 0
        os_.flags.discard(0x28)
        self.assertFalse(eol.extra_ball_check(1))
        # equal counts: "LIGHT M.B. + E.B."
        os_.adj[85] = 2
        for _ in range(4):
            eol.eol_letter(0)
        self.assertEqual(os_.pd.eol_left, 4)
        self.assertEqual(calls[-1][1]["flags"], 0xc)
        os_.adj[83], os_.adj[85] = 3, 3
        eol.eol_letter(0)                                     # full word: nothing more, still deff 55
        self.assertEqual(os_.pd.eol_left, 4)

    def test_multiball_grace_restart_total_and_ball_end(self):
        eol = self.start_game()
        os_ = self.tron
        os_.flag_set(0x26)
        self.assertTrue(eol.eol_vuk())
        self.assertTrue(os_.flag(0x27))
        self.assertFalse(os_.flag(0x26))
        self.assertTrue(eol.eol_running())
        self.assertTrue(eol.eol_running_or_grace_a())
        self.assertTrue(os_.hook("eol_running_or_grace"))
        self.assertFalse(eol.eol_letter(0))                   # no letters while it runs
        self.assertFalse(eol.eol_vuk())                       # not lit any more
        self.advance_time_and_run(8)
        # down to one ball: grace, then an add-a-ball (2nd disc hit) restarts the mode
        eol.eol_disc_jackpot(2)
        os_.hook("multiball_end")
        self.assertFalse(os_.flag(0x27))
        self.assertTrue(eol.active())
        self.assertTrue(eol.eol_running_or_grace_a())
        self.assertTrue(eol.eol_shot_score())
        eol.eol_disc_jackpot(2)                               # aab_left 1 -> 0: ball added
        self.assertTrue(os_.flag(0x27))
        self.assertFalse(os_.task_running(0xb0))
        self.assertEqual(eol.aab_left, 3)
        # grace runs out: the total waits for an idle display, then deff 61
        os_.hook("multiball_end")
        self.advance_time_and_run(187 * TICK)
        self.assertTrue(os_.task_running(0xb1))
        self.assertFalse(eol.eol_running_or_grace_a())
        self.advance_time_and_run(130 * TICK + 4)
        self.assertIsNotNone(self.last("deff_start", id=61))
        self.assertFalse(eol.active())
        self.assertFalse(eol.eol_shot_score())
        self.assertFalse(eol.jackpot_shot(0))
        self.advance_time_and_run(4)
        self.assertFalse(eol.total_pending)
        # a new multiball, then the ball ends while it runs: total shown, ball end waits for it
        os_.flag_set(0x26)
        self.assertTrue(eol.eol_vuk())
        os_.display.clear()
        eol.ball_end()
        self.assertFalse(os_.flag(0x27))
        self.assertEqual(eol.ball_end_wait(), 169)
        eol.ball_end()                                        # not active any more: nothing
        # tilted: no total
        os_.flag_set(0x27)
        os_.state |= 0x200
        eol.total_pending = False
        eol.ball_end()
        self.assertIsNone(eol.ball_end_wait())
        os_.state &= ~0x200
        eol.multiball_end()                                   # not running: nothing
        self.assertFalse(os_.task_running(0xb0))

    def test_start_refused_while_another_multiball_runs(self):
        eol = self.start_game()
        os_ = self.tron
        os_.flag_set(0x26)
        os_.flag_set(0x24)                                    # Disc Multiball running
        self.assertFalse(eol.eol_vuk())
        self.assertTrue(os_.flag(0x26))                       # stays lit
        self.assertFalse(eol.lit_rule())
        os_.flags.discard(0x24)
        self.assertTrue(eol.lit_rule())
        os_.state |= 0x200                                    # tilted: multiball_start refuses
        self.assertFalse(eol.eol_vuk())
        os_.state &= ~0x200
        # the extra ball is only marked given when the VUK award table took it
        hooks = os_.hooks["vuk_lit_add"]
        os_.hooks["vuk_lit_add"] = [lambda bits, unlimited=False: 0]
        self.assertFalse(eol.extra_ball_check(os_.adj_value(85)))
        os_.hooks["vuk_lit_add"] = hooks
        self.assertFalse(os_.flag(0x28))

    def test_combo_jackpot_hooks(self):
        eol = self.start_game()
        os_ = self.tron
        self.assertEqual(os_.hook("eol_combo_jackpot_value"), 500000)    # the combos feature's value
        os_.pd.eol_combo_jackpot = 850000
        self.assertFalse(eol.eol_combo_jackpot())             # not lit
        eol.eol_combo_jackpot_light()
        self.advance_time_and_run(200 * TICK)                 # 0xcf over, 0xd0 still collectable
        self.assertTrue(os_.task_running(0xd0))
        self.assertTrue(eol.eol_combo_jackpot())
        self.assertEqual(os_.pd.eol_jackpot_collected, 1)
        self.assertEqual(os_.pd.eol_combo_jackpot, 850000)    # not reset on collect


class TestMultiballAndDisplayModel(TronTestCase):
    """Generic OS / display pieces added with End of Line (multiball task, deff hold, idle wait)."""

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)
        self.hit_and_release_switch("s_zen_rollover")
        self.advance_time_and_run(1)

    def test_multiball_save_drain_not_audited(self):
        self.start_game()
        os_ = self.tron
        self.assertTrue(os_.multiball_start(2, 625, 125))
        self.advance_time_and_run(4)
        self.assertTrue(os_.mb_save_running())
        audits = os_.audits.get(0x2b, 0)
        self.assertEqual(os_._ball_drain(balls=1), {"balls": 0})       # saved, no "ball saved" audit
        self.assertEqual(os_.audits.get(0x2b, 0), audits)
        os_.state |= 0x200                                    # tilted: refused
        self.assertFalse(os_.multiball_start(4, 312, 187))
        os_.state &= ~0x200

    def test_deff_hold_and_idle_wait(self):
        self.start_game()
        os_, display = self.tron, self.tron.display
        display.start(58)                                     # 2.2 s, prio 196
        self.advance_time_and_run(0.5)
        display.start(61)                                     # prio 207 replaces it before its hold
        self.advance_time_and_run(2)
        self.assertEqual(display.fg, 61)
        ended = []
        display.when_idle(0x50, 60, timeout=10, on_end=lambda: ended.append(1))
        self.advance_time_and_run(0.3)
        self.assertEqual(ended, [1])                          # gave up waiting
        self.assertEqual(display.idle_waits, [])
        self.advance_time_and_run(2)
        display.when_idle(0x50, 60)                           # idle display: plays at once
        self.advance_time_and_run(0.1)
        self.assertEqual(display.fg, 60)
        # a show ends at the start of its deff's hold, and the mode's background deff restarts
        eol = self.tron.features_by_name["end_of_line"]
        os_.flag_set(0x27)
        display.clear()
        display.queue(0xa6, 56)
        self.advance_time_and_run(display.media[56].seconds - 5 * TICK)
        self.assertIsNone(display.show)
        self.assertEqual(display.fg, 56)
        self.assertEqual(display.fg_prio, 0x20)
        self.assertTrue(eol.background_on())
        self.assertEqual(self.last("deff_start", id=57)["rule"], 1)
        os_.flags.discard(0x27)

    def last(self, ev, **match):
        found = [e for e in self.tron.trace.events if e["ev"] == ev
                 and all(e.get(k) == v for k, v in match.items())]
        return found[-1] if found else None
