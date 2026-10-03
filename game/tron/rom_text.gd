extends MPFVariable
## One line of ROM text drawn like the ROM's text_draw_str: a ROM font (game/fonts, built by
## scripts/gen_fonts.py), x and the baseline row y in DMD dots, flags 2 = centred on x, 4 = right
## edge at x, otherwise left edge at x. Characters the font lacks are skipped, as in the ROM.
## With fit_fonts the first font whose text width is at most fit_width is used (text_draw_msg_fit),
## at the matching fit_ys row. With alt_when_empty the line moves to alt_x/alt_y while that other
## line ("lineN") is blank (the ROM draws a shorter layout when a value is not shown).
## Timed lines (deff frames in ms from the slide start): shown from show_after_ms, hidden from
## hide_after_ms (0 = never), and with level_steps the brightness (palette level 0-15 of the ROM's
## colour table) steps every step_ms; with blink_ms the line shows blink_ms, hides blink_ms, ... (counted from show_after_ms) Seekable for scripts/render_diff.py (seek_ms).

@export var rom_font: int = 12
@export var rom_x: int = 84
@export var rom_y: int = 16
@export var rom_flags: int = 2
@export var fit_fonts: PackedInt32Array = PackedInt32Array()
@export var fit_ys: PackedInt32Array = PackedInt32Array()
@export var fit_width: int = 0
@export var alt_x: int = 0
@export var alt_y: int = 0
@export var alt_when_empty: String = ""
@export var show_after_ms: int = 0
@export var hide_after_ms: int = 0
@export var level_steps: PackedInt32Array = PackedInt32Array()
@export var step_ms: int = 0
@export var blink_ms: int = 0
## blink_dark: the off phase of blink_ms draws the glyphs black over the picture instead of hiding them
## (the ROM prints with a palette mapping the font's colours to 0: deffs 116-124)
@export var blink_dark := false
## screens: the line shows only while the event arg `screen` (default 0) is one of these (an effect that
## draws one of several screens on the same rows, scripts/rom_layout.py SCREENS); empty = always
@export var screens: PackedInt32Array = PackedInt32Array()

static var _metrics: Dictionary = {}
static var _font_files: Dictionary = {}

var _use_alt := false
var _screen_on := true
var _elapsed_ms := 0.0
var _seeked := false


static func font_metrics(font_id: int) -> Dictionary:
	if _metrics.is_empty():
		var data = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/fonts.json"))
		for f in data["fonts"]:
			_metrics[int(f["id"])] = f
	return _metrics.get(font_id, {})


static func font_file(font_id: int) -> FontFile:
	if not _font_files.has(font_id):
		var f := FontFile.new()
		f.load_bitmap_font("res://fonts/rom_font_%02d.fnt" % font_id)
		_font_files[font_id] = f
	return _font_files[font_id]


## Text width as the ROM measures it (glyph widths, x offsets and the spacing between glyphs).
static func rom_width(m: Dictionary, s: String) -> int:
	var w := 0
	var n := 0
	for c in s:
		if m["glyphs"].has(c):
			var g = m["glyphs"][c]
			w += int(g["w"]) + int(g["xoff"]) + int(m["spacing"])
			n += 1
	return w - int(m["spacing"]) if n else 0


func _ready() -> void:
	super()
	clip_text = false
	autowrap_mode = TextServer.AUTOWRAP_OFF
	horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	vertical_alignment = VERTICAL_ALIGNMENT_TOP
	if screens.size():
		_screen_on = screens.has(0)
		visible = _screen_on
	if _timed():
		add_to_group("rom_timed")
		set_process(true)
	else:
		set_process(false)
	_layout()
	_apply_time()


func _timed() -> bool:
	return show_after_ms or hide_after_ms or blink_ms or level_steps.size()


func seek_ms(t: float) -> void:
	_seeked = true
	_elapsed_ms = t
	_apply_time()


func _process(delta: float) -> void:
	if not _seeked:
		_elapsed_ms += delta * 1000.0
		_apply_time()


func _apply_time() -> void:
	if not _timed():
		return
	var blink_on := blink_ms == 0 or int((_elapsed_ms - show_after_ms) / blink_ms) % 2 == 0
	visible = _screen_on and _elapsed_ms >= show_after_ms and (hide_after_ms == 0 or _elapsed_ms < hide_after_ms) \
		and (blink_on or blink_dark)
	if blink_dark:
		modulate = Color(1, 1, 1, 1) if blink_on else Color(0, 0, 0, 1)
	if level_steps.size() and step_ms > 0:
		var level := level_steps[mini(int(_elapsed_ms / step_ms), level_steps.size() - 1)] / 15.0
		modulate = Color(level, level, level, 1)


func update(settings: Dictionary, kwargs: Dictionary = {}) -> void:
	if screens.size():
		var shown = kwargs.get("screen", settings.get("screen", null))
		if shown != null and str(shown) != "":
			_screen_on = screens.has(int(shown))
		if not _timed():
			visible = _screen_on
	if alt_when_empty:
		var other = kwargs.get(alt_when_empty, settings.get(alt_when_empty, ""))
		_use_alt = other == null or str(other) == ""
	super(settings, kwargs)
	_layout()


func update_text(value) -> void:
	super(value)
	_layout()


func _layout() -> void:
	var font_id := rom_font
	var y := rom_y
	var m := font_metrics(font_id)
	var shown := ""
	for c in text:
		if m.get("glyphs", {}).has(c):
			shown += c
	for i in fit_fonts.size():                    # first font of the list that fits
		var fm := font_metrics(fit_fonts[i])
		var fs := ""
		for c in text:
			if fm["glyphs"].has(c):
				fs += c
		font_id = fit_fonts[i]
		m = fm
		shown = fs
		y = fit_ys[i] if i < fit_ys.size() else rom_y
		if rom_width(fm, fs) <= fit_width:
			break
	if m.is_empty():
		return
	if shown != text:
		text = shown
	var x := alt_x if _use_alt else rom_x
	if _use_alt:
		y = alt_y
	var w := rom_width(m, shown)
	var left := x
	if rom_flags & 2:
		left = x - w / 2
	elif rom_flags & 4:
		left = x + 1 - w
	var line_h := int(m["ascent"]) + int(m["descent"])
	add_theme_font_override("font", font_file(font_id))
	add_theme_font_size_override("font_size", line_h)
	add_theme_constant_override("line_spacing", 0)
	position = Vector2(left, y - int(m["ascent"]) + 1)
	size = Vector2(maxi(w, 1) + 2, line_h)
