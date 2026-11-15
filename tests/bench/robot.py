"""The bench's test base: a player robot on the physical table (tests/bench/table.py) and the invariants
it checks after every action (docs/test_bench.md).

The robot only does what a player or a ball can do: press buttons, plunge, send the ball on the
playfield to a switch, to the scoop or down the drain. It cannot hit a switch without a ball on the
playfield. Mode helpers (light_*, start_*) reach every mode through the switches, as a player would.
"""
import os
import random

from tests.bench.table import BALLS, Table
from tests.tron_test import TronTestCase

# the eight canonical shots and the other targets: name -> switches the ball closes, in order
SHOTS = {
    "left_orbit": ("s_left_orbit",),
    "left_ramp": ("s_l_ramp_entrance", "s_l_ramp_exit"),
    "left_loop": ("s_left_spinner",),
    "right_loop": ("s_right_inner_loop",),
    "right_ramp": ("s_r_ramp_entrance", "s_r_ramp_exit"),
    "right_orbit": ("s_right_orbit",),
    "disc": ("s_disc_opto",),
    "right_spinner": ("s_right_orbit_spinner",),
    "zen": ("s_zen_rollover",),
    "tron_t": ("s_tron_t",), "tron_r": ("s_tron_r",), "tron_o": ("s_tron_o",), "tron_n": ("s_tron_n",),
    "zuse_z": ("s_zuse_z",), "zuse_u": ("s_zuse_u",), "zuse_s": ("s_zuse_s",), "zuse_e": ("s_zuse_e",),
    "clu_c": ("s_clu_c",), "clu_l": ("s_clu_l",), "clu_u": ("s_clu_u",),
    "bank_l": ("s_recogniz_3_bank_l",), "bank_c": ("s_recogniz_3_bank_c",), "bank_r": ("s_recogniz_3_bank_r",),
    "pop_l": ("s_left_bumper",), "pop_r": ("s_right_bumper",), "pop_b": ("s_bottom_bumper",),
    "sling_l": ("s_left_slingshot",), "sling_r": ("s_right_slingshot",),
}
MAJOR_SHOTS = ("left_orbit", "left_ramp", "left_loop", "right_loop", "right_ramp", "right_orbit")
# repeat guards of the switch handlers (switches.py): the tasks that make the next hit "not a shot"
GUARDS = {
    "left_orbit": (0x67, 0x66, 0x3c), "right_orbit": (0x69, 0x68, 0x3c), "left_loop": (0x64,),
    "right_spinner": (0x65,), "disc": (0x3f,),
    "bank_l": (0x7b,), "bank_c": (0x7b,), "bank_r": (0x7b,),
    "tron_t": (0x77,), "tron_r": (0x77,), "tron_o": (0x77,), "tron_n": (0x77,),
    "zuse_z": (0x4c,), "zuse_u": (0x4c,), "zuse_s": (0x4c,), "zuse_e": (0x4c,),
}
MB_FLAGS = {0x24: "Disc", 0x27: "End of Line", 0x29: "Quorra", 0x2b: "Light Cycle", 0x37: "Portal"}
SOS_FLAG = 0x34
# tasks that belong to a ball in play: none of them may survive into attract mode (the combo window
# 0xcd/0xce/0xcf is created with flag 0x100, which the ROM's end of ball keeps: task_kill(0, 0x100))
BALL_TASKS = (0xc0, 0xc1, 0xc2, 0xc3, 0x59, 0x5b, 0x5a, 0x80, 0xc6, 199, 200, 0xab, 0xac, 0xad, 0xae, 0xaf,
              0xb0, 0xb1, 0xb3, 0xb4, 0xb8, 0xb9, 0xba, 0xbb, 0xbc, 0xbd, 0xd1, 0xd2, 0xd0,
              0x70, 0x72, 0x74, 0x7d, 0x31, 0x32, 0x34, 0x35, 0x43, 0xc9, 0xcc, "multiball")
