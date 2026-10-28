extends Node

## The PuP Pack player (autoload "Pup"): game/pup.cfg's windows, the PuP Pack's screens and playlists, and the
## "pup_play" commands MPF sends (game/tron_pup/mode.py).
##
## Windows (each on the monitor game/pup.cfg gives it):
## - backglass: PuP screens 2 (underlay) and 12 (pop-up top layer); [backglass] enabled=false leaves it out;
## - dmd: the game's 128x32 DMD (the main window's picture) in a neon frame over a live light cycle chase
##   (game/pup/lightcycles.gd), or ([dmd] background="frame") in the PuP Pack's DMD panel art;
## - topper (optional, [pup] third_screen): PuP screens 13 (underlay) and 14 (pop-up top layer).
## PuP screen 15 (OST music) has no window. Commands for a screen that is off are dropped.
## Media come from the converted copy of the pack (scripts/pup/gen_pup.py, manifest.json): Theora videos, the
## pack's own mp3 and pictures, all loaded at run time (nothing is imported into the Godot project).

const CONFIG_FILES := ["res://pup.cfg", "res://pup.local.cfg"]
const LAYERS := {"backglass": [2, 12], "topper": [13, 14]}
const MUSIC_SCREEN := 15
const DOTS_SHADER := preload("res://pup/dmd_dots.gdshader")
const PupScreen := preload("res://pup/pup_screen.gd")
const LightCycles := preload("res://pup/lightcycles.gd")
const NEON_SHADER := preload("res://pup/neon_frame.gdshader")
const ServiceBackglass := preload("res://pup/service_backglass.gd")

var cfg := ConfigFile.new()
var enabled := false
var pack_dir := ""
var media_dir := ""
var manifest := {}                  # pack path ("Drain/Drain1.mp4") -> {out, w, h, duration}
var still_path := ""                # the backglass still (manifest "still") the service menu draws on
var service_backglass: ServiceBackglass     # the service menu on the backglass ([backglass] service_menu)
var folders := {}                   # playlist folder (lower case) -> [pack paths], sorted
var playlists := {}                 # playlist folder (lower case) -> {alpha_sort, volume}
var screens := {}                   # PuP screen number -> PupScreen
var windows := {}
var _next := {}                     # playlist -> next index (AlphaSort playlists)
var _last := {}                     # playlist -> last pick (random playlists)
var _audio_cache := {}
var _audio_lock := Mutex.new()      # _audio_cache: the music preload fills it on a worker (_preload_audio())
## Which add-on plays the pack's mp4s without conversion (_pick_video_player()), else Godot plays the Theora copies:
## - GDE GoZen (Linux and Windows, pup_addons/gde_gozen): FFmpeg, with the GPU decoding (the Jetson's decoder when
##   libnvmpi is installed; Direct3D 11 Video / DXVA2 on Windows); the screens then use game/pup/gozen_player.gd;
## - the native_video add-on (macOS, and Windows' fallback, pup_addons/native_video).
## [pup] video_player (or TRON_VIDEO_PLAYER) = "native" picks native_video where both are installed (Windows).
var native_video := false
var gozen := false


## Layers fully covered by an opaque video above them are not drawn, and pause when silent (pup_screen.set_covered()):
## on a Raspberry Pi 4 a 1080p video layer costs ~6 ms of GPU to draw plus ~5 ms to convert its planes, and its
## hardware decoder slows the GPU down, for nothing when hidden. The screens' own visibility is untouched.
func _process(_delta: float) -> void:
	for section in LAYERS:
		var covered := false
		for i in range(LAYERS[section].size() - 1, -1, -1):
			var s = screens.get(LAYERS[section][i])
			if s == null:
				continue
			if not s.audio_only:
				s.set_covered(covered)
			if not covered and s.covers():
				covered = true


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	# answered even with the PuP off, so MPF's hello is never "unhandled"; pup_ready only when it is on
	MPF.server.registered_handlers["pup_play"] = [Callable(self, "_on_pup_play")]
	MPF.server.registered_handlers["pup_hello"] = [Callable(self, "_on_pup_hello")]
	MPF.server.registered_handlers["service_backglass"] = [Callable(self, "_on_service_backglass")]
	if not _load_config():
		return
	_pick_video_player()
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


