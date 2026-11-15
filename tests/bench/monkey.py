"""The random player of the stress tests: a seeded sequence of what a player and a ball can do. Every
action goes through the robot, so the invariants are checked after each one. A failure prints the seed and
the last actions: `TRON_BENCH_SEEDS=<seed>` plays the same game again."""
import random

from tests.bench.robot import SHOTS, BenchError

# action -> weight: shots dominate, as on a real ball
WEIGHTS = (
    ("shot", 60), ("scoop", 7), ("drain", 4), ("outlane", 2), ("wait", 6), ("long_wait", 1), ("flip", 4),
    ("tilt_bob", 1), ("start", 1), ("burst", 3), ("dirty", 4),
)
SHOT_WEIGHTS = {
    "left_orbit": 6, "left_ramp": 8, "left_loop": 6, "right_loop": 6, "right_ramp": 8, "right_orbit": 6,
    "disc": 8, "right_spinner": 3, "zen": 3, "bank_l": 4, "bank_c": 5, "bank_r": 4,
    "pop_l": 3, "pop_r": 3, "pop_b": 3, "sling_l": 3, "sling_r": 3,
}


class Monkey:

    def __init__(self, bench, seed, weights=WEIGHTS, tilt=True, players=True):
        self.b = bench
        self.seed = seed
        self.rng = random.Random(seed)
        self.weights = [(a, w) for a, w in weights if (tilt or a != "tilt_bob") and (players or a != "start")]
        self.log = []
        shots = {name: SHOT_WEIGHTS.get(name, 2) for name in SHOTS}
        self.shot_names, self.shot_weights = list(shots), list(shots.values())

    def pick(self):
        return self.rng.choices([a for a, _ in self.weights], [w for _, w in self.weights])[0]

    def random_shot(self):
        return self.rng.choices(self.shot_names, self.shot_weights)[0]

    def note(self, text):
        self.log.append("{:8.1f} {}".format(self.b.tron.now, text))

    def step(self):
        b = self.b
        if not b.machine.game:
            return False
        if b.tron.state & 0x40:
            b.press("s_start_button", settle=0.2)
            return True
        if b.table.pf == 0:                           # nothing to shoot at: time passes
            if b.table.shooter and b.autoplunge is None:
                b.table.launch()
            b.wait(0.2)
            return True
        action = self.pick()
        if action == "shot":
            name = self.random_shot()
            self.note(name)
            b.shot(name, clean=self.rng.random() < 0.7, settle=self.rng.choice((0.05, 0.25, 0.6)))
        elif action == "dirty":                       # a switch alone, guard or not, almost no time after it
            name = self.random_shot()
            switch = self.rng.choice(SHOTS[name])
            self.note("hit " + switch)
            b.hit(switch, settle=0.02)
        elif action == "burst":                       # a spinner or the bumpers rattle
            name = self.rng.choice(("left_loop", "right_spinner", "pop_l", "pop_r", "pop_b", "disc"))
            n = self.rng.randint(3, 12)
            self.note("{} x{}".format(name, n))
            for _ in range(n):
                if b.table.pf == 0:
                    break
                b.hit(SHOTS[name][0], settle=0.06)
        elif action == "scoop":
            self.note("scoop")
            b.scoop(wait=self.rng.random() < 0.8)
        elif action == "drain":
            self.note("drain")
            b.drain()
        elif action == "outlane":
            side = self.rng.choice(("left", "right"))
            self.note("outlane " + side)
            b.drain(outlane=side)
        elif action == "wait":
            b.wait(self.rng.choice((0.1, 0.5, 1, 2, 4)))
        elif action == "long_wait":
            seconds = self.rng.choice((8, 15, 31, 46))
            self.note("wait {}".format(seconds))
            b.wait(seconds)
        elif action == "flip":
            b.flip(self.rng.choice(("left", "right", "both")))
        elif action == "tilt_bob":
            self.note("tilt bob")
            b.tilt_bob(settle=self.rng.choice((0.1, 1.1)))
        elif action == "start":
            self.note("start")
            b.press("s_start_button")
        return True

    def play(self, actions=400, finish=True):
        """Play up to `actions` actions, then lose the balls until the game ends."""
        b = self.b
        try:
            for _ in range(actions):
                if not self.step():
                    break
            if finish and b.machine.game:
                self.note("finish")
                b.end_game(natural=True)
                b.check()
        except (AssertionError, BenchError, Exception) as e:      # pylint: disable=broad-except
            raise BenchError("seed {}: {}\nlast actions:\n  {}".format(
                self.seed, e, "\n  ".join(self.log[-25:]))) from e
