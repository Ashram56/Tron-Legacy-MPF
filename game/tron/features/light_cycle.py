"""Light Cycle Multiball (assets/rules/modes/light_cycle_multiball.md).

Progress: six shots (bits 0x01 left orbit, 0x02 left ramp, 0x04 left inner loop, 0x08 right inner loop,
0x40 right ramp, 0x80 right orbit); 4 different ones light the VUK on the first Light Cycle of the game,
6 afterwards. The VUK starts a 2-ball multiball. Three award chains run during the multiball:
A (left ramp Jackpot -> Super on left orbit / left inner loop -> Double Super on right inner loop /
right ramp), B (right orbit Jackpot -> Super on right inner loop / right ramp) and C (right ramp, always a
Jackpot). The mode ends when fewer than 2 balls are left, then an end window lets lit shots score for
437 more ticks before the total (deff 90).

Hooks: light_cycle_target(mask) (progress), light_cycle_mb_shot(mask) (awards), light_cycle_vuk(all_lit,
all_collected) (start), lc_mb_resume_in_end_window(), arcade_light_cycle_weight / arcade_light_cycle.
"""
from tron.features import Feature
from tron.os_layer import TICK

ORDER = 60
VUK_BIT = 4
ITEM = 6                                  # LIGHT CYCLE in the wizard items
SHOT_ORDER = (0x01, 0x02, 0x04, 0x08, 0x40, 0x80)   # Flynn's Arcade "ADV." order [table 0x040d2978]
ALL_SHOTS = 0xcf
# shot bit -> LIGHT CYCLE insert (table 0x040d3134): L orbit, L ramp, L inner, R inner, R ramp, R orbit
PROGRESS_LAMPS = {0x01: 14, 0x02: 11, 0x04: 62, 0x08: 59, 0x40: 42, 0x80: 35}
# award level -> (points, deff, audit) [0x01018804]
AWARDS = {1: (350000, 87, 0x4b), 2: (750000, 88, 0x4c), 3: (1500000, 89, 0x4d)}
TIMER_TICKS = 315                         # 312 counted down by 7 every 7 ticks (task 0xba / 0xbc)
GRACE_TICKS = 125                         # task 0xbb / 0xbd: the old lit shots still score
END_WINDOW = (312, 125)                   # tasks 0xb8 then 0xb9 after the last-but-one ball drains
SAVE_TICKS, SAVE_GRACE = 625, 125


def popcount(value):
    return bin(value & 0xff).count("1")


class Chain:
    """One award chain: lit shots and level, the previous ones during the grace after a timeout."""

    def __init__(self, lit, timer_task):
        self.home = lit
        self.timer_task = timer_task
        self.reset()

    def reset(self):
        self.lit, self.level, self.prev, self.prev_level = self.home, 1, 0, 0


