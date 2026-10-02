"""Quorra Multiball (assets/rules/modes/quorra_multiball.md).

Five left inner loops (first left spinner pulse) light Quorra Multiball at the VUK; each scores 10,000.
The VUK starts a 2-ball multiball worth 200,000. During it the left inner loop scores the Jackpot
(350,000 + 25,000 per earlier Quorra Multiball and per Jackpot, max 500,000), which also raises the
Super Jackpot on the right inner loop (1,000,000 at start). Three Recognizer 3-bank hits add a ball (up to
2 per multiball). The mode ends when fewer than 2 balls are left; an end window of 437 ticks keeps the
shots scoring, then the total is shown (deff 70).

"All Jackpots Doubled" (the double window, tasks 0x5c / 0x5d) is gated by quorra_double_armed, which
1.74 never sets, so it is not built: Jackpot and Super are always x1.

Hooks: quorra_to_light(mask) (progress), quorra_super_jackpots(mask) (awards: 4 Jackpot, 8 Super, 0x10
Recognizer bank), quorra_vuk(all_lit, all_collected), quorra_mb_resume_in_end_window(),
arcade_quorra_weight / arcade_quorra.
"""
from tron.features import Feature
from tron.os_layer import TICK

ORDER = 61
VUK_BIT = 2
ITEM = 4                                  # QUORRA in the wizard items
LOOPS_TO_LIGHT = 5
JACKPOT_MAX = 500000
SUPER_BASE, SUPER_STEP, SUPER_RESET_MAX = 1000000, 250000, 2500000
END_WINDOW = (312, 125)                   # tasks 0xb3 then 0xb4
SAVE_TICKS, SAVE_GRACE = 625, 125
# deff run_seconds - hold start; the intro deff 64 (deff_hold_frames(1, 0x20)) holds one tick only: its
# show ends 3.84 s after it starts (traces/quorra_multiball 24.18 -> 28.02)
HOLD_TAILS = {64: TICK, 67: 2.053 - 1.50, 68: 3.844 - 2.78, 69: 4.377 - 2.87}
AAB_SAVE_TICKS, AAB_SAVE_GRACE = 312, 187