func _pick_video_player() -> void:
	var has_native := ClassDB.class_exists("NativeVideoStream")
	var has_gozen := ClassDB.class_exists("GoZenVideo") \
		and ResourceLoader.exists("res://addons/gde_gozen/video_playback.gd")
	var want := OS.get_environment("TRON_VIDEO_PLAYER").strip_edges().to_lower()
	if want.is_empty():
		want = str(setting("pup", "video_player", "")).strip_edges().to_lower()
	gozen = has_gozen and not (want == "native" and has_native)
	native_video = has_native and not gozen
	print("PuP video player: %s" % ("GDE GoZen" if gozen else ("native_video" if native_video else "Godot (Theora)")))


func setting(section: String, key: String, default = null):
	return cfg.get_value(section, key, default)


func _load_media() -> bool:
	var path := media_dir.path_join("manifest.json")
	if not FileAccess.file_exists(path):
		push_warning("PuP: no converted media at %s (run scripts/pup/gen_pup.py): PuP off" % media_dir)
		return false
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		push_warning("PuP: %s is not valid: PuP off" % path)
		return false
	manifest = data.get("files", {})
	if data.get("still") is String:
		still_path = media_dir.path_join(data["still"])
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
	if bool(setting("backglass", "enabled", true)):
		_make_layered_window("backglass", defaults, video_volume)
	_make_dmd_window()
	if bool(setting("pup", "third_screen", true)):
		_make_layered_window("topper", defaults, video_volume)
	match str(setting("pup", "layout", "split")):
		"split":
			_split_windows()
		"stack":
			_stack_windows()
	_layout_dmd()
	if _dmd_area:
		_dmd_area.resized.connect(_layout_dmd)
	else:
		windows["dmd"].size_changed.connect(_layout_dmd)
	_follow_service_settings.call_deferred()
	if bool(setting("pup", "ost_music", true)):
		var music := PupScreen.new()
		music.setup(self, MUSIC_SCREEN, {"audio_only": true, "bus": "music",
			"volume": float(setting("pup", "music_volume", 100))})
		add_child(music)
		screens[MUSIC_SCREEN] = music
		_preload_audio()
	for n in screens:
		screens[n].start_background()
	if bool(setting("pup", "hide_cursor", true)):
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
	if bool(setting("dmd", "hide_main_window", true)):
		get_tree().root.mode = Window.MODE_MINIMIZED
		_check_main_window_hidden.call_deferred()
	_vsync_one_window()
	var placed := []
	for section in windows:
		placed.append("%s %s at %s" % [section, windows[section].size, windows[section].position])
	print("PuP: windows %s, screens %s" % [", ".join(placed), screens.keys()])
	_start_capture()


## Vsync on the backglass window only (else the first PuP window): with vsync on every window, each one's present
## waits for its own vertical blank, so a frame took one screen refresh per window (main, backglass, DMD, topper:
## 15 FPS on a Jetson Xavier NX, L4T R35). One vsync'd window still paces the frames of all of them.
func _vsync_one_window() -> void:
	if windows.is_empty() or DisplayServer.window_get_vsync_mode() == DisplayServer.VSYNC_DISABLED:
		return
	var keep: Window = windows.get("backglass", windows.values()[0])
	var others: Array = [get_tree().root] + windows.values()
	for w: Window in others:
		if w != keep:
			DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED, w.get_window_id())


## run.py --dmd-size WxH (Godot's --resolution, which sizes the main window): the size of the DMD window the
## player sees, which is this one when the PuP is on. Vector2i.ZERO when not given.
func _dmd_size_arg() -> Vector2i:
	var root_size := get_tree().root.size
	var default := Vector2i(int(ProjectSettings.get_setting("display/window/size/window_width_override", 0)),
		int(ProjectSettings.get_setting("display/window/size/window_height_override", 0)))
	return root_size if root_size != default and root_size.x > 0 and root_size.y > 0 else Vector2i.ZERO


