extends RefCounted
## A display effect drawn from its data instead of a scene of nodes: media/dmd/<name>/effect.json (scripts/gen_media.py
## write_effect()), its items in drawing order, as the effect's node scene (media/dmd/<name>/nodes.tscn) has its nodes:
##   {"type": "rect", "name", "x", "y", "w", "h", "level", "color"}      a filled rectangle (Background, Clear*, panel)
##   {"type": "frames", "name", "loop", "frames": [[picture, ms], ...]}  the effect's pictures, each shown for ms
##   {"type": "scroll", "name", "pic", "w", "h", "from", "to", "ms", "hold_ms"}   a picture moving up the display (attract logo)
##   {"type": "letters", "sprites": [{"name", "pic", "x", "y", "level", "color", "letter"}], ...}   tron/letter_panel.gd
##   {"type": "arcade", "cabinets", "icons_a", "icons_b", "frame_ms"}    tron/arcade_reel.gd
##   {"type": "text", "name", "var", "font", "x", "y", "flags", ...}     a line of ROM text, tron/rom_text.gd's fields
##   {"type": "panel", "score_lines", "match"}                          tron/score_display.gd over the named items
## A picture is a res:// path: a picture of media/dmd/ is shown in HD as its twin of media/dmd_hd/ (tools/dmd_mode.gd);
## any other picture (redrawn art, a larger frame) is shown as it is, fitted to the 128x32 box. The data can be edited
## or replaced by hand: nothing else needs generating again.
## Colour (HD with tools/dmd_mode.gd's colour on; scripts/dmd_color.py annotate()): the frames item's "color_frames"
## (pictures of media/dmd_color/, frame for frame, drawn as they are), a text line's "color" and a rectangle's
## "color_rgb" ("#rrggbb", in place of the text colour), a letter's "color_pic", the arcade reel's "color_cabinets",
## "color_icons_a" and "color_icons_b". Recorded text lines take their colours from media/dmd_color/text_colors.json.
##
## One State per show of the effect (tron/dmd_effect_slide.gd): its time, the values MPF sent, the lines' text; build()
## turns it into a draw list for tron/dmd_screen.gd, the same pixels the node scene draws (tests/test_dmd_hd.py). The
## logic is the node scripts' own, item for item (rom_text.gd, score_display.gd, letter_panel.gd, arcade_reel.gd).

const DmdEffect = preload("res://tron/dmd_effect.gd")
const RomText = preload("res://tron/rom_text.gd")
const RomTextHd = preload("res://tron/rom_text_hd.gd")
const LetterPanel = preload("res://tron/letter_panel.gd")
const ScoreDisplay = preload("res://tron/score_display.gd")
const ArcadeReel = preload("res://tron/arcade_reel.gd")
const MEDIA := "res://media/dmd/"
const MEDIA_HD := "res://media/dmd_hd/"
const DMD_COLOR := Color(1, 0.45, 0.05, 1)
const BOX := Rect2(0, 0, 128, 32)
const NO_INK := Color(0, 0, 0, 0)        # an HD line in the text colour (else its own colour: the colourisation's)

static var _data: Dictionary = {}       # effect.json path -> its items (parsed once)
static var _clips = null                # media/dmd_clip/clips.json (scripts/pup/gen_dmd_clips.py), parsed once

## The PuP clips on the DMD (HD): "clips" {effect: {"files": [...], "loop", "ms"}} are played behind the effect's text in place of
## its pictures, one of the files at random per show; "icons" {effect: picture} are the topper's HD icon of a character that
## glides into the hexagonal frame in place of the ROM's face. Off with TRON_DMD_CLIPS=0 or the project setting
## tron/dmd/clips; nothing is drawn differently when the clips are not made (the pack is private) or GDE GoZen is not installed.
const CLIP_DATA := "res://media/dmd_clip/clips.json"
const CLIP_PLAYER := "res://addons/gde_gozen/video_playback.gd"
const PANEL_SCORE_ZOOM := 1.25          # the status panel's small scores (P1-P4) are drawn this much larger in HD,
const PANEL_SCORE_ROOM := 39            # but never wider than this many dots (the panel is 40 wide)
const ICON_CENTRE_X := 58.0             # where the icon rests, in dots: left of the text, which is centred at x 100
const CLIP_NO_TEXT := ["deff_104"]          # the clip says it (the ROM's "ARCADE IS LIT" would only repeat it)
const ICON_TEXT_X := 100.0               # the text beside the icon is centred here
const ICON_GLIDE_MS := 600.0            # the face slides in from the right in this time


static func clips() -> Dictionary:
	if _clips == null:
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(CLIP_DATA)) if FileAccess.file_exists(CLIP_DATA) else null
		_clips = parsed if parsed is Dictionary else {}
	return _clips


## The redrawn mystery award icon (hd_art/deff_105/award_NN.png, scripts/pup/award_sprites.py), or null: the ROM's icon.
static var _award_art := {}

