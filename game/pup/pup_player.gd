extends Node

## The PuP Pack player (autoload "Pup"): game/pup.cfg's windows, the PuP Pack's screens and playlists, and the
## "pup_play" commands MPF sends (game/tron_pup/mode.py).
##
## Windows (each on the monitor game/pup.cfg gives it):
## - backglass: PuP screens 2 (underlay) and 12 (pop-up top layer);
## - dmd: the PuP Pack's DMD panel frame with the game's 128x32 DMD (the main window's picture) in its middle;
## - topper (optional, [pup] third_screen): PuP screens 13 (underlay) and 14 (pop-up top layer).
## PuP screen 15 (OST music) has no window. Commands for a screen that is off are dropped.
## Media come from the converted copy of the pack (scripts/gen_pup.py, manifest.json): Theora videos, the
## pack's own mp3 and pictures, all loaded at run time (nothing is imported into the Godot project).

const CONFIG_FILES := ["res://pup.cfg", "res://pup.local.cfg"]
const LAYERS := {"backglass": [2, 12], "topper": [13, 14]}
const MUSIC_SCREEN := 15
const DOTS_SHADER := preload("res://pup/dmd_dots.gdshader")
const PupScreen := preload("res://pup/pup_screen.gd")

var cfg := ConfigFile.new()
var enabled := false
var pack_dir := ""
var media_dir := ""
var manifest := {}                  # pack path ("Drain/Drain1.mp4") -> {out, w, h, duration}
var folders := {}                   # playlist folder (lower case) -> [pack paths], sorted
var playlists := {}                 # playlist folder (lower case) -> {alpha_sort, volume}
var screens := {}                   # PuP screen number -> PupScreen
var windows := {}
var _next := {}                     # playlist -> next index (AlphaSort playlists)
var _last := {}                     # playlist -> last pick (random playlists)
var _audio_cache := {}
## The native_video add-on (Windows, pup_addons/native_video): plays the pack's mp4s without conversion
var native_video := ClassDB.class_exists("NativeVideoStream")


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	# answered even with the PuP off, so MPF's hello is never "unhandled"; pup_ready only when it is on
	MPF.server.registered_handlers["pup_play"] = [Callable(self, "_on_pup_play")]
	MPF.server.registered_handlers["pup_hello"] = [Callable(self, "_on_pup_hello")]
	if not _load_config():
		return
	var root := ProjectSettings.globalize_path("res://").path_join("..").simplify_path()
	pack_dir = root.path_join(setting("pup", "pack_dir", "pup_pack/trn_174h"))
	media_dir = root.path_join(setting("pup", "media_dir", "pup_media/trn_174h"))
	if not _load_media():
		return
	enabled = true
	_load_playlists()
	call_deferred("_build")


func _load_config() -> bool:
	for path in CONFIG_FILES:
		if FileAccess.file_exists(path):
			var part := ConfigFile.new()
			if part.load(path) == OK:
				for section in part.get_sections():
					for key in part.get_section_keys(section):
						cfg.set_value(section, key, part.get_value(section, key))
	if OS.get_environment("TRON_PUP").to_lower() in ["0", "false", "no", "off"]:
		return false
	return bool(setting("pup", "enabled", false))


func setting(section: String, key: String, default = null):
	return cfg.get_value(section, key, default)


func _load_media() -> bool:
	var path := media_dir.path_join("manifest.json")
	if not FileAccess.file_exists(path):
		push_warning("PuP: no converted media at %s (run scripts/gen_pup.py): PuP off" % media_dir)
		return false
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		push_warning("PuP: %s is not valid: PuP off" % path)
		return false
	manifest = data.get("files", {})
	for key in manifest.keys():
		var folder: String = key.get_base_dir().to_lower()
		if not folders.has(folder):
			folders[folder] = []
		folders[folder].append(key)
	for folder in folders:
		folders[folder].sort_custom(func(a, b): return a.naturalnocasecmp_to(b) < 0)
	return true


func _load_playlists() -> void:
	for row in _read_csv(pack_dir.path_join("playlists.pup")):
		playlists[row.get("Folder", "").to_lower()] = {
			"alpha_sort": row.get("AlphaSort", "0") == "1",
			"volume": float(row.get("Volume", "100") if row.get("Volume", "") != "" else "100")}


func _read_csv(path: String) -> Array:
	var rows := []
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_warning("PuP: cannot read %s" % path)
		return rows
	var head := f.get_csv_line()
	while not f.eof_reached():
		var line := f.get_csv_line()
		if line.size() < 2:
			continue
		var row := {}
		for i in range(mini(head.size(), line.size())):
			row[head[i].strip_edges()] = line[i].strip_edges()
		rows.append(row)
	return rows

# ------------------------------------------------------------------ windows and screens