func _make_window(section: String) -> Window:
	var w := Window.new()
	w.name = "pup_" + section
	w.title = "Tron Legacy - " + section
	w.transient = false
	w.unresizable = false
	w.borderless = bool(setting(section, "borderless", false))
	w.close_requested.connect(func(): pass)
	w.window_input.connect(_forward_input)
	var screen := clampi(int(setting(section, "screen", 0)), 0, DisplayServer.get_screen_count() - 1)
	var size_cfg = setting(section, "size", [800, 600])
	var pos_cfg = setting(section, "position", [0, 0])
	w.size = Vector2i(int(size_cfg[0]), int(size_cfg[1]))
	if section == "dmd" and _dmd_size_arg() != Vector2i.ZERO:
		w.size = _dmd_size_arg()
	w.position = DisplayServer.screen_get_position(screen) + Vector2i(int(pos_cfg[0]), int(pos_cfg[1]))
	# black behind the screens: the window's clear colour, not a full-window ColorRect (one more full-window layer
	# drawn with Godot's canvas shader cost 3 to 6 FPS on a Raspberry Pi 4 with a 1080p backglass)
	RenderingServer.set_default_clear_color(Color.BLACK)
	add_child(w)
	if bool(setting(section, "fullscreen", false)):
		w.current_screen = screen
		w.mode = Window.MODE_FULLSCREEN
	# render_size = [w, h]: the window is drawn at that size and scaled up to the screen (fewer pixels for the GPU
	# to fill: a Raspberry Pi 4 fills ~150-200 Mpixel/s with video layers); the videos keep their resolution
	var render_size = setting(section, "render_size", [])
	if render_size is Array and render_size.size() == 2 and int(render_size[0]) > 0:
		w.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		w.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
		w.content_scale_size = Vector2i(int(render_size[0]), int(render_size[1]))
	windows[section] = w
	return w


## A bare X server (no window manager, the x86 and Pi images) ignores "minimised": the main window, which stays the source of the
## DMD picture and so cannot be closed or shrunk, is then moved far outside every monitor. Checked once, a second after start.
func _check_main_window_hidden() -> void:
	await get_tree().create_timer(1.0).timeout
	var root := get_tree().root
	if root.mode == Window.MODE_MINIMIZED:
		return
	root.position = Vector2i(-16000, -16000)
	print("PuP: the main window is not minimised by this window manager, moved off screen")


## [pup] layout="split" (the default): the backglass at the left, as large as the monitor's height allows (it keeps its own
## shape, 4:3 by default), and the DMD over the topper in the column at the right, `column_scale` (2) times as wide as the
## space the full-height backglass leaves. All borderless, so the sizes are exact: on 1920x1080 the backglass is 960x720 and the
## column 960 wide (the DMD about 960x240, the topper under it). A monitor that leaves the column less than
## a fifth of its width, or a fullscreen backglass, falls back to "stack". A DMD or topper whose `screen` is another monitor
## fills that monitor instead of joining the column.
func _split_windows() -> void:
	var back: Window = windows.get("backglass")
	var screen := clampi(int(setting("backglass", "screen", 0)), 0, DisplayServer.get_screen_count() - 1)
	var column: Array[Window] = []
	for section in ["dmd", "topper"]:
		if not windows.has(section) or windows[section].mode == Window.MODE_FULLSCREEN:
			continue
		var own := clampi(int(setting(section, "screen", 0)), 0, DisplayServer.get_screen_count() - 1)
		if own != screen:
			# [dmd] screen / [topper] screen on another monitor: the window fills that monitor
			windows[section].borderless = true
			windows[section].current_screen = own
			windows[section].mode = Window.MODE_FULLSCREEN
		else:
			column.append(windows[section])
	if back == null or back.mode == Window.MODE_FULLSCREEN or column.is_empty():
		if back != null and back.mode != Window.MODE_FULLSCREEN and not column.is_empty():
			_stack_windows()
		elif back != null and back.mode != Window.MODE_FULLSCREEN:
			# DMD and topper are on other monitors: the backglass alone, as large as its monitor allows
			var a := DisplayServer.screen_get_usable_rect(screen)
			var asp := float(back.size.x) / maxf(1.0, float(back.size.y))
			back.borderless = true
			back.size = Vector2i(mini(a.size.x, int(floor(a.size.y * asp))), int(round(minf(a.size.y, a.size.x / asp))))
			back.position = a.position
		else:
			_stack_windows()
		return
	var area := DisplayServer.screen_get_usable_rect(screen)
	if area.size.x <= 0 or area.size.y <= 0:
		return
	var aspect := float(back.size.x) / maxf(1.0, float(back.size.y))
	if column.size() == 2 and column[0] == windows.get("dmd") and column[1] == windows.get("topper") and _split_left_right(back, column, area):
		return
	var back_max := mini(area.size.x, int(floor(float(area.size.y) * aspect)))
	# the column is what the full-height backglass leaves, times [pup] column_scale (2: twice as wide, so the DMD and the
	# topper are twice as wide; the backglass gives that width up and stays 4:3, a smaller one)
	var col_w := mini(int(float(area.size.x - back_max) * float(setting("pup", "column_scale", 2.0))), int(area.size.x * 0.6))
	var back_w := area.size.x - col_w
	if back_w > back_max:
		back_w = back_max
		col_w = area.size.x - back_w
	if col_w < area.size.x / 5:
		_stack_windows()
		return
	back.borderless = true
	back.size = Vector2i(back_w, int(round(float(back_w) / aspect)))
	back.position = area.position
	# the column: each window keeps its own shape (the DMD its --dmd-size shape when given); when both do not fit the
	# height, both shrink together
	var fixed := _dmd_size_arg()
	var shapes := []
	var total_h := 0.0
	for w in column:
		var src := fixed if (w == windows.get("dmd") and fixed != Vector2i.ZERO) else w.size
		var h := float(col_w) * float(src.y) / maxf(1.0, float(src.x))
		shapes.append(h)
		total_h += h
	var k := minf(1.0, float(area.size.y) / maxf(1.0, total_h))
	var y := area.position.y
	for i in column.size():
		var w := column[i]
		w.borderless = true
		w.size = Vector2i(int(floor(col_w * k)), int(round(shapes[i] * k)))
		w.position = Vector2i(area.position.x + back_w, y)
		y += w.size.y


