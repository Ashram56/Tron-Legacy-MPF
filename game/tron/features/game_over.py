"""Game over: match, game-over music and the return to attract (game_flow.md 5.5 and 6.2)."""
import random

from tron.features import Feature

ATTRACT_DELAY = 482      # ticks from the match display to attract (7.84 s measured)


class GameOver(Feature):
    name = "match"

    def run(self, done):
        os_ = self.os
        os_.deff_start(38)
        os_.sound(0x01c)
        number = random.randrange(0, 100, 10)
        if os_.adj_value(30) < 11:
            for player in self.machine.game.player_list:
                if player.score % 100 == number:
                    os_.audit(0x0f)
                    os_.after(260, lambda: os_.sound(0x019))
        os_.after(ATTRACT_DELAY, lambda: self._attract(done))

    def _attract(self, done):
        os_ = self.os
        os_.sound(0x01d)
        os_.leff_start(133)
        done()


feature = GameOver
