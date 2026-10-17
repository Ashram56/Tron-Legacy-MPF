"""The service menu's NETWORK and SCORBIT menus (UTILITIES, added by this game): Wi-Fi status, scan, join with
a password typed on the coin-door buttons, hidden networks, forget (tron/network.py, a fake backend here and
nmcli's output parsed from canned text), and Scorbit (tron/scorbit.py) with a fake SDK: the game's scores,
player, ball and multiballs sent with commits, pairing, unpairing, its settings and the credential checks."""
import base64
import os
import tempfile
import time
import types

from tests.test_service import ServiceCase

from tron import network, scorbit                    # noqa: E402 (tests.tron_test puts game/ on the path)
from tron import rom_draw                            # noqa: E402
from tron.service import ENTRY_CHARS, MenuScreen, TextEntryScreen  # noqa: E402

KEY = base64.b64encode(bytes(range(72))).decode()     # well-formed, not a real key
CFG = {"provider": "tronmpf", "machine_id": "1234", "encrypted_key": KEY, "hostname": "production"}


class FakeWifi:
    available = True

    def __init__(self):
        self.calls = []
        self.connected = None

    def status(self):
        if not self.connected:
            return {"state": "DISCONNECTED", "ssid": "", "ip": "", "signal": None, "device": "wlan0"}
        return {"state": "CONNECTED", "ssid": self.connected, "ip": "192.168.1.20", "signal": 71, "device": "wlan0"}

    def scan(self):
        return [{"ssid": "Grid", "signal": 80, "secure": True, "in_use": False},
                {"ssid": "Arcade", "signal": 40, "secure": False, "in_use": False}]

    def connect(self, ssid, password=None, hidden=False):
        self.calls.append(("connect", ssid, password, hidden))
        if password not in (None, "aB1", "pw"):
            return {"ok": False, "message": "WRONG PASSWORD"}
        self.connected = ssid
        return {"ok": True, "message": "CONNECTED"}

    def forget(self, ssid):
        self.calls.append(("forget", ssid))
        self.connected = None
        return {"ok": True, "message": "FORGOTTEN"}


class NetworkCase(ServiceCase):

    def setUp(self):
        super().setUp()
        self.wifi = FakeWifi()
        self.svc._wifi = self.wifi
        self.svc.jobs_inline = True

    def network_menu(self, menu="GO TO NETWORK MENU"):
        self.enter()
        self.goto("GO TO UTILITIES MENU", menu)

    def type_text(self, text):
        """Choose each character with PLUS / MINUS (the shorter way round) and SELECT it, then END."""
        for ch in list(text) + [ENTRY_CHARS[0]]:
            screen = self.top
            target = ENTRY_CHARS.index(ch)
            n = len(ENTRY_CHARS)
            ahead = (target - screen.char) % n
            button = "plus" if ahead <= n - ahead else "minus"
            while screen.char != target:
                self.press(button, wait=0.01)
            self.press("select")


