"""Sea of Simulation, the mini wizard mode (assets/rules/modes/sea_of_simulation.md).

Lit when all nine items are lit, started at the VUK (on_vuk -> sos_vuk). Nine stages in item order;
each asks for its shots (simulation_shot ids, value = 1 << id) and collects its item when done. A stage
whose item is already collected is skipped and pays (k+1) million once per player (deff 115).
Game flags: 0x33 played since the last Portal, 0x34 running, 0x35 final stage, 0x36 completed.

ROM tables that are not in the decompile (stage 2 shot order, the CLU helmet sounds, the Light Cycle
chain table 0x040d3748) are modelled as the spec describes them; see STAGES.
"""
from tron.features import Feature
from tron.os_layer import TICK

ORDER = 40

# simulation_shot ids [table 0x040d35dc]
VUK, DISC, HELMETS = 0, 1, (6, 7, 8)
LEFT_ORBIT, LEFT_INNER_LOOP, RIGHT_INNER_LOOP, RIGHT_ORBIT = 14, 16, 17, 19


def bits(ids):
    out = 0
    for i in ids:
        out |= 1 << i
    return out


# Stage table 0x040d37d8, k = item: shot ids in spot order (the first needed one is spotted).
# Stage 2 (CLU): mask 0x94001, the decompile shows the left orbit first; the rest of the order is assumed.
# Stage 6 (LIGHT CYCLE): mask 0xc8000; its chain table 0x040d3748 is not readable here, so the three
# shots are needed in any order (shots already made stay excluded, as in the ROM).
STAGES = (
    (VUK,),
    (RIGHT_INNER_LOOP,),
    (LEFT_ORBIT, LEFT_INNER_LOOP, RIGHT_ORBIT, VUK),
    (9, 10, 11, 12),
    (LEFT_INNER_LOOP,),
    (14, 15, 16, 17, 18, 19),
    (15, 18, 19),
    (13,),
    (2, 3, 4, 5),
)
# The stage's messages (stage table + 0x18 and + 0x19), drawn by deff 114 under SEA OF SIMULATION
STAGE_TEXT = ("FLYNNS ARCADE", "GEM", "CLU HELMETS", "ZUSE TARGETS", "QUORRA", "DISCS", "LIGHT CYCLES",
              "RECOGNIZER", "TRON TARGETS")
SKIP_ITEMS = ("FLYNN", "GEM", "CLU", "ZUSE", "QUORRA", "DISC", "LIGHT CYCLE", "RECOGNIZER", "TRON")
RECOGNIZER_HITS = 6
# simulation shot id -> the inserts the stage lamps draw for it. The stage lamp functions (stage table
# +0x10, spawned by leff_136 [0x01026f74]) use lamp groups 0x4c-0x50 that are not readable here; these
# are the shot's inserts (lamps.csv), checked against traces/sea_of_simulation.jsonl (GEM: 57-59,
# ZUSE: 10 12 29 43, QUORRA: 60-64) and the captured show of leff 136 (CLU: 9 30 31 and the ejects).
SHOT_LAMPS = {VUK: (37, 38, 39, 40), 2: (4,), 3: (3,), 4: (2,), 5: (1,), 6: (9,), 7: (30,), 8: (31,),
              9: (12,), 10: (10,), 11: (43,), 12: (29,), 13: (54,),
              14: (16, 15, 14, 13), 15: (49, 50, 11), 16: (64, 63, 62, 61), 17: (57, 58, 59),
              18: (56, 55, 42), 19: (33, 34, 35, 36)}
STAGE_LAMPS = {4: (60,)}        # QUORRA stage: ADVANCE QUORRA blinks with the left inner loop
HELMET_BITS = 0x1c0
# deff 116+k "stage complete" variant (FUN_01027478): its animation and speech 0x111 take 2.105 s, then
# the deff drops to priority 0x20 for a 10-frame hold (traces/sea_of_simulation: 22.208 -> 24.318,
# 28.632 -> 30.736 when the queued deff 115 takes the display).
STAGE_DONE_SECONDS = 2.105
MAIN_TASK_TICKS = 90            # deff 114: 15 loops of 6 frames before the final-stage speech