## The icon last drawn and when (ms): an icon effect that follows another with the same face right away does not glide
## in again (the ROM replays the glide on each show; on the larger HD icon it read as a loop).
static var _icon_seen := ["", -100000]

## The clip last drawn: {"name", "path", "show", "t" (ms)}. An effect shown again right after itself (the ROM re-shows
## it for each new counter value) goes on with the same video instead of starting it over.
static var _clip_last := {"name": "", "path": "", "show": 0, "t": -100000}
static var _show_seq := 0
const CLIP_RESUME_MS := 700


static func award_art(id: int) -> Texture2D:
	if OS.get_environment("TRON_AWARD_ART").to_lower() in ["0", "off", "false"]:
		return null
	if not _award_art.has(id):
		var path := "res://hd_art/deff_105/award_%02d.png" % id
		var tex: Texture2D = null
		if FileAccess.file_exists(path):
			var img := Image.load_from_file(ProjectSettings.globalize_path(path))
			if img:
				img.generate_mipmaps()
				tex = ImageTexture.create_from_image(img)
		_award_art[id] = tex
	return _award_art[id]


static var _hd_art := {}


## A picture of game/hd_art (not in the import: loaded from the file), or null.
static func hd_art(path: String) -> Texture2D:
	if not _hd_art.has(path):
		var tex: Texture2D = null
		if FileAccess.file_exists(path):
			var img := Image.load_from_file(ProjectSettings.globalize_path(path))
			if img:
				img.generate_mipmaps()
				tex = ImageTexture.create_from_image(img)
		_hd_art[path] = tex
	return _hd_art[path]


static var _letter_art := {}


## The topper's HD letter ("Z", on = collected: red, else blue) of scripts/pup/letter_art.py, or null.
static func letter_art(letter: String, on: bool) -> Texture2D:
	if OS.get_environment("TRON_LETTER_ART").to_lower() in ["0", "off", "false"]:
		return null
	var key := "%s_%s" % [letter, "on" if on else "off"]
	if not _letter_art.has(key):
		var path := "res://hd_art/letters/%s.png" % key
		var tex: Texture2D = null
		if FileAccess.file_exists(path):
			var img := Image.load_from_file(ProjectSettings.globalize_path(path))
			if img:
				img.generate_mipmaps()
				tex = ImageTexture.create_from_image(img)
		_letter_art[key] = tex
		print("DMD: letter art %s: %s" % [key, "loaded" if tex else "missing at " + ProjectSettings.globalize_path(path)])
	return _letter_art[key]


## The ROM picks one of several film clips at random for some effects (assets/mpf_package/config/dmd_variants.yaml: the Disc
## Multiball and Light Cycle jackpots, Quorra's, the Sea of Simulation stages ...); the effect's "variants" hold them. Off for
## the render checks (tools/slide_capture.gd), which compare the one clip the reference capture shows.
static var _variant_rng: RandomNumberGenerator = null


## The index of the clip picked among `n`: random, or from a fixed sequence when TRON_DMD_SEED is set (reproducible runs: the
## conformance checks repeat a scenario and get the same clips).
static func pick_variant(n: int) -> int:
	if _variant_rng == null:
		_variant_rng = RandomNumberGenerator.new()
		var seed_text := OS.get_environment("TRON_DMD_SEED")
		if seed_text != "":
			_variant_rng.seed = int(seed_text)
		else:
			_variant_rng.randomize()
	return _variant_rng.randi() % n


static func variants_enabled() -> bool:
	return bool(ProjectSettings.get_setting("tron/dmd/variants", true))


static func clips_enabled() -> bool:
	var env := OS.get_environment("TRON_DMD_CLIPS").to_lower()
	if env in ["0", "off", "false"]:
		return false
	if env in ["1", "on", "true"]:
		return true
	return bool(ProjectSettings.get_setting("tron/dmd/clips", true))


