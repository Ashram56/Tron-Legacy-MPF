#!/usr/bin/env python3
"""Build the Godot (GMC) media of the game from the asset package.

Generated (all git-ignored, rebuilt by scripts/setup.py):
- game/sounds/<track>/snd_XXXX.wav    every ROM sample (GMC finds sounds by file name)
- game/media/dmd/deff_NNN/fNNN.png    the frames of each display effect
- game/slides/deffs/deff_NNN.tscn     one GMC slide per display effect (AnimatedSprite2D with the
                                      ROM frame timing, plus text labels for effects with values)
- game/tron/media_data.json           sound pools and slide facts for tron/media_bridge.py
- game/fonts/                         the ROM fonts (scripts/gen_fonts.py)

Display effects whose ROM text has no values ("BALL SAVED / KEEP SHOOTING") use the emulator's
reference capture, which includes the ROM fonts. Effects that print values (scores, counts) use the
graphics layer and draw each text line with tron/rom_text.gd: the ROM font, position and alignment of
the deff's draw call in the decompiled code (scripts/rom_layout.py).

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
    with open(path, encoding="utf-8") as f:
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
    timing = json.load(open(os.path.join(folder, "timing.json"), encoding="utf-8"))
    out = []
    for f in timing.get("graphics_frames", []):
        path = os.path.join(folder, f["file"])
        if os.path.exists(path):
            out.append((Image.open(path).convert("RGBA"), max(1, int(f["duration_ms"]))))
    return out


def text_lines(rom_text):
    return [t.strip() for t in rom_text.split(" / ")] if rom_text else []


def text_node(i, lay, name=None, var=None):
    """A tron/rom_text.gd label for text line i (lay from rom_layout.line_layouts)."""
    out = ['', '[node name="{}" type="Label" parent="."]'.format(name or "Line%d" % i), 'layout_mode = 0',
           'theme_override_colors/font_color = {}'.format(DMD_COLOR),
           'script = ExtResource("text")', 'variable_type = 1', 'variable_name = "{}"'.format(var or "line%d" % i),
           'rom_font = {}'.format(lay["font"]), 'rom_x = {}'.format(lay["x"]),
           'rom_y = {}'.format(lay["y"]), 'rom_flags = {}'.format(lay["flags"])]
    if "fit_fonts" in lay:
        out += ['fit_fonts = PackedInt32Array({})'.format(", ".join(map(str, lay["fit_fonts"]))),
                'fit_ys = PackedInt32Array({})'.format(", ".join(map(str, lay["fit_ys"]))),
                'fit_width = {}'.format(lay["fit_width"])]
    if "alt_when_empty" in lay:
        out += ['alt_x = {}'.format(lay["alt_x"]), 'alt_y = {}'.format(lay["alt_y"]),
                'alt_when_empty = "{}"'.format(lay["alt_when_empty"])]
    for key in ("show_after_ms", "hide_after_ms", "step_ms", "blink_ms"):
        if lay.get(key):
            out.append('{} = {}'.format(key, lay[key]))
    if lay.get("level_steps"):
        out.append('level_steps = PackedInt32Array({})'.format(", ".join(map(str, lay["level_steps"]))))
    return out


def level_color(level):
    """DMD_COLOR at palette level 0-15 (the slide tint keeps the level in the red channel)."""
    r, g, b = (float(v) for v in DMD_COLOR[6:-4].split(", "))
    return "Color({:.4g}, {:.4g}, {:.4g}, 1)".format(r * level / 15, g * level / 15, b * level / 15)


def rect_node(name, x, y, w, h, level):
    return ['', '[node name="{}" type="ColorRect" parent="."]'.format(name), 'layout_mode = 0',
            'offset_left = {}.0'.format(x), 'offset_top = {}.0'.format(y), 'offset_right = {}.0'.format(x + w),
            'offset_bottom = {}.0'.format(y + h), 'color = {}'.format(level_color(level))]


def score_display_nodes(score_lines=True, match=False):
    """deff 19 beyond its two text lines (ROM deff_019 0x01023a98, deff_draw_status_panel 0x010230ec):
    credits and replay lines (font 0, row 30), player scores and last points in the status panel (font 0
    right-aligned at x 38), the panel's separator (x 40) and dashes (row 31) at level 1, the timer bars
    at level 15, and tron/score_display.gd driving rotation, blink, dimming and bars."""
    import rom_layout
    out = []
    for name, var, x, y, flags in rom_layout.SCORE_PANEL:
        if score_lines or name not in ("Credits", "Replay"):
            out += text_node(0, {"font": 0, "x": x, "y": y, "flags": flags}, name, var)
    out += rect_node("Separator", 40, 0, 1, 32, 1)
    for k, (name, x) in enumerate((("BarDs", 4), ("BarBumpers", 16), ("BarSpinners", 28))):
        out += rect_node("Dash%d" % k, x, 31, 10, 1, 1)
        out += rect_node(name, x, 31, 0, 1, 15)
    for name in ("BarZfs", "BarClu", "BarGem"):
        out += rect_node(name, 40, 0, 1, 0, 15)
    out += ['', '[node name="ScoreDisplay" type="Node" parent="."]', 'script = ExtResource("score")']
    if score_lines:
        out.append('score_lines = true')
    if match:
        out.append('match_panel = true')
    return out


def write_slide(deff_id, frames, layouts, loop, folder_rel, panel=False):
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
    if any(layouts) or panel:
        parts.append('[ext_resource type="Script" path="res://tron/rom_text.gd" id="text"]')
    if panel:
        parts.append('[ext_resource type="Script" path="res://tron/score_display.gd" id="score"]')
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
    for i, lay in enumerate(layouts):
        if lay:
            parts += text_node(i, lay)
    if panel:
        parts += score_display_nodes(deff_id == 19, panel == "match")
    with open(os.path.join(GAME, "slides", "deffs", name + ".tscn"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")
    return name


def build_deffs(only_data):
    import rom_layout
    rows = {int(r["deff"]): r for r in csv.DictReader(open(os.path.join(PKG, "event_map.csv"), encoding="utf-8"))}
    fonts = json.load(open(os.path.join(GAME, "fonts", "fonts.json"), encoding="utf-8"))["fonts"]
    calls = rom_layout.deff_calls()
    panels = rom_layout.status_panel_deffs()
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
        layouts = rom_layout.line_layouts(deff_id, lines, fonts, calls.get(deff_id, []))
        panel = panels.get(deff_id) if source != "reference" else None   # captures show their panel
        info = {"slide": "deff_{:03d}".format(deff_id), "source": source, "text": lines, "loop": loop,
                "panel": panel,
                "fonts": [lay["font"] if lay else None for lay in layouts]}
        out[deff_id] = info
        if only_data:
            continue
        rel = "media/dmd/deff_{:03d}".format(deff_id)    # also a res:// path: "/" on every OS
        shutil.rmtree(os.path.join(GAME, rel), ignore_errors=True)
        os.makedirs(os.path.join(GAME, rel))
        frames = gif_frames(ref) if source == "reference" else png_frames(folder) if source == "graphics" else []
        end = rom_layout.GRAPHICS_END.get(deff_id)
        if end and source == "graphics" and len(frames) >= end:  # the ROM stops drawing bitmaps at frame `end`
            from PIL import Image
            last_ms = frames[end - 1][1]
            frames = frames[:end - 1] + [(frames[end - 1][0], frames[end - 2][1]),
                                         (Image.new("RGBA", (128, 32)), max(1, last_ms - frames[end - 2][1]))]
        write_slide(deff_id, frames, layouts, loop, rel, panel)
    return out


def main():
    import gen_fonts
    only_data = "--only-data" in sys.argv
    if not only_data or not os.path.exists(os.path.join(GAME, "fonts", "fonts.json")):
        gen_fonts.build()
    data = {"pools": build_sounds(only_data), "deffs": build_deffs(only_data)}
    with open(os.path.join(GAME, "tron", "media_data.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=0, sort_keys=True)
    print("media: {} sound pools, {} display effects".format(len(data["pools"]), len(data["deffs"])))


if __name__ == "__main__":
    main()
