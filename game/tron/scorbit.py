"""Scorbit (scorbit.io, added by this game): the running game's scores, ball, player and multiballs sent live
to Scorbit through its SDK (github.com/scorbit-io/scorbit_sdk: the `scorbit` Python wrapper and its native
library, Linux only), pairing the cabinet with a venue in the Scorbit app, and the operator's settings.

- Credentials: game/scorbit.cfg (public, empty) then game/scorbit.local.cfg (git-ignored): the provider
  name, machine id and encrypted provider key Scorbit gives a game maker. Nothing is sent without them.
- Settings (service menu UTILITIES > GO TO SCORBIT MENU > SCORBIT ADJUSTMENTS, persisted machine vars):
  SCORBIT ON / OFF and SCORBIT SERVER (production / staging), with the interface of tron.settings.Adjustments
  so the adjustment editor edits them.
- os.scorbit (Scorbit): starts the SDK when the settings and credentials allow it, follows MPF's game
  events, and on the MPF clock every TICK seconds sends what changed (scores, active player, ball, the
  running modes, the modes completed since the last tick) with one commit. The SDK's callbacks run in its
  own threads: they only store plain values, which the clock tick reads; nothing touches MPF from them.

When the SDK is not installed (Windows, macOS, a workspace set up without --scorbit) or not configured, the
game runs as before and the service menu says why Scorbit is off.
"""
import base64
import binascii
import configparser
import glob
import importlib.util
import logging
import os
import threading

GAME = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = ("scorbit.cfg", "scorbit.local.cfg")
SDK_VERSION = "2.0.4"           # the wrapper and native library scripts/setup.py --scorbit installs
GAME_CODE_VERSION = "1.74"      # the ROM rules this game plays (Tron Legacy LE 1.74)
TICK = 0.5                      # seconds between two commits while something changed
HOSTNAMES = ("production", "staging")
# game flags (tron/os_layer.py) shown as Scorbit modes while set; "MB:" is Scorbit's multiball category
MODES = {
    0x24: "MB:Disc Multiball",
    0x27: "MB:End of Line",
    0x29: "MB:Quorra Multiball",
    0x2b: "MB:Light Cycle Multiball",
    0x37: "MB:Portal Multiball",
    0x34: "NA:Sea of Simulation",
}
# timed modes shown while their clock task or its end grace runs (tron/features/timed_modes.Countdown)
TASK_MODES = {
    "NA:CLU Hurry-Up": (0xc0, 0xc1),
    "NA:GEM Hurry-Up": (0xc2, 0xc3),
    "NA:ZUSE Fast Scoring": (0x59, 0x5b),
    "NA:Find Flynn": (0xd1,),
}
# completed modes (achievements; SDK set_mode_completed, after 2.0.4): an item collected (ROM hook
# item_collect, outside Sea of Simulation, whose stages collect items too) ...
ITEM_MODES = {
    1: "NA:GEM Hurry-Up",           # a GEM award
    2: "NA:CLU Hurry-Up",           # every CLU shot made
    3: "NA:ZUSE Fast Scoring",      # all four ZUSE targets
    4: "MB:Quorra Multiball",       # super jackpot
    5: "MB:Disc Multiball",         # super jackpot
    6: "MB:Light Cycle Multiball",  # super jackpot
    7: "NA:Recognizer",             # five Recognizer hits light Disc Battle
    8: "NA:TRON Targets",           # T, R and O awards all started
}
# ... an audit counter going up (Find Flynn calls its item_collect directly) ...
AUDIT_MODES = {0x88: "NA:Find Flynn", 0x8b: "MB:Portal Multiball"}    # Flynn found, Portal super jackpot
# ... or a game flag set: 0x36 Sea of Simulation completed
FLAG_MODES = {0x36: "NA:Sea of Simulation"}
SOS_RUNNING = 0x34
# the SDK's AuthStatus values, as the service menu shows them
STATUS_TEXT = {0: "NOT CONNECTED", 1: "CONNECTING", 2: "CHECKING PAIRING", 3: "NOT PAIRED", 4: "PAIRED",
               5: "AUTHENTICATION FAILED"}
MIN_KEY_BYTES = 16 + 12 + 16    # salt, IV and tag of the SDK's encrypted key (source/utils/decrypt.cpp)

log = logging.getLogger("Scorbit")


