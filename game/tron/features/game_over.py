"""Game over: match, game-over music and the return to attract (game_flow.md 5.5 and 6.2)."""
import random

from tron.features import Feature

MATCH_REVEAL = 258       # ticks from deff 38 to the match award (traces/game_flow.jsonl 4.19 s)
ATTRACT_DELAY = 482      # ticks from the match display to attract (7.84 s measured)


class GameOver(Feature):
    name = "match"

    def run(self, done):
        os_ = self.os
        os_.deff_start(38)
        number = random.randrange(0, 100, 10)
        forced = os_.forced.get("match")
        matched = 0
        if os_.adj_value(30) < 11:
            matched = sum(1 for p in self.machine.game.player_list if p.score % 100 == number)
        if forced:
            matched = forced.pop(0)
        if matched:
            os_.after(MATCH_REVEAL, lambda: self._award(matched))
        os_.after(ATTRACT_DELAY, lambda: self._attract(done))

    def _award(self, matched):
        """Match award (adj 29): 0 = credit with knocker 0x019."""
        os_ = self.os
        for _ in range(matched):
            os_.audit(0x0f)
            if os_.adj_value(29) == 0:
                os_.sound(0x019)
                self.machine.events.post("tron_award_credit")

    def _attract(self, done):
        os_ = self.os
        os_.hook("attract_start")                 # event 0x08: deff 1, leff 1, attract tube rule
        # task 0x45 [0x0100f29c], one tick later: game-over music 0x01d with leff 133
        os_.after(1, lambda: (os_.sound(0x01d), os_.leff_start(133)))
        done()


feature = GameOver
