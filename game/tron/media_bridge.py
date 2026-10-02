"""Sends the rules' display effects and sound calls to the Godot media controller (GMC) over BCP.

The OS layer reports every deff start/stop and sound call here. Slides and sounds come from
scripts/gen_media.py (game/slides/deffs, game/sounds, game/tron/media_data.json). Without that data
or without a connected GMC (unit tests), nothing is sent.

- deff N -> slide "deff_NNN" at the deff's ROM priority; text lines with values are formatted from
  the deff's ROM text (event_map.csv rom_text) and its arguments.
- sound call N -> one sample of pool N (sounds.yaml), on the call's track (voice, sfx, music). Music
  calls replace the running music. Calls 0x01-0x08 are the ROM's channel stops.
"""
import json
import os
import re

CONTEXT = "tron_media"
SERVICE_PRIORITY = 1000         # the service slide covers every deff (ROM priorities are 0-255)
TICK = 0.01626                                     # seconds per ROM tick (os_layer.TICK)
SPEC = re.compile(r"%(P\d/[^%]*%|[-+ #0,]*\d*l?[dus])")


def format_rom_text(line, args):
    """printf as the ROM's text_printf_msg uses it: %d %u %s, %,02lu (score with commas),
    %P1/a/b/c/% (plural or ordinal pick by the previous number)."""
    args = list(args)
    last = [0]

    def sub(m):
        spec = m.group(1)
        if spec.startswith("P"):
            choices = spec[3:-1].split("/")
            n = last[0]
            if spec[1] == "1" and len(choices) > 2:     # ordinal list: 1-based
                return choices[n - 1] if 0 < n <= len(choices) else ""
            return choices[0] if n == 1 else (choices[2] if len(choices) > 2 else choices[-1])
        value = args.pop(0) if args else 0
        if spec.endswith("s"):
            return str(value)
        try:
            value = int(value)
        except (TypeError, ValueError):
            return str(value)
        last[0] = value
        text = "{:,}".format(value) if "," in spec else str(value)
        flags, width = re.match(r"([-+ #0,]*)(\d*)", spec).groups()
        if width:                                  # %,02lu: score 0 shows "00"; %06d zero-padded
            text = text.rjust(int(width), "0" if "0" in flags or width.startswith("0") else " ")
        return text
    return SPEC.sub(sub, line)