class TestNetworkMenu(NetworkCase):

    def test_menus_under_utilities(self):
        self.network_menu()
        self.assertEqual(["WI-FI STATUS", "SCAN WI-FI NETWORKS", "JOIN HIDDEN NETWORK", "FORGET WI-FI NETWORK",
                          "RETURN TO UTILITIES MENU", "EXIT SERVICE MENU", "DISPLAY HELP SCREEN"],
                         [i["text"] for i in self.top.items()])
        self.press("minus")
        self.press("minus")
        self.press("minus")
        self.press("select")                              # RETURN TO UTILITIES MENU
        self.assertEqual("UTILITIES", self.top.title)
        self.goto("GO TO SCORBIT MENU")
        self.assertEqual(["SCORBIT STATUS", "SCORBIT PAIRING", "SCORBIT ADJUSTMENTS", "SCORBIT UNPAIR"],
                         [i["text"] for i in self.top.items()][:4])

    def test_status(self):
        self.network_menu()
        self.goto("WI-FI STATUS")
        self.assertEqual(("WI-FI STATUS", "DISCONNECTED", ""), self.shown[-1])
        self.wifi.connected = "Grid"
        self.advance_time_and_run(2.5)                    # read again every 2 s
        self.assertEqual(("WI-FI STATUS", "CONNECTED", "GRID"), self.shown[-1])
        self.assertIn("192.168.1.20  71%", rom_draw.lines_of(self.svc.draw_items))
        self.press("back")
        self.assertIsInstance(self.top, MenuScreen)

    def test_scan_and_join_with_password(self):
        """A secured network asks for its password: lower case, upper case (left flipper: back a kind) and a
        number (right flipper twice from upper case), END joins; the result, then SELECT back to the menu."""
        self.network_menu()
        self.goto("SCAN WI-FI NETWORKS")
        self.assertEqual(("NETWORK 1 OF 2", "GRID", "80%  SECURED"), self.shown[-1])
        self.press("plus")
        self.assertEqual(("NETWORK 2 OF 2", "ARCADE", "40%  OPEN"), self.shown[-1])
        self.press("minus")
        self.press("select")
        entry = self.top
        self.assertIsInstance(entry, TextEntryScreen)
        self.assertEqual(("PASSWORD FOR GRID", "", "> a (LOWER CASE)"), self.shown[-1])
        self.press("select")                              # a
        self.hit_and_release_switch("s_right_flipper")    # upper case
        self.advance_time_and_run(0.05)
        self.assertEqual("> A (UPPER CASE)", self.shown[-1][2])
        self.press("plus")
        self.press("select")                              # B
        self.hit_and_release_switch("s_right_flipper")    # numbers
        self.advance_time_and_run(0.05)
        self.press("plus")
        self.press("select")                              # 1
        self.press("select")                              # 1 again ...
        self.press("back")                                # ... deleted
        self.assertEqual("aB1", self.shown[-1][1])
        for _ in range(3):                                # numbers -> upper -> lower -> END
            self.hit_and_release_switch("s_left_flipper")
            self.advance_time_and_run(0.05)
        self.assertEqual("> END (END)", self.shown[-1][2])
        self.assertIn("SELECT TO FINISH", rom_draw.lines_of(self.svc.draw_items))
        self.press("select")
        self.assertEqual([("connect", "Grid", "aB1", False)], self.wifi.calls)
        self.assertEqual(("JOIN NETWORK", "GRID", "CONNECTED"), self.shown[-1])
        self.press("select")
        self.assertEqual("NETWORK", self.top.title)
        self.assertEqual(4, len(self.svc.stack))          # entry, main, utilities, network

    def test_wrong_password_and_open_network(self):
        self.network_menu()
        self.goto("SCAN WI-FI NETWORKS")
        self.press("select")
        self.type_text("x")
        self.assertEqual(("JOIN NETWORK", "GRID", "WRONG PASSWORD"), self.shown[-1])
        self.press("back")
        self.assertEqual("NETWORK", self.top.title)
        self.goto("SCAN WI-FI NETWORKS")
        self.press("plus")
        self.press("select")                              # open: no password
        self.assertEqual(("connect", "Arcade", None, False), self.wifi.calls[-1])

    def test_hold_runs_the_letters(self):
        self.network_menu()
        self.goto("JOIN HIDDEN NETWORK")
        start = self.top.char
        self.hit_switch_and_run("s_service_plus", 0.3)
        self.assertEqual(start + 1, self.top.char)        # one step, then a pause
        self.advance_time_and_run(0.5)                    # 0.4 s, then every 0.08 s
        self.release_switch_and_run("s_service_plus", 0.5)
        self.assertIn(self.top.char - start, range(5, 9))
        held = self.top.char
        self.advance_time_and_run(0.5)
        self.assertEqual(held, self.top.char)             # released: it stops

    def test_hidden_network(self):
        self.network_menu()
        self.goto("JOIN HIDDEN NETWORK")
        self.assertEqual("NETWORK NAME", self.shown[-1][0])
        self.type_text("Lab 2")
        self.assertEqual("PASSWORD FOR LAB 2", self.shown[-1][0])
        self.type_text("pw")
        self.assertEqual(("connect", "Lab 2", "pw", True), self.wifi.calls[-1])
        # BACK with nothing typed leaves the entry
        self.press("select")
        self.goto("JOIN HIDDEN NETWORK")
        self.press("back")
        self.assertEqual("NETWORK", self.top.title)

    def test_text_entry_draw(self):
        """Lower case as small capitals (font 2), capitals in font 8, a symbol the fonts lack as a dim block,
        the letter being chosen underlined; long text scrolls."""
        self.network_menu()
        self.goto("JOIN HIDDEN NETWORK")
        entry = self.top
        entry.text = list("aB_")
        draw = entry.draw()
        texts = [d for d in draw if d.get("t") in ("A", "B")]
        self.assertEqual([2, 8, 2], [d["f"] for d in texts])                 # a, B, and the cursor's a
        self.assertTrue(any(d.get("l") == 6 for d in draw if "r" in d))      # _ has no glyph
        entry.text = list("x" * 40)
        xs = [d["x"] for d in entry.draw() if d.get("t") == "X"]
        self.assertLessEqual(max(xs), rom_draw.WIDTH)

    def test_forget(self):
        self.network_menu()
        self.goto("FORGET WI-FI NETWORK")
        self.assertEqual(("FORGET WI-FI NETWORK", "NOT CONNECTED", ""), self.shown[-1])
        self.press("back")
        self.wifi.connected = "Grid"
        self.goto("FORGET WI-FI NETWORK")
        self.assertEqual(("FORGET WI-FI NETWORK", "GRID", "PRESS 'SELECT' TO FORGET"), self.shown[-1])
        self.press("select")
        self.assertEqual(("forget", "Grid"), self.wifi.calls[-1])
        self.assertEqual("FORGOTTEN", self.shown[-1][2])

    def test_no_wifi_here(self):
        self.svc._wifi = network.NoWifi()
        self.network_menu()
        self.goto("SCAN WI-FI NETWORKS")
        self.assertEqual(("SCAN WI-FI NETWORKS", "WI-FI NOT AVAILABLE", ""), self.shown[-1])
        self.press("select")                              # nothing to join
        self.assertEqual("SCAN WI-FI NETWORKS", self.top.title)
        self.press("back")
        self.goto("WI-FI STATUS")
        self.assertEqual("NOT AVAILABLE", self.shown[-1][1])

    def test_threaded_job(self):
        """The real Job runs in a thread; the screen polls it on the clock."""
        self.svc.jobs_inline = False
        self.network_menu()
        self.goto("SCAN WI-FI NETWORKS")
        for _ in range(50):
            if self.top.networks is not None:
                break
            time.sleep(0.05)
            self.advance_time_and_run(0.25)
        self.assertEqual("GRID", self.shown[-1][1])


