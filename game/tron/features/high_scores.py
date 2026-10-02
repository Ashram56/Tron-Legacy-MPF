"""High-score table and initials entry (game_flow.md 5.5; OS code, not a rules mode).

Table [0x0001a554 / 0x0001a5c0]: one list of five entries, GRAND CHAMPION then HIGH SCORE #1-#4; an entry is a
name and a score, kept in MPF's data file "tron_high_scores" like the ROM's NVRAM records.
- Reset of an entry [0x0001a728]: the default name (3 initials, or the 10-letter name on adj 60) and the
  score of its adjustment (adj 49 GRAND CHAMPION SCORE, adj 50-53 HIGH SCORE #1-#4). RESET GRAND CHAMPION
  resets entry 0 (flag 1), RESET HIGH SCORES entries 1-4 (flag 2) [0x0001a9f4], RESET FACTORY SETTINGS
  all [0x0001ab18].
- adj 61 HSTD RESET COUNT [0x0001a4f0], at every game start while adj 48 = YES: a counter (reloaded from
  adj 61) counts the games down; at 0 the high scores (not the grand champion) are reset. 0 = OFF.
Entry at game over, before match [high_score_entry 0x0001ad4c], only on adj 48 ALLOW HIGH SCORES = YES; gf_state
0x40 is set meanwhile (START cannot start a game). For each entry in order, the best player of the game not
yet placed whose score beats the entry's [0x0001ab68, ties go to the earlier player]:
1. the player's initials (once per player and table; this game has one table): event 0x33, deff 31 "PLAYER n / ENTER INITIALS", events 0x34 / 0x35, deff 32 initials
   entry (below), event 0x36;
2. [0x0001abfc] the entry and the ones below move down one place and the player's name and score go in
   [0x0001a8c4]; the entry's award (adj 55-59 count, adj 54 kind: 0 credit with knocker, 1 ticket,
   2 token) and audit 0x10 HIGH SCORE AWARDS by the count; event 0x37, deff 33 (the entry, name and score,
   with the award), event 0x38.
Initials entry, deff 32 [0x010346e8], one frame per tick: the left / right flipper button picks the previous /
next letter (auto-repeat after 31 frames, then every 7; both buttons together do nothing), START takes it.
After the letters come three specials: BACK (deletes a letter), END and SPACE; once the name is full only
BACK and END can be picked, END at first. 3 initials (adj 60 = 0) or 10 letters. A 30 s countdown (63
frames a second) restarts on every button; at its end 15 more seconds are shown, then the entry ends with
what is entered (plus the letter under the cursor).
Not in the decompile (ROM data): the letter set (msg 0x34a / 0x34c), the default names of HIGH SCORE #3-#4
and the sounds of the entry (OS words 0x36f74/76/78, 0x39088/8a). The attract capture
(media/dmd/deff_001_attract_score_display) shows GRAND CHAMPION "G S", HIGH SCORE #1 "L R", #2 "J R".
"""
from tron.features import Feature

ORDER = 7
TITLES = ("GRAND CHAMPION", "HIGH SCORE #1", "HIGH SCORE #2", "HIGH SCORE #3", "HIGH SCORE #4")
SCORE_ADJ = (49, 50, 51, 52, 53)
AWARD_ADJ = (55, 56, 57, 58, 59)
FLAGS = (1, 2, 2, 2, 2)                  # reset groups: 1 grand champion, 2 high scores
DEFAULT_NAMES = ("G S", "L R", "J R", "???", "???")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SPECIALS = ("BACK", "END", "SPACE")
FRAME_TICKS = 1
SECOND_FRAMES = 63                       # 0x3e frames, then the second counts down
COUNTDOWN, LAST_COUNTDOWN = 30, 15
REPEAT_FIRST, REPEAT_NEXT = 31, 6        # held button: first repeat after 0x1f frames, then every 7
DEFF_SECONDS = {31: 1.841, 33: 2.353}    # run lengths (event_map.csv run_ms) when the media table has none
SOUNDS = {"left": None, "right": None, "select": None, "countdown": None, "enter_initials": None}


