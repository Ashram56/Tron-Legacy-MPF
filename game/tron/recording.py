"""Recording and replay of a played session (not in the ROM: a tool to reproduce what an owner saw).

Recording (on when scripts/run.py sets TRON_RECORD_DIR, which it does for every run): from each return to the attract
mode until the next, every switch change is kept with its time in seconds since that moment, with the random seed of the
game started in between. The file is `<dir>/<date>-<time>.json`, the format of the platform's scenario files
(MPF-Godot-Packaging common/games/replay_scenario.py) plus the seed:

    {"format": 1, "seed": 123456789, "events": [[seconds, "s_start_button", "on"], ...]}

It is written while the game runs (every 10 s) and when the game ends or MPF quits, only when a game was started.

Seed: at each game start the rules' generator (os_.random) is seeded with a number drawn then, or with TRON_SEED, or with the
replayed file's seed; the number is written to MPF's log ("tron_seed ...") and sent to Godot, which seeds its clip and
PuP picks with it (tools/replay_overlay.gd). The same seed and the same switch changes give the same draws.

Replay (`scripts/run.py --replay FILE`, TRON_REPLAY): the file's switch changes are played at their times from the moment
MPF enters the attract mode, on the virtual hardware; the trough switches are left out (the virtual trough moves the
balls), and the shooter lane is left to the machine's own ball. Godot shows a clock (mm:ss.s) from the same moment, and
`<file>.timeline.txt` lists, with the same clock, every switch change and every display effect (deff_start) that
follows, to match what was seen at a given time with the effect the game started.
"""
import json
import os
import random
import time

FORMAT = 1
SAVE_EVERY = 10.0            # seconds between two writes of a running recording
REPLAY_END_AFTER = 5.0       # seconds after the last event the timeline says the replay is over
SEED_BITS = 31