class TestNmcli(ServiceCase):
    """NmcliWifi on canned nmcli output (escaped ':' in names, one entry per name, the connected one first)."""

    def nmcli(self, replies):
        calls = []

        def run(args):
            calls.append(args)
            for key, reply in replies.items():
                if key in " ".join(args):
                    return reply
            return 1, "", "Error: unexpected"
        return network.NmcliWifi(run=run), calls

    def test_parse(self):
        self.assertEqual(["a:b", "c\\", ""], network.split_terse("a\\:b:c\\\\:"))
        wifi, calls = self.nmcli({
            "DEVICE,TYPE": (0, "eth0:ethernet:unavailable:\nwlan0:wifi:connected:Grid\\:5G\n", ""),
            "--rescan no": (0, "*:Grid\\:5G:72:WPA2\n", ""),
            "IP4.ADDRESS": (0, "192.168.1.20/24\n", ""),
            "--rescan yes": (0, " :Arcade:40:\n :Grid\\:5G:30:WPA2\n*:Grid\\:5G:72:WPA2\n :Office:90:WPA1 WPA2\n"
                                " ::95:WPA2\n", ""),
        })
        self.assertEqual({"state": "CONNECTED", "ssid": "Grid:5G", "ip": "192.168.1.20", "signal": 72,
                          "device": "wlan0"}, wifi.status())
        nets = wifi.scan()
        self.assertEqual(["Grid:5G", "Office", "Arcade"], [n["ssid"] for n in nets])
        self.assertEqual([True, False, False], [n["in_use"] for n in nets])
        self.assertEqual([True, True, False], [n["secure"] for n in nets])

    def test_errors(self):
        wifi, calls = self.nmcli({"connect": (4, "", "Error: Connection activation failed: (7) Secrets were "
                                                     "required, but not provided.")})
        self.assertEqual({"ok": False, "message": "WRONG PASSWORD"}, wifi.connect("Grid", "x"))
        self.assertEqual(["device", "wifi", "connect", "Grid", "password", "x"], calls[-1])
        wifi.connect("Lab", None, hidden=True)
        self.assertEqual(["device", "wifi", "connect", "Lab", "hidden", "yes"], calls[-1])
        self.assertEqual("NOT AUTHORIZED", network.error_text("Error: Not authorized to control networking."))
        self.assertEqual("SOMETHING ELSE", network.error_text("Error: something else"))
        wifi, _ = self.nmcli({"DEVICE,TYPE": (0, "eth0:ethernet:connected:Wired\n", "")})
        self.assertEqual("NO WI-FI DEVICE", wifi.status()["state"])

    def test_wpa_cli(self):
        """WpaCliWifi (the Jetson image): status, scan, join with the PSK hashed (never the password), keep the
        connection, replace a saved network of the same name, drop a failed one, forget."""
        self.assertEqual("f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e",
                         network.psk_hex("IEEE", "password"))          # IEEE 802.11i test vector
        self.assertEqual("caf\u00e9 \\", network.wpa_unescape("caf\\xc3\\xa9 \\\\"))
        state = {"wpa_state": "COMPLETED", "ssid": "Grid", "ip_address": "10.0.0.5"}
        nets = {"0": "Grid"}
        calls = []

        def run(args):
            calls.append(args)
            c = args[0]
            if c == "status":
                return 0, "".join("{}={}\n".format(k, v) for k, v in state.items()), ""
            if c == "signal_poll":
                return 0, "RSSI=-60\nLINKSPEED=72\n", ""
            if c == "scan":
                return 0, "OK\n", ""
            if c == "scan_results":
                return 0, ("bssid / frequency / signal level / flags / ssid\n"
                           "aa:01\t2412\t-60\t[WPA2-PSK-CCMP][ESS]\tGrid\n"
                           "aa:02\t2437\t-80\t[ESS]\tArcade\n"
                           "aa:03\t5180\t-40\t[WPA2-PSK-CCMP][ESS]\t\n"
                           "aa:04\t5180\t-50\t[WPA2-SAE][ESS]\tL\\xc3\\xa9o\n"), ""
            if c == "list_networks":
                return 0, "network id / ssid / bssid / flags\n" + "".join(
                    "{}\t{}\tany\t\n".format(k, v) for k, v in nets.items()), ""
            if c == "add_network":
                nets["1"] = None
                return 0, "1\n", ""
            if c == "set_network" and args[2] == "ssid":
                nets[args[1]] = args[3].strip('"')
            if c == "remove_network":
                nets.pop(args[1], None)
            if c == "select_network":
                state.update(wpa_state="COMPLETED" if args[1] == "1" and "right" in str(calls) else "4WAY_HANDSHAKE")
            return 0, "OK\n", ""

        wifi = network.WpaCliWifi("wlan0", run=run, sleep=lambda s: None)
        wifi.CONNECT_SECONDS = 3
        self.assertEqual({"state": "CONNECTED", "ssid": "Grid", "ip": "10.0.0.5", "signal": 80, "device": "wlan0"},
                         wifi.status())
        self.assertEqual([("Grid", 80, True, True), ("L\u00e9o", 100, True, False), ("Arcade", 40, False, False)],
                         [(n["ssid"], n["signal"], n["secure"], n["in_use"]) for n in wifi.scan()])
        # a wrong password: the added network is removed again, the others enabled, nothing saved
        result = wifi.connect("Grid", "wrong")
        self.assertEqual({"ok": False, "message": "WRONG PASSWORD"}, result)
        self.assertEqual({"0": "Grid"}, nets)
        self.assertNotIn(["save_config"], calls)
        self.assertFalse(any("wrong" in " ".join(c) for c in calls))           # the password never leaves
        self.assertIn(["set_network", "1", "psk", network.psk_hex("Grid", "wrong")], calls)
        calls.append(["right"])
        self.assertEqual({"ok": True, "message": "CONNECTED"}, wifi.connect("Grid", "right"))
        self.assertEqual({"1": "Grid"}, nets)                                    # replaced the old one
        self.assertEqual(["enable_network", "all"], calls[-2])
        self.assertEqual(["save_config"], calls[-1])
        self.assertEqual({"ok": True, "message": "FORGOTTEN"}, wifi.forget("Grid"))
        self.assertEqual({}, nets)
        self.assertEqual({"ok": False, "message": "NOT SAVED"}, wifi.forget("Grid"))
        state["wpa_state"] = "SCANNING"
        self.assertEqual("SCANNING", wifi.status()["state"])

    def test_backend_choice(self):
        os.environ["TRON_WIFI"] = "off"
        try:
            self.assertIsInstance(network.wifi_backend(), network.NoWifi)
        finally:
            del os.environ["TRON_WIFI"]


