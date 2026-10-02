"""VUK "lit at the scoop" table and the extra ball (game_flow.md 5.4, developer_guide.md 3.2).

Per player, one byte per award at 0x2111894 + 4*k + (p-1), k = 0..4 for bits 1 extra ball, 2 Quorra,
4 Light Cycle, 8 Portal, 0x10 CLU: vuk_lit_item_add/take/test [0x0102e8c0 / 0x0102eaa4 / 0x0102ec38].
"""
from tron.features import Feature

ORDER = 10
BITS = (1, 2, 4, 8, 0x10)
BASE = 0x2111894


class Scoop(Feature):
    name = "scoop"
    HOOKS = ("player_first_ball", "vuk_lit_add", "vuk_lit_take", "vuk_lit_test", "vuk_extra_ball")

    def __init__(self, os_):
        super().__init__(os_)
        for k, bit in enumerate(BITS):
            os_.register_poke(BASE + 4 * k, (lambda b: lambda p, v: self._set(p, b, v))(bit))

    def _set(self, p, bit, value):
        self.os.players[p].vuk_lit[bit] = value

    def player_first_ball(self):
        """event 0x26 handler 0x0102e834: everything unlit."""
        self.pd.vuk_lit = {bit: 0 for bit in BITS}

    def vuk_lit_add(self, bits, unlimited=False):
        """Light each award in `bits` (count capped at 1 unless unlimited); returns the bits lit."""
        lit = self.pd.vuk_lit
        cap = 0xff if unlimited else 1
        out = 0
        for bit in BITS:
            if not bits & bit:
                continue
            if lit[bit] < cap:
                lit[bit] += 1
            if bit == 1:
                if self.eb_light_game():
                    out |= 1
            else:
                out |= bit
        self.os.hook("rules_refresh")
        return out

    def vuk_lit_take(self, bits):
        lit = self.pd.vuk_lit
        out = 0
        for bit in BITS:
            if bits & bit and lit[bit]:
                lit[bit] -= 1
                out |= bit
        return out

    def vuk_lit_test(self, bits):
        lit = self.pd.vuk_lit
        return any(lit[bit] for bit in BITS if bits & bit)

    # ------------------------------------------------------------------ extra ball

    def eb_light_game(self):
        """0x01012190: OS lit count +1; deff 132 "EXTRA BALL IS LIT" (show task 0x82)."""
        os_ = self.os
        os_.light_extra_ball()
        if not os_.state & 0x305:
            os_.show(0x82, 132)
        return True

    def vuk_extra_ball(self):
        """eb_collect_game 0x01012228: the scoop collects one lit extra ball; deff 133 (show task 0x83)."""
        os_ = self.os
        self.vuk_lit_take(1)
        os_.collect_extra_ball()
        os_.show(0x83, 133)
        return True


feature = Scoop