## The default split: the backglass over the DMD in a left column of `[pup] split_left` (0.5) of the monitor's width, the topper
## in the right column from top to bottom (its videos fitted, not cropped), so the whole screen is used. The DMD keeps its own
## shape (4:1: its picture and frame are drawn for it, a taller window would only add margins) and the backglass takes the
## height that is left, its videos fitted: on 1920x1080 the DMD is 960x240 at the bottom, the backglass 960x840 over it and the
## topper 960x1080. False (nothing placed) when the backglass would get under 40 % of the height.
func _split_left_right(back: Window, column: Array[Window], area: Rect2i) -> bool:
	var left_w := int(area.size.x * clampf(float(setting("pup", "split_left", 0.5)), 0.3, 0.7))
	var dmd: Window = column[0]
	var topper: Window = column[1]
	var dmd_shape := float(dmd.size.y) / maxf(1.0, float(dmd.size.x))
	var fixed := _dmd_size_arg()
	if fixed != Vector2i.ZERO:
		dmd_shape = float(fixed.y) / maxf(1.0, float(fixed.x))
	var dmd_h := int(round(float(left_w) * dmd_shape))
	var back_h := area.size.y - dmd_h
	if back_h < int(area.size.y * 0.4):
		return false
	for w: Window in [back, dmd, topper]:
		w.borderless = true
	back.size = Vector2i(left_w, back_h)
	back.position = area.position
	dmd.size = Vector2i(left_w, dmd_h)
	dmd.position = area.position + Vector2i(0, back_h)
	topper.size = Vector2i(area.size.x - left_w, area.size.y)
	topper.position = area.position + Vector2i(left_w, 0)
	return true


## [pup] layout="stack": backglass, DMD and topper one under the other at the left of the backglass's monitor,
## as wide as fits its height (each keeps the aspect of its size in pup.cfg; run.py --dmd-size keeps the
## DMD's own size). Fullscreen windows stay out of the stack.
func _stack_windows() -> void:
	var order: Array[Window] = []
	for section in ["backglass", "dmd", "topper"]:
		if windows.has(section) and windows[section].mode != Window.MODE_FULLSCREEN:
			order.append(windows[section])
	if order.is_empty():
		return
	var screen := clampi(int(setting("backglass", "screen", 0)), 0, DisplayServer.get_screen_count() - 1)
	var area := DisplayServer.screen_get_usable_rect(screen)
	if area.size.x <= 0 or area.size.y <= 0:
		return
	var fixed := _dmd_size_arg()
	var free_h := float(area.size.y)
	var ratio := 0.0                        # sum of height/width of the windows that take the common width
	for w in order:
		free_h -= _title_height(w)
		if w == windows.get("dmd") and fixed != Vector2i.ZERO:
			free_h -= fixed.y
		else:
			ratio += float(w.size.y) / maxf(1.0, float(w.size.x))
	var width := int(minf(float(area.size.x), free_h / ratio)) if ratio > 0.0 else 0
	var y := area.position.y
	for w in order:
		if not (w == windows.get("dmd") and fixed != Vector2i.ZERO):
			w.size = Vector2i(width, int(round(width * float(w.size.y) / maxf(1.0, float(w.size.x)))))
		y += _title_height(w)
		w.position = Vector2i(area.position.x, y)
		y += w.size.y