def clock(t):
    """Seconds as mm:ss.s, the Godot overlay's format."""
    return "{:02d}:{:04.1f}".format(int(t // 60), t % 60)


class Session:
    """The recording and replay of one run of the machine; os_layer.Tron owns one."""

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        self.record_dir = os.environ.get("TRON_RECORD_DIR") or ""
        self.replay_path = os.environ.get("TRON_REPLAY") or ""
        self.forced_seed = os.environ.get("TRON_SEED") or ""
        self.seed = None                 # the seed of the game started in this recording
        self.events = []                 # [[seconds, switch, "on"|"off"]]
        self.origin = None               # machine clock of the recording's start
        self.recording = False
        self._saving = None
        self._path = None
        self._replay = None
        self._timeline = None
        self._replay_origin = None
        self._replay_events = []
        self._played = False
        self._handlers = []
        if not (self.record_dir or self.replay_path):
            return
        self.machine.events.add_handler("mode_attract_started", self._attract_started, priority=500)
        self.machine.events.add_handler("shutdown", self._shutdown, priority=500)
        if self.replay_path:
            self._load_replay()

    # ------------------------------------------------------------------ seed

    def game_seed(self):
        """The seed of the game that starts now (tron/os_layer.py _game_starting), or None: no per-game seed (tests and
        scripts seed the generator themselves)."""
        if self._replay is not None and self._replay.get("seed") is not None:
            seed = int(self._replay["seed"])
        elif self.forced_seed:
            seed = int(self.forced_seed)
        elif self.record_dir or self.replay_path:
            seed = random.SystemRandom().getrandbits(SEED_BITS)
        else:
            return None
        self.seed = seed
        self.os.random.seed(seed)
        self.os.trace.log("tron_seed", seed=seed)
        self.machine.log.info("tron_seed %d (recording %s)", seed, os.path.basename(self._path or "-"))
        self.os.media.send_seed(seed)
        self._save()
        return seed

    # ------------------------------------------------------------------ recording

    def _attract_started(self, **kwargs):
        self._finish()
        if self.replay_path:
            if not self._played:
                self._play_replay()
            return                       # a replay is not recorded again
        self.recording = True
        self.origin = self.machine.clock.get_time()
        self.events = []
        self.seed = None
        self._path = os.path.join(self.record_dir, time.strftime("%Y%m%d-%H%M%S") + ".json")
        self._hook_switches()
        if self._saving is None:
            self._saving = self.machine.clock.schedule_interval(self._save, SAVE_EVERY)

    def _hook_switches(self):
        if self._handlers:
            return
        sc = self.machine.switch_controller
        for name in self.machine.switches.keys():
            for state in (1, 0):
                sc.add_switch_handler(name, self._changed, state=state, callback_kwargs={"switch": name, "state": state})
                self._handlers.append((name, state))

    def _changed(self, switch=None, state=None, **kwargs):
        if not self.recording or self.origin is None:
            return
        self.events.append([round(self.machine.clock.get_time() - self.origin, 3), switch, "on" if state else "off"])

    def _save(self, *args):
        """Write the recording when a game was started in it."""
        if not self.recording or self.seed is None or not self._path:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"format": FORMAT, "seed": self.seed, "events": self.events}, f, separators=(",", ":"))
        os.replace(tmp, self._path)

    def _finish(self):
        if self.recording:
            self._save()
            self.recording = False

    def _shutdown(self, **kwargs):
        self._finish()
        if self._timeline:
            self._timeline.close()
            self._timeline = None

    # ------------------------------------------------------------------ replay

    def _load_replay(self):
        with open(self.replay_path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format") != FORMAT:
            raise SystemExit("replay {}: format {} is not supported".format(self.replay_path, data.get("format")))
        self._replay = data
        self._replay_events = sorted(data.get("events", []), key=lambda e: e[0])

    def _play_replay(self):
        from tron.switches import SW
        self._played = True
        trough = {SW[n] for n in (18, 19, 20, 21) if n in SW}
        out = os.path.splitext(self.replay_path)[0] + ".timeline.txt"
        self._timeline = open(out, "w", encoding="utf-8")
        self._replay_origin = self.machine.clock.get_time()
        self._line(0.0, "replay of {} (seed {})".format(os.path.basename(self.replay_path), self._replay.get("seed")))
        self.os.media.send_replay_clock()
        sc = self.machine.switch_controller
        last = 0.0
        for t, name, state in self._replay_events:
            last = max(last, t)
            if name in trough:
                continue
            if name not in self.machine.switches:
                self._line(t, "unknown switch {} left out".format(name))
                continue
            value = {"on": 1, "off": 0}.get(state)
            if value is None:            # "tap" / "toggle" of the page's recorder
                value = 2
            self.machine.clock.schedule_once(
                lambda n=name, s=value, tt=t: self._press(n, s, tt), max(t, 0.0))
        self.machine.clock.schedule_once(lambda: self._line(last + REPLAY_END_AFTER, "end of the replay"),
                                         last + REPLAY_END_AFTER)
        trace = self.os.trace
        inner = trace.log

        def log(ev, **fields):           # the display effects and the game's own milestones, on the replay's clock
            inner(ev, **fields)
            if ev in ("deff_start", "tron_seed", "game_start", "ball_start", "game_end"):
                self._line(self.machine.clock.get_time() - self._replay_origin,
                           ev + "".join(" {}={}".format(k, v) for k, v in fields.items() if k in ("id", "seed", "rule")))
        trace.log = log

    def _press(self, name, value, t):
        sc = self.machine.switch_controller
        if value == 2:                   # a tap
            sc.process_switch(name, 1, True)
            self.machine.clock.schedule_once(lambda: sc.process_switch(name, 0, True), 0.05)
        else:
            sc.process_switch(name, value, True)
        self._line(t, "{} {}".format(name, {0: "off", 1: "on", 2: "tap"}[value]))

    def _line(self, t, text):
        if self._timeline:
            self._timeline.write("{}  {}\n".format(clock(t), text))
            self._timeline.flush()