ARCADE_500K = 0
SETTLE = 0.25


class BenchError(AssertionError):
    """The bench itself was asked for something impossible (no ball to play), or an invariant broke."""


class Bench(TronTestCase):
    """One machine on the virtual platform with the physical table."""

    FREE_PLAY = True
    DROP_TARGETS = True          # LE drop targets (stay down until coil 3); False = the Pro's standups
    AUTOPLUNGE = 1.0             # the player plunges this long after a ball reaches the shooter lane (None: never)
    ARCADE = ARCADE_500K         # Flynn's Arcade award forced at every collect (None: the weighted draw)
    CHECK = True                 # check the invariants after every action

    def get_platform(self):
        return "virtual"

    def setUp(self):
        super().setUp()
        self.table = Table(self, drop_targets=self.DROP_TARGETS)
        self.rng = random.Random(1974)
        self.autoplunge = self.AUTOPLUNGE
        self.arcade = self.ARCADE
        self.problems = []           # invariant failures seen from inside callbacks
        self._scores = {}
        self._tilt_score = None
        self._desync_since = None
        self.balls_served = 0
        pick = self.tron.pick

        def forced_pick(name, weights):
            if name == "arcade" and self.arcade is not None and weights[self.arcade] > 0:
                return self.arcade
            return pick(name, weights)
        self.tron.pick = forced_pick
        self.machine.switch_controller.add_switch_handler("s_shooter_lane", self._on_shooter, state=1)
        self.tron.register("ball_served", self._check_ball_served)
        self.machine.events.add_handler("game_ended", self._check_game_ended, priority=1)
        self.advance_time_and_run(2)

    def tearDown(self):
        try:
            for _ in range(150):                 # a bonus count finishes: MPF's shutdown would clear its
                if not self.tron.state & 0x05 or not self.machine.game:      # ball_ending queue with no game
                    break
                self.advance_time_and_run(0.2)
            self.advance_time_and_run(2)         # a ball start in progress finishes (its event queue)
            if self.CHECK and not self.problems and not self._exception:
                self.check()
        finally:
            super().tearDown()
        if self.problems:
            raise BenchError("; ".join(self.problems))

    # ------------------------------------------------------------------ time

    def wait(self, seconds, check=True):
        self.advance_time_and_run(seconds)
        if check and self.CHECK:
            self.check()

    def wait_until(self, cond, timeout=30.0, step=0.1, what=""):
        waited = 0.0
        while not cond():
            if waited >= timeout:
                raise BenchError("timed out after {} s waiting for {}: {}".format(timeout, what() if callable(what) else what or cond, self.where()))
            self.advance_time_and_run(step)
            waited += step
        return waited

    def where(self):
        os_, game = self.tron, self.machine.game
        return "{} state={:#x} flags={} bip={} ball={} held={} mb_pending={}".format(
            self.table, os_.state, sorted(os_.flags), game.balls_in_play if game else None,
            game.player.ball if game and game.player else None, os_.ball_held, os_._mb_pending)

    # ------------------------------------------------------------------ buttons

    def press(self, switch, seconds=0.05, settle=0.1):
        self.machine.switch_controller.process_switch(switch, 1, True)
        self.advance_time_and_run(seconds)
        self.machine.switch_controller.process_switch(switch, 0, True)
        self.advance_time_and_run(settle)

    def start_game(self, players=1, plunge=True, validate=False):
        """START (free play unless the test turned it off), then the first plunge."""
        for _ in range(players):
            self.press("s_start_button")
            self.advance_time_and_run(0.4)
        self.assertIsNotNone(self.machine.game, "no game started")
        self.assertEqual(players, len(self.machine.game.player_list))
        if plunge:
            self.ball_in_play()
            if validate:
                self.validate()
        return self.tron

    def flip(self, side="both", seconds=0.05):
        for name in (("s_left_flipper", "s_right_flipper") if side == "both" else ("s_{}_flipper".format(side),)):
            self.machine.switch_controller.process_switch(name, 1, True)
        self.advance_time_and_run(seconds)
        for name in (("s_left_flipper", "s_right_flipper") if side == "both" else ("s_{}_flipper".format(side),)):
            self.machine.switch_controller.process_switch(name, 0, True)
        self.advance_time_and_run(0.05)

    def tilt_bob(self, settle=1.1):
        self.press("s_plumb_bob_tilt", settle=settle)

    def tilt_out(self):
        """Bob the plumb until the game tilts (adj 32 warnings first)."""
        for _ in range(8):
            if self.tron.tilted:
                return
            self.tilt_bob()
        raise BenchError("the game never tilted")

    # ------------------------------------------------------------------ the ball

    def _on_shooter(self, **kwargs):
        if self.autoplunge is not None:
            self.machine.clock.schedule_once(lambda *a: self._auto_plunge(), self.autoplunge)

    def _auto_plunge(self):
        if self.table.shooter and self.machine.game and self.autoplunge is not None:
            self.table.launch()

    def plunge(self):
        if not self.table.launch():
            raise BenchError("no ball in the shooter lane to plunge: " + self.where())
        self.advance_time_and_run(0.8)

    def ball_in_play(self, timeout=60.0):
        """Wait for a ball on the playfield (plunging it when the player has to); initials entry is answered."""
        waited = 0.0
        while self.table.pf == 0:
            if not self.machine.game:
                raise BenchError("the game is over: no ball will come")
            if self.tron.state & 0x40:
                self.press("s_start_button", settle=0.2)          # high score initials: take the letters
            if self.table.shooter and self.autoplunge is None:
                self.table.launch()
            self.advance_time_and_run(0.1)
            waited += 0.1
            if waited > timeout:
                raise BenchError("no ball reached the playfield in {} s: {}".format(timeout, self.where()))
        return waited

    def hit(self, switch, settle=SETTLE):
        """The ball on the playfield closes one switch."""
        if self.table.pf <= 0:
            raise BenchError("no ball on the playfield to hit {}: {}".format(switch, self.where()))
        hit = self.table.hit(switch)
        self.advance_time_and_run(settle)
        if self.CHECK:
            self.check()
        return hit

    def clear_guards(self, name, timeout=15.0):   # each ball leaving the shooter lane restarts 0x66
        guards = GUARDS.get(name, ())
        if guards:
            self.wait_until(lambda: not any(self.tron.task_running(t) for t in guards), timeout,
                            what=lambda: "the repeat guard of {} (tasks {})".format(
                                name, [hex(t) for t in guards if self.tron.task_running(t)]))

    def shot(self, name, clean=True, settle=SETTLE):
        """A shot by name (SHOTS). clean: wait for the switch's repeat guard first, so the hit is a shot."""
        if clean:
            self.clear_guards(name)
        for switch in SHOTS[name]:
            self.hit(switch, settle=0.08)
        self.wait(settle)

    def shots(self, *names, **kwargs):
        for name in names:
            self.shot(name, **kwargs)

    def scoop(self, wait=True, timeout=40.0):
        """The ball goes into the VUK; wait until it is kicked back onto the playfield."""
        if self.table.pf <= 0:
            raise BenchError("no ball on the playfield for the scoop: " + self.where())
        if not self.table.to_vuk():
            return False
        self.advance_time_and_run(0.1)
        if wait:
            self.wait_until(lambda: self.table.vuk == 0 and self.table.flight == 0, timeout,
                            what="the VUK kick")
            self.wait(SETTLE)
        return True

    def drain(self, outlane=None, settle=0.2):
        """One ball leaves the playfield (through an outlane when named: "left" / "right")."""
        if self.table.pf <= 0:
            raise BenchError("no ball on the playfield to drain: " + self.where())
        waited = 0.0
        while self.table.pf > self.machine.playfield.balls and waited < 1.5:
            # a ball just launched or kicked out: MPF counts it on the playfield at the end of the eject
            # (1 s). No real ball is back in the trough before that, and MPF would eject it again.
            self.advance_time_and_run(0.1)
            waited += 0.1
        if self.table.pf <= 0:
            return
        if outlane:
            self.table.hit("s_{}_outlane".format(outlane))
            self.advance_time_and_run(0.15)
        self.table.drain()
        self.advance_time_and_run(settle)
        if self.CHECK:
            self.check()

    def drain_all(self, timeout=40.0):
        """Drain every ball, also the ones still on their way, until none is out of the trough or the
        game serves a new one for the next ball."""
        waited = 0.0
        ball = self.ball_id()
        while self.machine.game and self.ball_id() == ball:
            if self.table.pf:
                self.drain()
            elif self.table.out == 0 and not self.tron._mb_pending and not self.tron.task_running("multiball"):
                break
            else:
                if self.table.shooter and self.autoplunge is None:
                    self.table.launch()
                self.advance_time_and_run(0.1)
                waited += 0.1
                if waited > timeout:
                    raise BenchError("balls never came back: " + self.where())

    def ball_id(self):
        """Counts the new balls served (serve type 3): a new ball, also a shoot-again one, changes it."""
        game = self.machine.game
        if not game or not game.player:
            return None
        return self.balls_served

    def lose_ball(self, natural=False):
        """One step of losing the ball: make the playfield valid (a drain before that is re-served), end
        the ball saves (natural=False) and drain one ball."""
        os_ = self.tron
        if not os_.pf_valid and not os_.tilted:
            self.validate()
        if not natural:
            self.no_ball_save()
        if os_.task_running("multiball") or os_._mb_pending:
            return          # the multiball task still launches: a drain now is launched again, as in the ROM
        if self.table.pf:
            self.drain()

    def end_ball(self, natural=False, timeout=120.0):
        """Lose the ball in play and wait for the next ball (served and on the playfield) or the game's
        end. natural: the ball saves are left to run (the robot drains again until they are over)."""
        ball = self.ball_id()
        waited = 0.0
        while self.machine.game and self.ball_id() == ball:
            if self.tron.state & 0x40:
                self.press("s_start_button", settle=0.2)
            if self.table.pf and not self.tron.state & 0x5:
                self.lose_ball(natural)
            elif self.table.shooter and self.autoplunge is None:
                self.table.launch()
            self.advance_time_and_run(0.2)
            waited += 0.2
            if waited > timeout:
                raise BenchError("the ball never ended: " + self.where())
        if self.machine.game:
            self.ball_in_play()

    def end_game(self, natural=False, timeout=900.0):
        waited = 0.0
        while self.machine.game:
            if self.tron.state & 0x40:
                self.press("s_start_button", settle=0.2)
            if self.table.pf and not self.tron.state & 0x5:
                self.lose_ball(natural)
            elif self.table.shooter and self.autoplunge is None:
                self.table.launch()
            self.advance_time_and_run(0.2)
            waited += 0.2
            if waited > timeout:
                raise BenchError("the game never ended: " + self.where())
        self.advance_time_and_run(1)

    def down_to_one_ball(self):
        """A multiball loses its balls until one is left (the saves are ended first)."""
        self.wait_until(lambda: not (self.table.flight or self.table.shooter or self.tron._mb_pending), 30,
                        what="the multiball's balls")
        self.no_ball_save()
        while self.table.pf > 1:
            self.drain()
        self.wait(0.8)
        if self.table.pf != 1:
            raise BenchError("not one ball left: " + self.where())

    def mb_starts(self, since=0):
        """(balls, save ticks, grace ticks) of every multiball_start call since the mark."""
        return [(e["balls"], e["save_ticks"], e["grace_ticks"]) for e in self.tron.trace.events[since:]
                if e["ev"] == "multiball_start"]

    def validate(self):
        """Make the playfield valid without starting anything: a sling, a bumper... three counting switches."""
        for name in ("sling_l", "sling_r", "pop_l"):
            if self.tron.pf_valid:
                break
            self.shot(name, settle=0.1)
        self.wait(0.3)
        self.assertTrue(self.tron.pf_valid)

    def no_ball_save(self):
        """Run the ball save out (or kill it): the next drain ends the ball."""
        self.tron.kill_ball_save()
        self.tron.kill_mb_save()

    # ------------------------------------------------------------------ reading the game

    @property
    def os(self):
        return self.tron

    @property
    def pd(self):
        return self.tron.pd

    def feature(self, name):
        return self.tron.features_by_name[name]

    def score(self, player=None):
        game = self.machine.game
        if not game:
            return 0
        p = game.player if player is None else game.player_list[player - 1]
        return p.score

    def flag(self, flag):
        return self.tron.flag(flag)

    def deffs(self, since=0):
        return [e["id"] for e in self.tron.trace.events[since:] if e["ev"] == "deff_start"]

    def sounds(self, since=0):
        return [int(e["call"], 16) for e in self.tron.trace.events[since:] if e["ev"] == "sound"]

    def audits_added(self, since=0):
        return [e["id"] for e in self.tron.trace.events[since:] if e["ev"] == "audit"]

    def adds(self, since=0):
        """The points of every score_add since the mark (before the score event's doubling)."""
        return [e["points"] for e in self.tron.trace.events[since:] if e["ev"] == "score_add"]

    def audit(self, n):
        return self.tron.audits[n]

    def mark(self):
        return len(self.tron.trace.events)

    def scored(self, fn):
        """Points the current player scored during fn()."""
        before = self.score()
        fn()
        return self.score() - before

    # ------------------------------------------------------------------ reaching the modes by the switches

    def set_items(self, lit=(), collected=()):
        """Test hook (the scenarios' poke): the nine items' lit / collected state of the player."""
        for i, item in enumerate(self.pd.items):
            item[0] = 1 if i in lit or i in collected else 0
            item[1] = 1 if i in collected else 0
        self.tron.request_refresh()
        self.advance_time_and_run(0.05)

    def light_clu(self):
        """C-L-U lanes until the hurry-up is lit at the scoop."""
        for _ in range(40):
            if self.tron.hook("vuk_lit_test", 0x10):
                return
            self.shots("clu_c", "clu_l", "clu_u", settle=0.1)
        raise BenchError("CLU never lit")

    def start_clu(self):
        self.light_clu()
        self.scoop()
        self.assertTrue(self.feature("clu").clock.running(), "CLU hurry-up did not start")

    def start_gem(self):
        gem = self.feature("gem")
        for _ in range(8):
            if gem.clock.running():
                return
            self.shot("right_loop")
        self.assertTrue(gem.clock.running(), "GEM hurry-up did not start")

    def start_zuse(self):
        zuse = self.feature("zuse")
        for _ in range(8):
            if zuse.clock.running():
                return
            self.shots("zuse_z", "zuse_u", "zuse_s", "zuse_e", settle=0.1)
        self.assertTrue(zuse.clock.running(), "ZUSE fast scoring did not start")

    def light_quorra(self):
        for _ in range(8):
            if self.tron.hook("vuk_lit_test", 2):
                return
            self.shot("left_loop")
        raise BenchError("Quorra never lit")

    def start_quorra(self):
        self.light_quorra()
        self.scoop()
        self.assertTrue(self.flag(0x29), "Quorra Multiball did not start")

    def light_light_cycle(self):
        for name in MAJOR_SHOTS * 2:
            if self.tron.hook("vuk_lit_test", 4):
                return
            self.shot(name)
        if not self.tron.hook("vuk_lit_test", 4):
            raise BenchError("Light Cycle never lit")

    def start_light_cycle(self):
        self.light_light_cycle()
        self.scoop()
        self.assertTrue(self.flag(0x2b), "Light Cycle Multiball did not start")

    def light_disc_battle(self):
        for _ in range(12):
            if self.flag(0x22):
                break
            self.shot("bank_c", settle=0.3)
        self.assertTrue(self.flag(0x22), "Disc Battle never lit")
        self.wait(1.5)                       # the 3-bank goes down

    def start_disc_multiball(self):
        self.light_disc_battle()
        for _ in range(14):
            if self.flag(0x24):
                break
            self.shot("disc")
        self.assertTrue(self.flag(0x24), "Disc Multiball did not start")

    def light_end_of_line(self):
        for _ in range(80):
            if self.flag(0x26):
                return
            self.shot("left_ramp", settle=0.1)
            self.shot("right_ramp", settle=0.1)
        raise BenchError("End of Line never lit")

    def start_end_of_line(self):
        self.light_end_of_line()
        self.scoop()
        self.assertTrue(self.flag(0x27), "End of Line Multiball did not start")

    def start_sea_of_simulation(self, collected=()):
        self.set_items(lit=range(9), collected=collected)
        self.scoop()
        self.assertTrue(self.flag(SOS_FLAG), "Sea of Simulation did not start")

    def start_portal(self):
        self.set_items(collected=range(9))
        self.scoop()
        self.assertTrue(self.flag(0x37), "Portal Multiball did not start")

    def start_tron_award(self):
        """T-R-O-N: the lit timed award starts (returns its bit: 1 double scoring, 2 bumpers, 4 spinners)."""
        lit = self.pd.tron_lit
        self.shots("tron_t", "tron_r", "tron_o", "tron_n", settle=0.15)
        self.wait(0.5)
        return lit

    # ------------------------------------------------------------------ invariants

    def problem(self, text):
        self.problems.append("{} [{}]".format(text, self.where()))

    def check(self):
        """The invariants (docs/test_bench.md). Raises BenchError with every one that does not hold."""
        os_, t, game = self.tron, self.table, self.machine.game
        bad = list(self.problems)
        self.problems = []
        if t.total() != BALLS:
            bad.append("the table holds {} balls".format(t.total()))
        if min(t.trough, t.shooter, t.vuk, t.pf, t.flight) < 0:
            bad.append("negative ball count on the table")
        if not game:
            self._scores, self._tilt_score, self._desync_since = {}, None, None
            if os_.state & 0x18 == 0 and not os_.state & 0x10:
                bad.append("no game but state {:#x}".format(os_.state))
            running = [f for f in list(MB_FLAGS) + [SOS_FLAG] if os_.flag(f)]
            if running:
                bad.append("mode flags {} set with no game".format(running))
        else:
            bad += self._check_game(os_, t, game)
        if bad:
            raise BenchError("invariant broken: " + "; ".join(bad) + " [" + self.where() + "]")

    def _check_game(self, os_, t, game):
        bad = []
        # scores only grow, and not at all while tilted
        for p in game.player_list:
            if p.score < self._scores.get(p.number, 0):
                bad.append("player {} score went down {} -> {}".format(p.number, self._scores[p.number], p.score))
            self._scores[p.number] = p.score
        if os_.tilted and game.player:
            if self._tilt_score is None:
                self._tilt_score = (game.player.number, game.player.score)
            elif self._tilt_score[0] == game.player.number and game.player.score != self._tilt_score[1]:
                bad.append("scored {} while tilted".format(game.player.score - self._tilt_score[1]))
        else:
            self._tilt_score = None
        # which modes may run together (developer_guide 3.3)
        mbs = [f for f in MB_FLAGS if os_.flag(f)]
        if len(mbs) > 1 and set(mbs) != {0x29, 0x2b}:
            bad.append("multiballs running together: " + ", ".join(MB_FLAGS[f] for f in mbs))
        if os_.flag(SOS_FLAG) and mbs:
            bad.append("Sea of Simulation with " + ", ".join(MB_FLAGS[f] for f in mbs))
        # bounded values
        f = os_.features_by_name
        if game.player and os_.players:
            pd = os_.pd
            checks = (("CLU clock", f["clu"].clock.seconds, 0, 40), ("GEM clock", f["gem"].clock.seconds, 0, 40),
                      ("ZUSE clock", f["zuse"].clock.seconds, 0, 45), ("bonus X", pd.get("bonus_x", 1), 1, 25),
                      ("extra balls collected", os_.eb_collected[os_.player_num - 1], 0, max(os_.adj_value(26), 0)),
                      ("tilt warnings", os_.tilt_warnings, 0, os_.adj_value(32)),
                      ("balls in play", game.balls_in_play, 0, BALLS),
                      ("ball number", game.player.ball, 1, os_.adj_value(31)))
            for name, value, lo, hi in checks:
                if not lo <= value <= hi:
                    bad.append("{} = {} outside {}..{}".format(name, value, lo, hi))
        # the rules' ball count against the balls really out of the trough: they may differ while balls
        # move (a serve, a save, a multiball launch, a drain being counted), never for long once all is still
        moving = (t.flight or t.shooter or t.vuk or os_._mb_pending or os_.task_running("multiball")
                  or os_.mb_save_running() or os_.ball_save)
        if game.balls_in_play == t.out or os_.state & 0x1d or game.ending or moving:
            self._desync_since = None
        elif self._desync_since is None:
            self._desync_since = os_.now
        elif os_.now - self._desync_since > 25:
            bad.append("the rules count {} balls in play, the table has {} out of the trough, for {:.0f} s".format(
                game.balls_in_play, t.out, os_.now - self._desync_since))
            self._desync_since = os_.now
        return bad

    def _check_ball_served(self, serve_type):
        """A new ball (serve type 3): nothing of the last ball is left running."""
        if serve_type != 3:
            return
        self.balls_served += 1
        os_ = self.tron
        flags = [f for f in list(MB_FLAGS) + [SOS_FLAG] if os_.flag(f)]
        if flags:
            self.problem("new ball with mode flags {} still set".format(flags))
        left = [t for t in (0xc0, 0xc1, 0xc2, 0xc3, 0x59, 0x5b, 0xc6, 199, 200, 0xab, 0xac, 0xad, 0xae, 0xaf, 0xb0,
                            0xb1, 0xb3, 0xb4, 0xb8, 0xb9, 0xd1, 0xd2, 0x34, 0x35, "multiball")
                if os_.task_running(t)]
        if left:
            self.problem("new ball with tasks {} still running".format(left))
        if os_.tilted:
            self.problem("new ball served while tilted")
        if os_._mb_pending:
            self.problem("new ball with {} multiball balls still to launch".format(os_._mb_pending))

    def _check_game_ended(self, **kwargs):
        self._scores, self._tilt_score, self._desync_since = {}, None, None

        def later():
            os_ = self.tron
            if self.machine.game:
                return                          # a restart: the next game is already running
            left = [t for t in BALL_TASKS if os_.task_running(t)]
            if left:
                self.problem("game over with tasks {} still running".format(left))
            if os_.flags & (set(MB_FLAGS) | {SOS_FLAG}):
                self.problem("game over with mode flags {}".format(sorted(os_.flags)))
        self.machine.clock.schedule_once(lambda *a: later(), 0.2)


def seeds(default):
    """Seeds of a stress test: `default` of them, or TRON_BENCH_SEEDS=N (or a list "3,17,40")."""
    spec = os.environ.get("TRON_BENCH_SEEDS", "")
    if "," in spec:
        return [int(s) for s in spec.split(",") if s.strip()]
    return list(range(int(spec) if spec else default))