class LightCycle(Feature):
    name = "light_cycle"
    HOOKS = ("player_first_ball", "light_cycle_target", "light_cycle_mb_shot", "light_cycle_vuk",
             "lc_mb_resume_in_end_window", "multiball_end", "ball_end", "ball_end_wait",
             "arcade_light_cycle_weight", "arcade_light_cycle")

    def __init__(self, os_):
        super().__init__(os_)
        self.a = Chain(0x02, 0xba)
        self.b = Chain(0x80, 0xbc)
        self.c_lit = 0x40                 # chain C: right ramp Jackpot, never changes
        self.mb_super_points = 0
        self.total = 0
        # rules [0x0101b5b4]: background deff 86 + music 0x0c2 (priority 7), leff 94, tube show 54
        os_.deff_rule(self.rule_active, 86, 0x0c2, 7)
        os_.lamp_rule(self.rule_active, leff=94, tube=54, order=0x0101ac3c)
        os_.lamp_update(self.progress_lamps)
        for addr, key in ((0x2111744, "lc_remaining"), (0x2111754, "lc_collected"), (0x2111764, "lc_starts")):
            os_.register_poke(addr, (lambda k: lambda p, v: setattr(os_.players[p], k, v))(key))

    def player_first_ball(self):
        """event 0x26 [0x010181bc] (the VUK lit byte is cleared by the scoop table's own reset)."""
        pd = self.pd
        pd.lc_remaining, pd.lc_collected = ALL_SHOTS, 0
        pd.lc_starts = 0
        pd.lc_super_points = 0
        pd.lc_clip_level = 0

    # ------------------------------------------------------------------ state tests

    def running(self):
        return self.os.flag(0x2b)

    def scoring_active(self):
        """lc_mb_scoring_active [0x01018288]: running or in the end window."""
        return self.running() or self.os.task_running(0xb8) or self.os.task_running(0xb9)

    def rule_active(self):
        """lc_mb_rule_active [0x0101ac3c]: running, but not while the intro deff 85 waits in the queue."""
        return self.running() and not self.os.display.queued(0x92)

    def wizard_takes_vuk(self, ready):
        """FUN_010263b0 / portal_mb_can_start: Simulation / Portal would start at this VUK instead."""
        os_ = self.os
        return bool(ready) and not os_.any_multiball() and not os_.task_running(0xad) and not os_.flag(0x34)

    def progress_allowed(self):
        """lc_progress_allowed [0x0101860c]."""
        os_ = self.os
        return not (self.running() or os_.flag(0x24) or os_.task_running(0xad) or os_.flag(0x34)
                    or os_.flag(0x37) or os_.hook("vuk_lit_test", VUK_BIT) or os_.flag(0x27))

    def progress_lamps(self):
        """lc_progress_lamps_rule [0x0101b4fc] (lamp rule): while progress counts, the shots still to make
        flash; everything else is off."""
        allowed = self.progress_allowed()
        remaining = self.pd.get("lc_remaining", 0)
        for bit, lamp in PROGRESS_LAMPS.items():
            self.os.lamps.lamp_set(lamp, 2 if allowed and remaining & bit else 0)

    def can_start(self, all_lit, all_collected):
        """lc_can_start [0x0101b0dc]."""
        os_ = self.os
        return not (self.running() or os_.flag(0x24) or os_.task_running(0xad)
                    or self.wizard_takes_vuk(all_lit) or os_.flag(0x34)
                    or self.wizard_takes_vuk(all_collected) or os_.flag(0x37))

    # ------------------------------------------------------------------ progress [0x010186bc]

    def light_cycle_target(self, mask, quiet=False):
        pd = self.pd
        if not self.progress_allowed() or not pd.lc_remaining & mask:
            return False
        pd.lc_remaining &= ~mask
        pd.lc_collected |= mask
        needed = 6 if pd.lc_starts else 4
        made = popcount(pd.lc_collected)
        if made < needed:
            if not quiet:
                self.os.deff_start(83, more=needed - made, mask=mask)
        elif self.os.hook("vuk_lit_add", VUK_BIT):
            pd.lc_remaining, pd.lc_collected = ALL_SHOTS, 0
            if not quiet:
                self.os.deff_start(84)
        return True

    # ------------------------------------------------------------------ start at the VUK

    def light_cycle_vuk(self, all_lit=False, all_collected=False):
        """lc_vuk_start_if_lit [0x0101b368]."""
        if self.os.hook("vuk_lit_test", VUK_BIT) and self.mb_start(all_lit, all_collected):
            self.os.hook("vuk_lit_take", VUK_BIT)
            return True
        return False

    def mb_start(self, all_lit, all_collected):
        """lc_mb_start [0x0101b26c]."""
        os_, pd = self.os, self.pd
        if not self.can_start(all_lit, all_collected):
            return False
        in_play = os_.rom_balls_in_play()
        if not os_.multiball_start(in_play + 1 if in_play else 2, SAVE_TICKS, SAVE_GRACE):
            return False
        os_.flag_set(0x2b)
        pd.lc_starts = min(pd.lc_starts + 1, 0xff)
        os_.hook("item_light", ITEM)
        os_.audit(0x4a)
        self.total = os_.score_add(150000)
        self.a.reset()
        self.b.reset()
        for task in (0xba, 0xbb, 0xbc, 0xbd):
            os_.task_kill(task)
        self.mb_super_points = 0
        os_.show(0x92, 85, on_start=os_.request_refresh)     # task 0x92 queues the intro
        os_.hook("dmb_cancel_restart_window")
        os_.hook("quorra_mb_resume_in_end_window")
        os_.display.raise_rule(86)
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ awards [0x01018804]

    def light_cycle_mb_shot(self, mask):
        a, b = self.a, self.b
        if not self.scoring_active():
            return False
        if not (a.lit | a.prev | b.lit | b.prev | self.c_lit) & mask:
            return False
        if a.prev & mask:
            level = a.prev_level
            self.advance_a(mask, level)
        elif b.prev & mask:
            level = b.prev_level
            self.advance_b(level)
        elif a.lit & mask:
            level = a.level
            self.advance_a(mask, level)
        elif b.lit & mask:
            level = b.level
            self.advance_b(level)
        else:
            level = 1                     # chain C
        self.award(level)
        return True

    def award(self, level):
        os_, pd = self.os, self.pd
        points, deff, audit = AWARDS[level]
        os_.audit(audit)
        scored = os_.score_add(points)
        pd.lc_super_points = min(pd.lc_super_points + level - 1, 0xff)
        self.mb_super_points = (self.mb_super_points + level - 1) & 0xff
        if self.mb_super_points > 2:
            os_.hook("item_collect", ITEM)
        self.total += scored
        os_.deff_start(deff, points=scored)
        if level == 3:                    # art for the next Jackpots (deff 87 clip range)
            pd.lc_clip_level = pd.lc_clip_level + 1 if pd.lc_clip_level < 5 else 0

    def advance_a(self, mask, level):
        """lc_chain_a_advance [0x010183a0]."""
        a = self.a
        if level == 1:
            a.lit, a.level = 0x05, 2
            self.start_timer(a)
        elif level == 2 and not mask & 0x01 and mask & 0x04:
            a.lit, a.level = 0x48, 3
            self.start_timer(a)
        elif level in (2, 3):
            a.lit, a.level = 0x02, 1
            self.kill_timer(a)

    def advance_b(self, level):
        """lc_chain_b_advance [0x01018544]."""
        b = self.b
        if level == 1:
            b.lit, b.level = 0x48, 2
            self.start_timer(b)
        else:
            b.lit, b.level = 0x80, 1
            self.kill_timer(b)

    def start_timer(self, chain):
        """task_recreate(0xba / 0xbc): 315 ticks, then the chain goes home and the old shots get a grace."""
        self.kill_timer(chain)
        self.os.task_start(chain.timer_task, TIMER_TICKS, lambda: self.timeout(chain))

    def kill_timer(self, chain):
        if self.os.task_kill(chain.timer_task):
            chain.prev, chain.prev_level = 0, 0      # the task's exit handler (grace clear)

    def timeout(self, chain):
        chain.prev, chain.prev_level = chain.lit, chain.level
        chain.lit, chain.level = chain.home, 1

        def grace_over():
            chain.prev, chain.prev_level = 0, 0
        self.os.task_start(chain.timer_task + 1, GRACE_TICKS, grace_over)

    # ------------------------------------------------------------------ end

    def multiball_end(self):
        """lc_mb_end_to_one_ball [0x0101b444]: flag off, end window (tasks 0xb8 then 0xb9)."""
        os_ = self.os
        if not self.running():
            return
        os_.flag_clear(0x2b)
        os_.task_start(0xb8, END_WINDOW[0], self.end_window_b9)
        os_.request_refresh()

    def end_window_b9(self):
        self.os.request_refresh()
        self.os.task_start(0xb9, END_WINDOW[1], self.end_window_over)

    def end_window_over(self):
        self.os.request_refresh()
        self.show_total()

    def lc_mb_resume_in_end_window(self):
        """[0x0101b488] Quorra start or add-a-ball during the end window: the multiball runs on."""
        os_ = self.os
        if not (os_.task_running(0xb8) or os_.task_running(0xb9)):
            return False
        os_.task_kill(0xb8)
        os_.task_kill(0xb9)
        os_.flag_set(0x2b)
        os_.hook("dmb_cancel_restart_window")
        os_.request_refresh()
        return True

    def show_total(self):
        """lc_show_total [0x0101b3c0]: task 0x52 shows deff 90 with the total (not tilted / game over)."""
        os_ = self.os
        if os_.state & 0x310 or not self.total:
            return
        os_.deff_start(90, total=self.total)
        info = os_.display.media.get(90)
        os_.task_start(0x52, round(info.seconds / TICK) if info else 0)

    def ball_end(self):
        """lc_end_of_ball [0x0101b4cc]."""
        os_ = self.os
        for task in (0xba, 0xbb, 0xbc, 0xbd):
            os_.task_kill(task)
        if self.scoring_active():
            os_.flag_clear(0x2b)
            os_.task_kill(0xb8)
            os_.task_kill(0xb9)
            self.show_total()

    def ball_end_wait(self):
        """The total task 0x52 (flag 0x2000) holds the bonus until it ends."""
        return self.os.task_ticks_left(0x52) or None

    # ------------------------------------------------------------------ Flynn's Arcade

    def arcade_light_cycle_weight(self, default):
        """[0x0100e144]: the weight while a Light Cycle Multiball could start."""
        os_ = self.os
        return default if self.can_start(os_.hook("items_all_lit"), os_.hook("items_all_collected")) else 0

    def arcade_light_cycle(self):
        """ADV. LIGHT CYCLE [0x0100e184]: the first open progress shot, quietly."""
        for mask in SHOT_ORDER:
            if self.progress_allowed() and self.pd.lc_remaining & mask:
                if self.light_cycle_target(mask, quiet=True):
                    return True
        return False


feature = LightCycle