func _title_height(w: Window) -> int:
	if w.borderless:
		return 0
	var title := w.get_size_with_decorations().y - w.size.y
	return title if title > 0 else 32


func _make_layered_window(section: String, defaults: Dictionary, volume: float) -> void:
	var w := _make_window(section)
	# [backglass] rect = [x, y, w, h]: the screens' area in the window (its render_size pixels when it has one);
	# with [dmd] window="stacked" and no rect, the window above the DMD band; else the whole window
	var parent: Node = w
	var rect = setting(section, "rect", [])
	var stacked := section == "backglass" and dmd_window_mode() == "stacked"
	if (rect is Array and rect.size() == 4 and float(rect[2]) > 0.0) or stacked:
		var area := Control.new()
		area.name = "pup_%s_screens" % section
		area.mouse_filter = Control.MOUSE_FILTER_IGNORE
		area.clip_contents = true
		if rect is Array and rect.size() == 4 and float(rect[2]) > 0.0:
			area.position = Vector2(float(rect[0]), float(rect[1]))
			area.size = Vector2(float(rect[2]), float(rect[3]))
		else:
			area.anchor_right = 1.0
			area.anchor_bottom = 1.0 - _dmd_band()
		w.add_child(area)
		parent = area
	for n in LAYERS[section]:
		var row: Dictionary = defaults.get(n, {})
		var layer := PupScreen.new()
		layer.setup(self, n, {"popup": n == LAYERS[section][1], "fit": setting(section, "fit", "fit"),
			"align": setting(section, "align", 0.5), "bus": "sfx", "volume": volume,
			"bg_playlist": row.get("PlayList", ""), "bg_file": row.get("PlayFile", "")})
		parent.add_child(layer)
		screens[n] = layer
	if section == "backglass" and bool(setting("backglass", "service_menu", true)):
		service_backglass = ServiceBackglass.new()
		parent.add_child(service_backglass)
		service_backglass.setup(still_path, str(setting(section, "fit", "fit")), float(setting(section, "align", 0.5)))


var _dmd_frame: TextureRect             # the pack's DMD panel art (background="frame" with a frame_image)
var _dmd_crop := Rect2i()
var _cycles: LightCycles                # the light cycle chase (background="lightcycles")
var _neon: ColorRect                    # its neon frame round the DMD
var _dmd_view: TextureRect              # the game's DMD (the main window's picture)
var _dmd_area: Control                  # [dmd] window="backglass": the DMD's area in the backglass window
var _service_dmd_size := -1             # the service menu's PUP DMD SIZE: -1 = pup.cfg's, 0 = cycles, 1 = full
const FRAME_PAD := 20.0                 # the neon frame's line and its glow past the DMD (772 px wide DMD)


