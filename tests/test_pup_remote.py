"""The game's side of the remote topper: the settings option and the cfg keys. The server, its media list, the PinUP rules and
the Raspberry Pi agent and image are the platform's (MPF-Godot-Packaging, mpf_godot/pup_remote/, tested there)."""
import json
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestRemoteSettings(unittest.TestCase):

    def test_option_targets_the_remote_section(self):
        with open(os.path.join(ROOT, "scripts", "package", "settings.json"), encoding="utf-8") as f:
            options = {o["id"]: o for o in json.load(f)["options"]}
        self.assertEqual({"ini": "game/pup.local.cfg", "section": "remote", "key": "enabled"}, options["remote.enabled"]["target"])
        self.assertFalse(options["remote.enabled"]["default"])
        self.assertEqual("remote", options["remote.port"]["target"]["section"])

    def test_cfg_has_the_keys_mode_reads(self):
        text = open(os.path.join(ROOT, "game", "pup.cfg"), encoding="utf-8").read()
        section = text[text.index("[remote]"):]
        for key in ("enabled", "port", "listen", "discovery", "media_port"):
            self.assertRegex(section, r"(?m)^%s=" % re.escape(key))


if __name__ == "__main__":
    unittest.main()
