"""End-of-ball bonus (assets/rules/modes/bonus.md)."""
from tron.features import Feature

LINE_TICKS = 21          # each line is shown 21 frames (0.341 s)
TOTAL_TICKS = 43 + 10    # TOTAL BONUS screen 43 frames, then a 10 frame hold
ITEM_LIT, ITEM_COLLECTED = 50000, 250000
# the item names (FUN_01015f40, messages 1491-1499), then SEA OF SIMULATION (0x610) and PORTAL (0x612)
ITEM_NAMES = ("FLYNN", "GEM", "CLU", "ZUSE", "QUORRA", "DISC", "LIGHT CYCLE", "RECOGNIZER", "TRON")


class Bonus(Feature):
    name = "bonus"
    HOOKS = ("player_first_ball", "ball_start", "bonus_x_add")

    def __init__(self, os_):
        super().__init__(os_)
        os_.register_poke(0x21115d4, lambda p, v: self.os.players[p].__setitem__("bonus_x", v))
        os_.register_poke(0x2111800, lambda p, v: self.os.players[p].__setitem__("sos_count", v))
        os_.register_poke(0x21118b8, lambda p, v: self.os.players[p].__setitem__("portal_count", v))
        # deff 25's screen and values as the count goes (0x01000e7c draws a full screen per line)
        self.shown = {"screen": 0, "base": 0, "name": "", "value": 0, "sum": 0, "mult": 1, "mult_total": 0, "total": 0}
        os_.deff_live((25,), lambda: dict(self.shown))

    def player_first_ball(self):
        pd = self.pd
        pd.items = [[0, 0] for _ in range(9)]     # [times lit, times collected] per item (3.4)
        pd.sos_count = 0
        pd.portal_count = 0

    def ball_start(self):
        if self.os.flag(0x2d):
            self.os.flag_clear(0x2d)
        else:
            self.pd.bonus_x = 1
        self.pd.bonus_base = 50000

    def bonus_x_add(self):
        """FUN_01000b28: +1 per right inner loop shot, cap 25."""
        self.pd.bonus_x = min(self.pd.bonus_x + 1, 25)

    def lines(self):
        """(leff, tube show, value, name) for each non-zero line, in display order [0x01000e7c]."""
        pd = self.pd
        out = [(20, None, pd.bonus_base, "")]
        for i, (lit, collected) in enumerate(pd.items):
            value = ITEM_COLLECTED if collected else ITEM_LIT if lit else 0
            if value:
                out.append((21 + i, 93 + i, value, ITEM_NAMES[i]))
        if pd.sos_count:
            out.append((30, 102, 450000 * pd.sos_count, "SEA OF SIMULATION"))
        if pd.portal_count:
            out.append((31, 103, 2250000 * pd.portal_count, "PORTAL"))
        return out

    def total(self):
        return sum(line[2] for line in self.lines()) * self.pd.bonus_x

    def _show(self, **values):
        self.shown.update(values)
        refresh = getattr(self.os.media, "score_changed", None)
        if refresh and 25 in getattr(self.os.media, "active", ()):
            refresh()

    def run(self, done):
        """deff 25: count the lines, then call done(total)."""
        os_ = self.os
        lines = self.lines()
        steps = list(range(2, self.pd.bonus_x + 1))
        base = sum(line[2] for line in lines)
        self.shown.update(screen=0, base=lines[0][2], name="", value=0, sum=lines[0][2], mult=1, mult_total=base,
                          total=self.total())
        os_.deff_start(25, hold=True, total=self.total())   # this feature drives the bonus media
        os_.leff_start(20)
        self._skip = False
        state = {"i": 0, "running": 0}

        def both_flippers():
            return self.machine.switches["s_left_flipper"].state and self.machine.switches["s_right_flipper"].state

        def show_line():
            if both_flippers():
                return show_total()
            i = state["i"]
            state["i"] += 1
            if i < len(lines):
                leff, tube, value, name = lines[i]
                if i > 0:
                    os_.leff_start(leff)
                    os_.tube_start(tube)
                    self._show(screen=1, name=name, value=value, sum=sum(line[2] for line in lines[:i + 1]))
                os_.after(LINE_TICKS, show_line)
            elif i - len(lines) < len(steps):
                k = steps[i - len(lines)]
                self._show(screen=2, mult=k, mult_total=base * k)
                os_.leff_start(32)
                os_.tube_start(104)
                os_.after(LINE_TICKS, show_line)
            else:
                show_total()

        def show_total():
            self._show(screen=3)
            os_.sound(0x0ba, in_deff=25)
            os_.tube_start(105)
            os_.after(TOTAL_TICKS, finish)

        def finish():
            os_.deff_stop(25)
            done(self.total())

        show_line()


feature = Bonus