func _make_dmd_window() -> void:
	var w: Node
	var mode := dmd_window_mode()
	if mode in ["stacked", "overlay"] and windows.has("backglass"):
		# the DMD drawn in the backglass window: "stacked" in a band under the screens, "overlay" over their bottom;
		# [dmd] rect = [x, y, w, h] (the backglass's render_size pixels when it has one) places it by hand. One full
		# screen window page-flips: a second window made X copy the backglass at every frame (Raspberry Pi 4, 30 FPS
		# cap: 21 instead of 29.6 FPS)
		var bg: Window = windows["backglass"]
		_dmd_area = Control.new()
		_dmd_area.name = "pup_dmd"
		_dmd_area.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_dmd_area.clip_contents = true
		var r = setting("dmd", "rect", [])
		if r is Array and r.size() == 4 and float(r[2]) > 0.0:
			_dmd_area.position = Vector2(float(r[0]), float(r[1]))
			_dmd_area.size = Vector2(float(r[2]), float(r[3]))
		else:
			_dmd_area.anchor_top = 1.0 - _dmd_band()
			_dmd_area.anchor_right = 1.0
			_dmd_area.anchor_bottom = 1.0
		bg.add_child(_dmd_area)
		w = _dmd_area
	else:
		var own := _make_window("dmd")
		# "external": no DMD window on screen (the DMD goes to a real display fed by the game, a PIN2DMD or a
		# ZeDMD), so a fullscreen backglass stays the only window and page-flips
		if mode == "external":
			own.hide()
		w = own
	var background := str(setting("dmd", "background", "lightcycles"))
	var frame_path := str(setting("dmd", "frame_image", ""))
	if background == "lightcycles":
		_cycles = LightCycles.new()
		w.add_child(_cycles)
		_neon = ColorRect.new()
		_neon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_neon.material = ShaderMaterial.new()
		_neon.material.shader = NEON_SHADER
		w.add_child(_neon)
	elif background == "frame" and frame_path != "":
		var image := Image.load_from_file(pack_dir.path_join(frame_path))
		if image:
			var c = setting("dmd", "frame_crop", [0, 0, image.get_width(), image.get_height()])
			_dmd_crop = Rect2i(int(c[0]), int(c[1]), int(c[2]), int(c[3]))
			_dmd_frame = TextureRect.new()
			_dmd_frame.texture = ImageTexture.create_from_image(image.get_region(_dmd_crop))
			_dmd_frame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			_dmd_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
			w.add_child(_dmd_frame)
		else:
			push_warning("PuP: cannot load the DMD frame %s" % frame_path)
	_dmd_view = TextureRect.new()
	_dmd_view.name = "dmd"
	_dmd_view.texture = get_tree().root.get_texture()
	_dmd_view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_dmd_view.stretch_mode = TextureRect.STRETCH_SCALE
	# the game's HD DMD mode (tools/dmd_mode.gd) draws smooth text at its window's size and has its own dots
	var dmd_mode = get_node_or_null("/root/DmdMode")
	var hd: bool = dmd_mode != null and bool(dmd_mode.get("hd"))
	_dmd_view.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR if hd else CanvasItem.TEXTURE_FILTER_NEAREST
	_dmd_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if bool(setting("dmd", "dots", true)) and not hd:
		var mat := ShaderMaterial.new()
		mat.shader = DOTS_SHADER
		mat.set_shader_parameter("dmd_size", Vector2(128, 32))
		_dmd_view.material = mat
	w.add_child(_dmd_view)


## [dmd] window: "window" (its own window, the default), "external" (no DMD on screen: a PIN2DMD or ZeDMD shows it),
## "stacked" (in the backglass window, in a band under its screens) or "overlay" (in the backglass window, over the
## bottom of its screens). Also true, false and "none" (= "external"), "backglass" (= "overlay"). "auto" = "external"
## when the launcher found a PIN2DMD or ZeDMD that answers (TRON_DMD_PANEL, scripts/package/dmd_panel.py), else
## "overlay" (the owner's choice on the Raspberry Pi 4, 2026-10-25).
func dmd_window_mode() -> String:
	var mode := str(setting("dmd", "window", "window")).to_lower()
	if mode == "auto":
		return "external" if OS.get_environment("TRON_DMD_PANEL") != "" else "overlay"
	return {"true": "window", "false": "external", "none": "external", "backglass": "overlay"}.get(mode, mode)


## The DMD band's share of the backglass window's height with "stacked" or "overlay": [dmd] band, 0.25 by default
## (a 16:9 window: the videos 3/4 of its height above, the DMD 4:1 across the middle of the band under them).
func _dmd_band() -> float:
	return clampf(float(setting("dmd", "band", 0.25)), 0.1, 0.5)