func _build() -> void:
	get_tree().root.gui_embed_subwindows = false
	var defaults := {}
	for row in _read_csv(pack_dir.path_join("screens.pup")):
		defaults[int(row.get("ScreenNum", "-1"))] = row
	var video_volume := float(setting("pup", "video_volume", 100))
	_make_layered_window("backglass", defaults, video_volume)
	if bool(setting("pup", "third_screen", true)):
		_make_layered_window("topper", defaults, video_volume)
	_make_dmd_window()
	if bool(setting("pup", "ost_music", true)):
		var music := PupScreen.new()
		music.setup(self, MUSIC_SCREEN, {"audio_only": true, "bus": "music",
			"volume": float(setting("pup", "music_volume", 100))})
		add_child(music)
		screens[MUSIC_SCREEN] = music
	for n in screens:
		screens[n].start_background()
	if bool(setting("dmd", "hide_main_window", true)):
		get_tree().root.mode = Window.MODE_MINIMIZED
	print("PuP: windows %s, screens %s" % [windows.keys(), screens.keys()])
	_start_capture()


func _make_window(section: String) -> Window:
	var w := Window.new()
	w.name = "pup_" + section
	w.title = "Tron Legacy - " + section
	w.transient = false
	w.borderless = bool(setting(section, "borderless", false))
	w.close_requested.connect(func(): pass)
	w.window_input.connect(_forward_input)
	var screen := clampi(int(setting(section, "screen", 0)), 0, DisplayServer.get_screen_count() - 1)
	var size_cfg = setting(section, "size", [800, 600])
	var pos_cfg = setting(section, "position", [0, 0])
	w.size = Vector2i(int(size_cfg[0]), int(size_cfg[1]))
	w.position = DisplayServer.screen_get_position(screen) + Vector2i(int(pos_cfg[0]), int(pos_cfg[1]))
	var back := ColorRect.new()
	back.color = Color.BLACK
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	back.mouse_filter = Control.MOUSE_FILTER_IGNORE
	w.add_child(back)
	add_child(w)
	if bool(setting(section, "fullscreen", false)):
		w.current_screen = screen
		w.mode = Window.MODE_FULLSCREEN
	windows[section] = w
	return w


func _make_layered_window(section: String, defaults: Dictionary, volume: float) -> void:
	var w := _make_window(section)
	for n in LAYERS[section]:
		var row: Dictionary = defaults.get(n, {})
		var layer := PupScreen.new()
		layer.setup(self, n, {"popup": n == LAYERS[section][1], "fit": setting(section, "fit", "fit"),
			"align": setting(section, "align", 0.5), "bus": "sfx", "volume": volume,
			"bg_playlist": row.get("PlayList", ""), "bg_file": row.get("PlayFile", "")})
		w.add_child(layer)
		screens[n] = layer


func _make_dmd_window() -> void:
	var w := _make_window("dmd")
	var area := Vector2(w.size)
	var dmd_rect := Rect2(Vector2.ZERO, area)
	var frame_path := str(setting("dmd", "frame_image", ""))
	if frame_path != "":
		var image := Image.load_from_file(pack_dir.path_join(frame_path))
		if image:
			var c = setting("dmd", "frame_crop", [0, 0, image.get_width(), image.get_height()])
			var crop := Rect2i(int(c[0]), int(c[1]), int(c[2]), int(c[3]))
			var frame := TextureRect.new()
			frame.texture = ImageTexture.create_from_image(image.get_region(crop))
			frame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var scale := minf(area.x / crop.size.x, area.y / crop.size.y)
			var origin := (area - Vector2(crop.size) * scale) * 0.5
			frame.position = origin
			frame.size = Vector2(crop.size) * scale
			w.add_child(frame)
			var r = setting("dmd", "dmd_rect", [c[0], c[1], c[2], c[3]])
			dmd_rect = Rect2(origin + (Vector2(float(r[0]), float(r[1])) - Vector2(crop.position)) * scale,
				Vector2(float(r[2]), float(r[3])) * scale)
		else:
			push_warning("PuP: cannot load the DMD frame %s" % frame_path)
	# the game's 128x32 DMD, 4:1, centred in its rect
	var dmd_size := Vector2(128, 32)
	var k := minf(dmd_rect.size.x / dmd_size.x, dmd_rect.size.y / dmd_size.y)
	var dmd := TextureRect.new()
	dmd.name = "dmd"
	dmd.texture = get_tree().root.get_texture()
	dmd.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	dmd.stretch_mode = TextureRect.STRETCH_SCALE
	dmd.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	dmd.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dmd.size = dmd_size * k
	dmd.position = dmd_rect.position + (dmd_rect.size - dmd.size) * 0.5
	if bool(setting("dmd", "dots", true)):
		var mat := ShaderMaterial.new()
		mat.shader = DOTS_SHADER
		mat.set_shader_parameter("dmd_size", dmd_size)
		dmd.material = mat
	w.add_child(dmd)


