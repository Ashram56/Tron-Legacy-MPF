"""Combos and the End of Line combo jackpot value (assets/rules/modes/combos.md).

A shot that is a combo starter opens a window (task 0xcd, then the 0xce grace) that lights the arrows
of the "next" shots; hitting one of them in time scores an N-way combo. Shot sequences that match a
named combo add its value to the End of Line combo jackpot (pd.eol_combo_jackpot, 500,000 at every
ball start). Lighting and collecting that jackpot belong to the End of Line feature
(hooks eol_combo_jackpot_light / eol_combo_jackpot); it reads the value with eol_combo_jackpot_value().
Shots use the switch layer's numbering 0-5: left orbit, left ramp, left inner loop, right inner loop,
right ramp, right orbit.
"""
from tron.features import Feature
from tron.lamps import ARROWS

STARTERS = 0x36                 # combo_starters at every ball start [0x010031ac]
WINDOW = 0x138                  # combo_timer at window open (312), -7 every 7 ticks
STEP = 7
GRACE = 125                     # task 0xce
BASE = 250000                   # combo_base at the player's first ball [0x0100317c]
STEP_VALUE = 50000
JACKPOT_START = 500000          # eol_combo_jackpot at every ball start
HISTORY_MAX = 5

# shot -> (mask, next shots lit) [table 0x040d2324]
SHOTS = {0: (0x01, 0x00), 1: (0x02, 0x05), 2: (0x04, 0x18), 3: (0x08, 0x00), 4: (0x10, 0x20), 5: (0x20, 0x18)}

LR, LO, LIL, RIL, RR, RO = 0x02, 0x01, 0x04, 0x08, 0x10, 0x20
# named combos [table 0x040d236c]: (name, shot masks oldest first, value added to the jackpot, audit, keep history)
NAMED = (
    ("CASTOR", (LR, LO), 350000, 0x7b, False),
    ("LAST ISO", (LR, LIL), 400000, 0x7c, True),
    ("THE OUTLANDS", (LR, LIL, RIL), 750000, 0x7d, False),
    ("LIGHT CYCLE", (LR, LIL, RR), 500000, 0x7e, True),
    ("LIGHT RUNNER", (LR, LIL, RR, RO), 650000, 0x7f, True),
    ("THE GRID", (LR, LIL, RR, RO, RIL), 850000, 0x80, False),
    ("SIREN", (LIL, RIL), 500000, 0x81, False),
    ("JARVIS", (LIL, RR), 350000, 0x82, True),
    ("3-MAN LIGHT JET", (LIL, RR, RO), 500000, 0x83, True),
    ("RICOCHET", (LIL, RR, RO, RIL), 650000, 0x84, False),
    ("END OF LINE", (RO, RIL), 550000, 0x85, False),
    ("RINZLER", (RO, RR), 350000, 0x86, False),
)


