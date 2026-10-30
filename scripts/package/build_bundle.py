#!/usr/bin/env python3
"""Build the prebuilt game bundle in format 2 (MPF-Godot-Packaging platforms/game-bundle-format2.md): files and facts only, the
platform launches the game. The bundle holds the game as it runs (generated config, media, sounds, Godot import), the add-on
"pup_art" (HD clips, letters, service still: made once by scripts/pup/pup_setup.py from the PuP Pack, copied here as they are),
the PuP manifest (the list of the pack's files; the pack itself is the author's zip, assigned on the platform's page), the
settings schema and the board profiles as data. No binary, no Serum or ZeDMD program (the platform's), no start script.

    python scripts/package/build_bundle.py --target all          # universal: arm64 + x86_64 textures, no binary
    python scripts/package/build_bundle.py --target x86_64       # a PC only
    python scripts/package/build_bundle.py --version 2026.10.24 --out /some/folder

The builder is the platform's, the same for every game: `python -m mpf_godot bundle` in MPF-Godot-Packaging
(set MPF_GODOT_PACKAGING to its checkout; default: a folder beside this repository). This file is what is Tron's:
which files the game reads (the lists below), the options schema and tool, the board profiles, the PuP install, and
the check that the generated media are current. It writes the game's bundle spec and calls the platform.

No binary is in the bundle: GoZen and the other add-ons come from the platform (bundle.json platform_addons).
Needs a workspace that scripts/setup.py has finished. No ROM, no PuP Pack, no credentials.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # scripts/
import gen_media  # noqa: E402  (HD_FRAME_IMPORT only)
import toolchain as tc  # noqa: E402
sys.path.insert(0, HERE)

ROOT = tc.ROOT
NAME = "tron-legacy-mpf"

# the few scripts the game's Python reads at run time (the remote topper finds the platform through mpf_platform.py)
SCRIPTS = ["mpf_platform.py", "toolchain.py", "fsutil.py"]

# generated once by scripts/setup.py (media, sounds, fonts) and shipped as they are; game/media minus dmd_clip (an add-on)
GENERATED = ["game/config/rom", "game/sounds", "game/slides/deffs", "game/tron/media_data.json",
             "game/fonts", "game/fonts_ttf/baked", "game/addons/mpf-gmc"]
MEDIA_NOT_COPIED = {"dmd_clip"}

ADDON = "addons/pup_art"                 # in the work tree and in the bundle
MANIFEST = "pup/manifest.json"

ASSET_FILES = ["assets/mpf_package/event_map.csv", "assets/mpf_package/lamp_effects.csv",
               "assets/mpf_package/service_menu.json", "assets/mpf_package/media/rom_images_all.zip"]

ASSET_DIRS = ["assets/mpf_package/config", "assets/rom_data/io", "assets/rom_data/pro", "assets/rom_data/settings",
              "assets/rom_data/deffs", "assets/io", "assets/callouts"]

ASSET_GLOBS = [("assets/mpf_package/media/dmd", "timing.json")]

NEVER = ["pup_media/trn_174h/dmd_art", "game/data", "game/audits", "game/logs", "game/monitor/logs", "game/monitor/settings.ini",
         "game/monitor/settings.ini.lock", "game/pup.local.cfg", "game/scorbit.local.cfg", "game/options.json",
         "game/.godot"]


def platform_dir():
    for c in (os.environ.get("MPF_GODOT_PACKAGING"), os.path.join(os.path.dirname(ROOT), "MPF-Godot-Packaging"),
              os.path.join(os.path.dirname(ROOT), "MPF-Godot")):
        if c and os.path.isfile(os.path.join(c, "mpf_godot", "bundle.py")):
            return c
    raise SystemExit("MPF-Godot-Packaging not found: clone it beside this repository or set MPF_GODOT_PACKAGING")


def check_workspace():
    problems = []
    if tc.media_stale():
        problems.append("the generated media are out of date: " + tc.media_stale())
    for rel in ("assets/mpf_package/service_menu.json", "game/config/rom", "game/media", "game/sounds",
                "game/addons/mpf-gmc/plugin.cfg", "game/fonts_ttf/baked"):
        if not os.path.exists(os.path.join(ROOT, rel)):
            problems.append("missing " + rel)
    if problems:
        raise SystemExit("the workspace is not ready (run `python scripts/setup.py` first):\n  " + "\n  ".join(problems))


def generated():
    """GENERATED that exists in the work tree, plus game/media folder by folder (dmd_clip is an add-on, not copied here)."""
    out = [rel for rel in GENERATED if os.path.exists(os.path.join(ROOT, rel))]
    media = os.path.join(ROOT, "game", "media")
    if os.path.isdir(media):
        out += ["game/media/" + n for n in sorted(os.listdir(media)) if n not in MEDIA_NOT_COPIED]
    return out


def stage_pup_files():
    """Copies, never generates: the PuP manifest (scripts/pup/gen_pup.py wrote it when the pack was installed on this
    builder) to pup/manifest.json, and the add-on folder from the files that setup made once from the pack. Returns what is missing."""
    missing = []
    src = os.path.join(ROOT, "pup_media", "trn_174h", "manifest.json")
    if os.path.exists(src):
        os.makedirs(os.path.join(ROOT, "pup"), exist_ok=True)
        shutil.copy2(src, os.path.join(ROOT, MANIFEST))
    else:
        missing.append("pup_media/trn_174h/manifest.json (install the PuP Pack with scripts/pup/pup_setup.py)")
    addon = os.path.join(ROOT, ADDON)
    shutil.rmtree(addon, ignore_errors=True)
    for from_rel, to_rel in (("game/media/dmd_clip", "dmd_clip"), ("game/hd_art/letters", "hd_art/letters"),
                             ("pup_media/trn_174h/service", "service")):
        full = os.path.join(ROOT, from_rel)
        if os.path.isdir(full):
            shutil.copytree(full, os.path.join(addon, to_rel), ignore=shutil.ignore_patterns("*.import"))
        else:
            missing.append(from_rel)
    return missing


def spec(template):
    """The format 2 spec the platform's builder reads (mpf_godot/bundle.py): files and facts, no command."""
    with open(os.path.join(HERE, "profiles.json"), encoding="utf-8") as f:
        old = json.load(f)
    profiles = {}
    for pr in old["profiles"]:
        if pr["id"] != "rpi4":
            continue
        limits = {k: v["choices"] for k, v in pr["limits"].items()}
        limits["pup.dmd.window"] = [c for c in limits["pup.dmd.window"] if c != "auto"]
        defaults = {k: v for k, v in pr["install"]["options"].items() if k in limits or k == "pup.third_screen"}
        defaults["pup.dmd.window"] = "overlay"
        profiles["rpi4"] = {"limits": limits, "defaults": defaults}
    asset_globs = []
    for folder, name in ASSET_GLOBS:
        for d in sorted(os.listdir(os.path.join(ROOT, folder))) if os.path.isdir(os.path.join(ROOT, folder)) else ():
            if os.path.exists(os.path.join(ROOT, folder, d, name)):         # a folder of the assets without one (flow_attract_cycle)
                asset_globs.append("{}/{}/{}".format(folder, d, name))
    return {
        "format": 2,
        "id": NAME,
        "name": "Tron Legacy (Stern 2011), MPF recreation",
        "game_dir": "game",
        "git_tracked": ["game"],
        "git_exclude": ["game/addons/", "game/native/"],        # add-ons and the Serum colouriser are the platform's
        "copy": ["scripts/" + s for s in SCRIPTS] + generated() + ASSET_FILES + ASSET_DIRS + asset_globs
                + ["scripts/package/settings.json", MANIFEST, ADDON],
        "never": NEVER,
        "never_names": ["*.local.cfg", "machine_vars.yaml", "scorbit_device_key.txt"],
        "import_seed": [{"dir": "game/media/dmd_hd", "skip_prefixes": ["solid", "hollow"], "template": template}],
        "platform_addons": ["gde_gozen", "dmd_out"],            # the game ships its own patched GMC (rule 4)
        "source_commits": {"assets_commit": "HEAD:assets"},
        "requires": {"python": ">=3.10",
                     "python_packages": [r for r in tc.REQUIREMENTS if not r.startswith("pytest")]},
        "mpf": {"configs": ["config"],
                "hardware": {"virtual": ["hw_virtual", "free_play"], "virtual_coins": ["hw_virtual"],
                             "virtual_le": ["hw_virtual_le", "free_play"], "proc": ["hw_proc"], "proc_le": ["hw_proc_le"],
                             "proc_fiber": ["hw_proc", "fiber_optics"]}},
        "dmd": {"rom": "trn_174h", "size": "128x32"},
        "pup": {"rom": "trn_174h", "manifest": MANIFEST},
        "addons": [{"id": "pup_art", "dir": ADDON, "setting": "dmd.mode", "when": "hd"}],
        "settings": {"schema": "scripts/package/settings.json"},
        "profiles": profiles,
        "keep_on_update": ["game/data", "game/audits", "game/logs", "game/pup.local.cfg", "game/scorbit.local.cfg"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--target", choices=["arm64", "x86_64", "all"], default="all",
                   help="arm64: Raspberry Pi 4 and Jetson (ETC2/ASTC textures); x86_64: a PC (S3TC/BPTC); all: both")
    p.add_argument("--version", help="default: the date and the short commit, 2026.10.24-ab12cd3")
    p.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the archive goes (default dist/)")
    p.add_argument("--no-archive", action="store_true", help="stop after staging; leave the folder")
    args = p.parse_args(argv)
    check_workspace()
    missing = stage_pup_files()
    if missing:
        print("warning: no PuP add-on part for: " + ", ".join(missing), flush=True)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    template = os.path.join(out, "hd_frame.import.template")
    with open(template, "w", encoding="utf-8", newline="\n") as f:
        f.write(gen_media.HD_FRAME_IMPORT)
    spec_path = os.path.join(ROOT, ".bundle_spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec(os.path.relpath(template, ROOT)), f, indent=2)
    cmd = [sys.executable, "-m", "mpf_godot", "bundle", spec_path, "--target", args.target, "--out", out]
    if args.version:
        cmd += ["--version", args.version]
    if args.no_archive:
        cmd.append("--no-archive")
    env = dict(os.environ, PYTHONPATH=platform_dir(), GODOT=os.environ.get("GODOT") or tc.godot_path())
    try:
        return subprocess.run(cmd, env=env, cwd=ROOT).returncode
    finally:
        os.remove(spec_path)


if __name__ == "__main__":
    sys.exit(main())
