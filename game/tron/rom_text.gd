extends MPFVariable
## One line of ROM text drawn like the ROM's text_draw_str: a ROM font (game/fonts, built by
## scripts/gen_fonts.py), x and the baseline row y in DMD dots, flags 2 = centred on x, 4 = right
## edge at x, otherwise left edge at x. Characters the font lacks are skipped, as in the ROM.
## With fit_fonts the first font whose text width is at most fit_width is used (text_draw_msg_fit),
## at the matching fit_ys row. With alt_when_empty the line moves to alt_x/alt_y while that other
## line ("lineN") is blank (the ROM draws a shorter layout when a value is not shown).

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

static var _metrics: Dictionary = {}
static var _font_files: Dictionary = {}

var _use_alt := false


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
	_layout()


func update(settings: Dictionary, kwargs: Dictionary = {}) -> void:
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