# ---------------------------------------------------------------------------------------------- Scorbit

class FakeGameState:
    def __init__(self, sdk):
        self.sdk = sdk
        self.calls = []
        self.status = 3
        self.machine_uuid = "c0ffee00-0000-0000-0000-000000000001"
        self.missing = set()                    # methods this SDK version lacks

    def __getattr__(self, name):
        if name not in self.__dict__.get("missing", ()) and name.startswith(("set_", "add_", "remove_", "commit", "destroy", "upload")):
            return lambda *args, **kwargs: self.calls.append((name,) + args)
        raise AttributeError(name)

    def request_pair_code(self, cb):
        self.calls.append(("request_pair_code",))
        self.sdk.pending.append(lambda: cb(0, "ab12cd"))

    def request_unpair(self, cb):
        self.calls.append(("request_unpair",))
        self.sdk.pending.append(lambda: cb(0, ""))


def fake_sdk():
    sdk = types.SimpleNamespace(pending=[], states=[], configs=[])

    class Config:
        def __init__(self):
            self.values = {}
            sdk.configs.append(self)

        def __getattr__(self, name):
            return lambda value: self.values.__setitem__(name[4:], value)

    def create_game_state(config):
        gs = FakeGameState(sdk)
        sdk.states.append(gs)
        return gs

    sdk.Config = Config
    sdk.create_game_state = create_game_state
    sdk.GameStartOrigin = types.SimpleNamespace(StartButton=0)
    sdk.EventType = types.SimpleNamespace(PairingStatusChanged=9, PlayersUpdated=4, DiagnosticsUploadRequested=6)
    return sdk


