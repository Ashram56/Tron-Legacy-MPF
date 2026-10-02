#!/usr/bin/env python3
"""Build the Godot (GMC) media of the game from the asset package.

Generated (all git-ignored, rebuilt by scripts/setup_workspace.sh):
- game/sounds/<track>/snd_XXXX.wav    every ROM sample (GMC finds sounds by file name)
- game/media/dmd/deff_NNN/fNNN.png    the frames of each display effect
- game/slides/deffs/deff_NNN.tscn     one GMC slide per display effect (AnimatedSprite2D with the
                                      ROM frame timing, plus text labels for effects with values)
- game/tron/media_data.json           sound pools and slide facts for tron/media_bridge.py

Display effects whose ROM text has no values ("BALL SAVED / KEEP SHOOTING") use the emulator's
reference capture, which includes the ROM fonts. Effects that print values (scores, counts) use the
graphics layer and draw their text lines with the slide's font (the ROM fonts are not exported).

Usage: .venv/bin/python scripts/gen_media.py [--only-data]
"""
import csv
import glob
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "assets", "mpf_package")
GAME = os.path.join(ROOT, "game")
DMD_COLOR = "Color(1, 0.45, 0.05, 1)"
# The score display and the other effects that show live values are drawn from text
TEXT_ONLY = {19, 25, 26, 33, 38, 40}


def load_yaml(path):
    from ruamel.yaml import YAML
    with open(path) as f:
        return YAML(typ="safe").load(f)


# ---------------------------------------------------------------------- sounds

def build_sounds(only_data):
    cfg = load_yaml(os.path.join(PKG, "config", "sounds.yaml"))
    sounds = cfg["sounds"]
    if not only_data:
        for name, s in sounds.items():
            track = s.get("track", "sfx")
            src = glob.glob(os.path.join(PKG, "media", "sounds", "*", s["file"]))
            if not src:
                continue
            dst_dir = os.path.join(GAME, "sounds", track)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, name + ".wav")
            if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src[0]):
                shutil.copyfile(src[0], dst)
    pools = {}
    for name, p in cfg.get("sound_pools", {}).items():
        members = p["sounds"]
        if isinstance(members, str):
            members = [m.strip() for m in members.split(",")]
        members = [m.split("|")[0].strip() for m in members if m.split("|")[0].strip() in sounds]
        if not members:
            continue
        call = int(name.split("_")[1], 16)
        pools[call] = {"type": p.get("type", "random"), "samples": members,
                       "track": sounds[members[0]].get("track", "sfx")}
    return pools


# ---------------------------------------------------------------------- display effects

def gif_frames(path):
    from PIL import Image, ImageSequence
    img = Image.open(path)
    out = []
    for frame in ImageSequence.Iterator(img):
        out.append((frame.convert("RGBA"), int(frame.info.get("duration", 49)) or 49))
    return out


def png_frames(folder):
    from PIL import Image
    timing = json.load(open(os.path.join(folder, "timing.json")))
    out = []
    for f in timing.get("graphics_frames", []):
        path = os.path.join(folder, f["file"])
        if os.path.exists(path):
            out.append((Image.open(path).convert("RGBA"), max(1, int(f["duration_ms"]))))
    return out


def text_lines(rom_text):
    return [t.strip() for t in rom_text.split(" / ")] if rom_text else []