class Combos(Feature):
    name = "combos"
    HOOKS = ("game_start", "player_first_ball", "ball_start", "combo_awards", "combo_lit",
             "eol_combo_jackpot_value")

    def __init__(self, os_):
        super().__init__(os_)
        self.starters = 0
        self.lit = 0
        self.count = 0
        self.timer = 0
        self.history = []
        # leff 159, the combo arrows [FUN_01003bf0]: no multiball and (starters or task 0xcd)
        os_.lamp_rule(lambda: not os_.any_multiball() and (self.starters or os_.task_running(0xcd)),
                      leff=159, order=0x01003bf0)
        os_.lamps.leff_code(159, self._leff_arrows)
        os_.register_poke(0x2111608, lambda p, v: setattr(os_.players[p], "eol_combo_jackpot", v), stride=4)

    def _leff_arrows(self, task):
        """leff159_combo_arrows [0x01003a74]: while the window (task 0xcd) runs, the lit shots' arrows
        alternate on / off every combo_timer / 31 ticks (2-10); the other arrows are released."""
        phase = task.data.setdefault("phase", True)
        window = self.os.task_running(0xcd)
        for shot, lamp in enumerate(ARROWS):
            if window and self.lit & SHOTS[shot][0]:
                task.set(lamp, phase)
            else:
                task.release(lamp)
        task.data["phase"] = not phase
        ticks = 6 if not window else 10 if self.timer >= 0x138 else max(2, self.timer // 31)
        task.sleep(ticks, self._leff_arrows)

    # ------------------------------------------------------------------ resets

    def game_start(self):
        """combo_game_start_reset [0x01003138] (event 0x2e): combos made this game, all players."""
        for pd in self.os.players:
            pd.combo_total = 0

    def player_first_ball(self):
        """[0x0100317c] (event 0x26)."""
        self.pd.combo_base = BASE

    def ball_start(self):
        """[0x010031ac] (event 0x11)."""
        self.starters = STARTERS
        self.pd.eol_jackpot_collected = 0
        self.pd.eol_combo_jackpot = JACKPOT_START

    def eol_combo_jackpot_value(self):
        return self.pd.eol_combo_jackpot

    # ------------------------------------------------------------------ window

    def window_running(self):
        return self.os.task_running(0xcd) or self.os.task_running(0xce)

    def combo_lit(self, shot):
        """combo_shot_is_lit [0x01003370]: window running and the shot is lit."""
        return bool(self.window_running() and self.lit & SHOTS[shot][0])

    def _window_step(self):
        """task_cd_combo_window [0x010033c4]: -7 every 7 ticks, then 125 ticks as task 0xce."""
        self.timer = max(self.timer - STEP, 0)
        if self.timer:
            self.os.task_start(0xcd, STEP, self._window_step)
            return
        self.os.task_start(0xce, GRACE, self.os.request_refresh)
        self.os.request_refresh()

    def _kill_window(self):
        self.os.task_kill(0xcd)
        self.os.task_kill(0xce)

    # ------------------------------------------------------------------ history

    def _is_prefix(self):
        h = self.history
        return any(len(h) <= len(seq) and tuple(h) == seq[:len(h)] for _, seq, _, _, _ in NAMED)

    def _append(self, mask):
        """combo_history_append + trim [0x010035c0, 0x010034ac]: keep the longest recent run that is
        still the start of a named combo."""
        if len(self.history) >= HISTORY_MAX:
            self.history = []
        self.history.append(mask)
        while self.history and not self._is_prefix():
            self.history.pop(0)
        return bool(self.history)

    def _match(self):
        """combo_named_match [0x01003618]: the history is a whole named sequence."""
        for entry in NAMED:
            if tuple(self.history) == entry[1]:
                if not entry[4]:
                    self.history = []
                return entry
        return None

    # ------------------------------------------------------------------ the shot

    def combo_awards(self, shot):
        """on_combo_shot [0x01003714]; returns True when a combo was scored."""
        os_, pd = self.os, self.pd
        mask, nxt = SHOTS[shot]
        scored = False
        if not (self.window_running() and self.lit & mask):
            self.count = 1
            self.history = []
            self._append(mask)
        else:
            self.count += 1
            pd.combo_total = min(pd.combo_total + 1, 0xffff)
            named = self._match() if self._append(mask) else None
            value = pd.combo_base + max(self.count - 2, 0) * STEP_VALUE
            points = os_.score_add(value)
            os_.deff_start(138, points=points, named=named and named[0], count=self.count,
                           total=pd.combo_total,       # the deff shows the jackpot after the add below
                           jackpot=pd.eol_combo_jackpot + (named[2] if named else 0))
            os_.audit(0x7a)
            if named:
                pd.eol_combo_jackpot += named[2]
                os_.audit(named[3])
            scored = True
        self._kill_window()
        if (not os_.any_multiball()
                and (self.starters & mask or (scored and not mask & 9)) and nxt):
            self.lit = nxt
            self.timer = WINDOW
            os_.task_start(0xcd, STEP, self._window_step)
        os_.request_refresh()
        return scored


feature = Combos
