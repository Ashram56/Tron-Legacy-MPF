"""Find Flynn and the nine wizard items (assets/rules/modes/find_flynn_and_items.md).

Items: 0 FLYNN, 1 GEM, 2 CLU, 3 ZUSE, 4 QUORRA, 5 DISC, 6 LIGHT CYCLE, 7 RECOGNIZER, 8 TRON.
pd.items[i] = [times lit, times collected] (also read by the bonus). Other features use the hooks
item_light(i), item_collect(i), items_all_lit(), items_all_collected(), items_clear(lit_only).
"""
from tron.features import Feature

ORDER = 15
FLYNN = 0
POSITIONS = 6          # 0 left orbit, 1 left ramp, 2 left inner loop, 3 right inner loop, 4 right ramp, 5 right orbit


class FindFlynn(Feature):
    name = "find_flynn"
    HOOKS = ("player_first_ball", "find_flynn_started", "find_flynn_completed", "ball_end", "tilt",
             "item_light", "item_collect", "items_all_lit", "items_all_collected", "items_clear")

    def __init__(self, os_):
        super().__init__(os_)
        self.pos = self.next = self.prev = 0
        self.direction = 1
        os_.lamp_rule(lambda: os_.task_running(0xd1), leff=157, tube=14, order=0x0100d5b4)
        for i in range(9):
            os_.register_poke(0x2111694 + 0x10 * i, (lambda i_: lambda p, v: self._poke_item(p, i_, v))(i), stride=4)
            os_.register_poke(0x2111695 + 0x10 * i, (lambda i_: lambda p, v: self._poke_item(p, i_, v << 8, 1))(i),
                              stride=4)

    def _poke_item(self, p, i, value, byte=None):
        """u32 item_stats: byte 0 = times lit, byte 1 = times collected (a 1-byte poke sets one byte)."""
        item = self.os.players[p].items[i]
        if byte == 1:
            item[1] = (value >> 8) & 0xff
        elif value > 0xff:
            item[0], item[1] = value & 0xff, (value >> 8) & 0xff
        else:
            item[0] = value & 0xff

    def player_first_ball(self):
        pd = self.pd
        pd.ff_started = 0
        pd.ff_completed = 0
        if not hasattr(pd, "items"):
            pd.items = [[0, 0] for _ in range(9)]

    # ------------------------------------------------------------------ items [0x01016188]

    def item_light(self, i):
        self.pd.items[i][0] = min(self.pd.items[i][0] + 1, 0xff)
        self.os.audit(0x68 + 2 * i)
        self.os.request_refresh()

    def item_collect(self, i):
        self.pd.items[i][1] = min(self.pd.items[i][1] + 1, 0xff)
        self.os.audit(0x69 + 2 * i)
        self.os.request_refresh()

    def items_all_lit(self):
        return all(lit for lit, _ in self.pd.items)

    def items_all_collected(self):
        return all(col for _, col in self.pd.items)

    def items_clear(self, lit_only=True):
        """SOS start clears the lit bytes (FUN_010160c8(1)); Portal start clears both (FUN_01016164)."""
        for item in self.pd.items:
            item[0] = 0
            if not lit_only:
                item[1] = 0

    # ------------------------------------------------------------------ Find Flynn

    def find_flynn_started(self):
        """sw12 [0x0100d698]."""
        os_ = self.os
        if (os_.task_running(0xd1) or os_.flag(0x34) or os_.hook("portal_running")
                or os_.any_multiball()):
            return
        self.pos = 0
        self.prev = self.next = 0
        self.direction = 1
        self.pd.ff_started += 1
        self.item_light(FLYNN)
        os_.audit(0x87)
        os_.deff_start(136)
        self._rove_wait()

    def _rove_wait(self):
        self.os.task_start(0xd1, 125, self._rove_choose)

    def _rove_choose(self):
        """Bounce back and forth over 0..5."""
        nxt = self.pos + self.direction
        if nxt < 0 or nxt >= POSITIONS:
            self.direction = -self.direction
            nxt = self.pos + self.direction
        self.next = nxt
        self.os.task_start(0xd1, 15, self._rove_move)

    def _rove_move(self):
        self.prev, self.pos = self.pos, self.next
        self.os.task_start(0xd1, 31, self._rove_wait)

    def find_flynn_completed(self, shot):
        """on_find_flynn_completed [0x0100d79c]: the shot at cur, next or prev finds Flynn."""
        os_ = self.os
        if not os_.task_running(0xd1):
            return False
        if shot not in (self.pos, self.next, self.prev):
            return False
        pd = self.pd
        value = min(250000 + 25000 * pd.ff_completed, 750000)
        os_.score_add(value)
        pd.ff_completed += 1
        self.item_collect(FLYNN)
        os_.audit(0x88)
        os_.task_kill(0xd1)
        os_.deff_start(137, value=value)
        return True

    def ball_end(self):
        self.os.task_kill(0xd1)

    def tilt(self):
        pass


feature = FindFlynn
