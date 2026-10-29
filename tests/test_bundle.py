"""The prebuilt bundle (docs/bundle.md): the options schema and tool (scripts/package/bundle_options.py), the saved
flags start.py adds to run.py, and the bundle builder's rules. The build itself (a Godot import) is not run here."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "package"))
import build_bundle as bb  # noqa: E402
import bundle_options as bo  # noqa: E402
import start  # noqa: E402

GAME = os.path.join(ROOT, "game")


def option(oid):
    return bo.by_id(bo.load_schema())[oid]


class TestSchema(unittest.TestCase):

    def test_ids_unique_and_typed(self):
        schema = bo.load_schema()
        ids = [o["id"] for o in schema["options"]]
        self.assertEqual(len(ids), len(set(ids)))
        groups = {g["id"] for g in schema["groups"]}
        for o in schema["options"]:
            self.assertIn(o["group"], groups, o["id"])
            self.assertIn(o["type"], ("bool", "integer", "number", "choice", "color", "size", "text"), o["id"])
            if o["type"] == "choice":
                self.assertIn(o["default"], o["choices"], o["id"])
            bo.convert(o, o["default"]) if o["default"] != "" else None

    def test_cfg_targets_exist_in_the_default_files(self):
        """A key the web page sets must be one the game reads: it has to be in the shipped cfg (pup.cfg, scorbit.cfg)."""
        for o in bo.load_schema()["options"]:
            t = o["target"]
            if "cfg" in t:
                shipped = os.path.join(GAME, t["cfg"].replace(".local", ""))
                self.assertIsNotNone(bo.cfg_read(shipped, t["section"], t["key"]), o["id"])

    def test_flags_are_run_py_flags(self):
        help_text = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "run.py"), "--help"],
                                   capture_output=True, text=True, timeout=60).stdout
        for o in bo.load_schema()["options"]:
            t = o["target"]
            for flag in (t.get("arg"), t.get("flag"), t.get("flag_off")):
                if flag:
                    self.assertIn(flag, help_text, o["id"])

    def test_defaults_match_the_game(self):
        project = open(os.path.join(GAME, "project.godot"), encoding="utf-8").read()
        self.assertEqual(float(re.search(r"dmd/text_glow=([\d.]+)", project).group(1)), option("dmd.text_glow")["default"])
        self.assertEqual(float(re.search(r"dmd/text_scale=([\d.]+)", project).group(1)), option("dmd.text_scale")["default"])
        self.assertEqual(re.search(r'dmd/font="(\w+)"', project).group(1), option("dmd.font")["default"])


class TestOptions(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_convert(self):
        self.assertEqual(bo.convert(option("pup.enabled"), "off"), False)
        self.assertEqual(bo.convert(option("dmd.text_glow"), "1.5"), 1.5)
        self.assertEqual(bo.convert(option("dmd.text_color"), "2A6CFF"), "#2a6cff")
        self.assertEqual(bo.convert(option("dmd.size"), "1920X480"), "1920x480")
        self.assertEqual(bo.convert(option("dmd.tint"), "Orange"), "orange")
        for oid, bad in (("dmd.text_glow", "5"), ("dmd.text_scale", "1.6"), ("dmd.size", "big"), ("dmd.tint", "red"),
                         ("pup.video_volume", "101"), ("pup.enabled", "maybe"), ("dmd.text_color", "blue"),
                         ("pup.video_volume", "1.5")):
            with self.assertRaises(bo.OptionError, msg=oid):
                bo.convert(option(oid), bad)

    def test_set_get_unset_and_flags(self):
        bo.set_values({"dmd.text_glow": "1.2", "dmd.font": "orbitron", "pup.ost_music": "false",
                       "machine.free_play": "no", "machine.fiber_optics": "true", "dmd.size": "1920x480"}, self.dir)
        got = bo.get_values(game=self.dir)
        self.assertEqual(got, {"dmd.text_glow": 1.2, "dmd.font": "orbitron", "pup.ost_music": False,
                               "machine.free_play": False, "machine.fiber_optics": True, "dmd.size": "1920x480"})
        self.assertEqual(bo.run_args(self.dir),
                         ["--dmd-font", "orbitron", "--dmd-text-glow", "1.2", "--dmd-size", "1920x480",
                          "--no-free-play", "--fiber-optics"])
        self.assertIn("ost_music=false", open(os.path.join(self.dir, "pup.local.cfg")).read())
        bo.unset_values(["dmd.text_glow", "pup.ost_music"], self.dir)
        self.assertNotIn("dmd.text_glow", bo.get_values(game=self.dir))
        self.assertNotIn("pup.ost_music", bo.get_values(game=self.dir))

    def test_nothing_is_written_when_one_value_is_bad(self):
        with self.assertRaises(bo.OptionError):
            bo.set_values({"dmd.font": "orbitron", "dmd.tint": "red"}, self.dir)
        self.assertEqual(bo.get_values(game=self.dir), {})

    def test_cfg_keeps_other_lines_and_sections(self):
        path = os.path.join(self.dir, "pup.local.cfg")
        with open(path, "w") as f:
            f.write("; mine\n[dmd]\nscreen=1\nsize=[960, 193]\n\n[pup]\nlayout=\"manual\"\n")
        bo.set_values({"pup.dmd.dmd_size": "full", "pup.layout": "stack", "pup.backglass.enabled": "false"}, self.dir)
        text = open(path).read()
        self.assertIn("; mine", text)
        self.assertIn("screen=1", text)
        self.assertIn("size=[960, 193]", text)
        self.assertEqual(bo.cfg_read(path, "dmd", "dmd_size"), '"full"')
        self.assertEqual(bo.cfg_read(path, "pup", "layout"), '"stack"')
        self.assertEqual(text.count("layout="), 1)
        self.assertEqual(bo.cfg_read(path, "backglass", "enabled"), "false")

    def test_pup_settings_read_what_is_written(self):
        sys.path.insert(0, GAME)
        from tron_pup import settings
        bo.set_values({"pup.video_volume": "40", "pup.dmd.dmd_size": "full", "pup.third_screen": "no"}, self.dir)
        shutil.copy(os.path.join(GAME, "pup.cfg"), self.dir)
        cfg = settings.load(self.dir)
        self.assertEqual(cfg["pup"]["video_volume"], 40)
        self.assertEqual(cfg["pup"]["third_screen"], False)
        self.assertEqual(cfg["dmd"]["dmd_size"], "full")

    def test_scorbit_secret_is_private_and_not_returned(self):
        key = "A" * 104
        bo.set_values({"scorbit.provider": "tron", "scorbit.machine_id": "1234", "scorbit.encrypted_key": key}, self.dir)
        path = os.path.join(self.dir, "scorbit.local.cfg")
        if os.name == "posix":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(bo.get_values(game=self.dir)["scorbit.encrypted_key"], {"set": True})
        self.assertNotIn(key, json.dumps(bo.get_values(game=self.dir)))
        sys.path.insert(0, GAME)
        from tron import scorbit
        shutil.copy(os.path.join(GAME, "scorbit.cfg"), self.dir)
        cfg = scorbit.load_config(self.dir)
        self.assertEqual((cfg["provider"], cfg["machine_id"], cfg["encrypted_key"]), ("tron", "1234", key))

    def test_start_merges_saved_flags_under_given_ones(self):
        saved = ["--dmd-font", "orbitron", "--no-free-play", "--dmd-size", "1920x480"]
        self.assertEqual(start.merge(saved, ["--dmd-font=rom", "--free-play", "--seconds", "5"]),
                         ["--dmd-size", "1920x480", "--dmd-font=rom", "--free-play", "--seconds", "5"])
        self.assertEqual(start.merge(saved, []), saved)


class TestBuilder(unittest.TestCase):

    def test_scripts_exist_and_import_nothing_else(self):
        for rel in bb.SCRIPTS:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "scripts", rel)), rel)
        # what the bundle's start script reaches, followed through every file it imports (not only run.py's own imports: a module
        # imported by an imported module was missing once, 2026-10-29, and the service restarted every 10 s)
        import ast
        scripts = os.path.join(ROOT, "scripts")
        listed = {s.split("/")[0][:-3] if s.endswith(".py") and "/" not in s else s.split("/")[0] for s in bb.SCRIPTS}
        local = lambda mod: (os.path.exists(os.path.join(scripts, mod + ".py")) or os.path.isdir(os.path.join(scripts, mod)))  # noqa: E731
        seen, queue, missing = set(), [os.path.join(scripts, "package", "start.py")], []
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            tree = ast.parse(open(path, encoding="utf-8").read())
            names = []
            for node in tree.body:                       # the statements that run on import (not functions: they are optional)
                if isinstance(node, ast.Import):
                    names += [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names.append(node.module.split(".")[0])
            for mod in names:
                if not local(mod):
                    continue
                if mod not in listed and mod != "package":
                    missing.append(f"{os.path.relpath(path, scripts)} imports {mod}")
                target = os.path.join(scripts, mod + ".py")
                if os.path.exists(target):
                    queue.append(target)
        self.assertEqual(missing, [], "listed in SCRIPTS (scripts/package/build_bundle.py)")

    def test_a_bundle_is_never_stale(self):
        import toolchain as tc
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNotNone(tc.media_stale(d))             # no stamp: stale
            open(os.path.join(d, "bundle.json"), "w").close()
            self.assertIsNone(tc.media_stale(d))

    def test_spec(self):
        """What the platform's builder (MPF-Godot-Packaging mpf_godot/bundle.py) is given."""
        sp = bb.spec("t")
        self.assertEqual(sp["platform_addons"], ["gde_gozen"])
        self.assertEqual(sp["git_exclude"], ["game/addons/"])        # no binary add-on from the game's tree
        self.assertEqual(sp["run"]["start"], "python3 scripts/package/start.py")
        self.assertNotIn("pytest", " ".join(sp["requires"]["python_packages"]))
        self.assertEqual(sp["options"]["count"], len(bo.load_schema()["options"]))
        self.assertIn("*.local.cfg", sp["never_names"])
        json.dumps(sp)

    @unittest.skipUnless(os.path.isdir(os.path.join(ROOT, "assets", "mpf_package")), "needs the assets submodule")
    def test_asset_files_exist(self):
        for rel in bb.ASSET_FILES + bb.ASSET_DIRS:
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)

    def test_never_list_covers_the_ignored_cabinet_files(self):
        ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
        for rel in ("game/data/", "game/audits/", "game/logs/", "game/pup.local.cfg", "game/scorbit.local.cfg"):
            self.assertIn(rel, ignore)
            self.assertIn(rel.rstrip("/"), bb.NEVER)