class Quorra(Feature):
    name = "quorra"
    HOOKS = ("player_first_ball", "quorra_to_light", "quorra_super_jackpots", "quorra_vuk",
             "quorra_mb_resume_in_end_window", "multiball_end", "ball_end", "ball_end_wait",
             "arcade_quorra_weight", "arcade_quorra")

    def __init__(self, os_):
        super().__init__(os_)
        self.jackpot = self.super = self.total = 0
        self.mb_supers = self.aab_hits = self.aab_count = 0
        # rules [0x0101fb1c]: background deff 65 + music 0x066 (priority 7), leff 68 + tube show 35,
        # leff 69 while a ball can be added
        os_.deff_rule(self.rule_active, 65, 0x066, 7)
        os_.lamp_rule(self.rule_active, leff=68, tube=35, order=0x0101f0ac)
        os_.lamp_rule(self.add_ball_available, leff=69, order=0x0101ce90)
        os_.lamp_update(self.advance_lamp)
        # deff_hold_frames(n, 0x20): the award deffs drop to priority 0x20 before they end, so the next
        # award replaces them (measured in traces/quorra_multiball: the hold starts 1.50 s into deff 67,
        # 2.78 s into deff 68 and 2.87 s into deff 69, where the deff rules run again)
        for deff, tail in HOLD_TAILS.items():
            os_.display.set_hold_tail(deff, tail)
        for addr, key in ((0x21117ac, "quorra_progress"), (0x21117b0, "quorra_starts"),
                          (0x21117b4, "quorra_supers")):
            os_.register_poke(addr, (lambda k: lambda p, v: setattr(os_.players[p], k, v))(key))

    def player_first_ball(self):
        """event 0x26 [0x0101cd7c] (the VUK lit byte is cleared by the scoop table's own reset)."""
        pd = self.pd
        pd.quorra_progress = pd.quorra_starts = pd.quorra_supers = 0

    # ------------------------------------------------------------------ state tests

    def running(self):
        return self.os.flag(0x29)

    def running_or_window(self):
        """[0x0101ce30]: running or in the first part of the end window (task 0xb3)."""
        return self.running() or self.os.task_running(0xb3)

    def scoring_active(self):
        """quorra_mb_scoring_active [0x0101ce60]."""
        return self.running_or_window() or self.os.task_running(0xb4)

    def add_ball_available(self):
        """[0x0101ce90]."""
        return self.running_or_window() and self.aab_count < 2

    def rule_active(self):
        """quorra_mb_rule_active [0x0101f0ac]: running, but not while the intro deff 64 waits."""
        return self.running() and not self.os.display.queued(0x8d)

    def wizard_takes_vuk(self, ready):
        os_ = self.os
        return bool(ready) and not os_.any_multiball() and not os_.task_running(0xad) and not os_.flag(0x34)

    def advance_lamp(self):
        """quorra_advance_lamp_rule [0x0101f85c] (lamp rule): ADVANCE QUORRA (60) flashes while Quorra
        could start but is not lit at the scoop yet."""
        os_ = self.os
        on = (self.can_start(bool(os_.hook("items_all_lit")), bool(os_.hook("items_all_collected")))
              and not os_.hook("vuk_lit_test", VUK_BIT))
        os_.lamps.lamp_set(60, 2 if on else 0)

    def can_start(self, all_lit, all_collected):
        """quorra_can_start [0x0101f2f8]."""
        os_ = self.os
        return not (self.running() or os_.flag(0x24) or os_.task_running(0xad)
                    or self.wizard_takes_vuk(all_lit) or os_.flag(0x34)
                    or self.wizard_takes_vuk(all_collected) or os_.flag(0x37) or os_.flag(0x27))

    def progress_allowed(self):
        """quorra_progress_allowed [0x0101f384]."""
        os_ = self.os
        return not (self.scoring_active() or os_.flag(0x24) or os_.task_running(0xad) or os_.flag(0x34)
                    or os_.flag(0x37) or os_.hook("vuk_lit_test", VUK_BIT)
                    or self.pd.quorra_progress >= LOOPS_TO_LIGHT or os_.flag(0x27))

    # ------------------------------------------------------------------ progress [0x0101f410]

    def quorra_to_light(self, mask, quiet=False):
        os_, pd = self.os, self.pd
        if not self.progress_allowed() or not mask & 4:
            return False
        scored = os_.score_add(10000)
        pd.quorra_progress = min(pd.quorra_progress + 1, LOOPS_TO_LIGHT)
        if pd.quorra_progress < LOOPS_TO_LIGHT:
            if not quiet:
                os_.deff_start(62, points=scored, left=LOOPS_TO_LIGHT - pd.quorra_progress)
        elif os_.hook("vuk_lit_add", VUK_BIT):
            pd.quorra_progress = 0
            if not quiet:
                os_.deff_start(63, points=scored)
        os_.request_refresh()
        return True

    # ------------------------------------------------------------------ start at the VUK [0x0101f688]

    def quorra_vuk(self, all_lit=False, all_collected=False):
        """While running or in the end window the VUK only arms the (unreachable) double window."""
        os_ = self.os
        if self.scoring_active():
            return False
        if os_.hook("vuk_lit_test", VUK_BIT) and self.mb_start(all_lit, all_collected):
            os_.hook("vuk_lit_take", VUK_BIT)
            return True
        return False

    def mb_start(self, all_lit, all_collected):
        """quorra_mb_start [0x0101f55c]."""
        os_, pd = self.os, self.pd
        if not self.can_start(all_lit, all_collected):
            return False
        in_play = os_.rom_balls_in_play()
        if not os_.multiball_start(in_play + 1 if in_play else 2, SAVE_TICKS, SAVE_GRACE):
            return False
        os_.flag_set(0x29)
        self.jackpot = min(350000 + 25000 * pd.quorra_starts, JACKPOT_MAX)
        pd.quorra_starts = min(pd.quorra_starts + 1, 0xff)
        os_.hook("item_light", ITEM)
        self.aab_hits = self.aab_count = self.mb_supers = 0
        self.super_reset()
        os_.audit(0x47)
        self.total = os_.score_add(200000)
        os_.show(0x8d, 64, on_start=os_.request_refresh)     # task 0x8d queues the intro
        os_.hook("lc_mb_resume_in_end_window")
        os_.display.raise_rule(65)
        os_.request_refresh()
        return True

    def super_reset(self):
        """[0x0101d06c]."""
        self.super = min(SUPER_BASE + SUPER_STEP * self.mb_supers, SUPER_RESET_MAX)

    # ------------------------------------------------------------------ awards [0x0101d0b4]

    def quorra_super_jackpots(self, mask):
        os_ = self.os
        if not self.scoring_active():
            return False
        if mask & 4:
            scored = os_.score_add(self.jackpot)
            self.total += scored
            os_.deff_start(68, points=scored, double=1)
            os_.audit(0x48)
            self.super += scored
            self.jackpot = min(self.jackpot + 25000, JACKPOT_MAX)
        elif mask & 8:
            scored = os_.score_add(self.super)
            self.total += scored
            os_.deff_start(69, points=scored, double=1)
            self.pd.quorra_supers = min(self.pd.quorra_supers + 1, 0xff)
            self.mb_supers = (self.mb_supers + 1) & 0xff
            os_.hook("item_collect", ITEM)
            os_.audit(0x49)
            self.super_reset()
        elif mask & 0x10 and self.aab_count < 2:
            self.recognizer_hit()
        else:
            return False
        os_.request_refresh()
        return True

    def recognizer_hit(self):
        """Recognizer 3-bank: 3 hits add a ball (multiball_add_balls(1, 0, 312, 187))."""
        os_ = self.os
        self.aab_hits += 1
        if self.aab_hits < 3:
            self.total += os_.score_add(50000)
            os_.deff_start(66, more=3 - self.aab_hits)
            return
        self.aab_hits = 0
        self.total += os_.score_add(500000)
        if os_.multiball_start(os_.rom_balls_in_play() + 1, AAB_SAVE_TICKS, AAB_SAVE_GRACE):
            self.aab_count += 1
            os_.deff_start(67)
            self.quorra_mb_resume_in_end_window()
            os_.hook("lc_mb_resume_in_end_window")

    # ------------------------------------------------------------------ end

    def multiball_end(self):
        """quorra_mb_end_to_one_ball [0x0101f798]."""
        os_ = self.os
        if not self.running():
            return
        os_.flag_clear(0x29)
        os_.task_start(0xb3, END_WINDOW[0], self.end_window_b4)
        os_.request_refresh()

    def end_window_b4(self):
        self.os.request_refresh()
        self.os.task_start(0xb4, END_WINDOW[1], self.end_window_over)

    def end_window_over(self):
        self.os.request_refresh()
        self.show_total()

    def quorra_mb_resume_in_end_window(self):
        """[0x0101f7e8]: Light Cycle start or a ball added during the end window."""
        os_ = self.os
        if not (os_.task_running(0xb3) or os_.task_running(0xb4)):
            return False
        os_.task_kill(0xb3)
        os_.task_kill(0xb4)
        os_.flag_set(0x29)
        os_.hook("dmb_cancel_restart_window")
        os_.request_refresh()
        return True

    def show_total(self):
        """quorra_show_total [0x0101f714]: task 0x50 shows deff 70 (not tilted / game over)."""
        os_ = self.os
        if os_.state & 0x310 or not self.total:
            return
        os_.deff_start(70, total=self.total)
        info = os_.display.media.get(70)
        os_.task_start(0x50, round(info.seconds / TICK) if info else 0)

    def ball_end(self):
        """quorra_end_of_ball [0x0101f82c]."""
        os_ = self.os
        if self.scoring_active():
            os_.flag_clear(0x29)
            os_.task_kill(0xb3)
            os_.task_kill(0xb4)
            self.show_total()

    def ball_end_wait(self):
        return self.os.task_ticks_left(0x50) or None

    # ------------------------------------------------------------------ Flynn's Arcade

    def arcade_quorra_weight(self, default):
        """[0x0100e0a0]."""
        return default if self.progress_allowed() else 0

    def arcade_quorra(self):
        """ADV. QUORRA [0x0100e0c4]: one quiet left inner loop."""
        return self.quorra_to_light(4, quiet=True)


feature = Quorra
