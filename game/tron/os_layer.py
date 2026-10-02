"""The Stern SAM "OS" layer of Tron Legacy LE 1.74, rebuilt on top of MPF.

MPF owns the hardware: switches, ball devices, the trough, players and turn order. This layer adds
the ROM's own semantics on top (see assets/rules/modes/game_flow.md and switches_and_shots.md):

- ROM tasks: named timers counted in 16.26 ms ticks (task ids are the ROM's, for cross-reference).
- Game flags, audits, adjustments (operator settings by ROM number) and the trace log.
- score_add (nothing while tilted or out of game), valid playfield, ball save, tilt, extra ball,
  the end-of-ball sequence with the bonus, and game over.
- Feature hooks: each rules feature registers functions under the ROM hook names
  (for example "portal_mb_shot"); switch handlers call them in the ROM's order.

Display effects, sounds, lamp effects and tube shows are posted as MPF events
(tron_deff_<id>, tron_sound_<call>, tron_leff_<id>, tron_tube_<id>) and written to the trace.
"""
import os
import re

from mpf.core.custom_code import CustomCode

from tron.trace import Trace

TICK = 0.01626          # seconds per ROM tick in play (game_flow.md section 0)
SECOND = 62             # ticks the ROM treats as one second

# game state word 0x37274 bits (game_flow.md section 3)
ST_BONUS, ST_END_BALL, ST_ATTRACT, ST_TILT = 0x01, 0x04, 0x10, 0x200

# valid playfield (game_flow.md 4.3): "force" switches validate at once, 3 distinct "counting" ones do
FORCE_SWITCHES = {11, 12, 14, 24, 25, 28, 29, 34, 37, 39, 43, 46}
COUNTING_SWITCHES = {7, 8, 13, 48, 35, 36, 38, 41, 44, 49, 50, 51, 30, 31, 32}

BALL_SAVE_GRACE = 218   # ticks (0xda) of grace after the ball-save timer (game_flow.md 5.1)


def adjustment_defaults(settings_path):
    """Read {adj number: (key, default)} from the asset package's settings.yaml comments."""
    out = {}
    key = None
    with open(settings_path) as f:
        for line in f:
            m = re.match(r"  ([a-z0-9_]+):\s+# adj (\d+)", line)
            if m:
                key, num = m.group(1), int(m.group(2))
                out[num] = [key, None]
                continue
            m = re.match(r"    default: (-?\d+)", line)
            if m and key is not None:
                out[num][1] = int(m.group(1))
                key = None
    return {n: tuple(v) for n, v in out.items()}


class Task:
    """One ROM task: a timer that calls back after a number of ticks."""

    __slots__ = ("id", "handle", "ticks", "start", "data")

    def __init__(self, task_id, handle, ticks, start, data=None):
        self.id, self.handle, self.ticks, self.start, self.data = task_id, handle, ticks, start, data


class PlayerData:
    """Per-player rule state (the ROM's NVRAM arrays indexed [player-1]). Item and attribute access."""

    def __getitem__(self, name):
        return getattr(self, name)

    def __setitem__(self, name, value):
        setattr(self, name, value)

    def get(self, name, default=None):
        return getattr(self, name, default)