def load_config(game_dir=GAME):
    """The [scorbit] keys of scorbit.cfg then scorbit.local.cfg (the later file wins)."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read([os.path.join(game_dir, name) for name in FILES], encoding="utf-8")
    cfg = dict(parser["scorbit"]) if parser.has_section("scorbit") else {}
    return {k: v.strip() for k, v in cfg.items()}


def key_problem(key):
    """Why the encrypted key cannot be used, None when it looks right. The SDK aborts the whole process
    (std::length_error) on a key whose base64 is cut short, so the game checks it first."""
    if len(key) >= 64 and all(c in "0123456789abcdefABCDEF" for c in key):
        return "KEY NOT ENCRYPTED"      # a raw hex key: Scorbit's encrypt_tool makes the base64 form (104 chars)
    try:
        raw = base64.b64decode(key, validate=True)
    except (binascii.Error, ValueError):
        return "KEY IS NOT BASE64"
    return "KEY TOO SHORT" if len(raw) < MIN_KEY_BYTES else None


def config_problem(cfg):
    """What is missing from the credentials, None when all is there."""
    if not cfg.get("provider") or not cfg.get("machine_id") or not cfg.get("encrypted_key"):
        return "NOT CONFIGURED"
    if not cfg["machine_id"].isdigit():
        return "BAD MACHINE ID"
    return key_problem(cfg["encrypted_key"])


def import_sdk():
    """(the scorbit module, None) or (None, why it is missing). The native library installed by
    scripts/setup.py --scorbit (tools/scorbit/lib) is found through SCORBIT_SDK_PATH unless that is set."""
    lib = os.path.join(GAME, "..", "tools", "scorbit", "lib")
    if not os.environ.get("SCORBIT_SDK_PATH") and os.path.isdir(lib):
        os.environ["SCORBIT_SDK_PATH"] = os.path.abspath(lib)
    if importlib.util.find_spec("scorbit") is None:
        return None, "SDK NOT INSTALLED"
    try:
        import scorbit
    except ImportError as e:            # the wrapper is there, its native library is not
        log.warning("Scorbit SDK library not found: %s", str(e).splitlines()[0] if str(e) else e)
        return None, "SDK LIBRARY MISSING"
    return scorbit, None


# ---------------------------------------------------------------------------------------------- settings

# item: (name, stored machine var, labels)
ITEMS = {1: ("SCORBIT", "scorbit_enabled", ("OFF", "ON")),
         2: ("SCORBIT SERVER", "scorbit_server", ("PRODUCTION", "STAGING"))}


class ScorbitSettings:
    """SCORBIT ADJUSTMENTS: SCORBIT (OFF / ON, factory ON: it runs only once configured) and SCORBIT SERVER
    (factory: scorbit.cfg's hostname), persisted machine vars, with the interface of Adjustments. A change
    restarts the SDK (changed())."""

    def __init__(self, machine, cfg, changed=None):
        self.machine = machine
        self.changed = changed
        self.info = {num: {"name": spec[0], "min": 0, "max": len(spec[2]) - 1, "step": 1}
                     for num, spec in ITEMS.items()}
        host = cfg.get("hostname", "production").lower()
        self.factory = {1: 1, 2: HOSTNAMES.index(host) if host in HOSTNAMES else 0}

    def default(self, num):
        return self.factory[num]

    def __getitem__(self, num):
        value = self.machine.variables.get_machine_var(ITEMS[num][1])
        if value is None or not 0 <= int(value) < len(ITEMS[num][2]):
            return self.default(num)
        return int(value)

    def __setitem__(self, num, value):
        old = self[num]
        key = ITEMS[num][1]
        self.machine.variables.configure_machine_var(key, persist=True)
        self.machine.variables.set_machine_var(key, int(value))
        if int(value) != old and self.changed:
            self.changed()

    def keys(self):
        return sorted(ITEMS)

    def menu(self, group=None):
        return self.keys()

    def label(self, num, value=None):
        return ITEMS[num][2][self[num] if value is None else value]

    def step(self, num, value, direction):
        return (value + direction) % len(ITEMS[num][2])

    def factory_reset(self):
        for num in self.keys():
            self[num] = self.default(num)

    @property
    def enabled(self):
        return bool(self[1])

    @property
    def hostname(self):
        return HOSTNAMES[self[2]]


# ---------------------------------------------------------------------------------------------- the link

class Scorbit:
    """os.scorbit: the SDK's game state while Scorbit runs (gs), the game's state sent to it, and what the
    service menu shows (status_text, pair_code)."""

    def __init__(self, os_, cfg=None, sdk=None):
        self.os = os_
        self.machine = os_.machine
        self.cfg = load_config() if cfg is None else cfg
        self._sdk = sdk                         # the scorbit module (tests pass a fake one)
        self.settings = ScorbitSettings(self.machine, self.cfg, changed=self.restart)
        self.gs = None
        self.problem = None                     # why Scorbit is not running (service menu), None when it is
        self._lock = threading.Lock()
        self._paired = None                     # last PairingStatusChanged (SDK thread)
        self._uploads = []                      # DiagnosticsUploadRequested (SDK thread)
        self.pair_code = None                   # the last short code, or None
        self.pair_error = None
        self.unpair_result = None
        self.players = {}                       # {player number: Scorbit name} of claimed players
        self._sent = {}
        self._modes = set()
        self._completed = []                    # completed modes not sent yet
        self._audits = {}
        self._flags = set()
        self._game = False
        self._clock = None
        self._warned = False
        os_.register("item_collect", self._item_collected)
        ev = self.machine.events
        ev.add_handler("game_started", self._game_started)
        ev.add_handler("game_ended", self._game_ended)
        ev.add_handler("shutdown", self.stop)
        self.start()

    # ------------------------------------------------------------------ lifecycle

    def start(self):
        if self.gs:
            return
        if os.environ.get("TRON_SCORBIT", "").strip().lower() in ("0", "off", "false", "no"):
            self.problem = "OFF (TRON_SCORBIT=0)"
            return
        if not self.settings.enabled:
            self.problem = "OFF"
            return
        sdk, why = (self._sdk, None) if self._sdk else import_sdk()
        if not sdk:
            self.problem = why
            return
        why = config_problem(self.cfg)
        if why:
            self.problem = why
            return
        self._sdk = sdk
        try:
            self.gs = sdk.create_game_state(self._config(sdk))
        except Exception as e:                  # noqa: BLE001: Scorbit never stops the game
            log.error("Scorbit could not start: %s", e)
            self.problem = "START FAILED"
            return
        self.problem = None
        self._sent = {}
        self._modes = set()
        self._clock = self.machine.clock.schedule_interval(self._tick, TICK)
        log.info("Scorbit started (%s, machine %s)", self.settings.hostname, self.cfg["machine_id"])

    def stop(self, **kwargs):
        if self._clock:
            self.machine.clock.unschedule(self._clock)
            self._clock = None
        gs, self.gs = self.gs, None
        if gs:
            try:
                if self._game:
                    gs.set_game_finished()
                gs.destroy()
            except Exception as e:              # noqa: BLE001
                log.warning("Scorbit stop: %s", e)
        self.pair_code = None

    def restart(self):
        self.stop()
        self.problem = None
        self.start()

    def _config(self, sdk):
        cfg = self.cfg
        config = sdk.Config()
        config.set_provider(cfg["provider"])
        config.set_machine_id(int(cfg["machine_id"]))
        config.set_game_code_version(GAME_CODE_VERSION)
        config.set_hostname(self.settings.hostname)
        config.set_encrypted_key(cfg["encrypted_key"])
        if cfg.get("serial_number", "").isdigit():
            config.set_serial_number(int(cfg["serial_number"]))
        if cfg.get("uuid"):
            config.set_uuid(cfg["uuid"])
        config.set_event_callback(self._event)
        config.set_save_key_callback(self._save_key)
        config.set_load_key_callback(self._load_key)
        return config

    def _key_path(self):
        return os.path.join(GAME, self.cfg.get("key_file") or "data/scorbit_device_key.txt")

    def _save_key(self, key):
        path = self._key_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)

    def _load_key(self):
        try:
            with open(self._key_path(), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    # ------------------------------------------------------------------ SDK callbacks (SDK threads)

    def _event(self, event):
        sdk = self._sdk
        kind = event.type
        if kind == sdk.EventType.PairingStatusChanged:
            paired = event.get_pairing_status_changed()
            with self._lock:
                self._paired = paired
                if paired:
                    self.pair_code = None
        elif kind == sdk.EventType.PlayersUpdated:
            players = event.get_players_updated() or {}
            with self._lock:
                self.players = {int(n): info.preferred_name for n, info in players.items() if info.has_info()}
        elif kind == sdk.EventType.DiagnosticsUploadRequested:
            with self._lock:
                self._uploads.append(True)

    def _pair_code(self, error, code):
        with self._lock:
            if int(error) == 0 and code:
                self.pair_code, self.pair_error = code, None
            else:
                self.pair_code, self.pair_error = None, "NOT PAIRED" if int(error) == 3 else "NO ANSWER"

    def _unpaired(self, error, reply):
        with self._lock:
            self.unpair_result = "UNPAIRED" if int(error) == 0 else (
                "NOT PAIRED" if int(error) == 3 else "NO ANSWER")

    # ------------------------------------------------------------------ service menu

    @property
    def running(self):
        return self.gs is not None

    def status_text(self):
        if not self.gs:
            return self.problem or "OFF"
        try:
            return STATUS_TEXT.get(int(self.gs.status), "UNKNOWN")
        except Exception:                       # noqa: BLE001
            return "UNKNOWN"

    def machine_uuid(self):
        try:
            return self.gs.machine_uuid if self.gs else ""
        except Exception:                       # noqa: BLE001
            return ""

    def request_pair_code(self):
        self.pair_code = self.pair_error = None
        if self.gs:
            self.gs.request_pair_code(self._pair_code)

    def request_unpair(self):
        self.unpair_result = None
        if self.gs:
            self.gs.request_unpair(self._unpaired)

    # ------------------------------------------------------------------ the game

    def _game_started(self, **kwargs):
        self._game = True
        self._sent = {}
        self._modes = set()
        self._completed = []
        self._audits = {a: self._audit(a) for a in AUDIT_MODES}
        self._flags = {f for f in FLAG_MODES if self.os.flag(f)}
        if self.gs:
            self.gs.set_game_started(self._sdk.GameStartOrigin.StartButton)
            self._tick()

    def _game_ended(self, **kwargs):
        if self.gs and self._game:
            self._tick()                        # the final scores first
            self.gs.set_game_finished()         # commits
        self._game = False

    def state(self):
        """What Scorbit should show now: {"scores": [..], "player": n, "ball": n} and the mode names."""
        game = self.machine.game
        if not game or not game.player:
            return None, set()
        scores = tuple(int(p.score) for p in game.player_list)
        state = {"scores": scores, "player": game.player.number, "ball": max(1, min(9, game.player.ball))}
        os_ = self.os
        modes = {name for flag, name in MODES.items() if os_.flag(flag)}
        modes |= {name for name, tasks in TASK_MODES.items() if any(os_.task_running(t) for t in tasks)}
        return state, modes

    def _audit(self, counter):
        try:
            return int(self.os.audits[counter])
        except Exception:                       # noqa: BLE001
            return 0

    def _item_collected(self, item):
        """ROM hook item_collect (MPF thread): queue the completed mode for the next tick."""
        name = ITEM_MODES.get(item)
        if name and self._game and not self.os.flag(SOS_RUNNING):
            self._completed.append(name)

    def completions(self):
        """The completed modes since the last tick: the queued items, the audits and flags that went up."""
        done, self._completed = self._completed, []
        for counter, name in AUDIT_MODES.items():
            count = self._audit(counter)
            if count > self._audits.get(counter, count):
                done.append(name)
            self._audits[counter] = count
        flags = {f for f in FLAG_MODES if self.os.flag(f)}
        done += [FLAG_MODES[f] for f in sorted(flags - self._flags)]
        self._flags = flags
        return done

    def _send_completed(self, gs, done):
        """set_mode_completed came after SDK 2.0.4: with an older SDK the completions are not sent."""
        send = getattr(gs, "set_mode_completed", None)
        if not send:
            if done and not self._warned:
                log.info("Scorbit SDK %s has no set_mode_completed: completed modes are not sent", SDK_VERSION)
                self._warned = True
            return False
        for name in done:
            send(name)
        return bool(done)

    def _tick(self, *args):
        gs = self.gs
        if not gs:
            return
        with self._lock:
            uploads, self._uploads = self._uploads, []
        if uploads:
            self._upload_logs()
        if not self._game:
            return
        state, modes = self.state()
        if state is None:
            return
        changed = False
        for i, score in enumerate(state["scores"]):
            if self._sent.get(("score", i)) != score:
                gs.set_score(i + 1, score)
                self._sent[("score", i)] = score
                changed = True
        for key, setter in (("player", gs.set_active_player), ("ball", gs.set_current_ball)):
            if self._sent.get(key) != state[key]:
                setter(state[key])
                self._sent[key] = state[key]
                changed = True
        for mode in modes - self._modes:
            gs.add_mode(mode)
            changed = True
        for mode in self._modes - modes:
            gs.remove_mode(mode)
            changed = True
        self._modes = modes
        if self._send_completed(gs, self.completions()):
            changed = True
        if changed:
            gs.commit()

    def _upload_logs(self):
        """Scorbit asked for diagnostics: the newest MPF logs (game/logs), at most five."""
        logs = sorted(glob.glob(os.path.join(GAME, "logs", "*.log")), key=os.path.getmtime, reverse=True)[:5]
        try:
            self.gs.upload_diagnostics(log_paths=logs, log_string="Tron Legacy MPF {}".format(GAME_CODE_VERSION))
        except Exception as e:                  # noqa: BLE001
            log.warning("Scorbit diagnostics upload: %s", e)