if __name__ == "__main__":
    unittest.main()


class TestBoardProfile(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "package"))
        import board_profile
        self.bp = board_profile
        self.saved = os.environ.pop("TRON_BOARD_PROFILE", None)

    def tearDown(self):
        if self.saved is not None:
            os.environ["TRON_BOARD_PROFILE"] = self.saved

    def test_profiles_are_valid(self):
        schema = bo.by_id(bo.load_schema())
        for p in self.bp.load():
            for oid, value in p.get("install", {}).get("options", {}).items():
                self.assertEqual(bo.convert(schema[oid], value), value, oid)   # a known option, a valid value
            for name in p.get("install", {}).get("cfg", {}):
                self.assertTrue(os.path.exists(os.path.join(GAME, name.replace(".local", ""))), name)
            for a in p.get("run", {}).get("godot_args", []):
                self.assertTrue(a["args"] and a["args"][0].startswith("--"))

    def test_detect_by_device_tree(self):
        profiles = self.bp.load()
        self.assertEqual(self.bp.detect(profiles, ["Raspberry Pi 4 Model B Rev 1.1"])["id"], "rpi4")
        self.assertEqual(self.bp.detect(profiles, ["raspberrypi,4-model-b", "brcm,bcm2711"])["id"], "rpi4")
        self.assertIsNone(self.bp.detect(profiles, ["NVIDIA Jetson Xavier NX Developer Kit"]))
        self.assertIsNone(self.bp.detect(profiles, []))
        os.environ["TRON_BOARD_PROFILE"] = "rpi4"
        self.assertEqual(self.bp.detect(profiles, [])["id"], "rpi4")

    def test_apply_sets_only_what_is_unset_and_only_once(self):
        profile = next(p for p in self.bp.load() if p["id"] == "rpi4")
        with tempfile.TemporaryDirectory() as game:
            bo.set_values({"machine.model": "le"}, game=game)
            path = os.path.join(game, "pup.local.cfg")
            bo.cfg_write(path, "dmd", "window", "false")
            self.bp.apply(profile, game=game)
            self.assertEqual(bo.get_values(["machine.model"], game=game), {"machine.model": "le"})    # the operator's
            self.assertEqual(bo.cfg_read(path, "dmd", "window"), "false")
            self.assertEqual(bo.cfg_read(path, "backglass", "render_size"), "[1280, 720]")
            self.assertEqual(bo.get_values(["pup.third_screen"], game=game), {"pup.third_screen": False})
            bo.cfg_write(path, "backglass", "render_size", None)                         # removed by the operator
            self.assertIn("earlier install", self.bp.apply(profile, game=game)[0])
            self.assertIsNone(bo.cfg_read(path, "backglass", "render_size"))

    def test_limits_narrow_the_schema_and_are_put_back(self):
        profile = next(p for p in self.bp.load() if p["id"] == "rpi4")
        limits = profile["limits"]
        full = bo.by_id(bo.load_schema(limits={}))
        for oid, limit in limits.items():
            self.assertTrue(limit["why"] and set(limit["choices"]) < set(full[oid]["choices"]), oid)
            value = profile["install"]["options"].get(oid)
            self.assertTrue(value is None or value in limit["choices"], oid)
        narrow = bo.by_id(bo.load_schema(limits=limits))
        self.assertEqual(narrow["dmd.mode"]["choices"], limits["dmd.mode"]["choices"])
        self.assertIn("limited", narrow["dmd.mode"])
        with self.assertRaises(bo.OptionError):
            bo.convert(narrow["dmd.mode"], "hd")
        os.environ["TRON_BOARD_PROFILE"] = "rpi4"                              # what the settings page sees on a Pi
        self.assertNotIn("hd", bo.by_id(bo.load_schema())["dmd.mode"]["choices"])
        with tempfile.TemporaryDirectory() as game:
            with self.assertRaises(bo.OptionError):
                bo.set_values({"dmd.mode": "hd"}, game=game)
            bo.store_write({"dmd.mode": "hd"}, game=game)                       # set before, or by hand
            path = os.path.join(game, "pup.local.cfg")
            bo.cfg_write(path, "dmd", "window", "true")                          # the older spelling of "window"
            bo.cfg_write(path, "dmd", "background", '"frame"')
            log = self.bp.enforce(profile, game=game)
            self.assertEqual(bo.get_values(["dmd.mode", "pup.dmd.window", "pup.dmd.background"], game=game),
                             {"dmd.mode": "classic", "pup.dmd.window": "auto", "pup.dmd.background": "frame"})
            self.assertEqual(len(log), 2)
            self.assertEqual(self.bp.enforce(profile, game=game), [])
            bo.unset_values(["pup.dmd.background"], game=game)                  # the game's default: light cycles
            self.assertIn("pup.dmd.background", self.bp.enforce(profile, game=game)[0])
            self.bp.apply(profile, game=game)
            bo.store_write({"dmd.mode": "hd"}, game=game)
            self.assertIn("instead of", self.bp.apply(profile, game=game)[0])    # limits hold after the first install

    def test_run_settings_and_godot_args(self):
        profile = {"id": "t", "run": {"env": [{"name": "A", "value": "1", "if": {"file": "/nonexistent/{kernel}"}},
                                              {"name": "B", "value": "2"}],
                                      "godot_args": [{"args": ["--max-fps", "30"]},
                                                     {"args": ["--render-thread", "separate"], "if": {"env": "NOPE_X"}}]}}
        os.environ.pop("NOPE_X", None)
        self.assertEqual(self.bp.run_settings(profile), ({"B": "2"}, ["--max-fps", "30"]))
        os.environ["NOPE_X"] = "1"
        try:
            self.assertEqual(self.bp.run_settings(profile)[1], ["--max-fps", "30", "--render-thread", "separate"])
        finally:
            del os.environ["NOPE_X"]
        self.assertEqual(self.bp.add_godot_args(["--dmd", "classic"], ["--max-fps", "30"]),
                         ["--dmd", "classic", "--", "--max-fps", "30"])
        self.assertEqual(self.bp.add_godot_args(["--", "--max-fps", "60"], ["--max-fps", "30", "--fullscreen"]),
                         ["--", "--max-fps", "60", "--fullscreen"])
        self.assertEqual(self.bp.add_godot_args(["--seconds", "5"], []), ["--seconds", "5"])


