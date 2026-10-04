"""Flynn's Arcade mystery award at the VUK (assets/rules/modes/flynns_arcade.md).

The award functions of the other features are reached through hooks named arcade_<award>_weight
(returns the entry's weight, given its default) and arcade_<award> (gives the award, returns True when
given). A feature that is not built leaves its entry at weight 0.
"""
from tron.features import Feature
from tron.os_layer import TICK

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
# What each award is called: the ROM's audit names "FLYNN'S ARCADE: <name>" (audits 91-102, counters
# 0x53-0x5e), in bag order = award id 1-12. Deff 105 prints no text: it shows the award's icon (table
# 0x040d29a0 {id, icon_a, icon_b}, assets deff_105 parts/index.json); the name goes with the deff's event.
AWARD_NAMES = ("500K", "ADV. GEM", "ADV. CLU", "ADV. ZUSE", "ADV. QUORRA", "ADV. DISC", "ADV. LIGHT CYCLE",
               "ADV. RECOGNIZER", "ADV. SEA OF SIMUL.", "MORE TIME", "LIGHT EXTRA BALL", "LIGHT SPECIAL")

# deff_105_arcade_award [0x0100e8bc]: 3 cabinets 45 dots wide, 5 apart, enter from x 0x7f - 45 and move
# 4 dots left every frame of 3 ticks until the slot holding the award is centred on x 84 (0x54).
CABINET_W, CABINET_GAP, REEL_X, REEL_STEP, FRAME_TICKS = 45, 5, 0x7f - 45, 4, 3
BLINK_MIN, BLINK_MAX = 21, 61       # blink steps: at least 21 (ends on an even step), at most 61
SOUND_INTRO, SOUND_ROLL, SOUND_STOP = 0x0e4, 0x0e1, 0x0e3


def scroll_frames(slot):
    """Frames the reel scrolls before the award's slot stops (5, 18 or 30 for slot 0, 1, 2)."""
    stop = 0x54 - CABINET_GAP * slot - CABINET_W * slot - CABINET_W // 2
    n, x = 0, REEL_X
    while stop < x:
        n, x = n + 1, x - REEL_STEP
    return n


def blink_frames(sound_seconds):
    """Frames of the blink loop: step l blinks the award (icon_a on even steps); the loop goes on while
    l < 21, l is odd or sound 0x0e3 still plays, up to 61 steps (the ROM's do/while)."""
    l = 0
    while l + 1 < BLINK_MAX and (l < BLINK_MIN or l % 2 or (l + 1) * FRAME_TICKS * TICK < sound_seconds):
        l += 1
    return l + 1


def award_percentage_ok(rate, adj, margin):
    """arcade_weight_extra_ball / arcade_weight_special [0x0100e2dc / 0x0100e354]: the award stays in the bag
    while the machine's award percentage (audit 16 EXTRA BALL PERCENTAGE / 24 SPECIAL PERCENTAGE) equals the
    operator's adj 27 / 24, or is more than `margin` below it."""
    return rate == adj or rate + margin < adj


class Arcade(Feature):
    name = "arcade"
    HOOKS = ("player_first_ball", "ball_start", "arcade_light", "arcade_collect", "arcade_lit")

    def __init__(self, os_):
        super().__init__(os_)
        os_.lamp_update(self.lamp_rule)

    def lamp_rule(self):
        """arcade_lamp_rule [0x0100df3c]: lamp 45 flashes while the arcade is lit and no multiball runs."""
        lit = not self.os.any_multiball() and self.pd.get("arcade_lit")
        self.os.lamps.lamp_set(45, 2 if lit else 0)

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
        os_.show(0x97, 105, **self.reel(i + 1))
        if self.award(name):
            os_.audit(audit)
            self.pd.arcade_lit = 0
            os_.hook("rules_refresh")
            return True
        os_.display.cancel(0x97)
        return False

    def reel(self, award_id):
        """deff_105_arcade_award [0x0100e8bc] for award id 1-12 (the bag pick, task arg +0x30): its random
        choices, run length and sounds, as the deff's args. Per slot: a cabinet from table 0x040d2990
        (FUN_0000c6b4(4)) and an award id FUN_0000c6b4(13) + 1, 13 -> 1, moved on past ids already shown.
        The award goes where it already shows, else in a random slot (FUN_0000c6b4(3)). A test or
        scenario can force the slot (os.forced["arcade_slot"])."""
        os_ = self.os
        rnd = os_.random
        cabinets, icons = [], []
        for _ in range(3):
            cabinets.append(rnd.randrange(4))
            first = rnd.randrange(13)
            v = first
            while True:
                v = v + 1 if v + 1 < 13 else 1
                if v not in icons or v == first:
                    break
            icons.append(v)
        forced = os_.forced.get("arcade_slot")
        slot = forced.pop(0) if forced else None
        if slot is None:
            slot = icons.index(award_id) if award_id in icons else rnd.randrange(3)
        elif award_id in icons and icons.index(award_id) != slot:
            icons[icons.index(award_id)] = icons[slot]
        icons[slot] = award_id
        scroll = scroll_frames(slot)
        lengths = os_.sample_lengths(SOUND_STOP)
        sample = os_.pick("sample_0x{:03x}".format(SOUND_STOP), [1] * len(lengths)) if len(lengths) > 1 else 0
        sample = sample or 0
        blink = blink_frames(lengths[sample] if lengths else 0)
        stop_at = scroll * FRAME_TICKS * TICK

        def stop():
            os_.sound_stop(SOUND_ROLL)                     # FUN_0002ceb4(0xe1)
            os_.sound(SOUND_STOP, in_deff=105, index=sample)

        from tron.display import HOLD_TICKS
        return dict(award=award_id, award_name=AWARD_NAMES[award_id - 1],
                    cab0=cabinets[0], cab1=cabinets[1], cab2=cabinets[2],
                    icon0=icons[0], icon1=icons[1], icon2=icons[2], slot=slot, scroll=scroll, blink=blink,
                    run_seconds=((scroll + blink) * FRAME_TICKS + HOLD_TICKS) * TICK,
                    sounds=[(0, lambda: os_.sound(SOUND_INTRO, in_deff=105)),
                            (0, lambda: os_.sound(SOUND_ROLL, in_deff=105)),
                            (stop_at, stop)])

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
