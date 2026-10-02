"""Flynn's Arcade mystery award at the VUK (assets/rules/modes/flynns_arcade.md).

The award functions of the other features are reached through hooks named arcade_<award>_weight
(returns the entry's weight, given its default) and arcade_<award> (gives the award, returns True when
given). A feature that is not built leaves its entry at weight 0.
"""
from tron.features import Feature

ORDER = 20
# (name, default weight, audit) in bag order [entries table 0x040f08dc]
AWARDS = (
    ("500k", 100, 0x53),
    ("gem", 25, 0x54),
    ("clu", 25, 0x55),
    ("zuse", 25, 0x56),
    ("quorra", 25, 0x57),
    ("disc", 25, 0x58),
    ("light_cycle", 25, 0x59),
    ("recognizer", 100, 0x5a),
    ("sos", 101, 0x5b),
    ("more_time", 100, 0x5c),
    ("extra_ball", 1, 0x5d),
    ("special", 1, 0x5e),
)


def award_percentage_ok(rate, adj, margin):
    """arcade_weight_extra_ball / arcade_weight_special [0x0100e2dc / 0x0100e354]: the award stays in the bag
    while the machine's award percentage (audit 16 EXTRA BALL PERCENTAGE / 24 SPECIAL PERCENTAGE) equals the
    operator's adj 27 / 24, or is more than `margin` below it."""
    return rate == adj or rate + margin < adj


class Arcade(Feature):
    name = "arcade"
    HOOKS = ("player_first_ball", "ball_start", "arcade_light", "arcade_collect", "arcade_lit")

    def player_first_ball(self):
        self.pd.arcade_lit = 0                    # 0x0100dd38

    def ball_start(self):
        self.light()                              # LAB_0100dd64

    def arcade_lit(self):
        return bool(self.pd.arcade_lit)

    def arcade_light(self, _=None):
        """Right orbit [0x0102a794]: relight when task 0x3c is not running and no multiball runs."""
        if not self.os.task_running(0x3c) and not self.os.any_multiball():
            self.light()

    def light(self):
        """0x0100ddb0(1): media only when the flag goes 0 -> 1 (deff 104 brings leff 115 and 0x0df)."""
        if not self.pd.arcade_lit:
            self.pd.arcade_lit = 1
            self.os.deff_start(104)
            self.os.hook("rules_refresh")

    # ------------------------------------------------------------------ the award

    def weights(self):
        os_ = self.os
        out = []
        for name, default, _ in AWARDS:
            if name == "500k":
                w = default + (1000 if os_.adj_value(42) or os_.flag(0xf) else 0)
            elif name == "more_time":
                w = default if os_.hook("timed_feature_running") and not os_.flag(0x2c) else 0
            elif name == "extra_ball":
                w = default if (os_.eb_collected[os_.player_num - 1] < os_.adj_value(26)
                                and award_percentage_ok(os_.audits.value(16), os_.adj_value(27), 3)) else 0
            elif name == "special":
                w = default if (os_.specials_collected[os_.player_num - 1] < os_.adj_value(22)
                                and award_percentage_ok(os_.audits.value(24), os_.adj_value(24), 2)) else 0
            else:
                w = os_.hook("arcade_{}_weight".format(name), default) if os_.has_hook(
                    "arcade_{}_weight".format(name)) else 0
            out.append(w or 0)
        return out

    def arcade_collect(self):
        """0x0100de3c / 0x0100debc: lit and no multiball -> one weighted award, deff 105 (task 0x97)."""
        os_ = self.os
        if not self.pd.arcade_lit or os_.any_multiball():
            return False
        weights = self.weights()
        i = os_.pick("arcade", weights)
        if i is None:
            return False
        name, _, audit = AWARDS[i]
        self.last_award = name
        os_.show(0x97, 105, award=name)
        if self.award(name):
            os_.audit(audit)
            self.pd.arcade_lit = 0
            os_.hook("rules_refresh")
            return True
        os_.display.cancel(0x97)
        return False

    def award(self, name):
        os_ = self.os
        if name == "500k":
            os_.score_add(500000)
            return True
        if name == "more_time":
            os_.hook("more_time")                 # 0x0100f98c: every running timer back to full
            os_.flag_set(0x2c)
            return True
        if name == "extra_ball":
            return bool(os_.hook("vuk_lit_add", 1, True))
        if name == "special":
            os_.light_special()
            return True
        return bool(os_.hook("arcade_" + name))


feature = Arcade