## Frame and DMD laid out for the DMD window's current size (again on every resize and size change).
func _layout_dmd() -> void:
	var area := _dmd_area.size if _dmd_area else Vector2(windows["dmd"].size)
	var dmd_rect := Rect2(Vector2.ZERO, area)
	var pa := pixel_aspect()
	if _cycles:
		var w := cycles_dmd_width(area, pa) if not full_size_dmd() else full_dmd_width(area, pa)
		var h := w / 4.0 * pa
		dmd_rect = Rect2((area - Vector2(w, h)) * 0.5, Vector2(w, h))
		_cycles.position = Vector2.ZERO
		_cycles.size = area
		_cycles.show_cycles(not full_size_dmd())
		_cycles.set_dmd_rect(dmd_rect)
		var k := w / 772.0   # the frame was drawn for a 772 px wide DMD (a 1280x390 bar panel)
		_neon.position = Vector2.ZERO
		_neon.size = area
		var neon := {"size": area, "box": Vector4(dmd_rect.position.x, dmd_rect.position.y, w, h),
			"margin": 12.0 * k, "radius": 18.0 * k, "scale": k}
		for key in neon:
			_neon.material.set_shader_parameter(key, neon[key])
	elif _dmd_frame:
		var scale := minf(area.x / _dmd_crop.size.x, area.y / _dmd_crop.size.y)
		var origin := (area - Vector2(_dmd_crop.size) * scale) * 0.5
		_dmd_frame.position = origin
		_dmd_frame.size = Vector2(_dmd_crop.size) * scale
		var c := _dmd_crop
		var r = setting("dmd", "dmd_rect", [c.position.x, c.position.y, c.size.x, c.size.y])
		dmd_rect = Rect2(origin + (Vector2(float(r[0]), float(r[1])) - Vector2(c.position)) * scale,
			Vector2(float(r[2]), float(r[3])) * scale)
	# the game's 128x32 DMD, 4:1 on the glass (pa: the monitor's pixels may not be square), centred in its rect
	var dmd_size := Vector2(128, 32 * pa)
	var k := minf(dmd_rect.size.x / dmd_size.x, dmd_rect.size.y / dmd_size.y)
	_dmd_view.size = dmd_size * k
	_dmd_view.position = dmd_rect.position + (dmd_rect.size - _dmd_view.size) * 0.5


## The DMD window's size ([dmd] dmd_size in pup.cfg, the service menu's ADJUSTMENTS > DISPLAY ADJUSTMENTS >
## PUP DMD SIZE over it): false = "cycles", a smaller DMD with the light cycles round it; true = "full", the DMD
## full size over the grid alone.
func full_size_dmd() -> bool:
	if _service_dmd_size >= 0:
		return _service_dmd_size == 1
	return str(setting("dmd", "dmd_size", "cycles")) == "full"


## A pixel's width over its height on the DMD window's monitor: [dmd] screen_mm (the monitor's picture, in mm)
## over its resolution. 1 (square pixels) without screen_mm. A 1280x390 bar of 360x109 mm: 0.28125 mm over
## 0.27949 mm = 1.0063, so a DMD 4:1 on the glass is 0.6% taller than 4:1 in pixels.
func pixel_aspect() -> float:
	var mm := screen_mm()
	var px := Vector2(DisplayServer.screen_get_size(_dmd_screen()))
	if mm == Vector2.ZERO or px.x <= 0.0 or px.y <= 0.0:
		return 1.0
	return (mm.x / px.x) / (mm.y / px.y)


## [dmd] screen_mm as a Vector2, ZERO when not given.
func screen_mm() -> Vector2:
	var mm = setting("dmd", "screen_mm", [0, 0])
	var v := Vector2(float(mm[0]), float(mm[1])) if mm is Array and mm.size() == 2 else Vector2.ZERO
	return v if v.x > 0.0 and v.y > 0.0 else Vector2.ZERO


func _dmd_screen() -> int:
	if windows.has("dmd"):
		return windows["dmd"].current_screen
	if _dmd_area:
		return windows["backglass"].current_screen
	return int(setting("dmd", "screen", 0))


## "cycles": lightcycles_dmd of the window's width, at most lightcycles_dmd_height of its height.
func cycles_dmd_width(area: Vector2, pa: float) -> float:
	return minf(area.x * float(setting("dmd", "lightcycles_dmd", 0.68)),
		area.y * float(setting("dmd", "lightcycles_dmd_height", 0.62)) * 4.0 / pa)


## "full": as large as the window takes with the neon frame round it (FRAME_PAD of a 772 px wide DMD on each
## side), and no wider than [dmd] full_dmd_mm (the width of a real DMD, 320 mm) when screen_mm is given.
## docs/pup/README.md, "DMD size", has the 1280x390 bar's numbers.
func full_dmd_width(area: Vector2, pa: float) -> float:
	var pad := 2.0 * FRAME_PAD / 772.0
	var w := minf(area.x / (1.0 + pad), area.y / (pa / 4.0 + pad))
	var cap := float(setting("dmd", "full_dmd_mm", 320))
	var mm := screen_mm()
	var px := Vector2(DisplayServer.screen_get_size(_dmd_screen()))
	if cap > 0.0 and mm != Vector2.ZERO and px.x > 0.0:
		w = minf(w, cap / (mm.x / px.x))
	return w


