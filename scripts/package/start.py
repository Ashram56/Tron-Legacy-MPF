#!/usr/bin/env python3
"""Start the installed bundle with its saved settings: scripts/run.py plus the flags in game/options.json.

    python scripts/package/start.py                 # as saved
    python scripts/package/start.py --seconds 20    # any run.py option; one given here wins over the saved one

Settings are changed with scripts/package/bundle_options.py (docs/bundle.md). The board's profile
(scripts/package/board_profile.py) adds its environment and Godot arguments, under the saved and given ones. With the
DMD display on "auto" (`[dmd] window`), it looks for a PIN2DMD or a ZeDMD (scripts/package/dmd_panel.py): the game then
shows the DMD on the panel found, else in the backglass window over the videos.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
sys.path.insert(0, HERE)

import board_profile  # noqa: E402
import bundle_options  # noqa: E402
import dmd_panel  # noqa: E402
import run  # noqa: E402


def merge(saved, given):
    """The saved flags without those the command line sets again (--name or --name=value, either form)."""
    def name(a):                    # --free-play and --no-free-play are one setting
        return a.split("=", 1)[0].replace("--no-", "--", 1)

    names = {name(a) for a in given if a.startswith("--")}
    out, i = [], 0
    while i < len(saved):
        a = saved[i]
        if name(a) in names:
            i += 1 if "=" in a or i + 1 >= len(saved) or saved[i + 1].startswith("--") else 2
            continue
        out.append(a)
        i += 1
    return out + list(given)


def add_run_flag(argv, flag):
    """run.py's arguments with flag before Godot's '--' (none added when it is there already)."""
    head = argv[:argv.index("--")] if "--" in argv else argv
    if any(a.split("=", 1)[0] == flag for a in head):
        return argv
    return head + [flag] + argv[len(head):]


def dmd_panel_args(args, mode, find=dmd_panel.find):
    """For [dmd] window="auto": sets TRON_DMD_PANEL (the game reads it) and, when run.py can drive the panel found,
    asks it to. Returns run.py's arguments."""
    if mode != "auto":
        return args
    panel = os.environ.get("TRON_DMD_PANEL")
    if panel is None:
        panel = find()
        os.environ["TRON_DMD_PANEL"] = panel
    print("DMD display auto: " + ("a {} answers, the DMD goes there".format(panel) if panel else
                                  "no PIN2DMD or ZeDMD answers, the DMD goes over the backglass videos"), flush=True)
    if panel and hasattr(run, "zedmd_feed"):        # run.py's --pin2dmd and --zedmd
        args = add_run_flag(args, "--" + panel)
    return args


def main(argv=None):
    given = list(sys.argv[1:] if argv is None else argv)
    args = merge(bundle_options.run_args(), given)
    profile = None if os.environ.get("TRON_BOARD_PROFILE") == "none" else board_profile.detect()
    if profile:
        env, extra = board_profile.run_settings(profile)
        env = {k: v for k, v in env.items() if k not in os.environ}
        os.environ.update(env)
        args = board_profile.add_godot_args(args, extra)
        print("board profile {}: env {}, Godot {}".format(profile["id"], env or "-", " ".join(extra) or "-"),
              flush=True)
    mode = bundle_options.get_values(["pup.dmd.window"]).get("pup.dmd.window")
    args = dmd_panel_args(args, mode)
    return run.main(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
