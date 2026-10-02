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
import random
import re

from mpf.core.custom_code import CustomCode

from tron.trace import Trace

TICK = 0.01626          # seconds per ROM tick in play (game_flow.md section 0)
SECOND = 62             # ticks the ROM treats as one second

# game state word 0x37274 bits (game_flow.md section 3)
ST_BONUS, ST_END_BALL, ST_ATTRACT, ST_TILT = 0x01, 0x04, 0x10, 0x200

# valid playfield (game_flow.md 4.3): "force" switches validate at once, 3 distinct "counting" ones do
FORCE_SWITCHES = {11, 12, 14, 24, 25, 28, 29, 34, 37, 39, 43, 46}
COUNTING_SWITCHES = {7, 8, 13, 48, 35, 36, 38, 41, 44, 49, 50, 51, 30, 31, 32, 1, 2, 3, 4}   # + TRON targets

MULTIBALL_FLAGS = (0x27, 0x24, 0x2b, 0x29, 0x37)
BALL_SAVE_GRACE = 218
SERVE_EJECT_TICKS = 32
SAVE_EJECT_TICKS = 39
AUTO_LAUNCH_TICKS = 12      # task 0x3c after an auto-launch (inferred: covers the shooter lane opening)
MB_TASK = "multiball"       # the multiball task (ROM id: trough device + 0x18)
MB_EJECT_TICKS = 101        # trough eject cycle while it launches multiball balls (portal_multiball.jsonl)
# The VUK device stays busy for a fixed time after its kick, however soon MPF confirms the eject: the first
# multiball ball leaves the shooter lane (sound 0x0ea) 3.0 s after the kick in every ROM trace
# (light_cycle_multiball 26.70 -> 29.73, portal_multiball 17.87 -> 20.86, quorra_multiball 28.86 -> 31.88);
# MPF's trough eject + auto-launch take the remaining ~0.6 s.
VUK_BUSY_TICKS = 149
# A request without the VUK (add-a-ball, a drain during the save) launches its first ball after a trough
# cycle: sound 0x0ea 1.43 s after the Quorra add-a-ball (quorra_multiball 46.68 -> 48.11), of which MPF's
# trough eject + auto-launch take ~0.6 s.
MB_FIRST_EJECT_TICKS = 51
BALL_SEARCH_TICKS = 104     # search task 0x2b; a drain during it ends the ball after it (game_flow.jsonl 88.70 -> 90.39)   # ticks (0xda) of grace after the ball-save timer (game_flow.md 5.1)


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
        self.eb_collected = [0] * 4  # extra balls collected per player (0x3d470)
        self.specials_lit = [0] * 4  # 0x3d4ef
        self.specials_collected = [0] * 4  # 0x3d4f3
        self.shoot_again = False    # game flag 9: this ball is a shoot-again ball
        self.ball_scored = False
        self.serve_type = 0
        self.coins = 0
        self._mb_pending = 0
        self._mb_save = (0, 0)
        self._mb_balls = 0          # balls requested from the running multiball task (rom_balls_in_play)
        self.rules = []
        self._refresh_pending = False
        self._score_pending = {}
        self.forced = {}             # name -> list of forced pick results (tests)
        self.random = random.Random()
        self._new_game = False
        self._search_handle = None
        self.ball_search_count = 0
        self.ball_held = False       # a ball sits in the VUK waiting for its kickout
        self.ball_validated = False  # the playfield was validated on this ball (base music 0x01b)
        self.vuk_ejecting = False    # VUK eject not yet confirmed by a playfield switch (no ball search)
        self.vuk_device_busy = False  # VUK released, eject not yet confirmed by the ball device
        self.vuk_released_at = -999.0 # when the VUK last kicked its ball out (switches.vuk_eject)
        self._mb_first_at = -999.0    # earliest launch of a new multiball request's first ball
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
        ev.add_handler("tron_vuk_release", self._vuk_eject_confirmed, unconfirmed=True)
        ev.add_handler("balldevice_bd_vuk_ball_eject_success", self._vuk_eject_confirmed)
        ev.add_handler("balldevice_bd_shooter_lane_ejecting_ball", self._shooter_ejecting)
        sw = self.machine.switch_controller
        sw.add_switch_handler("s_coin", self._coin)
        sw.add_switch_handler("s_plumb_bob_tilt", self._plumb_bob)

        self.register("rules_refresh", self.request_refresh)
        self.register_poke(0x3d46c, lambda p, v: self.eb_lit.__setitem__(p, v))
        from tron.display import Display, Leffs, Tubes     # noqa: E402 (import after machine setup)
        self.display = Display(self)
        self.tubes = Tubes(self)
        self.leffs = Leffs(self)
        from tron import switches                   # noqa: E402
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

    def has_hook(self, name):
        return bool(self.hooks.get(name))

    def any_multiball(self):
        """FUN_0100f918: End of Line, Disc, Light Cycle, Quorra or Portal multiball running."""
        return any(f in self.flags for f in MULTIBALL_FLAGS)

    def pick(self, name, weights):
        """Weighted random pick (index into weights). A test can force the results per name through
        self.forced[name] (a list of indexes, used in order), e.g. from a ROM reference trace."""
        forced = self.forced.get(name)
        if forced:
            return forced.pop(0)
        if max(weights) >= 1000:
            return weights.index(max(weights))
        total = sum(weights)
        if total <= 0:
            return None
        r = self.random.randrange(total)
        for i, w in enumerate(weights):
            if r < w:
                return i
            r -= w
        return None

    # ------------------------------------------------------------------ lamp rules

    def lamp_rule(self, cond, leff=None, tube=None, order=0):
        """Lamp/tube rule (leff_rule_init / FUN_00000da4): lamp-matrix effect `leff` and/or ramp tube show
        `tube` run while cond() is true. Re-evaluated by rules_refresh() in `order` (use the ROM address
        of the rule's condition function, so rules start in the ROM's order)."""
        self.rules.append([cond, leff, tube, False, order])
        self.rules.sort(key=lambda r: r[4])

    def deff_rule(self, cond, deff_id, music=None, priority=0, on_start=None):
        """lamp_rule_init(list 2, cond, deff, music, priority): mode background deff + music (display.py)."""
        self.display.add_rule(cond, deff_id, music, priority, on_start)

    def request_refresh(self, *_):
        """rules_refresh_request: evaluate the lamp rules once the current handler has finished."""
        if not self._refresh_pending:
            self._refresh_pending = True
            self.machine.clock.schedule_once(self.rules_refresh, TICK / 2)

    def rules_refresh(self, leffs_only=False):
        """leffs_only: only start refused rule leffs whose flashers were freed (display.Leffs)."""
        if leffs_only:
            active_game = bool(self.game) and not self.state & (ST_ATTRACT | ST_END_BALL | ST_BONUS)
            for rule in self.rules:
                if rule[3] and rule[1] is not None and self.leffs.retry_due(rule[1]) and active_game and rule[0]():
                    self.leff_start(rule[1], loop=True)
            return
        self._refresh_pending = False
        active_game = bool(self.game) and not self.state & (ST_ATTRACT | ST_END_BALL | ST_BONUS)
        for rule in self.rules:
            cond, leff, tube, on = rule[:4]
            want = bool(active_game and cond())
            if want and leff is not None and (not on or self.leffs.retry_due(leff)):
                self.leff_start(leff, loop=True)     # also a refused one whose outputs are free now
            elif on and not want and leff is not None:
                self.leff_stop(leff)
            # a tube rule restarts its show whenever it is not running (refused or taken over before)
            if tube is not None:
                if want and not self.tubes.is_running(tube):
                    self.tube_start(tube)
                elif not want and self.tubes.is_running(tube):
                    self.tube_stop(tube)
            rule[3] = want
        self.display.rules_refresh()                 # list 2: background deff rules and their music
        self.machine.events.post("tron_rules_refresh")

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
        return self.display.start(deff_id, **args)

    def deff_stop(self, deff_id):
        self.display.stop(deff_id)

    def show(self, task_id, deff_id, **kwargs):
        """queue_fullscreen_deff [0x0100fbb0] run as show task task_id (0x81-0xa7)."""
        self.display.queue(task_id, deff_id, **kwargs)

    def show_running(self):
        return self.display.show_running()

    def base_music(self):
        """Music of the score-display deff rules [0x0100f594 / 0x0100f5c8]: 0x01a until the playfield is
        validated on this ball, then 0x01b; 0x029 while Disc Battle is lit (hook dbattle_is_lit)."""
        if self.hook("dbattle_is_lit"):
            return 0x029
        return 0x01b if self.ball_validated else 0x01a

    def music(self, call):
        """Play a background music call and remember it (display.rules_refresh plays it again on a change)."""
        self.display.music = call
        self.sound(call)

    def sound(self, call, in_deff=0):
        self.trace.log("sound", call="0x{:03x}".format(call), in_deff=in_deff)
        self.machine.events.post("tron_sound_{:03x}".format(call))

    def sound2(self, call, arg):
        """snd_play2(call, arg) [0x0002c950]: a sound call with an argument (e.g. a spoken number). The
        ROM traces log these from inside snd_play2 (caller 0x2c97c), which trace_check leaves out."""
        self.trace.log("sound", call="0x{:03x}".format(call), in_deff=0, arg=arg, caller="0x2c97c")
        self.machine.events.post("tron_sound_{:03x}".format(call), arg=arg)

    def leff_start(self, leff_id, loop=False):
        """Logged like the ROM's call; returns False when a higher-priority leff keeps the outputs."""
        self.trace.log("leff_start", id=leff_id)
        if not self.leffs.start(leff_id, loop):
            return False
        self.machine.events.post("tron_leff_{}".format(leff_id))
        return True

    def leff_stop(self, leff_id):
        self.leffs.stop(leff_id)
        self.trace.log("leff_stop", id=leff_id)
        self.machine.events.post("tron_leff_{}_stop".format(leff_id))

    def tube_start(self, show_id):
        return self.tubes.start(show_id)

    def tube_stop(self, show_id):
        self.tubes.stop(show_id)

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
        """MPF's live ball count (includes a ball held in the VUK)."""
        game = self.machine.game
        return game.balls_in_play if game else 0

    def rom_balls_in_play(self):
        """The ROM's balls_in_play [0x0001e4a8]: while the multiball task runs (balls still to launch, or its
        ball save / grace) it is the requested count; otherwise the balls not in a device (a ball held in
        the VUK is not in play). E.g. a second multiball started during the first one's save adds a ball."""
        if self.task_running(MB_TASK) or self.mb_save_running():
            return self._mb_balls
        return max(0, self.balls_in_play() - (1 if self.ball_held else 0))

    # ------------------------------------------------------------------ multiball (0x0001ed7c)

    def multiball_start(self, balls, save_ticks=0, grace_ticks=0):
        """multiball_start(balls, 0, save_ticks, grace_ticks) [0x0001ed7c]: bring the number of balls in
        play up to `balls` (counting the VUK ball, capped at the 4 installed), kill the single-ball save
        and (re)start the multiball task: leff 13, then the launches and the multiball save (a larger
        pending request wins). Returns False (nothing done) during tilt, end of ball or attract
        (gf_state & 0x214), else True."""
        if not self.game:
            return False
        self.trace.log("multiball_start", balls=balls, save_ticks=save_ticks, grace_ticks=grace_ticks)
        if self.state & 0x214:                       # tilt, end of ball or attract: refused (returns 0)
            return False
        self.machine.events.post("tron_multiball_start", balls=balls)
        self.kill_ball_save()
        target = min(balls, 4)
        running = self.task_running(MB_TASK) or self.mb_save_running()
        self._mb_balls = max(target, self._mb_balls) if running else target
        add = target - self.balls_in_play()
        if add > 0:
            self._mb_pending += add
            self.game.balls_in_play += add
        # the call recreates the multiball task, which starts leff 13 when it runs (one tick later)
        self.after(1, lambda: self.game and not self.state & 0x214 and self.leff_start(13))
        if not (self.task_running(MB_TASK) or self.mb_save_running()):
            self._mb_save = (save_ticks, grace_ticks)          # no multiball task: the new values
            self._mb_request()
            return True
        # a running multiball task: the larger save and grace win
        if self.task_running(MB_TASK) and not (self.task_running(0x34) or self.task_running(0x35)):
            self._mb_save = (max(self._mb_save[0], save_ticks), max(self._mb_save[1], grace_ticks))
        elif save_ticks > self.task_ticks_left(0x34):
            self.task_kill(0x35)
            self.task_start(0x34, save_ticks, lambda: self._mb_save_grace(grace_ticks))
        if not self.task_running(MB_TASK) and self._mb_pending:
            self._mb_request(start_save=False)
        return True

    def _mb_request(self, start_save=True):
        """(Re)create the multiball task for new balls: the first one waits a trough cycle."""
        self._mb_first_at = self.now + (MB_FIRST_EJECT_TICKS - 0.5) * TICK
        self._mb_task(start_save)

    def _mb_task(self, start_save=True):
        """Multiball task FUN_0001ea60: wait until no ball device is busy (the VUK keeps or is ejecting
        its ball), then start the save and launch the balls one per trough eject cycle, the first one
        after a trough cycle (_mb_request)."""
        vuk_busy_until = self.vuk_released_at + (VUK_BUSY_TICKS - 0.5) * TICK
        if self.ball_held or self.vuk_device_busy or self.now < vuk_busy_until:
            self.task_start(MB_TASK, 1, lambda: self._mb_task(start_save))
            return
        if start_save:
            save_ticks, grace_ticks = self._mb_save
            if save_ticks:
                self.task_kill(0x35)
                self.task_start(0x34, save_ticks, lambda: self._mb_save_grace(grace_ticks))
            else:
                self._mb_save_grace(grace_ticks)
        if self.now < self._mb_first_at:
            self.task_start(MB_TASK, 1, lambda: self._mb_task(False))
            return
        self._mb_launch()

    def _mb_launch(self):
        if self._mb_pending <= 0 or not self.game or self.state & 0x214:
            self._mb_pending = 0
            self.task_kill(MB_TASK)
            return
        self._mb_pending -= 1
        self.machine.playfield.add_ball(balls=1, player_controlled=False)
        self.task_start(MB_TASK, MB_EJECT_TICKS, self._mb_launch)

    def _mb_save_grace(self, grace_ticks):
        self.leff_stop(13)
        # the ball search waits for the end of the multiball task (save, then grace) [0x0001ea60]
        self.task_start(0x35, grace_ticks, self.ball_search_reload)

    def mb_save_running(self):
        """The multiball save, also while the multiball task still waits to start it."""
        return self.task_running(0x34) or self.task_running(0x35) or (
            self.task_running(MB_TASK) and bool(self._mb_save[0]))

    def kill_mb_save(self):
        if self.task_kill(0x34):
            self.leff_stop(13)
        self.task_kill(0x35)

    def score_add(self, points):
        """score_add [0x0002340c]: x playfield multiplier (always 1); nothing while tilted or out of game."""
        if not self.game or self.state & 0x210 or not self.game.player:
            return 0
        self.trace.log("score_add", points=points, multiplier=1, player=self.player_num)
        points = self.score_event(points)
        self.ball_search_reload()
        self._add_score(points)
        if not self.ball_scored:
            self.ball_scored = True
            if self.shoot_again:
                self.shoot_again = False
                self.flag_clear(9)
        return points

    def score_event(self, points):
        """Score event 0x4c: its hooks may change the points (TRON double scoring x2)."""
        for fn in self.hooks.get("score_event", ()):
            points = fn(points)
        return points

    def _add_score(self, points):
        """The score display reports the sum of all score_adds of one task run as one "score" event."""
        player = self.game.player
        player.score += points
        if not self._score_pending:
            self.machine.clock.schedule_once(self._score_flush, 0)
        self._score_pending[self.player_num] = self._score_pending.get(self.player_num, 0) + points

    def _score_flush(self):
        pending, self._score_pending = self._score_pending, {}
        for num, delta in pending.items():
            total = self.game.player_list[num - 1].score if self.game else 0
            self.trace.log("score", player=num, delta=delta, total=total)

    def base_score(self, points):
        """FUN_0102a188: base switch score, nothing while tilted."""
        if not self.tilted:
            self.score_add(points)

    def adj_value(self, num):
        return self.adj[num]

    # ------------------------------------------------------------------ valid playfield (4.3)

    def playfield_switch(self, num):
        """Called by switch handlers: force switches validate at once, 3 distinct counting ones do."""
        if num != 11:
            self.vuk_ejecting = False                # a playfield switch confirms the VUK eject
        self.ball_search_reload()
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
        self.ball_validated = True
        # the base music rule switches to the main play music (0x01b) one tick later
        self.after(1, lambda: self.in_play and self.display.rules_refresh())

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

    def _vuk_eject_confirmed(self, unconfirmed=False, **kwargs):
        """The VUK device task runs from the release until MPF confirms the eject (a playfield switch or
        the eject timeout); the multiball task waits for it."""
        self.vuk_device_busy = unconfirmed

    def _shooter_ejecting(self, mechanical_eject=False, **kwargs):
        """Auto-launch (coil 2): the OS runs task 0x3c from the launch, so the shooter lane does not raise
        the orbit post and the launched ball's orbit pass is ignored (sw23; portal_multiball_shots.jsonl
        24.07 launch, 0x3c at the launch, left orbit 1.8 s later scores no shot). Length not traced."""
        if not mechanical_eject:
            self.task_start(0x3c, AUTO_LAUNCH_TICKS)

    def _attract_started(self, **kwargs):
        self.state = ST_ATTRACT

    # ------------------------------------------------------------------ game start (4.1)

    def _game_starting(self, queue=None, **kwargs):
        self.state = 0
        self.players = [PlayerData() for _ in range(4)]
        self.eb_lit = [0] * 4
        self.eb_collected = [0] * 4
        self.specials_lit = [0] * 4
        self.specials_collected = [0] * 4
        self.shoot_again = False
        self.flags.clear()
        self.tasks_kill_all()
        self.audit(0x11)
        self.display.clear()
        self._new_game = True
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
            self.deff_start(26, player=self.player_num)   # speech 0x11b comes with the deff
            self.leff_start(16)
        self.deff_start(19)
        self.ball_validated = False
        self.music(self.base_music())
        self.hook("ball_start_media")                # leffs/tube shows the features start with the ball
        self.deff_stop(27)                           # instant info off
        if self._new_game:
            self._new_game = False
            self.sound(0x0f5)
        self.ball_search_count = 0
        self.ball_search_reload()
        self.serve(3)
        # The trough eject task kicks the ball about 32 ticks after the serve (traces/game_flow.jsonl
        # ball start 1.90 s, trough eject 2.42 s); MPF ejects when the ball_starting queue clears.
        if queue:
            queue.wait()
            self.after(SERVE_EJECT_TICKS, queue.clear)

    def _ball_started(self, **kwargs):
        pass

    def serve(self, serve_type):
        """serve(type) [0x0001f258]: 3 = new ball (arms ball save), 1/2 = ball-save replacement."""
        self.serve_type = serve_type
        self.pf_valid = False                        # gf_pf_valid 0 at every serve
        self._counting_seen = set()
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
        self.after(1, lambda: self.ball_save == "armed" and self.leff_start(14))   # from task 0x31
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
        self.vuk_ejecting = False
        if self.balls_in_play() - balls > 0:
            if self.mb_save_running() and not self.tilted:
                # multiball save: the multiball task launches a replacement. Unlike the single-ball save
                # (ball_save_try 0x00019b34) it shows nothing and audits nothing.
                self._mb_pending += balls
                if not self.task_running(MB_TASK):
                    self._mb_request(start_save=False)
                return {"balls": 0}
            self.hook("ball_drained", balls)
            # trough entry (0x0101bbc0 case 0xe): installed - balls in devices (the VUK counts) < 2
            if self.balls_in_play() - balls - (1 if self.ball_held else 0) < 2:
                self.kill_mb_save()
                self.hook("multiball_end")           # 0x0101bcec: fewer than 2 balls in play
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
            # trough eject task, then the auto-launch (traces/game_flow.jsonl: save 7.96 s, eject 8.60 s)
            self.after(SAVE_EJECT_TICKS, lambda: self.machine.playfield.add_ball(player_controlled=False))
            return {"balls": 0}
        return {"balls": balls}

    # ------------------------------------------------------------------ ball search (5.2)

    def ball_search_reload(self, seconds=10):
        """0x00019d58: reload the ball-search countdown (every playfield switch and every score)."""
        if self._search_handle:
            self.machine.clock.unschedule(self._search_handle)
        self._search_handle = self.machine.clock.schedule_once(self._ball_search, seconds * SECOND * TICK)

    def _ball_search(self):
        self._search_handle = None
        if not self.game:
            return
        # no search while the multiball task (save and grace, FUN_0001ea60) runs: it reloads at its end
        if (self.pf_valid and not self.state & (ST_END_BALL | ST_BONUS | 0x18) and not self.ball_held
                and not self.vuk_ejecting and not self.mb_save_running()):
            self.ball_search_count += 1
            self.task_start(0x2b, BALL_SEARCH_TICKS)
            self.audit(0x25)
            self.hook("ball_search")
            self.machine.events.post("tron_ball_search", count=self.ball_search_count)
        self.ball_search_reload(15 if self.tilted else 10)

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
        self.hook("tilt_start")                      # event 0x66, posted before the tilt state is set
        self.state |= ST_TILT
        self.ball_search_reload(15)
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

    def light_special(self):
        """0x00024014(1): special lit (collected at a lit outlane), deff 81 "SPECIAL IS LIT"."""
        self.specials_lit[self.player_num - 1] += 1
        self.deff_start(81)

    def collect_special(self):
        """Outlane with special lit [0x000240ac]: deff 82, 100,000, then the award per adj 23 (or 5 M
        over the adj 22 limit). Audit 0x0e."""
        p = self.player_num - 1
        if not self.specials_lit[p]:
            return False
        self.specials_lit[p] -= 1
        self.deff_start(82)
        self.sound(0x09e)
        self.score_add(100000)
        if self.specials_collected[p] >= self.adj_value(22):
            self.score_add(5000000)
        else:
            self.specials_collected[p] += 1
            self.audit(0x0e)
            award = self.adj_value(23)
            if award == 3:
                self.score_add(5000000)
            elif award == 4:
                self.collect_extra_ball()
            elif award == 0:
                self.machine.events.post("tron_award_credit")
        return True

    # ------------------------------------------------------------------ end of ball (6.1)

    def _ball_ending(self, queue=None, **kwargs):
        queue.wait()
        if self.task_running(0x2b):
            self.after(self.task_ticks_left(0x2b), lambda: self._ball_ending_go(queue))
            return
        self._ball_ending_go(queue)

    def _ball_ending_go(self, queue):
        self.state |= ST_END_BALL
        self.kill_ball_save()
        self.kill_mb_save()
        self._mb_pending = 0
        self.task_kill(MB_TASK)
        self.display.clear()
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
            # event 0x16, multiplier 1, not a score_add; the score event still applies (a TRON double
            # scoring still running doubles the bonus: traces/zen_rollover.jsonl 31.67 s, 2 x 150,000)
            self._add_score(self.score_event(total))
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
        if self._search_handle:
            self.machine.clock.unschedule(self._search_handle)
            self._search_handle = None
