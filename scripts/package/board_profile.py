#!/usr/bin/env python3
"""The settings of the board the bundle runs on (scripts/package/profiles.json, docs/bundle.md). Standard library only.

    python scripts/package/board_profile.py detect     # the profile id of this board, or nothing
    python scripts/package/board_profile.py apply      # at install: its settings, only those nobody has set; once
    python scripts/package/board_profile.py run        # what start.py adds at each start (env, Godot arguments)

TRON_BOARD_PROFILE=<id> picks a profile by hand, TRON_BOARD_PROFILE=none turns them off. The profile applied at
install is recorded in game/data/board_profile.json: a later install of the same profile changes nothing, so a
setting the operator removed stays removed.
"""
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bundle_options as bo  # noqa: E402

PROFILES = os.path.join(HERE, "profiles.json")
DEVICE_TREE = ("/proc/device-tree/model", "/proc/device-tree/compatible")
RECORD = os.path.join("data", "board_profile.json")    # in game/


def load(path=PROFILES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["profiles"]


def board_names(files=DEVICE_TREE):
    """The board's model and compatible strings (NUL separated in the device tree); empty on a PC."""
    out = []
    for path in files:
        try:
            with open(path, "rb") as f:
                out += [s.decode("utf-8", "replace") for s in f.read().split(b"\0") if s]
        except OSError:
            pass
    return out


def detect(profiles=None, names=None):
    """The matching profile (a dict), or None."""
    profiles = load() if profiles is None else profiles
    forced = os.environ.get("TRON_BOARD_PROFILE", "").strip()
    if forced:
        return next((p for p in profiles if p["id"] == forced), None)
    names = board_names() if names is None else names
    for p in profiles:
        if any(m in n for m in p["match"] for n in names):
            return p
    return None


def holds(cond):
    """A profile's 'if': {"file": path} ({kernel} = uname -r), {"env": name} (set and not 0), or none."""
    if not cond:
        return True
    if "file" in cond:
        return os.path.exists(cond["file"].format(kernel=platform.release()))
    if "env" in cond:
        return os.environ.get(cond["env"], "") not in ("", "0")
    return False


def apply(profile, game=bo.GAME, schema=None):
    """Sets the profile's install settings that are not set yet; returns the lines to log."""
    record = os.path.join(game, RECORD)
    try:
        with open(record, encoding="utf-8") as f:
            if json.load(f).get("profile") == profile["id"]:
                return ["board profile {}: applied at an earlier install, left as it is".format(profile["id"])]
    except (OSError, ValueError):
        pass
    log, inst = [], profile.get("install", {})
    have = bo.get_values(game=game, schema=schema)
    want = {k: v for k, v in inst.get("options", {}).items() if k not in have}
    if want:
        bo.set_values(want, game=game, schema=schema)
    log += ["{} = {} (board profile {})".format(k, json.dumps(v), profile["id"]) for k, v in want.items()]
    for name, sections in inst.get("cfg", {}).items():
        path = bo.cfg_path({"cfg": name}, game)
        for section, keys in sections.items():
            for key, value in keys.items():
                if bo.cfg_read(path, section, key) is None:
                    bo.cfg_write(path, section, key, json.dumps(value))
                    log.append("{} [{}] {}={} (board profile {})".format(name, section, key, json.dumps(value),
                                                                       profile["id"]))
    os.makedirs(os.path.dirname(record), exist_ok=True)
    with open(record, "w", encoding="utf-8") as f:
        json.dump({"profile": profile["id"], "set": log}, f, indent=2)
        f.write("\n")
    return log or ["board profile {}: every setting was already set".format(profile["id"])]


def run_settings(profile):
    """({env name: value}, [Godot arguments]) for this start: the entries whose 'if' holds."""
    env, args = {}, []
    if profile:
        for e in profile.get("run", {}).get("env", []):
            if holds(e.get("if")):
                env[e["name"]] = e["value"]
        for a in profile.get("run", {}).get("godot_args", []):
            if holds(a.get("if")):
                args += a["args"]
    return env, args


def add_godot_args(argv, extra):
    """run.py's arguments with the profile's Godot arguments after its '--', skipping a name given already."""
    argv = list(argv)
    if "--" not in argv:
        argv.append("--")
    given = {a.split("=", 1)[0] for a in argv[argv.index("--") + 1:] if a.startswith("--")}
    i = 0
    while i < len(extra):
        name, value = extra[i], extra[i + 1] if i + 1 < len(extra) and not extra[i + 1].startswith("--") else None
        if name not in given:
            argv += [name] + ([value] if value is not None else [])
        i += 2 if value is not None else 1
    return argv if argv[-1] != "--" else argv[:-1]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "detect"
    profile = None if os.environ.get("TRON_BOARD_PROFILE") == "none" else detect()
    if cmd == "detect":
        print(profile["id"] if profile else "")
    elif cmd == "apply":
        for line in apply(profile) if profile else ["no board profile for this machine"]:
            print(line)
    elif cmd == "run":
        env, args = run_settings(profile)
        print(json.dumps({"profile": profile and profile["id"], "env": env, "godot_args": args}))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