## The service menu's PUP DMD SIZE (MPF machine variable pup_dmd_size, tron/settings.py DisplaySettings,
## sent by GMC's machine variable monitor): -1 = pup.cfg's dmd_size, 0 = with the light cycles, 1 = full size.
func _follow_service_settings() -> void:
	var mpf = get_tree().root.get_node_or_null("MPF")
	if mpf == null or mpf.game == null:
		return
	mpf.game.machine_update.connect(service_setting)
	if mpf.game.machine_vars.has("pup_dmd_size"):
		service_setting("pup_dmd_size", mpf.game.machine_vars["pup_dmd_size"])


func service_setting(var_name: String, value) -> void:
	if var_name != "pup_dmd_size" or not str(value).is_valid_int():
		return
	var v := clampi(str(value).to_int(), -1, 1)
	if v == _service_dmd_size:
		return
	var was := full_size_dmd()
	_service_dmd_size = v
	if full_size_dmd() != was and (windows.has("dmd") or _dmd_area):
		print("PuP: DMD %s (service menu)" % ("full size" if full_size_dmd() else "with the light cycles"))
		_layout_dmd()


func _forward_input(event: InputEvent) -> void:
	# keys pressed in a PuP window drive the game like keys in the DMD window (gmc.cfg [keyboard], Esc)
	get_tree().root.push_input(event)

# ------------------------------------------------------------------ MPF

func _on_pup_hello(_message: Dictionary) -> void:
	if not enabled or windows.is_empty():
		return
	MPF.server.send_event_with_args("pup_ready", {"ost": 1 if screens.has(MUSIC_SCREEN) else 0}, false)


## The service menu's screen for the backglass (tron/service_backglass.py); dropped without a backglass.
func _on_service_backglass(message: Dictionary) -> void:
	if service_backglass == null:
		return
	var parsed = JSON.parse_string(str(message.get("state", "")))
	if parsed is Dictionary:
		service_backglass.show_state(parsed)


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
			# in order from a random first file: the pack's AlphaSort playlists are numbered variants
			# (StartGame 1-3, Drain1-5), and starting at 1 every boot showed the same one first
			var i: int = _next.get(playlist, randi()) % files.size()
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


## Where a pack file plays from: the pack's own video with the native_video add-on or GoZen, else the converted copy.
func media_path(key: String) -> String:
	var entry: Dictionary = manifest[key]
	if (native_video or gozen) and entry.has("w") and key.get_extension().to_lower() in ["mp4", "m4v", "mov"]:
		return pack_dir.path_join(key)
	if not entry.has("out"):
		push_warning("PuP: %s was not converted (gen_pup.py --native) and no video add-on is loaded" % key)
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
	_audio_lock.lock()
	var kept = _audio_cache.get(path)
	_audio_lock.unlock()
	if kept != null:
		return kept
	return _read_audio(path)


## The pack's music (mp3, ogg) read and decoded on a worker at start, one file after the other, so no first play
## reads it on the main thread (20-60 ms per mp3 on a Jetson Xavier NX). Memory: the same as after a game that played them
## all, since every played stream stays cached anyway.
func _preload_audio() -> void:
	var paths: Array[String] = []
	for key in manifest:
		if key.get_extension().to_lower() in ["mp3", "ogg"]:
			var path := media_path(key)
			if path != "":
				paths.append(path)
	if paths.is_empty():
		return
	WorkerThreadPool.add_task(func():
		var t0 := Time.get_ticks_msec()
		var bytes := 0
		for path in paths:
			var stream := _read_audio(path)
			if stream is AudioStreamMP3:
				bytes += stream.data.size()
		print("PuP: %d music files preloaded (%.1f MB) in %d ms" % [
			paths.size(), bytes / 1048576.0, Time.get_ticks_msec() - t0]),
		false, "PuP music preload")


func _read_audio(path: String) -> AudioStream:
	_audio_lock.lock()
	var kept = _audio_cache.get(path)
	_audio_lock.unlock()
	if kept != null:
		return kept
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
	_audio_lock.lock()
	if _audio_cache.has(path):          # read on both threads at once: keep the first
		stream = _audio_cache[path]
	else:
		_audio_cache[path] = stream
	_audio_lock.unlock()
	return stream


func load_image(path: String) -> Texture2D:
	var image := Image.load_from_file(path)
	return ImageTexture.create_from_image(image) if image else null

# ------------------------------------------------------------------ checks without a screen

## godot --path game -- --pup-capture-dir=/abs/path [--pup-capture-every-ms=2000]: saves every PuP window
## as <window>_NNNN.png (scripts/pup/pup_check.py).
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