class ScorbitCase(NetworkCase):

    def setUp(self):
        super().setUp()
        self.tron.scorbit.stop()
        self.sdk = fake_sdk()
        self.tmp = tempfile.mkdtemp()
        cfg = dict(CFG, key_file=os.path.join(self.tmp, "key.txt"))
        self.tron.scorbit = self.sb = scorbit.Scorbit(self.tron, cfg=cfg, sdk=self.sdk)

    @property
    def gs(self):
        return self.sdk.states[-1]

    def calls(self, *names):
        return [c for c in self.gs.calls if c[0] in names]


class TestScorbit(ScorbitCase):

    def start_game(self):
        self.fill_trough()
        self.hit_and_release_switch("s_start_button")
        self.advance_time_and_run(2)
        self.release_switch_and_run("s_shooter_lane", 1)

    def drain(self):
        """Validate, no ball save, drain; the next ball is plunged."""
        self.hit_and_release_switch("s_zen_rollover")
        self.advance_time_and_run(0.3)
        self.tron.kill_ball_save()
        self.machine.default_platform.add_ball_to_device(self.machine.ball_devices["bd_trough"])
        self.advance_time_and_run(15)
        if self.machine.game:
            self.release_switch_and_run("s_shooter_lane", 1)

    def test_config_sent_to_the_sdk(self):
        values = self.sdk.configs[-1].values
        self.assertEqual(("tronmpf", 1234, "1.74", "production", KEY),
                         (values["provider"], values["machine_id"], values["game_code_version"],
                          values["hostname"], values["encrypted_key"]))
        # the SDK stores the cabinet's device key through the game (owner-only file, git-ignored data/)
        values["save_key_callback"]("device-key")
        self.assertEqual("device-key", values["load_key_callback"]())
        self.assertEqual(0o600, os.stat(os.path.join(self.tmp, "key.txt")).st_mode & 0o777)

    def test_game_scores_ball_player_modes(self):
        self.tron.adj[31] = 2                              # 2 balls per game
        self.start_game()
        self.assertEqual([("set_game_started", 0)], self.calls("set_game_started"))
        self.assertIn(("set_current_ball", 1), self.gs.calls)
        self.assertIn(("set_active_player", 1), self.gs.calls)
        self.tron.score_add(12340)
        self.advance_time_and_run(0.6)
        self.assertEqual(("set_score", 1, self.machine.game.player.score), self.calls("set_score")[-1])
        commits = len(self.calls("commit"))
        self.advance_time_and_run(2)
        self.assertEqual(commits, len(self.calls("commit")))       # nothing changed: no commit
        self.tron.flag_set(0x37)
        self.advance_time_and_run(0.6)
        self.assertEqual([("add_mode", "MB:Portal Multiball")], self.calls("add_mode"))
        self.tron.flag_clear(0x37)
        self.advance_time_and_run(0.6)
        self.assertEqual([("remove_mode", "MB:Portal Multiball")], self.calls("remove_mode"))
        self.drain()
        self.assertIn(("set_current_ball", 2), self.gs.calls)
        self.drain()
        self.assertIsNone(self.machine.game)
        self.assertEqual("set_game_finished", self.gs.calls[-1][0])

    def test_timed_modes_and_completed_modes(self):
        self.tron.adj[31] = 1
        self.start_game()
        self.tron.task_start(0xc0, 1000, lambda: None)     # CLU hurry-up clock
        self.advance_time_and_run(0.6)
        self.assertEqual([("add_mode", "NA:CLU Hurry-Up")], self.calls("add_mode"))
        self.tron.hook("item_collect", 2)                  # every CLU shot made
        self.tron.audit(0x88)                              # Flynn found
        self.tron.task_kill(0xc0)
        self.advance_time_and_run(0.6)
        self.assertEqual([("set_mode_completed", "NA:CLU Hurry-Up"), ("set_mode_completed", "NA:Find Flynn")],
                         self.calls("set_mode_completed"))
        self.assertEqual([("remove_mode", "NA:CLU Hurry-Up")], self.calls("remove_mode"))
        self.assertEqual("commit", self.gs.calls[-1][0])
        # Sea of Simulation's stages collect items too: only the whole mode counts
        self.tron.flag_set(0x34)
        self.tron.hook("item_collect", 5)
        self.advance_time_and_run(0.6)
        self.assertEqual(2, len(self.calls("set_mode_completed")))
        self.tron.flag_clear(0x34)
        self.tron.flag_set(0x36)
        self.advance_time_and_run(1.2)
        self.assertEqual([("set_mode_completed", "NA:Sea of Simulation")], self.calls("set_mode_completed")[2:])

    def test_sdk_without_mode_completed(self):
        """SDK 2.0.4 has no set_mode_completed: the running modes are still sent."""
        self.gs.missing.add("set_mode_completed")
        self.tron.adj[31] = 1
        self.start_game()
        self.tron.flag_set(0x29)
        self.tron.hook("item_collect", 4)
        self.advance_time_and_run(0.6)
        self.assertEqual([("add_mode", "MB:Quorra Multiball")], self.calls("add_mode"))
        self.assertEqual([], self.calls("set_mode_completed"))

    def test_pairing_and_unpair_screens(self):
        self.network_menu("GO TO SCORBIT MENU")
        self.goto("SCORBIT STATUS")
        self.assertEqual(("SCORBIT STATUS", "NOT PAIRED", "MACHINE 1234  PRODUCTION"), self.shown[-1])
        self.assertIn("C0FFEE00000000000000000000000001", rom_draw.lines_of(self.svc.draw_items))
        self.press("back")
        self.goto("SCORBIT PAIRING")
        self.assertEqual("ASKING SCORBIT", self.shown[-1][1])
        self.sdk.pending.pop(0)()                     # the SDK's thread answers
        self.advance_time_and_run(0.5)
        self.assertEqual(("SCORBIT PAIRING", "AB12CD", "ENTER IN THE SCORBIT APP"), self.shown[-1])
        self.gs.status = 4
        self.sb._event(types.SimpleNamespace(type=9, get_pairing_status_changed=lambda: True))
        self.advance_time_and_run(0.5)
        self.assertEqual("PAIRED", self.shown[-1][1])
        self.press("back")
        self.goto("SCORBIT UNPAIR")
        self.assertEqual(("SCORBIT UNPAIR", "PAIRED", "PRESS 'SELECT' TO UNPAIR"), self.shown[-1])
        self.press("select")
        self.assertIn(("request_unpair",), self.gs.calls)
        self.sdk.pending.pop(0)()
        self.advance_time_and_run(0.5)
        self.assertEqual("UNPAIRED", self.shown[-1][1])
        self.press("select")
        self.assertEqual("SCORBIT", self.top.title)

    def test_settings_restart_and_off(self):
        self.network_menu("GO TO SCORBIT MENU")
        self.goto("SCORBIT ADJUSTMENTS")
        self.assertEqual(("SCORBIT ADJUSTMENTS", "01 SCORBIT", "ON (FACTORY)"), self.shown[-1])
        first = self.gs
        self.press("plus")                            # 02 SCORBIT SERVER
        self.press("select")
        self.press("plus")
        self.press("select")
        self.assertEqual("staging", self.sb.settings.hostname)
        self.assertIn(("destroy",), first.calls)      # restarted on the other server
        self.assertEqual("staging", self.sdk.configs[-1].values["hostname"])
        self.press("minus")
        self.press("select")
        self.press("minus")
        self.press("select")                          # SCORBIT OFF
        self.assertFalse(self.sb.running)
        self.assertEqual("OFF", self.sb.status_text())
        self.press("back")
        self.goto("SCORBIT PAIRING")
        self.assertEqual(("SCORBIT PAIRING", "SCORBIT IS OFF", "OFF"), self.shown[-1])
        self.sb.settings.factory_reset()              # RESET FACTORY SETTINGS: on, production
        self.assertTrue(self.sb.running)
        self.assertEqual("production", self.sdk.configs[-1].values["hostname"])

    def test_diagnostics_upload(self):
        self.sb._event(types.SimpleNamespace(type=6))
        self.advance_time_and_run(0.6)
        self.assertEqual("upload_diagnostics", self.calls("upload_diagnostics")[0][0])