class Entry:
    """Initials entry, deff 32 [0x010346e8]."""

    def __init__(self, hs, player, done):
        self.hs, self.os, self.machine = hs, hs.os, hs.machine
        self.player = player
        self.done = done
        self.size = 10 if self.os.adj[60] == 1 else 3
        self.name = ""
        self.cursor = 0
        self.seconds, self.counting = COUNTDOWN, False
        self.frame_left = SECOND_FRAMES - 1
        self.select = False
        self.buttons = {"s_left_flipper": [False, False, 0], "s_right_flipper": [False, False, 0]}  # was, holding, repeat
        self.handler = self.machine.switch_controller.add_switch_handler("s_start_button", self._start, state=1)
        self.os.deff_start(32, hold=True, player=player, seconds=self.seconds)
        self.show()
        self.handle = self.os.after(FRAME_TICKS, self.frame)

    def letter(self):
        return LETTERS[self.cursor] if self.cursor < len(LETTERS) else SPECIALS[self.cursor - len(LETTERS)]

    def show(self):
        self.machine.events.post("tron_initials", player=self.player, name=self.name, letter=self.letter(),
                                 seconds=self.seconds if self.counting else None)
        self.os.media.text_show("text_page", ["PLAYER {} - ENTER INITIALS".format(self.player),
                                              self.name + ("_" if self.cursor >= len(LETTERS) else self.letter()),
                                              str(self.seconds) if self.counting else ""], 244)

    def _start(self):
        self.select = True

    def _sound(self, key):
        if SOUNDS[key] is not None:
            self.os.sound(SOUNDS[key])

    def _step(self, name):
        """One frame of a button: (stepped, holding)."""
        state = self.buttons[name]
        down = bool(self.machine.switches[name].state)
        stepped = False
        if down and not state[0]:
            state[1], state[2], stepped = True, REPEAT_FIRST, True
        elif state[1] and down:
            state[2] -= 1
            if state[2] == -1:
                state[2], stepped = REPEAT_NEXT, True
        else:
            state[1] = False
        state[0] = down
        return stepped, state[1]

    def move(self, step):
        n = len(LETTERS)
        if len(self.name) < self.size:
            self.cursor = (self.cursor + step) % (n + 3)
        else:
            self.cursor = n + 1 if self.cursor == n else n      # a full name: BACK <-> END
        self._sound("left" if step < 0 else "right")
        self.show()

    def frame(self):
        left, hold_l = self._step("s_left_flipper")
        right, hold_r = self._step("s_right_flipper")
        if not (hold_l and hold_r):
            if left and not right:
                self.move(-1)
            elif right and not left:
                self.move(1)
        if hold_l or hold_r or self.select:
            self.seconds = LAST_COUNTDOWN if self.counting else COUNTDOWN
            self.frame_left = SECOND_FRAMES - 1
        elif self.frame_left == 0:
            self.frame_left = SECOND_FRAMES - 1
            if self.seconds == 0:
                if self.counting:
                    if self.cursor < len(LETTERS) and len(self.name) < self.size:
                        self.name += self.letter()       # the letter under the cursor is part of the name
                    return self.finish()
                self.counting, self.seconds = True, LAST_COUNTDOWN
                self._sound("countdown")
            else:
                self.seconds -= 1
            self.show()
        else:
            self.frame_left -= 1
        if self.select:
            self.select = False
            if self.take():
                return self.finish()
        self.handle = self.os.after(FRAME_TICKS, self.frame)

    def take(self):
        """START: the letter or special under the cursor. Returns True at END."""
        n = len(LETTERS)
        if self.cursor >= n:
            special = SPECIALS[self.cursor - n]
            self._sound("select")
            if special == "END":
                return True
            if special == "BACK":
                self.name = self.name[:-1]
            elif len(self.name) < self.size:
                self.name += " "
        elif len(self.name) < self.size:
            self.name += LETTERS[self.cursor]
            self._sound("select")
        if len(self.name) >= self.size:
            self.cursor = n + 1                         # END
        self.show()
        return False

    def finish(self):
        self.machine.switch_controller.remove_switch_handler_by_key(self.handler)
        self.os.deff_stop(32)
        self.os.media.text_hide("text_page")
        self.done(self.name)