class MediaBridge:

    def __init__(self, os_):
        self.os = os_
        self.machine = os_.machine
        path = os.path.join(os.path.dirname(__file__), "media_data.json")
        self.data = None
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.data = {"pools": {int(k): v for k, v in data["pools"].items()},
                         "deffs": {int(k): v for k, v in data["deffs"].items()}}
        self.music_key = None
        self.counters = {}
        self.last_scores = {}
        self.award = (0, None, None)               # last points, shown since, blink counter since
        self.bar_max = {}
        self._refresh = None
        self.active = set()                        # deffs on screen that draw the status panel

    # ------------------------------------------------------------------ transport

    def connected(self, need_data=True):
        bcp = getattr(self.machine, "bcp", None)
        if (need_data and not self.data) or not bcp or not getattr(bcp, "transport", None):
            return False
        return bool(bcp.transport.get_named_client("local_display"))

    def _send(self, name, settings, priority=0, need_data=True, **kwargs):
        if not self.connected(need_data):
            return
        self.machine.bcp.interface.bcp_trigger(name=name, settings=settings, context=CONTEXT,
                                               calling_context=CONTEXT, priority=priority, **kwargs)

    # ------------------------------------------------------------------ display effects

    def deff_lines(self, deff_id, args):
        info = self.data["deffs"].get(deff_id) if self.data else None
        if not info:
            return {}
        if not info["text"]:
            return self.score_display_args() if info.get("panel") else {}
        values = list(args.values())
        if deff_id == 19:                              # score display: ball number and score
            values = [self.machine.game.player.ball if self.os.game and self.os.game.player else 0,
                      self.os.game.player.score if self.os.game and self.os.game.player else 0]
        out = self.score_display_args() if info.get("panel") else {}
        for i, line in enumerate(info["text"]):
            n = len(SPEC.findall(line))
            if n and len(values) < n:              # value not reported by the rules: leave the line blank
                out["line{}".format(i)] = ""
                values = []
                continue
            out["line{}".format(i)] = format_rom_text(line, values[:n])
            values = values[n:]
        return out

    def deff_start(self, deff_id, priority, **args):
        info = self.data["deffs"].get(deff_id) if self.data else None
        if not info:
            return
        slide = info["slide"]
        if info.get("panel"):
            self.active.add(deff_id)
            if self._refresh is None and self.connected():   # timer bars move between scores
                self._refresh = self.machine.clock.schedule_interval(self.score_changed, 0.25)
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}})
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None,
                                           "priority": priority}},
                   priority=priority, **self.deff_lines(deff_id, args))

    def deff_stop(self, deff_id):
        info = self.data["deffs"].get(deff_id) if self.data else None
        self.active.discard(deff_id)
        if info:
            self._send("slides_play", {info["slide"]: {"action": "remove", "key": info["slide"], "expire": None}})

    # ------------------------------------------------------------------ score display (deff 19)

    def credits_text(self):
        """FUN_00004ff4: "FREE PLAY", "CREDITS n", "CREDITS a/b" (coins toward the next credit) or
        "CREDITS n a/b". The credit count comes from the OS when it keeps one (os.credits,
        os.credit_fraction = (coins, coins per credit), os.free_play); 3 coins make a credit."""
        if getattr(self.os, "free_play", False):
            return "FREE PLAY"
        whole = int(getattr(self.os, "credits", 0) or 0)
        num, den = getattr(self.os, "credit_fraction", None) or (getattr(self.os, "coins", 0) % 3, 3)
        if num == 0:
            return "CREDITS %d" % whole
        if whole == 0:
            return "CREDITS %d/%d" % (num, den)
        return "CREDITS %d %d/%d" % (whole, num, den)

    def replay_text(self):
        """FUN_01023704: the current player's first replay level not yet awarded ("REPLAY AT <level>",
        the award text for adj 13 = 0; the other awards' texts are ROM messages not in the package)."""
        level_of = getattr(self.os, "replay_level", None)
        if not level_of:
            return ""
        done = getattr(self.os, "replays_awarded", {}).get(self.os.player_num, set())
        for n in range(1, 5):
            level = level_of(n)
            if level and n not in done:
                return "REPLAY AT " + format_rom_text("%,02lu", [level])
        return ""

    def _bar(self, key, seconds, start=0):
        """Timer bar length 0-10: seconds * 10 / start (FUN_01022ffc keeps the larger of both)."""
        top = max(self.bar_max.get(key, 0) if seconds else 0, start, seconds)
        self.bar_max[key] = top
        return seconds * 10 // top if top else 0

    def score_display_args(self):
        """Event args of deff 19 beyond line0/line1, for tron/score_display.gd."""
        game = self.os.game
        players = game.player_list if game else []
        now = self.machine.clock.get_time()
        current = self.os.player_num
        if current and players:                      # last points: the current player's score change
            score = players[current - 1].score
            delta = score - self.last_scores.get(current, score)
            self.last_scores[current] = score
            value, shown, _ = self.award
            if delta > 0:
                age = (now - shown) / TICK if shown is not None else 99
                self.award = (value, shown, now) if age < 16 and delta < value else (delta, now, now)
        value, shown, blink = self.award
        out = {"players": max(len(players), 1), "player": current or 1,
               "valid": bool(getattr(self.os, "ball_validated", False)) or not game,
               "credits": self.credits_text(), "replay": self.replay_text() if game else "",
               "award": format_rom_text("%,02lu", [value]) if value else "",
               "award_age": int((now - shown) / TICK) if shown is not None else 99,
               "blink_age": int((now - blink) / TICK) if blink is not None else 999}
        for p in range(1, 5):
            out["p%d" % p] = format_rom_text("%,02lu", [players[p - 1].score]) if p <= len(players) else ""
        feats = self.os.features_by_name if hasattr(self.os, "features") else {}
        targets = feats.get("tron_targets")
        for bit, key in ((1, "bar_ds"), (2, "bar_bumpers"), (4, "bar_spinners")):
            secs = targets.secs.get(bit, 0) if targets else 0
            out[key] = self._bar(key, secs)
        for name, key in (("zuse", "bar_zfs"), ("clu", "bar_clu"), ("gem", "bar_gem")):
            clock = getattr(feats.get(name), "clock", None)
            out[key] = self._bar(key, clock.seconds if clock else 0)
        return out

    def score_changed(self, *_):
        """Score flush (and every 0.25 s while a panel shows): refresh the score display and the
        status panel of the effects on screen."""
        if not self.data:
            return
        args = None
        for deff_id in sorted(self.active | ({19} if self.os.display.bg == 19 else set())):
            info = self.data["deffs"].get(deff_id)
            if not info or not info.get("panel"):
                continue
            args = self.score_display_args() if args is None else args
            if deff_id == 19:
                args = dict(args, **{k: v for k, v in self.deff_lines(19, {}).items() if k.startswith("line")})
            self._send("slides_play", {info["slide"]: {"action": "update", "key": info["slide"],
                                                       "expire": None}}, **args)
        if args is None:
            self.score_display_args()                  # keep the last-points tracking current

    # ------------------------------------------------------------------ service menu

    def text_show(self, slide, lines, priority):
        """Rules text on a generic slide (game/slides/<slide>.tscn, labels line0-line2); needs no generated
        media: the service menu, the attract pages and the initials entry."""
        lines = {"line{}".format(i): text for i, text in enumerate(lines)}
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}}, need_data=False)
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None, "priority": priority}},
                   priority=priority, need_data=False, **lines)

    def text_hide(self, slide):
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}}, need_data=False)

    def service_show(self, lines):
        """Service menu text (tron/service.py), above every deff."""
        self.text_show("service", lines, SERVICE_PRIORITY)

    def service_hide(self):
        self.text_hide("service")

    # ------------------------------------------------------------------ sounds

    def sound(self, call, index=None):
        if not self.data:
            return
        if 1 <= call <= 8:                             # channel stop
            if self.music_key:
                self._send("sounds_play", {self.music_key: {"action": "stop", "key": self.music_key}})
                self.music_key = None
            return
        pool = self.data["pools"].get(call)
        if not pool:
            return
        samples = pool["samples"]
        if index is not None and index < len(samples):  # the rules picked the sample (sound lengths)
            sample = samples[index]
        elif pool["type"].startswith("random"):
            sample = samples[self.os.random.randrange(len(samples))]
        else:                                          # sequence
            n = self.counters.get(call, 0)
            self.counters[call] = n + 1
            sample = samples[n % len(samples)]
        track = pool["track"]
        settings = {"action": "play", "bus": track, "key": sample}
        if track == "music":
            if self.music_key:
                self._send("sounds_play", {self.music_key: {"action": "stop", "key": self.music_key}})
            self.music_key = sample
            settings["loops"] = -1
        self._send("sounds_play", {sample: settings})