class TestScorbitSdk(TestScorbit):
    """The real SDK (scripts/setup.py --scorbit) when it is installed: it starts with a well-formed key that
    Scorbit does not know, takes a whole game without a network, and stops."""

    def setUp(self):
        ServiceCase.setUp(self)
        sdk, why = scorbit.import_sdk()
        if not sdk:
            self.skipTest(why)
        self.tron.scorbit.stop()
        self.tmp = tempfile.mkdtemp()
        cfg = dict(CFG, hostname="staging", key_file=os.path.join(self.tmp, "key.txt"))
        self.tron.scorbit = self.sb = scorbit.Scorbit(self.tron, cfg=cfg)

    def tearDown(self):
        self.sb.stop()
        super().tearDown()

    def test_real_sdk_game(self):
        self.assertTrue(self.sb.running)
        self.assertIn(self.sb.status_text(), ("NOT CONNECTED", "CONNECTING", "AUTHENTICATION FAILED"))
        self.tron.adj[31] = 1
        self.start_game()
        self.tron.score_add(5000)
        self.tron.flag_set(0x24)
        self.tron.task_start(0xd1, 1000, lambda: None)
        self.tron.audit(0x88)                          # a completed mode: skipped by SDK 2.0.4
        self.advance_time_and_run(1)
        self.drain()
        self.assertIsNone(self.machine.game)
        self.sb.request_pair_code()
        self.sb.settings[2] = 0                        # a restart on the other server
        self.assertTrue(self.sb.running)

    test_config_sent_to_the_sdk = test_game_scores_ball_player_modes = None
    test_pairing_and_unpair_screens = test_settings_restart_and_off = test_diagnostics_upload = None
    test_timed_modes_and_completed_modes = test_sdk_without_mode_completed = None


