extends Node
## DMD display mode: "classic" (the ROM's 128x32 dots, scaled up by whole pixels: exactly the ROM output)
## or "hd" (the same 128x32 layout drawn at the window's resolution: smooth HD fonts and upscaled effect
## frames, made by scripts/gen_fonts.py and scripts/gen_media.py with scripts/dmd_hd.py).
##
## Chosen, first match wins:
##   1. --proc-dmd (the P-ROC feeds the machine's own 128x32 DMD): always classic;
##   2. the user arg --dmd=hd|classic   (godot --path game -- --dmd=classic; scripts/run.py --dmd classic);
##   3. render captures (--job=, slide_capture; --capture-dir=, render_check): classic, so the ROM checks
##      compare dots;
##   4. the environment variable TRON_DMD=hd|classic;
##   5. the project setting tron/dmd/mode (game/project.godot, default "hd").
## In classic mode this node does nothing at all: the output is the 128x32 picture as before.
##
## HD mode: the window's content scale mode becomes canvas_items (2D drawn at the window's resolution,
## kept at the 4:1 aspect), textures are filtered, tron/rom_text.gd loads the HD fonts (fonts/hd/), and
## every sprite showing a picture of media/dmd/ shows its twin of media/dmd_hd/ (same name), scaled down
## to the same 128x32 footprint.
## Dot-matrix look (HD only): --dmd-dots=N (or TRON_DMD_DOTS=N, or tron/dmd/dots): round dots, N per DMD
## dot along each axis (1 = the 128x32 grid of the real display, 2 = 256x64, ...); 0 = off (default).

const MEDIA := "res://media/dmd/"
const MEDIA_HD := "res://media/dmd_hd/"
const DOTS_SHADER := "res://tools/dmd_dots.gdshader"

var mode := "classic"
var hd := false
var dots := 0
var frame_scale := 8
var _frames_hd := {}


static func choose(args: PackedStringArray, env_mode: String, setting: String) -> String:
	if "--proc-dmd" in args:
		return "classic"
	for a in args:
		if a.begins_with("--dmd="):
			var m := a.trim_prefix("--dmd=").to_lower()
			if m in ["hd", "classic"]:
				return m
	for a in args:
		if a.begins_with("--job=") or a.begins_with("--capture-dir="):
			return "classic"
	if env_mode.to_lower() in ["hd", "classic"]:
		return env_mode.to_lower()
	return "hd" if setting.to_lower() == "hd" else "classic"


func _enter_tree() -> void:
	var args := OS.get_cmdline_user_args()
	mode = choose(args, OS.get_environment("TRON_DMD"),
		str(ProjectSettings.get_setting("tron/dmd/mode", "hd")))
	hd = mode == "hd" and FileAccess.file_exists("res://fonts/hd/fonts_hd.json")
	if mode == "hd" and not hd:
		push_warning("DMD: HD media not generated (scripts/gen_media.py), showing the classic DMD")
		mode = "classic"
	if not hd:
		return
	dots = int(ProjectSettings.get_setting("tron/dmd/dots", 0))
	if OS.get_environment("TRON_DMD_DOTS").is_valid_int():
		dots = int(OS.get_environment("TRON_DMD_DOTS"))
	for a in args:
		if a == "--dmd-dots":
			dots = 2
		elif a.begins_with("--dmd-dots="):
			dots = int(a.trim_prefix("--dmd-dots="))
	if FileAccess.file_exists(MEDIA_HD + "scale.json"):
		var info = JSON.parse_string(FileAccess.get_file_as_string(MEDIA_HD + "scale.json"))
		if info is Dictionary:
			frame_scale = int(info.get("scale", frame_scale))
	var root := get_tree().root
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	root.content_scale_stretch = Window.CONTENT_SCALE_STRETCH_FRACTIONAL
	root.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	get_tree().node_added.connect(_on_node_added)
	print("DMD: hd mode, window %s%s" % [root.size, (", dot-matrix look %d" % dots) if dots > 0 else ""])


func _ready() -> void:
	if hd and dots > 0:
		var layer := CanvasLayer.new()
		layer.layer = 128
		var rect := ColorRect.new()
		rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		rect.size = Vector2(128, 32)
		var mat := ShaderMaterial.new()
		mat.shader = load(DOTS_SHADER)
		mat.set_shader_parameter("grid", Vector2(128 * dots, 32 * dots))
		rect.material = mat
		layer.add_child(rect)
		add_child(layer)


## The HD twin of a classic DMD picture, or null.
func hd_texture(tex: Texture2D) -> Texture2D:
	if tex == null or not tex.resource_path.begins_with(MEDIA):
		return null
	var path := MEDIA_HD + tex.resource_path.trim_prefix(MEDIA)
	return load(path) if ResourceLoader.exists(path) else null


func _hd_frames(frames: SpriteFrames) -> SpriteFrames:
	if _frames_hd.has(frames):
		return _frames_hd[frames]
	var out := SpriteFrames.new()
	var complete := true
	for anim in frames.get_animation_names():
		if not out.has_animation(anim):
			out.add_animation(anim)
		out.set_animation_loop(anim, frames.get_animation_loop(anim))
		out.set_animation_speed(anim, frames.get_animation_speed(anim))
		for i in frames.get_frame_count(anim):
			var tex := frames.get_frame_texture(anim, i)
			var big := hd_texture(tex)
			complete = complete and big != null
			out.add_frame(anim, big if big else tex, frames.get_frame_duration(anim, i))
	_frames_hd[frames] = out if complete else frames
	return _frames_hd[frames]


func _on_node_added(node: Node) -> void:
	if node is AnimatedSprite2D:
		var sprite := node as AnimatedSprite2D
		if sprite.sprite_frames and sprite.sprite_frames != _hd_frames(sprite.sprite_frames):
			sprite.sprite_frames = _hd_frames(sprite.sprite_frames)
			sprite.scale = sprite.scale / frame_scale
	elif node is Sprite2D:
		var s := node as Sprite2D
		var big := hd_texture(s.texture)
		if big:
			s.texture = big
			s.scale = s.scale / frame_scale