class SeaOfSimulation(Feature):
    name = "sea_of_simulation"
    HOOKS = ("player_first_ball", "sos_vuk", "simulation_shot", "sos_clear_skip_flags", "arcade_sos_weight",
             "arcade_sos", "ball_end", "ball_end_wait", "tilt_start")

    def __init__(self, os_):
        super().__init__(os_)
        self.stage = 0
        self.needed = 0
        self.total = 0
        self.skip_value = [0] * 9
        self.skip_paid = [1] * 9
        self.skip_queue = []
        self.skip_showing = False
        self.helmets = 0            # 0x3b678: C, L, U helmets lit in stage 2
        self.lc_made = 0            # 0x3b67c: Light Cycle shots made in stage 6
        self.rec_hits = 0           # 0x3b680: recognizer hits in stage 7
        self.end_wait = 0
        os_.deff_live((114,), self.stage_text)
        os_.deff_live((115,), self.skip_text)
        self.skip_shown = (0, 0)    # deff 115: the skipped stage shown and the points it paid
        os_.lamp_rule(self.lit_rule, leff=134, tube=64, order=0x010267fc)
        os_.lamp_rule(self.running_rule, leff=136, tube=66, order=0x01026dbc)
        os_.lamps.leff_code(136, self._leff_stage)
        os_.deff_rule(self.running_rule, 114, music=0x108, priority=9, on_start=self._status_started)

    # ------------------------------------------------------------------ state

    def _leff_stage(self, task):
        """leff_136 [0x01026f74]: the current stage's lamp function on its own layer. A stage with one
        shot chases / blinks its inserts (FUN_010247d0 / FUN_01024a94: 6-tick steps); a stage with several
        toggles the needed shots' inserts every 3 ticks (FUN_01024d68 / FUN_0102522c, solid in the
        traces). Inserts of shots already made are released."""
        phase = task.data.setdefault("phase", True)
        shots = STAGES[self.stage] if 0 <= self.stage < len(STAGES) else ()
        wanted = set()
        for shot in shots:
            if self.needed & (1 << shot):
                wanted.update(SHOT_LAMPS.get(shot, ()))
        if wanted:
            wanted.update(STAGE_LAMPS.get(self.stage, ()))
        for lamp in set(task.layer.mask) | wanted:
            if lamp in wanted:
                task.set(lamp, phase)
            else:
                task.release(lamp)
        task.data["phase"] = not phase
        task.sleep(6 if len(shots) == 1 else 3, self._leff_stage)

    def player_first_ball(self):
        """Event 0x26 [0x01024640]: SOS starts and skip bonuses given, per player."""
        self.pd.sos_count = 0
        self.pd.sos_skip_flags = 0

    def sos_clear_skip_flags(self):
        """FUN_01026f4c (also called by the Portal start)."""
        self.pd.sos_skip_flags = 0

    def running(self):
        return self.os.flag(0x34)

    def can_start(self, lit):
        """FUN_010263b0: lit, no multiball, no Disc multiball start (task 0xad), SOS not running."""
        os_ = self.os
        return bool(lit) and not os_.any_multiball() and not os_.task_running(0xad) and not self.running()

    def lit_rule(self):
        """FUN_010267fc: leff 134 / tube show 64 while SOS can be started."""
        return self.can_start(self.os.hook("items_all_lit"))

    def stage_text(self):
        """deff 114's stage lines: FUN_0102635c(sos_stage) -> "SHOOT" / the stage's item (none past stage 8)."""
        if 0 <= self.stage < len(STAGE_TEXT):
            return {"shoot": "SHOOT", "item": STAGE_TEXT[self.stage]}
        return {"shoot": "", "item": ""}

    def skip_text(self):
        """deff 115: messages 0x65d + 2k / 0x65e + 2k (item / BONUS; FLYNN and GEM read off the capture,
        the other items named as in the stage table) and the points paid."""
        k, points = self.skip_shown
        return {"item": SKIP_ITEMS[k] if 0 <= k < len(SKIP_ITEMS) else "", "bonus": "BONUS", "value": points}

    def running_rule(self):
        """FUN_01026dbc: running, and the intro (task 0xa0) is not still waiting for the display."""
        os_ = self.os
        return self.running() and not (os_.display.task_running(0xa0) and not os_.display.running(113))

    def _status_started(self):
        """deff 114: speech 0x112 once on the final stage (flag 0x35)."""
        os_ = self.os
        if os_.flag(0x35):
            def speech():
                if os_.display.running(114) and os_.flag(0x35):
                    os_.sound(0x112, in_deff=114)
                    os_.flag_clear(0x35)
            os_.after(MAIN_TASK_TICKS, speech)

    # ------------------------------------------------------------------ start [0x01026520]

    def sos_vuk(self, all_lit):
        os_ = self.os
        if not self.can_start(all_lit):
            return False
        self.skip_value = [0] * 9
        self.skip_paid = [0] * 9
        self.skip_queue = []
        os_.show(0xa0, 113)
        self.total = os_.score_add(1000000)
        self.stage = 0
        self.setup()
        os_.flag_set(0x34)
        os_.flag_clear(0x35)
        os_.flag_clear(0x36)
        os_.flag_set(0x33)
        self.pd.sos_count = min(self.pd.get("sos_count", 0) + 1, 0xff)
        os_.hook("items_clear", True)
        os_.hook("dmb_cancel_restart_window")
        os_.request_refresh()
        return True

    def setup(self):
        """sos_stage_setup [0x01026490]: set up the stage; skip the stages whose item is collected."""
        while True:
            k = self.stage
            if self.collected(k):
                self.skip(k)
                if k == 8:
                    self.complete()
                    return
                self.stage += 1
                continue
            self.needed = bits(STAGES[k])
            self.helmets = self.lc_made = self.rec_hits = 0
            if sum(1 for i in range(k, 9) if not self.collected(i)) == 1:
                self.os.flag_set(0x35)
            return

    def collected(self, k):
        return bool(self.pd.items[k][1])

    def skip(self, k):
        """Stage set-up for a collected item: no shots; the first time per player, queue (k+1) million."""
        self.needed = 0
        pd = self.pd
        if not pd.sos_skip_flags & (1 << k):
            self.skip_value[k] = (k + 1) * 1000000
            self.skip_paid[k] = 0
            self.skip_queue.append(k)
            pd.sos_skip_flags |= 1 << k
            self._next_skip_show()

    def _next_skip_show(self):
        """Task 0xa2 per skipped stage: deff 115 pays the bonus when it gets the display [0x010270a4]."""
        if self.skip_showing or not self.skip_queue:
            return
        k = self.skip_queue.pop(0)
        self.skip_showing = True

        self.skip_shown = (k, self.skip_value[k])

        def pay():
            if not self.skip_paid[k]:
                self.skip_paid[k] = 1
                points = self.os.score_add(self.skip_value[k])
                self.total += points
                self.skip_shown = (k, points)          # deff 115 prints score_add's result (local_34)

        def ended():
            self.skip_showing = False
            self._next_skip_show()
        self.os.show(0xa2, 115, on_start=pay, on_end=ended)

    # ------------------------------------------------------------------ shots [0x01026608]

    def simulation_shot(self, shot, quiet=0):
        if not self.running():
            return False
        k = self.stage
        awarded = self.stage_shot(k, shot, quiet)
        if self.needed == 0:
            self.os.hook("item_collect", k)          # stage audit 0x69 + 2k with the item
            if k == 8:
                self.complete()
            else:
                self.stage += 1
                self.setup()
        self.os.request_refresh()
        return awarded

    def stage_shot(self, k, shot, quiet):
        """The stage's shot function: which bit the shot takes, then the award."""
        bit = 1 << shot
        if k == 2:
            bit = self.helmet_shot(bit)
        elif k == 5 and shot == DISC:
            bit = self.next_needed(k) or bit         # the disc spots the next needed shot
        if not self.needed & bit:
            return False
        if k == 6:                                   # shots made stay excluded (chain table 0x040d3748)
            self.lc_made |= bit
            self.needed &= ~self.lc_made
        elif k == 7:                                 # six recognizer hits, each one paid
            self.rec_hits = min(self.rec_hits + 1, RECOGNIZER_HITS)
            if self.rec_hits >= RECOGNIZER_HITS:
                self.needed &= ~bit
        else:
            self.needed &= ~bit
        self.award(k, quiet)
        return True

    def helmet_shot(self, bit):
        """Stage 2 [0x01024f34]: a helmet lights its letter (leff 141, or 142 when already lit); all three
        spot the next needed shot (leff 143). The letters' speech calls are in a ROM table not read here."""
        os_ = self.os
        if not bit & HELMET_BITS:
            return bit
        if not self.helmets & bit:
            self.helmets |= bit
            os_.leff_start(141)
        else:
            os_.leff_start(142)
        if self.helmets & HELMET_BITS == HELMET_BITS:
            self.helmets = 0
            os_.leff_start(143, lamp="rom_group_50")
            return self.next_needed(2) or bit
        return bit

    def next_needed(self, k):
        """The stage's spot function: the first needed shot in table order (as a bit)."""
        return next((1 << shot for shot in STAGES[k] if self.needed & (1 << shot)), 0)

    def award(self, k, quiet):
        """(k+1) x 100,000, a tenth when spotted quietly; deff 116+k, or show task 0xa1 when quiet."""
        os_ = self.os
        points = os_.score_add((k + 1) * (10000 if quiet else 100000))
        self.total += points
        done = not self.needed
        length = STAGE_DONE_SECONDS if done else None
        if quiet:
            os_.show(0xa1, 116 + k, value=points, done=done, run_seconds=length)
        else:
            os_.deff_start(116 + k, value=points, done=done, run_seconds=length)

    def complete(self):
        """sos_complete [0x01026430]: flag 0x36, SOS ends, deff 125."""
        os_ = self.os
        os_.flag_set(0x36)
        if self.running():
            os_.flag_clear(0x34)
            self.show_total()
            os_.request_refresh()

    def show_total(self):
        """FUN_01026724, task 0x56: deff 125 after completion, else deff 126 TOTAL (not when tilted)."""
        os_ = self.os
        if os_.state & 0x310:
            return 0
        deff = 125 if os_.flag(0x36) else 126
        os_.deff_start(deff, total=self.total)
        info = os_.display.media.get(deff)
        return round(info.seconds / TICK) if info else 0

    # ------------------------------------------------------------------ Flynn's Arcade ADV. SOS

    def arcade_sos_weight(self, default):
        return default + 1000 if self.running() else 0

    def arcade_sos(self):
        """sos_spot_current_stage [0x010266c0]: the stage's next shot, quietly."""
        if not self.running():
            return False
        shot = self.next_needed(self.stage)
        return self.simulation_shot(shot.bit_length() - 1 if shot else 0, 1)

    # ------------------------------------------------------------------ end

    def ball_end(self):
        """Event 0x1d [0x01026784]: SOS stops and shows its total."""
        self.end_wait = 0
        self.skip_queue = []
        self.skip_showing = False
        if self.running():
            self.os.flag_clear(0x34)
            self.end_wait = self.show_total()
            self.os.request_refresh()

    def ball_end_wait(self):
        return self.end_wait or None

    def tilt_start(self):
        """Event 0x66 [0x01026794]: a running SOS pays every skip bonus not paid yet."""
        if not self.running():
            return
        for k in range(9):
            if self.skip_value[k] and not self.skip_paid[k]:
                self.total += self.os.score_add(self.skip_value[k])
                self.skip_paid[k] = 1


feature = SeaOfSimulation
