"""The service menu on the PuP backglass (tron/service_backglass.py): every service screen describes itself for
game/pup/service_backglass.gd, the device views carry where each switch, lamp and coil is, the description goes
over BCP, and the DMD's screens stay the ROM's."""
import json
import os
import sys
import tempfile
from unittest import mock

from tests.test_network import NetworkCase
from tests.test_service import ServiceCase
from tests.tron_test import GAME, ROOT

if GAME not in sys.path:
    sys.path.insert(0, GAME)
from tron import service_backglass as bg  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts", "pup"))
import gen_pup  # noqa: E402

KINDS = {"entry", "menu", "rows", "adjust", "switches", "lamps", "coils", "trough", "message"}


class TestBackglass(ServiceCase):

    def setUp(self):
        super().setUp()
        self.sent = []
        media = self.tron.media
        send = media.service_backglass
        media.service_backglass = lambda state: (self.sent.append(state), send(state))

    @property
    def state(self):
        return self.svc.backglass

    def check(self, state):
        """Every description: shown, a known kind, a title, where the operator is, the buttons; JSON-able."""
        self.assertTrue(state["show"])
        self.assertIn(state["kind"], KINDS)
        self.assertTrue(state["title"])
        self.assertTrue(state["path"])
        self.assertLessEqual(len(state["path"]), 3)
        self.assertTrue(state["hints"])
        json.dumps(state)

    def test_every_screen_describes_itself(self):
        """Walk the whole tree as test_service does: each screen's description is valid, and a device view
        brings the device table when it opens, not on its refreshes."""
        self.enter()
        kinds = set()

        def walk():
            menu = self.top
            self.check(self.state)
            for item in list(menu.items()):
                if item["kind"] in ("back", "exit"):
                    continue
                self.goto(item["text"])
                self.check(self.state)
                kinds.add(self.state["kind"])
                if item["kind"] == "submenu":
                    walk()
                    self.goto(next(i["text"] for i in self.top.items() if i["kind"] == "back"))
                else:
                    if self.state["kind"] in ("switches", "lamps", "coils", "trough"):
                        opened = [s for s in self.sent if s.get("title") == self.top.title]
                        self.assertIn("devices", opened[0], item["text"])
                        self.assertTrue(all("devices" not in s for s in opened[1:]), item["text"])
                    self.sent.clear()
                    self.press("plus")
                    self.check(self.state)
                    self.press("back")
                    if self.top is not menu:
                        self.press("back")

        walk()
        self.assertEqual(KINDS, kinds | {"entry"})

    def test_entry_and_main_menu(self):
        self.advance_time_and_run(1)
        self.press("select")
        self.assertEqual("entry", self.state["kind"])
        self.assertEqual(["SERVICE"], self.state["path"])
        self.press("select")
        state = self.state
        self.assertEqual("menu", state["kind"])
        self.assertTrue(state["main"])
        self.assertEqual(0, state["sel"])
        diag = state["items"][0]
        self.assertEqual("GO TO DIAGNOSTICS MENU", diag["text"])
        self.assertEqual(0, diag["icon"])
        self.assertTrue(diag["info"])
        self.assertIn("BALL TROUGH TEST", [c[0] for c in diag["children"]])
        self.assertEqual("EXIT SERVICE MENU", state["items"][-1]["text"])
        self.press("plus")
        self.assertEqual(1, self.state["sel"])
        self.goto("GO TO AUDITS MENU")
        self.assertFalse(self.state["main"])
        self.assertEqual(["SERVICE", "AUDITS"], self.state["path"])

    def test_switch_test_places_the_switch(self):
        self.enter()
        self.goto("GO TO DIAGNOSTICS MENU", "GO TO SWITCH MENU", "SWITCH TEST")
        devices = bg.devices(self.svc)
        self.assertIsNone(self.state["focus"])
        self.hit_and_release_switch("s_right_orbit")
        self.advance_time_and_run(0.1)
        self.assertEqual("s_right_orbit", self.state["focus"])
        self.assertEqual("test", self.state["mode"])
        spot = devices["switches"]["s_right_orbit"]
        number = spot["n"]
        self.assertEqual([(int(number) - 1) // 8 + 1, (int(number) - 1) % 8 + 1], spot["cell"])
        self.assertTrue(0 < spot["at"][0] < 1 and 0 < spot["at"][1] < 1)
        self.assertNotIn("s_service_select", devices["switches"])          # the buttons are not shown
        self.hit_switch_and_run("s_left_orbit", 0.1)
        self.assertIn("s_left_orbit", self.state["active"])
        self.assertEqual(["hit any switch on the playfield"], self.state["hints"][0])

    def test_lamp_and_coil_tests(self):
        self.enter()
        self.goto("GO TO DIAGNOSTICS MENU", "GO TO LAMP MENU", "SINGLE LAMP TEST")
        state = self.state
        self.assertEqual("lamps", state["kind"])
        self.assertEqual(1, len(state["focus"]))
        lamp = bg.devices(self.svc)["lamps"][state["focus"][0]]
        self.assertRegex(lamp["color"], r"^#[0-9a-f]{6}$")
        self.assertEqual("LAMP #{}".format(lamp["n"]), state["number"])
        self.advance_time_and_run(0.6)
        self.assertEqual(self.top.on, self.state["on"])
        self.assertEqual(state["focus"] if self.top.on else [], self.state["lit"])
        self.press("back")
        self.goto("LAMP COLUMN TEST")
        self.assertGreater(len(self.state["focus"]), 1)
        self.press("back")
        self.goto("RETURN TO DIAGNOSTICS MENU", "GO TO COIL MENU", "SINGLE COIL TEST")
        self.press("select")
        state = self.state
        coil = bg.devices(self.svc)["coils"][state["fired"]]
        self.assertEqual(state["list"][state["sel"]], state["fired"])
        self.assertFalse(state["flashers"])
        self.assertTrue(coil["wires"])                         # the ROM coil table's wire colours
        self.assertIsNotNone(coil["pulse"])

    def test_adjustments_page(self):
        self.enter()
        self.goto("GO TO ADJUSTMENTS MENU", "STANDARD ADJUSTMENTS")
        state = self.state
        self.assertEqual("adjust", state["kind"])
        self.assertLessEqual(len(state["rows"]), bg.ADJUST_PAGE)
        self.assertEqual(1, state["page"][0])
        self.assertFalse(state["editing"])
        self.press("select")
        self.assertTrue(self.state["editing"])
        self.assertEqual("change", self.state["hints"][0][-1])
        self.press("plus")
        row = self.state["rows"][self.state["sel"]]
        self.assertTrue(row["changed"])
        self.assertEqual(self.top.adj.label(row["number"], self.top.editing), row["value"])
        self.press("back")
        self.assertFalse(self.state["rows"][self.state["sel"]]["changed"])

    def test_audits_page(self):
        self.enter()
        self.goto("GO TO AUDITS MENU", "STANDARD AUDITS")
        for _ in range(bg.PAGE + 1):
            self.press("plus")
        state = self.state
        self.assertEqual("rows", state["kind"])
        self.assertEqual(bg.PAGE + 1, state["page"][0])
        self.assertEqual(1, state["sel"])
        number, name, value = state["rows"][1]
        self.assertEqual(self.top.current(), number)

    def test_hidden_on_exit_and_sent_over_bcp(self):
        sent = []
        bridge = self.tron.media
        with mock.patch.object(bridge, "connected", lambda need_data=True: not need_data), \
                mock.patch.object(self.machine, "bcp", mock.Mock(), create=True):
            self.machine.bcp.interface.bcp_trigger = lambda **kw: sent.append(kw)
            self.machine.bcp.interface.bcp_trigger_client = lambda client, **kw: sent.append(kw)
            self.enter()
            self.press("back")
        states = [json.loads(kw["state"]) for kw in sent if kw.get("name") == "service_backglass"]
        self.assertEqual("entry", states[0]["kind"])
        self.assertEqual("menu", states[1]["kind"])
        self.assertEqual({"show": False}, states[-1])
        self.assertEqual({"show": False}, self.state)

    def test_device_table(self):
        """Every playfield switch and matrix lamp of the MPF Monitor layout is placed; every lamp has its
        insert colour (game/monitor/light_colors.csv) but the cabinet's."""
        self.enter()
        devices = bg.devices(self.svc)
        placed = [n for n, d in devices["switches"].items() if d["at"]]
        self.assertGreater(len(placed), 40)
        self.assertTrue(all(d["at"] for d in devices["lamps"].values()))
        colors = bg._colors(self.machine)
        self.assertGreaterEqual(len(set(devices["lamps"]) & set(colors)), 60)    # the cabinet buttons: white
        self.assertTrue(all(len(d["color"]) == 7 for d in devices["lamps"].values()))
        self.assertTrue(any(d["flasher"] for d in devices["coils"].values()))

    def test_matrix_cell(self):
        self.assertEqual([1, 1], bg.matrix_cell("1"))
        self.assertEqual([5, 4], bg.matrix_cell("36"))
        self.assertEqual(["D", 3], bg.matrix_cell("D3"))
        self.assertIsNone(bg.matrix_cell("aux_strobe_0x10"))


class TestStill(ServiceCase):

    def test_background_video_from_screens_pup(self):
        with tempfile.TemporaryDirectory() as pack:
            os.makedirs(os.path.join(pack, "Background - Backglass"))
            with open(os.path.join(pack, "Background - Backglass", "BG.mp4"), "wb") as f:
                f.write(b"")
            with open(os.path.join(pack, "screens.pup"), "w", encoding="utf-8") as f:
                f.write('ScreenNum,ScreenDes,PlayList,PlayFile,Loopit,Active,Priority,CustomPos\n'
                        '13,"Topper - Underlay","Background - Topper",,0,off,0,"0,0,0,100,100"\n'
                        '2,"Backglass - Underlay","Background - Backglass",BG.mp4,0,ForceBack,90,\n')
            self.assertEqual(os.path.join(pack, "Background - Backglass", "BG.mp4"), gen_pup.background_video(pack))
            os.remove(os.path.join(pack, "screens.pup"))
            self.assertIsNone(gen_pup.background_video(pack))


class TestNetworkAndScorbit(NetworkCase):
    """The NETWORK and SCORBIT menus (UTILITIES, added by this game) on the backglass."""

    def test_menus_networks_password_and_pairing(self):
        self.enter()
        self.goto("GO TO UTILITIES MENU")
        state = self.svc.backglass
        network = next(i for i in state["items"] if i["text"] == "GO TO NETWORK MENU")
        self.assertIn("SCAN WI-FI NETWORKS", [c[0] for c in network["children"]])
        self.goto("GO TO NETWORK MENU", "SCAN WI-FI NETWORKS")
        state = self.svc.backglass
        self.assertEqual("rows", state["kind"])
        self.assertEqual([[1, "GRID", "80%  SECURED"], [2, "ARCADE", "40%  OPEN"]], state["rows"])
        self.press("plus")
        self.assertEqual(1, self.svc.backglass["sel"])
        self.press("minus")
        self.press("select")                              # a secured network: its password
        self.press("select")                              # a
        self.press("plus")
        state = self.svc.backglass
        self.assertEqual("text", state["kind"])
        self.assertEqual("*", state["text"])              # the password never shows on the backglass
        self.assertEqual("*", state["char"])
        self.assertEqual([1, 63], state["count"])
        self.assertEqual("a", self.shown[-1][1])           # the DMD shows it, as the ROM's editors do

    def test_hidden_network_name_shows(self):
        self.enter()
        self.goto("GO TO UTILITIES MENU", "GO TO NETWORK MENU", "JOIN HIDDEN NETWORK")
        self.press("select")
        self.assertEqual("a", self.svc.backglass["text"])

    def test_pairing_code_is_big(self):
        self.enter()
        self.goto("GO TO UTILITIES MENU", "GO TO SCORBIT MENU", "SCORBIT PAIRING")
        state = self.svc.backglass
        self.assertEqual("message", state["kind"])
        self.assertTrue(state["big"])
        self.assertEqual(self.top.lines()[1:], state["lines"])
