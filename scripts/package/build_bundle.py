#!/usr/bin/env python3
"""Build the prebuilt game bundle (docs/bundle.md): the game as it runs, with nothing left to generate or import.

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
import board_profile  # noqa: E402
import bundle_options  # noqa: E402

ROOT = tc.ROOT
NAME = "tron-legacy-mpf"

SCRIPTS = ["run.py", "dmd_out.py", "mpf_platform.py", "toolchain.py", "fsutil.py", "gmc_patch.py", "pup/__init__.py", "pup/pup_setup.py",
           "pup/gen_pup.py", "pup/pup_art.py", "pup/gen_dmd_clips.py", "pup/dmd_clip_plan.json", "pup/letter_art.py", "pup/award_sprites.py",
           "package/__init__.py", "package/start.py", "package/bundle_options.py",
           "package/options.json", "package/board_profile.py", "package/profiles.json"]

GENERATED = ["game/config/rom", "game/sounds", "game/media", "game/slides/deffs", "game/tron/media_data.json",
             "game/fonts", "game/fonts_ttf/baked", "game/addons/mpf-gmc",
             # made from the PuP Pack at the bundle's creation (--pup-zip), shipped as they are: nothing is made on the target
             "game/hd_art/letters", "game/hd_art/deff_105", "pup_media/trn_174h",
             # the ZeDMD feeder and the game's Serum colouriser, built here per CPU (make_feeders): nothing is compiled on the target
             "game/native/bin/arm64", "game/native/bin/x86_64"]

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
    """GENERATED that exists in the work tree; pup_media/<id> folder by folder, without the builder's scratch art folder."""
    out = []
    for rel in GENERATED:
        full = os.path.join(ROOT, rel)
        if rel.startswith("pup_media/") and os.path.isdir(full):
            out += [rel + "/" + n for n in sorted(os.listdir(full)) if n != "dmd_art"]
        elif os.path.exists(full):
            out.append(rel)
    return out


def spec(template):
    """The bundle spec the platform's builder reads (mpf_godot/bundle.py). `template` is the .import text of an HD frame."""
    with open(os.path.join(HERE, "options.json"), encoding="utf-8") as f:
        options = json.load(f)
    asset_globs = []
    for folder, name in ASSET_GLOBS:
        for d in sorted(os.listdir(os.path.join(ROOT, folder))) if os.path.isdir(os.path.join(ROOT, folder)) else ():
            if os.path.exists(os.path.join(ROOT, folder, d, name)):         # a folder of the assets without one (flow_attract_cycle)
                asset_globs.append("{}/{}/{}".format(folder, d, name))
    return {
        "id": NAME,
        "name": "Tron Legacy (Stern 2011), MPF recreation",
        "game_dir": "game",
        "git_tracked": ["game"],
        "git_exclude": ["game/addons/"],
        "copy": ["scripts/" + s for s in SCRIPTS] + generated() + ASSET_FILES + ASSET_DIRS + asset_globs,
        "never": NEVER,
        "never_names": ["*.local.cfg", "machine_vars.yaml", "scorbit_device_key.txt"],
        "import_seed": [{"dir": "game/media/dmd_hd", "skip_prefixes": ["solid", "hollow"], "template": template}],
        "platform_addons": ["gde_gozen"],
        "source_commits": {"assets_commit": "HEAD:assets"},
        "requires": {
            "python": ">=3.10",
            "python_packages": [r for r in tc.REQUIREMENTS if not r.startswith("pytest")],
            "mpf_gmc": tc.GMC_VERSION + " (patched copy included)",
            "programs": ["ffmpeg (PuP install: reads the pack's videos)", "xvfb-run (only without a screen)"],
            "env": {"GODOT": "path of the Godot executable (default tools/godot/ in the bundle)",
                    "TRON_VENV": "folder of the Python venv with MPF (default .venv in the bundle)"},
        },
        "run": {
            "start": "python3 scripts/package/start.py",
            "start_note": "adds the saved options (game/options.json) to scripts/run.py; any run.py flag can follow",
            "cwd": ".",
            "ports": {"5050": "Godot (GMC), localhost only", "5051": "MPF, localhost only (MPF Monitor)"},
        },
        "options": {"schema": "scripts/package/options.json", "tool": "scripts/package/bundle_options.py",
                    "count": len(options["options"])},
        "pup": {
            "installed_from": "the pack's own zip (VP Universe), never in this bundle: the page only unpacks it (extract_only). What the "
                             "game derives from it (pup_media/trn_174h: manifest, still, converted files) is made on the builder (--pup-zip) "
                             "and is in this bundle",
            "extract_only": True,
            "install": "python3 scripts/pup/pup_setup.py --pup-zip ZIP_PATH_OR_URL",
            "status": "python3 scripts/pup/pup_setup.py --status",
            "pack_dir": "pup_pack/trn_174h",
            "needs_restart": True,
        },
        "extra": {"profiles": {"file": "scripts/package/profiles.json",
                               "apply": "python3 scripts/package/board_profile.py apply",
                               "detect": "python3 scripts/package/board_profile.py detect",
                               "ids": [p["id"] for p in board_profile.load()]}},
        "keep_on_update": ["game/data", "game/audits", "game/logs", "game/options.json", "game/pup.local.cfg",
                           "game/scorbit.local.cfg", "pup_pack"],
    }