func _forward_input(event: InputEvent) -> void:
	# keys pressed in a PuP window drive the game like keys in the DMD window (gmc.cfg [keyboard], Esc)
	get_tree().root.push_input(event)

# ------------------------------------------------------------------ MPF

func _on_pup_hello(_message: Dictionary) -> void:
	if not enabled or windows.is_empty():
		return
	MPF.server.send_event_with_args("pup_ready", {"ost": 1 if screens.has(MUSIC_SCREEN) else 0}, false)


func _on_pup_play(message: Dictionary) -> void:
	var n := int(message.get("screen", -1))
	if screens.has(n):
		screens[n].command(message)

# ------------------------------------------------------------------ media

## Pack path of the file a play names, or the next file of its playlist; returns the converted file's path.
func pick(playlist: String, file: String) -> String:
	var key := ""
	if file != "":
		key = _find(playlist, file)
	else:
		var files: Array = folders.get(playlist.to_lower(), [])
		if files.is_empty():
			return ""
		var info: Dictionary = playlists.get(playlist.to_lower(), {})
		if info.get("alpha_sort", false):
			var i: int = _next.get(playlist, 0) % files.size()
			_next[playlist] = i + 1
			key = files[i]
		else:
			var i := randi() % files.size()
			if files.size() > 1 and files[i] == _last.get(playlist, ""):
				i = (i + 1 + randi() % (files.size() - 1)) % files.size()
			key = files[i]
			_last[playlist] = key
	if key == "":
		push_warning("PuP: no file %s in playlist %s" % [file, playlist])
		return ""
	return media_path(key)


## Where a pack file plays from: the pack's own video with the native_video add-on, else the converted copy.
func media_path(key: String) -> String:
	var entry: Dictionary = manifest[key]
	if native_video and entry.has("w") and key.get_extension().to_lower() in ["mp4", "m4v", "mov"]:
		return pack_dir.path_join(key)
	if not entry.has("out"):
		push_warning("PuP: %s was not converted (gen_pup.py --native) and the native_video add-on is not loaded" % key)
		return ""
	return media_dir.path_join(entry.out)


func video_stream(path: String) -> VideoStream:
	var stream: VideoStream = ClassDB.instantiate("NativeVideoStream") if path.get_extension().to_lower() != "ogv" \
		else VideoStreamTheora.new()
	stream.file = path
	return stream


func _find(playlist: String, file: String) -> String:
	var want := file.get_basename().to_lower()
	for key in folders.get(playlist.to_lower(), []):
		if key.get_file().get_basename().to_lower() == want:
			return key
	return ""


func volume_of(cmd: Dictionary) -> float:
	if cmd.has("volume") and str(cmd.volume) != "":
		return float(cmd.volume) / 100.0
	return float(playlists.get(str(cmd.get("playlist", "")).to_lower(), {}).get("volume", 100.0)) / 100.0


func aspect_of(path: String) -> float:
	for key in manifest:
		var entry: Dictionary = manifest[key]
		var here := pack_dir.path_join(key) == path or media_dir.path_join(entry.get("out", key)) == path
		if here and entry.get("h", 0) > 0:
			return float(entry.w) / float(entry.h)
	return 16.0 / 9.0


func load_audio(path: String) -> AudioStream:
	if _audio_cache.has(path):
		return _audio_cache[path]
	var data := FileAccess.get_file_as_bytes(path)
	if data.is_empty():
		push_warning("PuP: cannot read %s" % path)
		return null
	var stream: AudioStream
	match path.get_extension().to_lower():
		"mp3":
			stream = AudioStreamMP3.new()
			stream.data = data
		"ogg":
			stream = AudioStreamOggVorbis.load_from_buffer(data)
	_audio_cache[path] = stream
	return stream


func load_image(path: String) -> Texture2D:
	var image := Image.load_from_file(path)
	return ImageTexture.create_from_image(image) if image else null

# ------------------------------------------------------------------ checks without a screen

## godot --path game -- --pup-capture-dir=/abs/path [--pup-capture-every-ms=2000]: saves every PuP window
## as <window>_NNNN.png (scripts/pup_check.py).
func _start_capture() -> void:
	var dir := ""
	var every := 2000
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--pup-capture-dir="):
			dir = arg.split("=", true, 1)[1]
		elif arg.begins_with("--pup-capture-every-ms="):
			every = int(arg.split("=", true, 1)[1])
	if dir == "":
		return
	DirAccess.make_dir_recursive_absolute(dir)
	var timer := Timer.new()
	timer.wait_time = every / 1000.0
	var count := [0]
	timer.timeout.connect(func():
		for section in windows:
			windows[section].get_texture().get_image().save_png("%s/%s_%04d.png" % [dir, section, count[0]])
		count[0] += 1)
	add_child(timer)
	timer.start()