## The items of an effect's data ([] when it cannot be read).
static func items_of(path: String) -> Array:
	if not _data.has(path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		_data[path] = _ints(parsed.get("items", [])) if parsed is Dictionary else []
		if not parsed is Dictionary:
			push_warning("DMD effect %s: no data" % path)
	return _data[path]


## JSON's numbers are floats: whole ones become ints (flags, positions, fonts are used as ints).
static func _ints(v):
	if v is Array:
		return v.map(func(x): return _ints(x))
	if v is Dictionary:
		var out := {}
		for k in v:
			out[k] = _ints(v[k])
		return out
	if v is float and v == floorf(v) and absf(v) < 1e9:
		return int(v)
	return v


static func _dmd() -> Node:
	return (Engine.get_main_loop() as SceneTree).root.get_node_or_null("DmdMode")


## The picture drawn for a picture path: in HD its media/dmd_hd/ twin when there is one.
static func picture(path: String, hd: bool) -> Texture2D:
	if hd and path.begins_with(MEDIA):
		var big := MEDIA_HD + path.trim_prefix(MEDIA)
		if ResourceLoader.exists(big):
			return load(big)
	return load(path) if ResourceLoader.exists(path) else null


class State extends RefCounted:
	var items: Array
	var hd := false
	var color := false             # the colourisation's colours (HD, tools/dmd_mode.gd color)
	var color_scale := 2.0         # media/dmd_color/ pictures are this many times the classic ones
	var elapsed_ms := 0.0
	var seeked := false
	var values := {}               # every event arg received (the panel, letters and reel read them)
	var received_ms := 0.0         # time of the last update (the panel's ages count from there)
	var texts := {}                # text item index -> its text
	var use_alt := {}              # text item index -> drawn at alt_x / alt_y
	var screen_on := {}            # text item index -> its screen is shown
	var _pictures := {}            # picture path -> texture (loaded once per show)
	var _durations := PackedFloat32Array()
	var _total_ms := 0.0
	var _frames_item := -1
	var _variant := -1             # the clip picked for this show (item "variants"), -1: the effect's own frames
	var effect_name := ""          # deff_NNN, to find the effect's clips (tron/dmd_effect_slide.gd)
	var clip_path := ""            # the PuP clip playing behind the text for this show (absolute path), "" for the ROM's pictures
	var clip_loop := false
	var icon_path := ""            # the character's HD icon replacing the ROM's face
	var show := 0                  # counts the shows: a new one restarts the clip
	var glide_done := false        # the same icon was on screen a moment ago: it stays in place

	func _init(of: Array, hd_mode: bool, name := "") -> void:
		items = of
		hd = hd_mode
		effect_name = name
		var dmd = DmdEffect._dmd()
		color = hd and dmd != null and dmd.color
		for i in items.size():
			if items[i]["type"] == "frames":
				_frames_item = i
		reset()

	## Back to the start of a show: time 0, no values, no text (as a node scene just built).
	func reset() -> void:
		elapsed_ms = 0.0
		seeked = false
		_pick_variant()
		clip_path = ""
		icon_path = ""
		if hd and effect_name != "" and DmdEffect.clips_enabled() and ResourceLoader.exists(DmdEffect.CLIP_PLAYER):
			var data := DmdEffect.clips()
			var c: Dictionary = data.get("clips", {}).get(effect_name, {})
			if c.get("files", []).size():
				var last: Dictionary = DmdEffect._clip_last
				if last["name"] == effect_name and Time.get_ticks_msec() - int(last["t"]) < DmdEffect.CLIP_RESUME_MS:
					clip_path = last["path"]
					show = int(last["show"])           # the same show: the video is not restarted
				else:
					clip_path = ProjectSettings.globalize_path(c["files"].pick_random())
					DmdEffect._show_seq += 1
					show = DmdEffect._show_seq
				clip_loop = bool(c.get("loop", false))
			icon_path = str(data.get("icons", {}).get(effect_name, ""))
		glide_done = icon_path != "" and DmdEffect._icon_seen[0] == icon_path \
			and Time.get_ticks_msec() - int(DmdEffect._icon_seen[1]) < 700
		values = {}
		received_ms = 0.0
		texts = {}
		use_alt = {}
		screen_on = {}
		for i in items.size():
			var it: Dictionary = items[i]
			if it["type"] == "text":
				texts[i] = ""
				use_alt[i] = false
				screen_on[i] = it.get("screens", []).has(0) if it.get("screens", []).size() else true

	func advance(delta: float) -> void:
		if not seeked:
			elapsed_ms += delta * 1000.0

	func seek_ms(t: float) -> void:
		seeked = true
		elapsed_ms = t

	## The event args of a show or an update (GMC's action_update), as each node script takes them.
	func update(settings: Dictionary, kwargs: Dictionary) -> void:
		for k in kwargs:
			values[k] = kwargs[k]
		received_ms = elapsed_ms
		for i in items.size():
			var it: Dictionary = items[i]
			if it["type"] != "text":
				continue
			if it.get("screens", []).size():           # tron/rom_text.gd update()
				var shown = kwargs.get("screen", settings.get("screen", null))
				if shown != null and str(shown) != "":
					screen_on[i] = it["screens"].has(int(shown))
			if it.get("alt_when_empty", "") != "":
				var other = kwargs.get(it["alt_when_empty"], settings.get(it["alt_when_empty"], ""))
				use_alt[i] = other == null or str(other) == ""
			var v = null                                 # MPFVariable update(): kwargs, tokens, settings
			var has := true
			if it["var"] in kwargs:
				v = kwargs[it["var"]]
			elif it["var"] in settings.get("tokens", {}):
				v = settings["tokens"][it["var"]]
			elif it["var"] in settings:
				v = settings[it["var"]]
			else:
				has = false
			if has:
				texts[i] = "" if v == null else ("%s" % v if (v is int or v is float) else str(v))

	func _int(key: String, default := 0) -> int:
		var v = values.get(key, default)
		return int(v) if v != null and str(v) != "" else default

	## The frames of this show: the effect's own, or the clip picked at random among its variants.
	func _frames() -> Array:
		var it: Dictionary = items[_frames_item]
		return it["variants"][_variant] if _variant >= 0 else it["frames"]

	func _pick_variant() -> void:
		_durations = PackedFloat32Array()
		_total_ms = 0.0
		_variant = -1
		if _frames_item < 0:
			return
		var vs: Array = items[_frames_item].get("variants", [])
		if vs.size() and DmdEffect.variants_enabled():
			_variant = DmdEffect.pick_variant(vs.size())
		for f in _frames():
			_durations.append(float(f[1]))
			_total_ms += float(f[1])

	## The frame shown at the current time (AnimatedSprite2D's timing: each picture for its ms; a loop starts over).
	func frame_index() -> int:
		if _durations.is_empty() or _total_ms <= 0.0:
			return 0
		var t := elapsed_ms
		if items[_frames_item].get("loop", false):
			t = fmod(t, _total_ms)
		var acc := 0.0
		for i in _durations.size():
			acc += _durations[i]
			if t < acc:
				return i
		return _durations.size() - 1

	func _picture(path: String) -> Texture2D:
		if not _pictures.has(path):
			_pictures[path] = DmdEffect.picture(path, hd)
		return _pictures[path]

	## The draw list of the current time: what tron/dmd_screen.gd draws, in order. Lists are compared to redraw only
	## on a change, so they hold values, not objects made here.
	func build() -> Array:
		var dmd = DmdEffect._dmd()
		var text_color: Color = dmd.text_color if hd and dmd else Color.WHITE
		var out: Array = []
		var panel := _panel_state()
		for i in items.size():
			var it: Dictionary = items[i]
			match it["type"]:
				"rect":
					var r := Rect2(it["x"], it["y"], it["w"], it["h"])
					var c := Color(it["color"][0], it["color"][1], it["color"][2], 1)
					var mod := Color.WHITE
					var st: Dictionary = panel.get(it["name"], {})
					if clip_path != "":
						continue                         # the ROM's blocks: the clip is behind the text
					if st.has("visible") and not st["visible"]:
						continue
					if st.has("rect"):
						r = st["rect"]
					if st.has("mod"):
						mod = st["mod"]
					if color and it.has("color_rgb"):
						c = Color(it["color_rgb"])
					elif hd and it["name"] != "Background":
						c = dmd.text_tint(c)
					if r.size.x > 0 and r.size.y > 0:
						out.append(["rect", r, c * mod])
				"frames":
					var k := frame_index()
					var all := _frames()
					var f: Array = all[k] if all.size() else []
					if clip_path != "" or icon_path != "":
						_clip_frame(out, f, dmd)
						continue
					if hd and effect_name == "deff_080" and _clu_letters(out):
						continue
					if color and _variant < 0 and f.size() and it.has("color_frames") and k < it["color_frames"].size():
						var ctex := _picture(it["color_frames"][k])
						if ctex:
							out.append(["tex", ctex, BOX, Color.WHITE])
							_frame_text(out, str(f[0]).trim_prefix(MEDIA), dmd, true)
							continue
					var tex := _picture(f[0]) if f.size() else null
					if tex:
						out.append(["tex", tex, BOX, dmd.text_tint(DMD_COLOR) if hd else DMD_COLOR])
						if hd and tex.resource_path.begins_with(MEDIA_HD):
							_frame_text(out, tex.resource_path.trim_prefix(MEDIA_HD), dmd)
				"scroll":
					var art: Texture2D = DmdEffect.hd_art(str(it["hd_pic"])) if hd and it.has("hd_pic") else null
					var pic := art if art else _picture(it["pic"])
					if pic:
						var h := float(it["h"])
						if art:                       # the owner's coloured picture, as wide as the display
							h = 128.0 * art.get_height() / art.get_width()
						var u := clampf(elapsed_ms / float(it["ms"]), 0.0, 1.0)
						var y := floorf(lerpf(float(it["from"]), -h, u))
						out.append(["tex", pic, Rect2(0.0, y, float(it["w"]) if not art else 128.0, h),
							Color.WHITE if art else (dmd.text_tint(DMD_COLOR) if hd else DMD_COLOR)])
				"letters":
					_letters(out, it, dmd)
				"arcade":
					_arcade(out, it, dmd)
				"text":
					_text(out, i, it, panel.get(it["name"], {}))
		return out

	# ------------------------------------------------------------------ text (tron/rom_text.gd)

	func _timed(it: Dictionary) -> bool:
		return it.get("show_after_ms", 0) or it.get("hide_after_ms", 0) or it.get("blink_ms", 0) \
			or it.get("cycle_ms", 0) or it.get("level_steps", []).size()

	func _text(out: Array, i: int, it: Dictionary, st: Dictionary) -> void:
		var visible: bool = screen_on[i]
		var mod := Color.WHITE
		if _timed(it):                                    # rom_text.gd _apply_time()
			var show_after: int = it.get("show_after_ms", 0)
			var hide_after: int = it.get("hide_after_ms", 0)
			var blink: int = it.get("blink_ms", 0)
			var cycle: int = it.get("cycle_ms", 0)
			var blink_dark: bool = it.get("blink_dark", false)
			var blink_on := blink == 0 or int((elapsed_ms - show_after) / blink) % 2 == 0
			var cycle_on: bool = cycle == 0 or fposmod(elapsed_ms - it.get("cycle_offset_ms", 0), cycle) \
				< it.get("cycle_on_ms", 0)
			visible = screen_on[i] and cycle_on and elapsed_ms >= show_after \
				and (hide_after == 0 or elapsed_ms < hide_after) and (blink_on or blink_dark)
			if blink_dark:
				mod = Color(1, 1, 1, 1) if blink_on else Color(0, 0, 0, 1)
			var steps: Array = it.get("level_steps", [])
			var step: int = it.get("step_ms", 0)
			if steps.size() and step > 0:
				var level: float = steps[mini(int(elapsed_ms / step), steps.size() - 1)] / 15.0
				mod = Color(level, level, level, 1)
		if st.has("visible"):
			visible = st["visible"]
		if st.has("mod"):
			mod = st["mod"]
		if not visible:
			return
		var lay := _layout(i, it, st.get("rom_y", it["y"]))
		if lay.is_empty() or lay["text"] == "":
			return
		if hd and clip_path != "" and it["name"] in ["P1", "P2", "P3", "P4"] and lay["text"] in ["0", "00"]:
			return                      # an empty score drawn white over a clip: a stray "00"
		var flags: int = it["flags"]
		if hd and icon_path != "" and int(it["x"]) > 41:       # beside the icon the lines are centred, not against the right edge
			flags = 2
			lay["pos"].x = ICON_TEXT_X - float(lay["w"]) / 2.0
		var xf := Transform2D(0.0, lay["pos"])
		if hd and it["name"] in ["P1", "P2", "P3", "P4"] and flags & 4:
			# the small scores of the status panel: a little larger than the ROM's, about the right edge and the baseline
			var z := minf(PANEL_SCORE_ZOOM, float(PANEL_SCORE_ROOM) / maxf(float(lay["w"]), 1.0))
			var anchor := Vector2(lay["pos"].x + float(lay["w"]), lay["pos"].y + float(lay["ascent"]) - 1.0)
			xf = Transform2D(0.0, Vector2(z, z), 0.0, anchor + (lay["pos"] - anchor) * z)
		if hd:
			out.append(["htext", [lay["text"], lay["font"], lay["ascent"], lay["line_h"], lay["w"], flags, 0, -1],
				xf, mod, Rect2(), Color(it["color"]) if color and it.has("color") else NO_INK,
				(1 if effect_name == "deff_019" and it["name"] == "Line1" else (2 if it["name"] in ["P1", "P2", "P3", "P4", "Award"] else 0)),
				clip_path != "" or icon_path != ""])
		else:
			var font := RomText.font_file(lay["font"])
			out.append(["ctext", font, lay["text"], lay["pos"] + Vector2(0, font.get_ascent(lay["line_h"])),
				lay["line_h"], DMD_COLOR * mod])

	## rom_text.gd _layout(): the font (first of fit_fonts that fits), the text it can draw, the place.
	func _layout(i: int, it: Dictionary, rom_y: int) -> Dictionary:
		var text: String = texts[i]
		var font_id: int = it["font"]
		var y := rom_y
		var m := RomText.font_metrics(font_id)
		var shown := ""
		for c in text:
			if m.get("glyphs", {}).has(c):
				shown += c
		var fits: Array = it.get("fit_fonts", [])
		var fit_ys: Array = it.get("fit_ys", [])
		for k in fits.size():
			var fm := RomText.font_metrics(fits[k])
			var fs := ""
			for c in text:
				if fm["glyphs"].has(c):
					fs += c
			font_id = fits[k]
			m = fm
			shown = fs
			y = fit_ys[k] if k < fit_ys.size() else rom_y
			var mins: Array = it.get("score_min", [])
			if mins.size() > k:
				if int(text.replace(",", "")) >= int(mins[k]):
					break
			elif RomText.rom_width(fm, fs) <= it.get("fit_width", 0):
				break
		if m.is_empty():
			return {}
		texts[i] = shown                                   # as the label keeps it
		var alt: bool = use_alt[i]
		var x: int = it.get("alt_x", 0) if alt else it["x"]
		if alt:
			y = it.get("alt_y", 0)
		var w := RomText.rom_width(m, shown)
		var left := x
		if it["flags"] & 2:
			left = x - w / 2
		elif it["flags"] & 4:
			left = x + 1 - w
		var ascent := int(m["ascent"])
		return {"text": shown, "font": font_id, "pos": Vector2(left, y - ascent + 1), "w": w, "ascent": ascent,
			"line_h": ascent + int(m["descent"])}

	# ------------------------------------------------------------------ status panel (tron/score_display.gd)

	## The panel's changes to its named items: {name: {"visible", "mod", "rom_y", "rect"}}.
	func _panel_state() -> Dictionary:
		var out := _panel_state_rom()
		if clip_path != "" or icon_path != "":      # no ROM dot left over the clip or the icon: the separator, the dashes, the bars
			for n in ["Separator", "Dash0", "Dash1", "Dash2", "BarDs", "BarBumpers", "BarSpinners", "BarZfs", "BarClu", "BarGem"]:
				out[n] = {"visible": false}
		return out

	func _panel_state_rom() -> Dictionary:
		var panel := {}
		for it in items:
			if it["type"] == "panel":
				panel = it
		if panel.is_empty():
			return {}
		var out := {}
		var ticks := int(elapsed_ms / ScoreDisplay.TICK_MS)
		if values.has("rot_ms"):                  # the rotation runs on the machine's clock, not the effect's
			ticks = int((_int("rot_ms") + elapsed_ms - received_ms) / ScoreDisplay.TICK_MS)
		var since := int((elapsed_ms - received_ms) / ScoreDisplay.TICK_MS)
		var players := maxi(_int("players", 1), 1)
		var current := _int("player", 1)
		var replay := str(values.get("replay", ""))
		var alt := replay != "" and ScoreDisplay.replay_phase(ticks)
		var score_lines: bool = panel.get("score_lines", false)
		var match_panel: bool = panel.get("match", false)
		if score_lines:
			out["Line0"] = {"visible": not alt}
			out["Credits"] = {"visible": not alt}
			out["Replay"] = {"visible": alt}
		var blink_age := _int("blink_age", 0) + since
		var blank := not bool(values.get("valid", true)) and blink_age >= 63 and (blink_age - 62) % 14 <= 6
		if score_lines:
			out["Line1"] = {"visible": not blank}
		for p in range(1, 5):
			var st := {"visible": p <= players and not (blank and p == current),
				"rom_y": 21 if p == 2 and players == 2 else p * 8 - 3,
				"mod": Color(1, 1, 1, 1) if p == current else (Color(0.5, 0.5, 0.5, 1) if hd else Color(0.2, 0.2, 0.2, 1))}
			if match_panel:
				st["visible"] = p <= players
				st["mod"] = Color(2 / 15.0, 2 / 15.0, 2 / 15.0, 1)
			out["P%d" % p] = st
		if match_panel:
			out["Separator"] = {"mod": Color(15, 15, 15, 1)}
			for n in ["Award", "Dash0", "Dash1", "Dash2", "BarDs", "BarBumpers", "BarSpinners", "BarZfs", "BarClu",
					"BarGem"]:
				out[n] = {"visible": false}
			return out
		var age := _int("award_age", 99) + since
		var lv := ((26 - age) >> 1) / 15.0
		out["Award"] = {"visible": players < 3 and _int("award", 0) != 0 and age < 26,
			"rom_y": 13 if current == 1 else current * 8 + 13, "mod": Color(lv, lv, lv, 1)}
		for b in [["BarDs", "bar_ds", 4], ["BarBumpers", "bar_bumpers", 16], ["BarSpinners", "bar_spinners", 28]]:
			out[b[0]] = {"rect": Rect2(b[2], 31, clampi(_int(b[1]), 0, 10), 1)}
		for b in [["BarZfs", "bar_zfs", 10], ["BarClu", "bar_clu", 21], ["BarGem", "bar_gem", 32]]:
			var n := clampi(_int(b[1]), 0, 10)
			out[b[0]] = {"rect": Rect2(40, b[2] - n, 1, n)}
		return out

	## The C, L, U of deff 80 (the CLU targets) redrawn smooth (scripts/pup/letter_art.py clu_letters): the ROM's blocks
	## upscaled looked smeared. False when the pictures are not there.
	func _clu_letters(out: Array) -> bool:
		var arts: Array = []
		for l in ["C", "L", "U"]:
			var art := DmdEffect.letter_art("CLU_" + l, true)
			if art == null:
				return false
			arts.append(art)
		var cells := [47.0, 74.0, 101.0]         # the ROM letters: 20 dots wide, rows 6-25, 27 dots apart
		for i in 3:
			var m := 20.0 * 0.14 / (1.0 - 2.0 * 0.14)       # the picture has 14 % margin
			out.append(["tex", arts[i], Rect2(cells[i] - m, 6.0 - m, 20.0 + 2 * m, 20.0 + 2 * m), Color.WHITE])
		return true

	# ------------------------------------------------------------------ letters (tron/letter_panel.gd)

	func _mask(key: String) -> int:
		if key == "":
			return 0
		var v = values.get(key, 0)
		return int(v) if v != null and str(v) != "" else 0

	func _letters(out: Array, it: Dictionary, dmd) -> void:
		var frame_ms: float = it["frame_ms"]
		var frame := int(elapsed_ms / frame_ms) if frame_ms > 0 else 0
		var lit := _mask(it["lit_key"])
		var fresh := _mask(it["new_key"])
		var st: Dictionary = {} if not hd else dmd.text_style()
		for s in it["sprites"]:
			var i := int(str(s["name"]).right(1))
			var state := LetterPanel.letter_state(i, lit, fresh, it["all_new"], frame, it["blink_shift"],
				it["solid_after"])
			if it["hide_after_ms"] > 0 and elapsed_ms >= it["hide_after_ms"]:
				state = ""
			if state != str(s["name"]).left(-1).to_lower():
				continue
			var art: Texture2D = DmdEffect.letter_art(str(s["letter"]), state == "solid") if hd else null
			if art:          # the topper's letter: red collected, blue still to get (dimmed), in the ROM's cell
				var cell := Rect2(s["x"], s["y"] + 0.5, 21, 21)
				var k := minf(cell.size.x / art.get_width(), cell.size.y / art.get_height())
				var size := Vector2(art.get_width(), art.get_height()) * k
				out.append(["tex", art, Rect2(cell.position + (cell.size - size) / 2, size),
					Color.WHITE if state == "solid" else Color(0.7, 0.7, 0.7, 1)])
				continue
			var colored: bool = color and s.has("color_pic")
			var tex := _picture(s["color_pic"] if colored else s["pic"])
			if tex == null:
				continue
			var classic := Color(s["color"][0], s["color"][1], s["color"][2], 1)
			var rect := Rect2(s["x"], s["y"], 0, 0)
			var dots := Vector2i((tex.get_size() / (color_scale if colored else (float(dmd.frame_scale) if hd and
				tex.resource_path.begins_with(MEDIA_HD) else 1.0))).round())
			rect.size = Vector2(dots)
			if not hd:
				out.append(["tex", tex, rect, classic])
				continue
			var level: float = classic.r          # orange times the palette level: the level
			out.append(["tex", tex, rect, Color.WHITE if colored else dmd.text_tint(Color(level, 0, 0, 1))])
			if float(st["glow"]) > 0.0:
				LetterPanel.start_glow(tex)
				var glow := LetterPanel.made_glow(tex)
				if glow:
					var g: Color = st["glow_color"] * (float(st["glow"]) * level)
					g.a = 1.0
					var m := float(LetterPanel.GLOW_DOTS)
					out.append(["glowtex", glow, Rect2(rect.position - Vector2(m, m), rect.size + Vector2(2 * m, 2 * m)), g])

	# ------------------------------------------------------------------ arcade reel (tron/arcade_reel.gd)

	func _arcade(out: Array, it: Dictionary, dmd) -> void:
		var frame := int(elapsed_ms / float(it["frame_ms"])) if float(it["frame_ms"]) > 0 else 0
		var slot := _int("slot", -1)
		var state := ArcadeReel.reel_state(frame, _int("scroll", 0), _int("blink", 0), 82, 4)
		var x: int = state[0]
		var blink_step: int = state[1]
		var tint: Color = dmd.text_tint(DMD_COLOR) if hd else DMD_COLOR
		var colored: bool = color and it.has("color_cabinets") and it.has("color_icons_a") and it.has("color_icons_b")
		var k := color_scale if colored else 1.0
		if colored:
			tint = Color.WHITE
		var icons_a: Array = it["color_icons_a"] if colored else it["icons_a"]
		var icons_b: Array = it["color_icons_b"] if colored else it["icons_b"]
		var cabinets: Array = it["color_cabinets"] if colored else it["cabinets"]
		for i in 3:
			var cab := _int("cab%d" % i, 0)
			var id := _int("icon%d" % i, 0)
			var art_shown := false
			if id >= 1 and id <= icons_a.size() and id <= icons_b.size():
				var bright := blink_step < 0 or (i == slot and blink_step % 2 == 0)
				var art: Texture2D = DmdEffect.award_art(id) if hd else null
				var icon := DmdEffect.picture(icons_a[id - 1] if bright else icons_b[id - 1], false) if art == null else null
				if art:      # the redrawn icon, in its own colours, dimmed when the award is not blinking; no cabinet, so it fills the slot
					art_shown = true
					out.append(["tex", art, Rect2(Vector2(x + 3.0, 1.3), Vector2(39.0, 29.6)), Color.WHITE if bright else Color(0.4, 0.4, 0.4, 1)])
				elif icon:
					out.append(["tex", icon, Rect2(Vector2(x + 8, 5), icon.get_size() / k), tint])
			var tex: Texture2D = DmdEffect.picture(cabinets[cab], false) if cab >= 0 and cab < cabinets.size() else null
			if tex:
				if not art_shown:
					out.append(["tex", tex, Rect2(Vector2(x, 0), tex.get_size() / k), tint])
				x += roundi(tex.get_width() / k) + 5
			else:
				x += 45 + 5

	# ------------------------------------------------------------------ recorded text (tools/dmd_mode.gd FrameText)

	## colored: over a colour picture, which keeps its rectangles; each line in its colour (text_colors.json).
	## An effect whose pictures a PuP clip or the character's HD icon replace: the clip entry (tron/dmd_screen.gd plays it
	## behind everything), or the icon gliding in, and the text lines the recorded frame carries (drawn in our font).
	func _clip_frame(out: Array, f: Array, dmd) -> void:
		if clip_path != "":
			DmdEffect._clip_last = {"name": effect_name, "path": clip_path, "show": show, "t": Time.get_ticks_msec()}
			out.append(["clip", clip_path, show, clip_loop])
		else:
			var tex := _picture(icon_path)
			if tex:
				var h := 32.0
				var w := h * tex.get_width() / tex.get_height()
				DmdEffect._icon_seen = [icon_path, Time.get_ticks_msec()]
				var t := 1.0 if glide_done else clampf(elapsed_ms / DmdEffect.ICON_GLIDE_MS, 0.0, 1.0)
				var ease := 1.0 - pow(1.0 - t, 3.0)
				out.append(["tex", tex, Rect2(lerpf(132.0, DmdEffect.ICON_CENTRE_X - w / 2.0, ease), 0.0, w, h), Color.WHITE])
		if f.size() and not (clip_path != "" and effect_name in DmdEffect.CLIP_NO_TEXT):
			_frame_text(out, str(f[0]).trim_prefix(MEDIA), dmd, color, false, 41, ICON_TEXT_X if icon_path != "" else 0.0)

	## min_x: recorded lines further left are the ROM's counters (the "00" of a jackpot value), not drawn over a clip.
	## box_x: when set, the lines are centred on it (the text beside the icon) instead of the ROM's alignment.
	func _frame_text(out: Array, key: String, dmd, colored := false, shapes := true, min_x := 0, box_x := 0.0) -> void:
		var tcol: Color = dmd.text_color
		var inks: Array = dmd.text_colors().get(key, []) if colored else []
		for r in ([] if colored or not shapes else dmd.frame_shapes().get(key, [])):
			var lv := float(r[4]) / 15.0
			var c := Color(tcol.r * lv, tcol.g * lv, tcol.b * lv, 1)
			var box := Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]) + 1, float(r[3]) - float(r[1]) + 1)
			if int(r[5]):
				out.append(["rect", box, c])
			else:                       # a one-dot frame
				out.append(["rect", Rect2(box.position, Vector2(box.size.x, 1)), c])
				out.append(["rect", Rect2(box.position + Vector2(0, box.size.y - 1), Vector2(box.size.x, 1)), c])
				out.append(["rect", Rect2(box.position + Vector2(0, 1), Vector2(1, box.size.y - 2)), c])
				out.append(["rect", Rect2(box.position + Vector2(box.size.x - 1, 1), Vector2(1, box.size.y - 2)), c])
		var clean := not RomTextHd.clean().is_empty()
		var lines: Array = dmd.frame_text().get(key, [])
		for li in lines.size():
			var l: Array = lines[li]
			var ink: Color = Color(str(inks[li])) if li < inks.size() and inks[li] != null else NO_INK
			var m := RomText.font_metrics(int(l[1]))
			if m.is_empty() or int(l[2]) < min_x:
				continue
			var whole := str(l[0])
			var from := int(l[6])
			var n := int(l[7])
			var ascent := int(m["ascent"])
			var pos := Vector2(float(l[2]), float(l[3]) - ascent + 1)
			var lv := float(l[4]) / 15.0
			var mod := Color(lv, lv, lv, 1)
			var params: Array
			if clean:          # aligned as the recorded line: against an edge of the DMD, else centred on it
				var align := 4 if int(l[2]) + int(l[5]) >= 127 else (0 if int(l[2]) <= 1 else 2)
				if box_x > 0.0:
					align = 2
					pos.x = box_x - float(l[5]) / 2.0
				params = [whole, int(l[1]), ascent, ascent + int(m["descent"]), int(l[5]), align, from, n]
			else:              # the ROM's dot font: the part shown, where the ROM draws it
				var part := whole.substr(from, n)
				if from > 0:
					pos.x += RomText.rom_width(m, whole.left(from)) + int(m["spacing"])
				params = [part, int(l[1]), ascent, ascent + int(m["descent"]), RomText.rom_width(m, part), 0, 0, -1]
			if l.size() > 9:   # a zoomed line (scripts/frame_text.py ZOOMS): about its middle, clipped
				var z := float(l[8])
				var left := float(l[9])
				var mid := pos + Vector2(float(l[5]) / 2.0, ascent - int(m["cap"]) / 2.0)
				pos = mid + (pos - mid) * z
				out.append(["htext", params, Transform2D(0.0, Vector2(z, z), 0.0, pos), mod, Rect2(left, 0, 128 - left, 32), ink])
				continue
			out.append(["htext", params, Transform2D(0.0, pos), mod, Rect2(), ink, 0, clip_path != "" or icon_path != ""])