class HighScores(Feature):
    name = "high_scores"

    def __init__(self, os_):
        super().__init__(os_)
        self.store = self.machine.create_data_manager("tron_high_scores")
        data = self.store.get_data() or {}
        entries = data.get("entries") or []
        self.entries = [dict(e) for e in entries] if len(entries) == len(TITLES) else None
        self.count = data.get("reset_count")
        self.entry = None
        self._loaded()

    @property
    def adj(self):
        return self.os.adj

    def _loaded(self):
        if self.entries is None:                    # no valid record: every entry is reset [0x0001b0b4]
            self.entries = [None] * len(TITLES)
            self.reset(3)
        if self.count is None:
            self.count = self.adj[61]
            self.save()

    def save(self):
        self.store.save_all(data={"entries": [dict(e) for e in self.entries], "reset_count": self.count})

    def default_name(self, i):
        return DEFAULT_NAMES[i]

    def reset(self, mask):
        """FUN_0001a9f4: reset the entries of the flag mask (1 grand champion, 2 high scores)."""
        for i, flag in enumerate(FLAGS):
            if flag & mask:
                self.entries[i] = {"name": self.default_name(i), "score": self.adj[SCORE_ADJ[i]]}
        self.save()

    def reset_all(self):
        """FUN_0001ab18: every entry and the reset counter."""
        self.reset(3)
        self.count = self.adj[61]
        self.save()

    def game_started(self):
        """FUN_0001a4f0: adj 61 HSTD RESET COUNT, counted down by every game while adj 48 = YES."""
        if not self.adj[61] or self.adj[48] != 1:
            return
        if self.count < 1:
            self.reset(2)
            self.count = self.adj[61]
        else:
            self.count -= 1
        self.save()

    def table(self):
        """(title, name, score) of each entry, or [] when high scores are off (FUN_0001a6c8)."""
        if self.adj[48] != 1:
            return []
        return [(TITLES[i], e["name"], e["score"]) for i, e in enumerate(self.entries)]

    # ------------------------------------------------------------------ entry at game over

    def run(self, done):
        os_ = self.os
        if self.adj[48] != 1 or not os_.game:
            done()
            return
        os_.state |= 0x40
        self.scores = [p.score for p in self.machine.game.player_list]
        self.placed = [False] * len(self.scores)
        self.names = [None] * len(self.scores)
        self._done = done
        self._next(0)

    def best(self, i):
        """FUN_0001ab68: the best unplaced player beating entry i (ties: the earlier player), or 0."""
        best = 0
        for n, score in enumerate(self.scores, 1):
            if not self.placed[n - 1] and score > self.entries[i]["score"]:
                if not best or score > self.scores[best - 1]:
                    best = n
        return best

    def _deff(self, deff_id, then, **args):
        info = self.os.display.media.get(deff_id)
        seconds = info.seconds if info and info.seconds else DEFF_SECONDS[deff_id]
        self.os.deff_start(deff_id, run_seconds=seconds, **args)
        self.machine.clock.schedule_once(lambda: then(), seconds)

    def _next(self, i):
        if i >= len(TITLES):
            self.os.state &= ~0x40
            self.save()
            self._done()
            return
        player = self.best(i)
        if not player:
            self._next(i + 1)
            return
        post = self.machine.events.post
        post("tron_high_score", stage=0x33, player=player, entry=i)

        def initials():
            post("tron_high_score", stage=0x34, player=player, entry=i)
            post("tron_high_score", stage=0x35, player=player, entry=i)
            self.entry = Entry(self, player, entered)

        def entered(name):
            self.entry = None
            self.names[player - 1] = name
            post("tron_high_score", stage=0x36, player=player, entry=i)
            self._place(i, player)
        self._deff(31, initials, player=player)

    def _place(self, i, player):
        """FUN_0001abfc: the entry and the ones below move down, the award, deff 33."""
        os_ = self.os
        self.entries[i + 1:] = self.entries[i:-1]
        self.entries[i] = {"name": self.names[player - 1], "score": self.scores[player - 1]}
        self.save()
        count = self.adj[AWARD_ADJ[i]]
        kind = self.adj[54]
        if count:
            if kind == 0:
                os_.award_credit(count)
                for _ in range(count):
                    os_.knock()                     # FUN_0001b370(1, n)
            elif kind == 1:
                for _ in range(count):
                    self.machine.events.post("tron_award_ticket")
            os_.audit(0x10, count)
        post = self.machine.events.post
        post("tron_high_score", stage=0x37, player=player, entry=i)
        self.placed[player - 1] = True

        def shown():
            post("tron_high_score", stage=0x38, player=player, entry=i)
            self._next(i + 1)
        self._deff(33, shown, player=player, title=TITLES[i], name=self.entries[i]["name"],
                   score=self.entries[i]["score"], award=kind if count else None, count=count)


feature = HighScores