class TronOS(CustomCode):

    def on_load(self):
        self.trace = Trace(self.machine)
        self.tasks = {}
        self.flags = set()
        self.audits = {}
        self.state = ST_ATTRACT
        self.hooks = {}             # hook name -> [functions], called in registration order
        self.pokes = {}             # ROM RAM address -> setter(value), for the scenarios' "poke"
        self.features = []
        self.players = []           # PlayerData per player
        self.pf_valid = False
        self._counting_seen = set()
        self.ball_save = None       # None, "armed" or "grace"
        self.ball_save_left = 0
        self.tilt_warnings = 0
        self._last_bob = -999.0
        self.eb_lit = []            # OS lit extra balls per player (0x3d46c)
        self.eb_collected = []      # extra balls collected per player (0x3d470)
        self.shoot_again = False    # game flag 9: this ball is a shoot-again ball
        self.ball_scored = False
        self.serve_type = 0
        self.coins = 0
        settings = os.path.join(self.machine.machine_path, "..", "assets", "mpf_package", "config",
                                "settings.yaml")
        self.adj_table = adjustment_defaults(settings)
        self.adj = {n: d for n, (_, d) in self.adj_table.items()}
        self.machine.tron = self

        ev = self.machine.events
        ev.add_handler("game_starting", self._game_starting, priority=1000)
        ev.add_handler("ball_starting", self._ball_starting, priority=1000)
        ev.add_handler("ball_started", self._ball_started, priority=1000)
        ev.add_handler("ball_drain", self._ball_drain, priority=1000)
        ev.add_handler("ball_ending", self._ball_ending, priority=1000)
        ev.add_handler("game_ending", self._game_ending, priority=1000)
        ev.add_handler("game_ended", self._game_ended, priority=1000)
        ev.add_handler("mode_attract_started", self._attract_started)
        sw = self.machine.switch_controller
        sw.add_switch_handler("s_coin", self._coin)
        sw.add_switch_handler("s_plumb_bob_tilt", self._plumb_bob)

        self.register_poke(0x3d46c, lambda p, v: self.eb_lit.__setitem__(p, v))
        from tron import switches                   # noqa: E402 (import after machine setup)
        self.switches = switches.SwitchLayer(self)
        from tron.features import load_features     # noqa: E402
        self.features = load_features(self)

    # ------------------------------------------------------------------ infrastructure

    @property
    def now(self):
        return self.machine.clock.get_time()

    def task_start(self, task_id, ticks, callback=None, data=None):
        """(Re)start ROM task task_id: it runs for `ticks` ticks, then calls callback()."""
        self.task_kill(task_id)

        def fire():
            task = self.tasks.pop(task_id, None)
            if task is not None and callback:
                callback()
        handle = self.machine.clock.schedule_once(fire, ticks * TICK)
        self.tasks[task_id] = Task(task_id, handle, ticks, self.now, data)
        return self.tasks[task_id]

    def task_kill(self, task_id):
        task = self.tasks.pop(task_id, None)
        if task is not None:
            self.machine.clock.unschedule(task.handle)
            return True
        return False

    def task_running(self, task_id):
        return task_id in self.tasks

    def task_ticks_left(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return 0
        return max(0, task.ticks - round((self.now - task.start) / TICK))

    def after(self, ticks, callback):
        """Anonymous delay (not a ROM task id)."""
        return self.machine.clock.schedule_once(lambda: callback(), ticks * TICK)

    def hook(self, name, *args):
        """Call every feature function registered under ROM hook `name`; return the last result."""
        result = None
        for fn in self.hooks.get(name, ()):
            r = fn(*args)
            if r is not None:
                result = r
        return result

    def register(self, name, fn):
        self.hooks.setdefault(name, []).append(fn)

    def register_poke(self, addr, setter, players=4, stride=1):
        """Map a per-player ROM RAM array (addr + stride*(p-1)) to a setter(player_index, value)."""
        for p in range(players):
            self.pokes[addr + stride * p] = (lambda p_: lambda v: setter(p_, v))(p)

    def poke(self, addr, value):
        if addr not in self.pokes:
            raise KeyError("no rebuild state mapped to ROM address 0x{:x}".format(addr))
        self.pokes[addr](value)

    # ------------------------------------------------------------------ outputs

    def deff_start(self, deff_id, **args):
        self.trace.log("deff_start", id=deff_id)
        self.machine.events.post("tron_deff_{}".format(deff_id), **args)

    def deff_stop(self, deff_id):
        self.trace.log("deff_stop", id=deff_id)
        self.machine.events.post("tron_deff_{}_stop".format(deff_id))

    def sound(self, call):
        self.trace.log("sound", call="0x{:03x}".format(call), in_deff=0)
        self.machine.events.post("tron_sound_{:03x}".format(call))

    def leff_start(self, leff_id):
        self.trace.log("leff_start", id=leff_id)
        self.machine.events.post("tron_leff_{}".format(leff_id))

    def leff_stop(self, leff_id):
        self.trace.log("leff_stop", id=leff_id)
        self.machine.events.post("tron_leff_{}_stop".format(leff_id))

    def tube_start(self, show_id):
        self.trace.log("tube_show_start", id=show_id)
        self.machine.events.post("tron_tube_{}".format(show_id))

    def tube_stop(self, show_id):
        self.trace.log("tube_show_stop", id=show_id)
        self.machine.events.post("tron_tube_{}_stop".format(show_id))

    def audit(self, audit_id, n=1):
        self.audits[audit_id] = self.audits.get(audit_id, 0) + n
        self.trace.log("audit", id=audit_id, n=n)

    def flag_set(self, flag):
        self.flags.add(flag)
        self.trace.log("flag_set", flag=flag)

    def flag_clear(self, flag):
        self.flags.discard(flag)
        self.trace.log("flag_clear", flag=flag)

    def flag(self, flag):
        return flag in self.flags

    # ------------------------------------------------------------------ game state

    @property
    def game(self):
        return self.machine.game

    @property
    def player_num(self):
        """Current player, 1-4 (0 when no game)."""
        game = self.machine.game
        return game.player.number if game and game.player else 0

    @property
    def pd(self):
        """Rule state of the current player."""
        return self.players[self.player_num - 1]

    @property
    def tilted(self):
        return bool(self.state & ST_TILT)

    @property
    def in_play(self):
        """Normal play: a game runs and no tilt, end-of-ball or bonus is in progress."""
        return self.state == 0

    def balls_in_play(self):
        game = self.machine.game
        return game.balls_in_play if game else 0

    def score_add(self, points):
        """score_add [0x0002340c]: x playfield multiplier (always 1); nothing while tilted or out of game."""
        if not self.game or self.state & 0x210 or not self.game.player:
            return 0
        self.trace.log("score_add", points=points, multiplier=1, player=self.player_num)
        self._add_score(points)
        if not self.ball_scored:
            self.ball_scored = True
            if self.shoot_again:
                self.shoot_again = False
                self.flag_clear(9)
        return points

    def _add_score(self, points):
        player = self.game.player
        player.score += points
        self.trace.log("score", player=self.player_num, delta=points, total=player.score)

    def base_score(self, points):
        """FUN_0102a188: base switch score, nothing while tilted."""
        if not self.tilted:
            self.score_add(points)

    def adj_value(self, num):
        return self.adj[num]

    # ------------------------------------------------------------------ valid playfield (4.3)

    def playfield_switch(self, num):
        """Called by switch handlers: force switches validate at once, 3 distinct counting ones do."""
        if num in COUNTING_SWITCHES:
            self.hook("counting_switch", num)        # event 0x6b
        elif num in FORCE_SWITCHES:
            self.hook("instant_switch", num)         # event 0x6c
        if self.pf_valid:
            return
        if num in FORCE_SWITCHES:
            self._validate()
        elif num in COUNTING_SWITCHES:
            self._counting_seen.add(num)
            if len(self._counting_seen) >= 3:
                self._validate()

    def _validate(self):
        self.pf_valid = True
        self.flag_set(0x1c)                          # event 0x6a handler [0x0100f25c]
        self.hook("playfield_valid")

    # ------------------------------------------------------------------ coins and start

    def _coin(self):
        """Coin switch: 3 coins make a credit (factory pricing), as the reference traces show."""
        self.coins += 1
        self.audit(4)
        self.audit(7)
        if self.coins % 3 == 0:
            self.audit(1)
            self.sound(0x0f1)
            self.flag_set(47)
        else:
            self.sound(0x0f0)
        self.deff_start(10)

    def _attract_started(self, **kwargs):
        self.state = ST_ATTRACT

    # ------------------------------------------------------------------ game start (4.1)

    def _game_starting(self, queue=None, **kwargs):
        self.state = 0
        self.players = [PlayerData() for _ in range(4)]
        self.eb_lit = [0] * 4
        self.eb_collected = [0] * 4
        self.shoot_again = False
        self.flags.clear()
        self.tasks_kill_all()
        self.audit(0x11)
        self.hook("game_start")                      # event 0x2e

    def tasks_kill_all(self):
        for task_id in list(self.tasks):
            self.task_kill(task_id)

    # ------------------------------------------------------------------ ball start (4.2)

    def _ball_starting(self, queue=None, **kwargs):
        player = self.game.player
        first_ball = player.ball == 1 and not self.shoot_again
        self.state = 0
        self.pf_valid = False
        self._counting_seen = set()
        self.ball_scored = False
        self.tilt_warnings = 0
        if first_ball:
            self.hook("player_first_ball")           # event 0x26
        self.hook("ball_start")                      # event 0x11
        if self.shoot_again:
            self.deff_start(26, player=self.player_num)
            self.leff_start(16)
            self.sound(0x11b)
        self.deff_start(19)
        self.sound(0x01a)
        self.hook("ball_start_media")                # leffs/tube shows the features start with the ball
        self.serve(3)

    def _ball_started(self, **kwargs):
        pass

    def serve(self, serve_type):
        """serve(type) [0x0001f258]: 3 = new ball (arms ball save), 1/2 = ball-save replacement."""
        self.serve_type = serve_type
        self.hook("ball_served", serve_type)         # event 0x0f
        if serve_type == 3:
            self._arm_ball_save()

    # ------------------------------------------------------------------ ball save (5.1)

    def _arm_ball_save(self):
        ticks = self.adj_value(38) * SECOND
        self.task_kill(0x31)
        self.task_kill(0x32)
        if ticks <= 0:
            self.ball_save = None
            return
        self.ball_save = "armed"
        self.ball_save_left = ticks
        self.leff_start(14)
        self.task_start(0x31, 6, self._ball_save_poll)

    def _ball_save_poll(self):
        if self.pf_valid and self.ball_save_left > 6:
            self.ball_save_left -= 6
        if self.ball_save_left > 6:
            self.task_start(0x31, 6, self._ball_save_poll)
            return
        self.leff_stop(14)
        self.ball_save = "grace"
        self.task_start(0x32, BALL_SAVE_GRACE, self._ball_save_end)

    def _ball_save_end(self):
        self.ball_save = None

    def kill_ball_save(self):
        """Multiball start kills the single-ball save (0x00019bdc)."""
        if self.ball_save == "armed":
            self.leff_stop(14)
        self.task_kill(0x31)
        self.task_kill(0x32)
        self.ball_save = None

    def _ball_drain(self, balls=0, **kwargs):
        """ball_drain relay: ball save and re-serve before the playfield is valid [0x0001dd90]."""
        if not balls or not self.game:
            return {"balls": balls}
        if self.balls_in_play() - balls > 0:
            self.hook("ball_drained", balls)
            return {"balls": balls}
        if self.tilted:
            return {"balls": balls}
        if not self.pf_valid:
            # not a lost ball: re-serve the same ball (type 7), no bonus
            self.serve_type = 7
            self.machine.playfield.add_ball(player_controlled=True)
            return {"balls": 0}
        if self.ball_save:
            self.kill_ball_save()
            self.deff_start(20)
            self.leff_start(15)
            self.audit(0x2b)
            self.hook("ball_saved")
            self.serve(1)
            self.machine.playfield.add_ball(player_controlled=False)
            return {"balls": 0}
        return {"balls": balls}

    # ------------------------------------------------------------------ tilt (5.3)

    def _plumb_bob(self):
        if not self.game or self.tilted or self.state & ST_END_BALL:
            return
        if self.now - self._last_bob < SECOND * TICK:
            return
        self._last_bob = self.now
        if self.tilt_warnings < self.adj_value(32):
            self.tilt_warnings += 1
            self.deff_start(23)
            self.leff_start(11)
            self.sound(0x016)
            self.after(31, lambda: self.sound(0x03d))
            return
        self.state |= ST_TILT
        self.audit(0x2a)
        self.kill_ball_save()
        self.machine.events.post("tron_tilt")
        self.hook("tilt")                            # event 0x65
        self.deff_start(21)
        self.leff_start(9)
        self.sound(0x017)
        self.after(63, lambda: self.sound(0x03e))
        for flipper in self.machine.flippers.values():
            flipper.disable()

    # ------------------------------------------------------------------ extra ball (5.4)

    def light_extra_ball(self):
        """OS part of 0x01012190: lit count +1 for the current player."""
        self.eb_lit[self.player_num - 1] += 1

    def collect_extra_ball(self):
        """0x01012228 OS part: returns True when an extra ball was awarded, False when it paid points."""
        p = self.player_num - 1
        self.eb_lit[p] = max(0, self.eb_lit[p] - 1)
        if self.eb_collected[p] < self.adj_value(26):
            self.eb_collected[p] += 1
            self.game.player.extra_balls += 1
            self.audit(9)
            return True
        self.score_add(3000000)
        return False

    # ------------------------------------------------------------------ end of ball (6.1)

    def _ball_ending(self, queue=None, **kwargs):
        queue.wait()
        self.state |= ST_END_BALL
        self.kill_ball_save()
        self.hook("ball_end")                        # event 0x1d: every mode stops
        for flipper in self.machine.flippers.values():
            flipper.disable()
        self.audit(8)
        wait_ticks = self.hook("ball_end_wait") or 0  # mode TOTAL displays (flag-0x2000 tasks)
        self.after(wait_ticks, lambda: self._ball_ending_bonus(queue))

    def _ball_ending_bonus(self, queue):
        if self.tilted:
            self._ball_ending_done(queue)
            return
        self.state |= ST_BONUS
        bonus = self.features_by_name.get("bonus")
        if bonus:
            bonus.run(lambda total: self._bonus_done(queue, total))
        else:
            self._bonus_done(queue, 0)

    def _bonus_done(self, queue, total):
        if total:
            self._add_score(total)                   # event 0x16, multiplier 1, not a score_add
            self.hook("score_changed")
        self.state &= ~ST_BONUS
        self._ball_ending_done(queue)

    def _ball_ending_done(self, queue):
        self.state &= ~(ST_TILT | ST_END_BALL)
        for flipper in self.machine.flippers.values():
            flipper.enable()
        if self.game.player.extra_balls:
            self.shoot_again = True
            self.flag_set(9)
        queue.clear()

    @property
    def features_by_name(self):
        return {f.name: f for f in self.features}

    # ------------------------------------------------------------------ game over (6.2)

    def _game_ending(self, queue=None, **kwargs):
        self.state |= 0x18
        self.audit(47)
        self.audit(19)
        self.hook("game_over")
        queue.wait()
        match = self.features_by_name.get("match")
        if match:
            match.run(queue.clear)
        else:
            queue.clear()

    def _game_ended(self, **kwargs):
        self.state = ST_ATTRACT
        self.tasks_kill_all()