class TestDmdPanel(unittest.TestCase):
    """start.py's [dmd] window="auto": the detection itself is the platform's (mpf_godot.dmd_panel, tested there)."""

    def test_start_auto(self):
        saved = os.environ.pop("TRON_DMD_PANEL", None)
        self.addCleanup(lambda: os.environ.pop("TRON_DMD_PANEL", None) if saved is None else
                        os.environ.__setitem__("TRON_DMD_PANEL", saved))
        args = ["--hw", "proc", "--", "--max-fps", "30"]
        self.assertEqual(start.dmd_panel_args(list(args), "stacked", find=lambda: self.fail("looked")), args)
        self.assertEqual(start.dmd_panel_args(list(args), "auto", find=lambda: ""), args)
        self.assertEqual(os.environ["TRON_DMD_PANEL"], "")
        os.environ.pop("TRON_DMD_PANEL")
        out = start.dmd_panel_args(list(args), "auto", find=lambda: "zedmd")
        self.assertEqual(os.environ["TRON_DMD_PANEL"], "zedmd")
        self.assertEqual(out, ["--hw", "proc", "--zedmd", "--", "--max-fps", "30"])
        self.assertEqual(start.add_run_flag(["--zedmd", "--", "--x"], "--zedmd"), ["--zedmd", "--", "--x"])
