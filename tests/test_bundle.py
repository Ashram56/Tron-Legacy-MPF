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
        # run.py's imports, found by reading it: every module is in the list
        src = open(os.path.join(ROOT, "scripts", "run.py"), encoding="utf-8").read()
        for mod in re.findall(r"^import (\w+)  # noqa", src, flags=re.M) + re.findall(r"^from (\w+) import", src, flags=re.M):
            if os.path.exists(os.path.join(ROOT, "scripts", mod + ".py")) or os.path.isdir(os.path.join(ROOT, "scripts", mod)):
                self.assertTrue(any(s == mod + ".py" or s.startswith(mod + "/") for s in bb.SCRIPTS), mod)

    def test_texture_formats(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "project.godot")
            shutil.copy(os.path.join(GAME, "project.godot"), path)
            bb.set_texture_formats(path, "etc2")
            text = open(path).read()
            self.assertIn("import_etc2_astc=true", text)
            self.assertIn("import_s3tc_bptc=false", text)
            bb.set_texture_formats(path, "both")      # again: the old lines are replaced, not doubled
            text = open(path).read()
            self.assertEqual(text.count("import_etc2_astc"), 1)
            self.assertIn("import_s3tc_bptc=true", text)
            self.assertIn("thread_model=2", text)       # the rest of [rendering] is kept

    def test_prune_formats_leaves_only_the_target_variant(self):
        with tempfile.TemporaryDirectory() as d:
            imported = os.path.join(d, ".godot", "imported")
            os.makedirs(imported)
            os.makedirs(os.path.join(d, "media"))
            for ext in ("s3tc", "etc2"):
                open(os.path.join(imported, "f.png-{}.{}.ctex".format("a" * 32, ext)), "w").close()
            open(os.path.join(imported, "g.png-{}.ctex".format("b" * 32)), "w").close()
            path = os.path.join(d, "media", "f.png.import")
            with open(path, "w") as f:
                f.write('[remap]\n\nimporter="texture"\npath.s3tc="res://.godot/imported/f.png-{0}.s3tc.ctex"\n'
                        'path.etc2="res://.godot/imported/f.png-{0}.etc2.ctex"\nmetadata={{\n'
                        '"imported_formats": ["s3tc_bptc", "etc2_astc"],\n"vram_texture": true\n}}\n\n[deps]\n\n'
                        'dest_files=["res://.godot/imported/f.png-{0}.s3tc.ctex", '
                        '"res://.godot/imported/f.png-{0}.etc2.ctex"]\n'.format("a" * 32))
            self.assertEqual(bb.prune_formats(d, "etc2"), 1)
            text = open(path).read()
            self.assertNotIn("s3tc.ctex", text)
            self.assertNotIn("path.s3tc", text)
            self.assertIn('path.etc2=', text)
            self.assertIn('"imported_formats": ["etc2_astc"],', text)
            self.assertEqual(bb.count_variants(d), {"etc2": 1, "": 1})
            self.assertEqual(bb.prune_formats(d, "both"), 0)

    def test_seed_imports_only_for_effect_frames(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "game", "media", "dmd_hd", "deff_001")
            os.makedirs(folder)
            for name in ("f000.png", "solid0.png", "hollow0.png"):
                open(os.path.join(folder, name), "w").close()
            open(os.path.join(d, "game", "media", "dmd_hd", "scale.json"), "w").close()
            self.assertEqual(bb.seed_imports(d), 1)
            self.assertTrue(os.path.exists(os.path.join(folder, "f000.png.import")))
            self.assertFalse(os.path.exists(os.path.join(folder, "solid0.png.import")))
            self.assertIn("compress/mode=2", open(os.path.join(folder, "f000.png.import")).read())

    def test_a_bundle_is_never_stale(self):
        import toolchain as tc
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNotNone(tc.media_stale(d))             # no stamp: stale
            open(os.path.join(d, "bundle.json"), "w").close()
            self.assertIsNone(tc.media_stale(d))

    def test_cabinet_data_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "game", "data"))
            self.assertEqual(bb.forbidden(d), ["game/data"])
            os.makedirs(os.path.join(d, "game", "x"))
            open(os.path.join(d, "game", "x", "scorbit.local.cfg"), "w").close()
            self.assertIn(os.path.join("game", "x", "scorbit.local.cfg"), bb.forbidden(d))

    def test_manifest(self):
        m = bb.manifest("v1", "arm64", "etc2", {})
        self.assertEqual(m["format"], 1)
        self.assertEqual(m["run"]["start"], "python3 scripts/package/start.py")
        self.assertEqual(m["requires"]["godot"], "4.6.3")
        self.assertNotIn("pytest", " ".join(m["requires"]["python_packages"]))
        self.assertEqual(m["options"]["count"], len(bo.load_schema()["options"]))
        json.dumps(m)

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