class TestScorbitOff(ServiceCase):
    """Without the SDK (this workspace) or without credentials, Scorbit stays off and says why."""

    def test_reasons(self):
        sb = self.tron.scorbit
        self.assertFalse(sb.running)
        self.assertIn(sb.status_text(), ("SDK NOT INSTALLED", "SDK LIBRARY MISSING", "NOT CONFIGURED"))
        self.assertEqual("NOT CONFIGURED", scorbit.config_problem({"provider": "x"}))
        self.assertEqual("BAD MACHINE ID", scorbit.config_problem(dict(CFG, machine_id="12a")))
        self.assertEqual("KEY IS NOT BASE64", scorbit.config_problem(dict(CFG, encrypted_key="abc")))
        self.assertEqual("KEY TOO SHORT", scorbit.config_problem(dict(CFG, encrypted_key="QUJDREVGR0g=")))
        self.assertIsNone(scorbit.config_problem(CFG))
        no_creds = scorbit.Scorbit(self.tron, cfg={}, sdk=fake_sdk())
        self.assertEqual("NOT CONFIGURED", no_creds.status_text())
        self.enter()
        self.goto("GO TO UTILITIES MENU", "GO TO SCORBIT MENU", "SCORBIT STATUS")
        self.assertEqual(sb.status_text(), self.shown[-1][1])

    def test_public_config_has_no_credentials(self):
        cfg = scorbit.load_config(game_dir=tempfile.mkdtemp())
        self.assertEqual({}, cfg)
        public = {}
        import configparser
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(os.path.join(scorbit.GAME, "scorbit.cfg"), encoding="utf-8")
        public = dict(parser["scorbit"])
        self.assertEqual(("", "", ""), (public["provider"], public["machine_id"], public["encrypted_key"]))
