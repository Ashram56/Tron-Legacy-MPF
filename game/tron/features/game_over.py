"""Game over: match, game-over music and the return to attract (game_flow.md 5.5 and 6.2)."""
from tron.features import Feature
from tron.os_layer import TICK

MATCH_REVEAL = 258       # ticks from deff 38 to the match award (traces/game_flow.jsonl 4.19 s)
MATCH_FRAMES = 65 * 4    # deff 38 [0x0102cdd8]: 65 frames of deff_frame_sleep(4) ...
MATCH_HIT_FRAMES = 24 * 4   # ... 24 more of FUN_000279c4(4) when a player matched ...
MATCH_END_SLEEP = 0x7d   # ... and task_sleep(0x7d) at the end; match [0x0001b660] returns when the deff ends
MUSIC_TICKS = 0x271      # leff 133 runs 625 ticks with the game-over music [0x0100f29c]
SPEECH_WAIT_MAX = 0x1d4  # FUN_0100ff08: wait for the speech to end, at most 468 ticks
SPEECH_GAP = 0x2e        # then 46 ticks before the music


class GameOver(Feature):
    name = "match"

    def __init__(self, os_):
        super().__init__(os_)
        self.countdown = None    # attr_gameover_countdown 0x3afec: game overs left until the speech (RAM, per power-up)

    def run(self, done):
        os_ = self.os
        if os_.hook("slammed"):
            # slam_reset_task [0x00023e18] ends in the halt loop 0x10ce8: the machine resets and boots again: the version
            # screen (deff 5) first, deff 1 / leff 1 BOOT_SECONDS later like at power-up (features/attract.py)
            from tron.features.attract import BOOT_SECONDS
            pages = os_.features_by_name.get("attract_pages")
            if pages:
                pages.boot = True
            os_.machine.clock.schedule_once(lambda dt=None: None if os_.game else os_.hook("attract_start"), BOOT_SECONDS)
            done()
            return
        forced = os_.forced.get("match")
        if os_.adj_value(30) == 11 and not forced:     # match [0x0001b660]: MATCH PERCENTAGE OFF, no match
            self._attract(done)                        # at all (no deff 38): straight to the attract mode
            return
        number = os_.random.randrange(0, 100, 10)
        matched = 0
        # adj 30 MATCH PERCENTAGE: the number can match only while the machine's match rate (TOTAL MATCHES
        # 0x0f x 100 / games 0x11, persistent audits) is below adj 30; otherwise the ROM moves on by tens
        # to a number no player has.
        audits = os_.audits
        rate = audits[0x0f] * 100 // audits[0x11] if audits[0x11] else 0
        ends = [p.score % 100 for p in self.machine.game.player_list]
        if rate < os_.adj_value(30):
            matched = ends.count(number)
        elif not forced:
            for _ in range(10):
                number = (number + 10) % 100
                if number not in ends:
                    break
        winners = sum(1 << (i + 1) for i, e in enumerate(ends) if e == number)     # task + 0x30: bit p set when player p matches (0x0102cdd8)
        if forced:
            matched = forced.pop(0)
            winners = winners or (2 if matched else 0)
        os_.deff_start(38, number=number, number_again=number, winners=winners)   # deff 38 prints the number (task + 0x34)
        if matched:
            os_.after(MATCH_REVEAL, lambda: self._award(matched))
        os_.after(MATCH_FRAMES + (MATCH_HIT_FRAMES if matched else 0) + MATCH_END_SLEEP, lambda: self._attract(done))

    def _award(self, matched):
        """Match award (adj 29): 0 = credit with knocker 0x019."""
        os_ = self.os
        for _ in range(matched):
            os_.audit(0x0f)
            if os_.adj_value(29) == 0:
                os_.award_credit()                # FUN_00004cf0, then the knocker FUN_0001b370
                os_.knock()
            else:
                self.machine.events.post("tron_award_ticket" if os_.adj_value(29) == 1 else "tron_award_token")

    def _attract(self, done):
        os_ = self.os
        os_.hook("attract_start")                 # event 0x08: deff 1, leff 1, attract tube rule
        os_.after(1, self._music_task)            # task 0x45 [0x0100f29c], one tick later
        done()

    def _music_task(self):
        """game_over_music_task [0x0100f29c]: speech 0x01e when no game can be started on the credits left,
        else on every 4th-6th game over (countdown = random(3) + 4, set on the first run and after each
        speech); the speech is waited for (FUN_0100ff08, max 468 ticks) plus 46 ticks; then music 0x01d
        with leff 133 for 625 ticks."""
        os_ = self.os
        if not os_.state & 0x10:                  # no game over any more (a game started in the tick)
            return
        if self.countdown is None:
            self.countdown = os_.random.randrange(3) + 4
        gap = 0
        if not os_.credit_model.can_start():
            speech = True
        else:
            self.countdown -= 1
            speech = self.countdown < 1
        if speech:
            self.countdown = os_.random.randrange(3) + 4
            end = os_.sound(0x01e)
            gap = SPEECH_GAP + (min(SPEECH_WAIT_MAX, int((end - os_.now) / TICK + 0.999)) if end else 0)
        os_.after(gap, self._music)

    def _music(self):
        os_ = self.os
        os_.sound(0x01d)
        os_.leff_start(133)
        os_.after(MUSIC_TICKS, lambda: os_.leff_stop(133))


feature = GameOver