def make_pup_art(args):
    """Install the pack on this builder and make the art, or stop: a bundle is never left to make it on the target."""
    if args.no_pup_art:
        return
    zip_ = args.pup_zip or os.environ.get("MPF_BUNDLE_PUP_ZIP")
    if not zip_:
        raise SystemExit("give the PuP Pack's zip with --pup-zip ZIP (the art of the HD DMD is made from it here, never on the machine "
                         "that runs the game), or --no-pup-art for a bundle without it")
    env = dict(os.environ, TRON_PUP_ZIP=zip_)
    for cmd in ([sys.executable, os.path.join(HERE, "..", "pup", "pup_setup.py")],):
        if subprocess.run(cmd, cwd=ROOT, env=env).returncode:
            raise SystemExit("the PuP Pack could not be installed and its art made (above)")
    for rel in ("game/media/dmd_clip/clips.json", "game/hd_art/letters/Z_on.png", "game/hd_art/letters/N_on.png"):
        if not os.path.exists(os.path.join(ROOT, rel)):
            raise SystemExit("the PuP art is incomplete: no " + rel)


ZIG_TARGETS = {"arm64": "aarch64-linux-gnu", "x86_64": "x86_64-linux-gnu"}


def make_feeders(args):
    """The ZeDMD programs for each target CPU, into game/native/bin/<arch>/, so the bundle carries them: the player's machine
    never compiles. zedmd_feed is the platform's plain feeder; dmd_serum is the game's own Serum colouriser (game/native/dmd_serum,
    libserum linked in). The host's CPU builds with the system compiler, the other with zig (`zig cc -target ...`); a CPU that
    cannot be built is reported (no ZeDMD output there)."""
    if args.no_feeder:
        return
    import dmd_out
    want = ["arm64", "x86_64"] if args.target == "all" else [args.target]
    for arch in want:
        for name, build in (("zedmd_feed", dmd_out.build_feeder), ("dmd_serum", dmd_out.build_serum)):
            out = os.path.join(tc.GAME, "native", "bin", arch, name)
            if os.path.exists(out):
                continue
            if dmd_out.arch() == arch:
                ok = build(out)
            elif shutil.which("zig"):
                t = ZIG_TARGETS[arch]
                ok = build(out, cc="zig cc -target " + t, cxx="zig c++ -target " + t)
            else:
                ok = False
            print("{} for {}: {}".format(name, arch, "built" if ok else "NOT built (needs zig for another CPU than this one's, "
                  "git, CMake and the MPF-Godot-Packaging checkout): this bundle has no ZeDMD output there"), flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--target", choices=["arm64", "x86_64", "all"], default="all",
                   help="arm64: Raspberry Pi 4 and Jetson (ETC2/ASTC textures); x86_64: a PC (S3TC/BPTC); all: both")
    p.add_argument("--version", help="default: the date and the short commit, 2026.10.24-ab12cd3")
    p.add_argument("--out", default=os.path.join(ROOT, "dist"), help="where the archive goes (default dist/)")
    p.add_argument("--pup-zip", help="the PuP Pack's zip (a path or URL): installed here and the HD DMD's art (clips, ZUSE/TRON letters, "
                   "award icons) made from it, then shipped in the bundle. Nothing is made on the machine that runs the game")
    p.add_argument("--no-pup-art", action="store_true", help="a bundle without that art (the HD DMD then shows the ROM's dot animations)")
    p.add_argument("--no-feeder", action="store_true", help="no prebuilt ZeDMD programs in the bundle")
    p.add_argument("--no-archive", action="store_true", help="stop after staging; leave the folder")
    args = p.parse_args(argv)
    make_pup_art(args)
    make_feeders(args)
    check_workspace()
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
