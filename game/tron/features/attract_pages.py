"""The pages of the attract display, deff 1 [0x01034364] (attract_and_service.md 5.1), shown as text on the
generic slide game/slides/text_page.tscn above deff 1. The pages log no rules events.

Order, one page every 2.016 s (126 ticks at 16.0 ms): GAME OVER (first pass only), the credit text
(FUN_00004ff4), the last game's score of each of its players, the high-score table entries (0x01000564,
GRAND CHAMPION and HIGH SCORE #1-#4, while adj 48 allows high scores), the Tron logo (3.76 s), the
animation (3.98 s), the Stern web address, the operator's custom message (adj 2 CUSTOM MESSAGE = ON and a message
set; its place in the order is inferred), the date and time; then again from the credit page. Without a
last game the attract capture (media/dmd/deff_001_attract_score_display) shows "REPLAY AT" and the replay
level there. The right flipper button shows the next page at once, the left one the previous.
"""
from tron.features import Feature

ORDER = 7
PAGE_SECONDS = 2.016
LOGO_SECONDS, ANIMATION_SECONDS = 3.76, 3.98
PRIORITY = 2                     # just above deff 1 (priority 1)


class AttractPages(Feature):
    name = "attract_pages"
    HOOKS = ("attract_start",)

    def __init__(self, os_):
        super().__init__(os_)
        self.handle = None
        self.pages = []
        self.index = 0
        self.last_scores = []
        ev = self.machine.events
        ev.add_handler("game_starting", self.stop, priority=2000)
        ev.add_handler("tron_service_entered", self.stop)
        ev.add_handler("game_ending", self._game_ending, priority=2000)
        ev.add_handler("init_phase_5", self._power_up)
        sc = self.machine.switch_controller
        sc.add_switch_handler("s_right_flipper", lambda: self.step(1), state=1)
        sc.add_switch_handler("s_left_flipper", lambda: self.step(-1), state=1)

    def _power_up(self, **kwargs):
        """Power-up: deff 1 with the attract feature (attract.BOOT_SECONDS)."""
        from tron.features.attract import BOOT_SECONDS   # noqa: E402
        self.machine.clock.schedule_once(lambda dt=None: None if self.os.game else self.attract_start(),
                                         BOOT_SECONDS)

    def _game_ending(self, **kwargs):
        self.last_scores = [p.score for p in self.machine.game.player_list] if self.machine.game else []

    def page_list(self, first_pass):
        os_ = self.os
        pages = [("GAME OVER", ["GAME OVER"], PAGE_SECONDS)] if first_pass else []
        pages.append(("CREDITS", lambda: [os_.credit_model.text()], PAGE_SECONDS))
        if self.last_scores:
            for n, score in enumerate(self.last_scores, 1):
                pages.append(("PLAYER {}".format(n), ["PLAYER {}".format(n), "{:,}".format(score)], PAGE_SECONDS))
        elif os_.replay_level(1):
            pages.append(("REPLAY", ["REPLAY AT", "{:,}".format(os_.replay_level(1))], PAGE_SECONDS))
        hs = os_.features_by_name.get("high_scores")
        for title, name, score in (hs.table() if hs else []):
            pages.append((title, [title, name, "{:,}".format(score)], PAGE_SECONDS))
        pages.append(("LOGO", [], LOGO_SECONDS))
        pages.append(("ANIMATION", [], ANIMATION_SECONDS))
        pages.append(("URL", ["LEARN MORE ABOUT", "STERN PINBALL AT", "WWW.STERNPINBALL.COM"], PAGE_SECONDS))
        text = self.machine.variables.get_machine_var("custom_message_text")
        if os_.adj[2] == 1 and text:                   # adj 2 CUSTOM MESSAGE ON with a message [0x010002dc]
            pages.append(("CUSTOM MESSAGE", [text], PAGE_SECONDS))
        from tron.service import clock_now, clock_text   # noqa: E402
        day, clock = clock_text(self.machine, clock_now(self.machine), os_.adj[3])
        pages.append(("CLOCK", [day, clock], PAGE_SECONDS))
        return pages

    def attract_start(self):
        self.stop()
        self.pages = self.page_list(True)
        self.index = 0
        self.show()

    def stop(self, **kwargs):
        if self.handle:
            self.machine.clock.unschedule(self.handle)
            self.handle = None
        if self.pages:
            self.pages = []
            self.os.media.text_hide("text_page")

    def show(self):
        name, lines, seconds = self.pages[self.index]
        lines = lines() if callable(lines) else lines
        self.machine.events.post("tron_attract_page", page=name, lines=lines)
        self.os.media.text_show("text_page", lines, PRIORITY)
        if self.handle:
            self.machine.clock.unschedule(self.handle)
        self.handle = self.machine.clock.schedule_once(lambda dt=None: self.step(1), seconds)

    def step(self, n):
        if not self.pages or self.os.game or self.os.in_service:
            return
        self.index += n
        if self.index >= len(self.pages):          # the list wraps to the credit page (no GAME OVER)
            self.pages = self.page_list(False)
            self.index = 0
        elif self.index < 0:
            self.index = len(self.pages) - 1
        self.show()


feature = AttractPages
