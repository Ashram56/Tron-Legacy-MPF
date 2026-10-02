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
        return "{:,}".format(value) if "," in spec else str(value)
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
        if not info or not info["text"]:
            return {}
        values = list(args.values())
        if deff_id == 19:                              # score display: ball number and score
            values = [self.machine.game.player.ball if self.os.game and self.os.game.player else 0,
                      self.os.game.player.score if self.os.game and self.os.game.player else 0]
        out = {}
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
        self._send("slides_play", {slide: {"action": "remove", "key": slide, "expire": None}})
        self._send("slides_play", {slide: {"action": "play", "key": slide, "expire": None,
                                           "priority": priority}},
                   priority=priority, **self.deff_lines(deff_id, args))

    def deff_stop(self, deff_id):
        info = self.data["deffs"].get(deff_id) if self.data else None
        if info:
            self._send("slides_play", {info["slide"]: {"action": "remove", "key": info["slide"], "expire": None}})

    def score_changed(self):
        if self.os.display.bg == 19:
            self._send("slides_play", {"deff_019": {"action": "update", "key": "deff_019", "expire": None}},
                       **self.deff_lines(19, {}))

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