def write_slide(deff_id, frames, lines, loop, folder_rel):
    name = "deff_{:03d}".format(deff_id)
    ext, entries = [], []
    seen = {}
    for i, (img, ms) in enumerate(frames):
        digest = hashlib.md5(img.tobytes()).hexdigest()
        if digest not in seen:
            fname = "f{:03d}.png".format(len(seen))
            img.save(os.path.join(GAME, folder_rel, fname))
            seen[digest] = "t{}".format(len(seen))
            ext.append('[ext_resource type="Texture2D" path="res://{}/{}" id="{}"]'.format(
                folder_rel, fname, seen[digest]))
        entries.append('{{"duration": {:.1f}, "texture": ExtResource("{}")}}'.format(ms, seen[digest]))
    parts = ['[gd_scene load_steps={} format=3]'.format(len(ext) + (3 if frames else 2)), '',
             '[ext_resource type="Script" path="res://addons/mpf-gmc/classes/mpf_slide.gd" id="slide"]']
    if lines:
        parts.append('[ext_resource type="Script" path="res://addons/mpf-gmc/classes/mpf_variable.gd" id="var"]')
    parts += ext
    if frames:
        parts += ['', '[sub_resource type="SpriteFrames" id="frames"]',
                  'animations = [{{"frames": [{}], "loop": {}, "name": &"default", "speed": 1000.0}}]'.format(
                      ", ".join(entries), "true" if loop else "false")]
    parts += ['', '[node name="{}" type="Control"]'.format(name), 'layout_mode = 3', 'anchors_preset = 0',
              'offset_right = 128.0', 'offset_bottom = 32.0', 'script = ExtResource("slide")', '',
              '[node name="Background" type="ColorRect" parent="."]', 'layout_mode = 0',
              'offset_right = 128.0', 'offset_bottom = 32.0', 'color = Color(0, 0, 0, 1)']
    if frames:
        parts += ['', '[node name="Anim" type="AnimatedSprite2D" parent="."]',
                  'modulate = {}'.format(DMD_COLOR), 'sprite_frames = SubResource("frames")',
                  'autoplay = "default"', 'centered = false']
    n = len(lines)
    for i in range(n):
        top = round(32 * i / n)
        parts += ['', '[node name="Line{}" type="Label" parent="."]'.format(i), 'layout_mode = 0',
                  'offset_top = {}.0'.format(top), 'offset_right = 128.0',
                  'offset_bottom = {}.0'.format(round(32 * (i + 1) / n)),
                  'theme_override_colors/font_color = {}'.format(DMD_COLOR),
                  'theme_override_font_sizes/font_size = {}'.format(8 if n > 2 else 10),
                  'horizontal_alignment = 1', 'vertical_alignment = 1',
                  'script = ExtResource("var")', 'variable_type = 1',
                  'variable_name = "line{}"'.format(i)]
    with open(os.path.join(GAME, "slides", "deffs", name + ".tscn"), "w") as f:
        f.write("\n".join(parts) + "\n")
    return name


def build_deffs(only_data):
    rows = {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(PKG, "event_map.csv")))}
    out = {}
    os.makedirs(os.path.join(GAME, "slides", "deffs"), exist_ok=True)
    for folder in sorted(glob.glob(os.path.join(PKG, "media", "dmd", "deff_*"))):
        deff_id = int(os.path.basename(folder).split("_")[1])
        row = rows.get(deff_id, {})
        rom_text = row.get("rom_text", "")
        dynamic = "%" in rom_text or deff_id in TEXT_ONLY
        loop = row.get("background_loop") == "yes"
        ref = os.path.join(folder, "reference_capture.gif")
        has_graphics = os.path.isdir(os.path.join(folder, "frames"))
        if dynamic or not os.path.exists(ref):
            source, lines = ("graphics" if has_graphics else "none"), text_lines(rom_text)
        else:
            source, lines = "reference", []
        info = {"slide": "deff_{:03d}".format(deff_id), "source": source, "text": lines, "loop": loop}
        out[deff_id] = info
        if only_data:
            continue
        rel = os.path.join("media", "dmd", "deff_{:03d}".format(deff_id))
        shutil.rmtree(os.path.join(GAME, rel), ignore_errors=True)
        os.makedirs(os.path.join(GAME, rel))
        frames = gif_frames(ref) if source == "reference" else png_frames(folder) if source == "graphics" else []
        write_slide(deff_id, frames, lines, loop, rel)
    return out


def main():
    only_data = "--only-data" in sys.argv
    data = {"pools": build_sounds(only_data), "deffs": build_deffs(only_data)}
    with open(os.path.join(GAME, "tron", "media_data.json"), "w") as f:
        json.dump(data, f, indent=0, sort_keys=True)
    print("media: {} sound pools, {} display effects".format(len(data["pools"]), len(data["deffs"])))


if __name__ == "__main__":
    main()
