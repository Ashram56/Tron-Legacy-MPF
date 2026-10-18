extends Control
## The service menu on the PuP backglass: a larger view of the service screen the DMD shows (tron/service.py; the
## DMD keeps the ROM's look), drawn over a still of the pack's backglass art with both neon frames kept lit.
##
## MPF sends the screen's description with every DMD refresh as the BCP trigger "service_backglass" (state = JSON,
## tron/service_backglass.py has the keys of each kind); {"show": false} when the menu closes. The view fades in
## when the menu opens and out when it closes (FADE_SECONDS), over the backglass videos, which keep playing.
## Everything is drawn once per description at the still's 1920x1080 in a SubViewport, then fitted in the
## backglass window as the videos are ([backglass] fit, align). The still is scripts/pup/gen_pup.py's (manifest
## "still"); without it the frames are drawn in neon on black (service_backglass.gdshader).

const SHADER := preload("res://pup/service_backglass.gdshader")
const DESIGN := Vector2(1920, 1080)
const FADE_SECONDS := 0.5
const PLAYFIELD := "res://monitor/playfield.jpg"
const IMAGES_ZIP := "../assets/mpf_package/media/rom_images_all.zip"     # the ROM's images (menu icons)

const CYAN := Color8(64, 200, 255)
const ICE := Color8(190, 240, 255)
const DIM := Color8(40, 110, 150)
const SOFT := Color8(130, 180, 205)
const ORANGE := Color8(255, 150, 30)
const AMBER := Color8(255, 210, 150)
const GREEN := Color8(80, 255, 170)
const RED := Color8(255, 80, 70)
const PANEL := Color(0.016, 0.063, 0.1, 0.75)
const PANEL_ON := Color(0.04, 0.2, 0.29, 0.86)
const PANEL_HOT := Color(0.23, 0.13, 0.024, 0.86)
const CELL_OFF := Color8(8, 24, 36)
const WIRES := {"BLK": Color8(20, 20, 20), "BRN": Color8(120, 70, 30), "RED": Color8(220, 40, 40),
	"ORG": Color8(255, 140, 20), "YEL": Color8(250, 220, 40), "GRN": Color8(40, 180, 70),
	"BLU": Color8(40, 90, 230), "VIO": Color8(150, 60, 210), "GRY": Color8(140, 140, 140),
	"WHT": Color8(240, 240, 240)}

# areas of the 1920x1080 still, clear of the neon lines (the main frame's window ends above the lower frame)
const LABEL := Rect2(575, 880, 770, 182)             # the lower frame's box: where, buttons, version
const PF_AREA := Rect2(318, 118, 382, 708)           # the playfield picture of the device views
const CARD := Rect2(742, 190, 868, 230)              # the tested device
const LOWER := Rect2(742, 470, 868, 352)             # matrix, list or legend under it
const TOP := 826.0                                   # content ends here (the lower frame's line is at 846)

var fit := "fit"
var align := 0.5
var state := {}
var devices := {}
var showing := false
var _viewport: SubViewport
var _still: TextureRect
var _paper: Control
var _view: TextureRect
var _tween: Tween
var _orb: Font
var _raj: Font
var _pf_tex: Texture2D
var _pf_rect := Rect2()
var _icons := {}
var _zip: ZIPReader


func setup(still_path: String, fit_mode: String, align_v: float) -> void:
	fit = fit_mode
	align = align_v
	_orb = load("res://fonts_ttf/Orbitron.ttf")
	_raj = load("res://fonts_ttf/Rajdhani-Bold.ttf")
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)     # follows the window (already sized)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	modulate.a = 0.0
	_viewport = SubViewport.new()
	_viewport.size = Vector2i(DESIGN)
	_viewport.disable_3d = true
	_viewport.transparent_bg = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(_viewport)
	_still = TextureRect.new()
	_still.size = DESIGN
	_still.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_still.stretch_mode = TextureRect.STRETCH_SCALE
	_still.material = ShaderMaterial.new()
	_still.material.shader = SHADER
	var image := Image.load_from_file(still_path) if still_path != "" and FileAccess.file_exists(still_path) else null
	if image == null:
		image = Image.create(4, 4, false, Image.FORMAT_RGB8)
		_still.material.set_shader_parameter("has_still", false)
	_still.texture = ImageTexture.create_from_image(image)
	_viewport.add_child(_still)
	_paper = Control.new()
	_paper.size = DESIGN
	_paper.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST      # the ROM's icons, scaled up
	_paper.draw.connect(_paint)
	_viewport.add_child(_paper)
	_view = TextureRect.new()
	_view.texture = _viewport.get_texture()
	_view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_view.stretch_mode = TextureRect.STRETCH_SCALE
	_view.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_view)
	resized.connect(_layout)
	_load_playfield()
	_layout()


## The view at the place and size of the backglass videos (16:9, as pup_screen.gd fits them).
func _layout() -> void:
	var area := size
	var w := area.x
	var h := area.y
	var aspect := DESIGN.x / DESIGN.y
	if fit != "stretch" and area.x > 0 and area.y > 0:
		var fitted := area.x / area.y > aspect
		if fit == "fill":
			fitted = not fitted
		if fitted:
			w = area.y * aspect
		else:
			h = area.x / aspect
	_view.position = Vector2((area.x - w) * 0.5, (area.y - h) * align)
	_view.size = Vector2(w, h)


## The playfield picture, made the size it is drawn at once (no aliasing from scaling it down at each draw).
func _load_playfield() -> void:
	var image := Image.load_from_file(ProjectSettings.globalize_path(PLAYFIELD))
	if image == null:
		return
	var h := PF_AREA.size.y
	var w := roundf(h * image.get_width() / image.get_height())
	image.resize(int(w), int(h), Image.INTERPOLATE_LANCZOS)
	_pf_tex = ImageTexture.create_from_image(image)
	_pf_rect = Rect2(PF_AREA.position.x + (PF_AREA.size.x - w) * 0.5, PF_AREA.position.y, w, h)


## A description from MPF (the BCP trigger's state, already parsed).
func show_state(new_state: Dictionary) -> void:
	if new_state.has("devices"):
		devices = new_state["devices"]
	if not bool(new_state.get("show", false)):
		if showing:
			showing = false
			_fade(0.0)                       # the last screen stays drawn while it fades out
		return
	state = new_state
	_paper.queue_redraw()
	_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	if not showing:
		showing = true
		_fade(1.0)


func _fade(to: float) -> void:
	if _tween:
		_tween.kill()
	visible = true
	_layout.call_deferred()             # a hidden Control misses its window's resizes
	_tween = create_tween()
	_tween.tween_property(self, "modulate:a", to, FADE_SECONDS * absf(to - modulate.a)) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	if to <= 0.0:
		_tween.tween_callback(func(): visible = false)

# ------------------------------------------------------------------ the screens

func _paint() -> void:
	if state.is_empty():
		return
	match str(state.get("kind", "message")):
		"entry":
			_paint_entry()
		"menu":
			if bool(state.get("main", false)):
				_paint_main_menu()
			else:
				_paint_menu()
		"rows":
			_paint_rows()
		"adjust":
			_paint_adjust()
		"switches":
			_paint_switches()
		"lamps":
			_paint_lamps()
		"coils":
			_paint_coils()
		"trough":
			_paint_trough()
		"text":
			_paint_text()
		_:
			_paint_message()
	_paint_footer()


func _paint_footer() -> void:
	var cx := LABEL.get_center().x
	var path: Array = state.get("path", ["SERVICE"])
	_text(Vector2(cx, LABEL.position.y + 28), "  >  ".join(path), 24, CYAN, _orb, 0, true, LABEL.size.x - 40)
	_keys(cx, LABEL.position.y + 92, state.get("hints", []))
	_text(Vector2(cx, LABEL.position.y + 146), "SERVICE MODE  /  TRON L.E. V1.74", 22, DIM, _orb, 0, false)


func _paint_entry() -> void:
	var box := Rect2(560, 300, 800, 330)
	_box(box, CYAN, PANEL, 2, 12, true)
	_text(Vector2(960, 390), str(state.get("title", "SERVICE MENU")), 64, ICE, _orb, 0, true, 740, CYAN)
	var lines: Array = state.get("lines", [])
	for i in lines.size():
		_text(Vector2(960, 480 + i * 64), str(lines[i]), 34 if i == 0 else 28, ICE if i == 0 else SOFT, _raj, 0,
			i == 0, 740)


func _paint_message() -> void:
	var lines: Array = state.get("lines", [])
	var h := 160.0 + 64.0 * lines.size()
	var box := Rect2(460, 467 - h * 0.5, 1000, h)
	_box(box, CYAN, PANEL, 2, 12, true)
	_text(Vector2(960, box.position.y + 70), str(state.get("title", "")), 48, ICE, _orb, 0, true, 920, CYAN)
	var big := bool(state.get("big", false))
	for i in lines.size():
		if big and i == 0:
			_text(Vector2(960, box.position.y + 170), str(lines[0]), 84, AMBER, _orb, 0, true, 920, ORANGE)
		else:
			_text(Vector2(960, box.position.y + 150 + i * 64 + (60 if big else 0)), str(lines[i]), 36, ICE, _raj, 0,
				false, 920)


## A name or password being typed: the text in large letters, the character being chosen in a cursor box.
func _paint_text() -> void:
	var box := Rect2(360, 250, 1200, 420)
	_box(box, CYAN, PANEL, 2, 12, true)
	_text(Vector2(960, 310), str(state.get("prompt", "")), 40, ICE, _orb, 0, true, 1120, CYAN)
	var typed := str(state.get("text", ""))
	var ch := str(state.get("char", ""))
	var size := 64
	var shown := typed
	while shown.length() > 1 and _orb.get_string_size(shown + "WW", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > 1100:
		shown = shown.substr(1)                        # the end of a long text, as the DMD scrolls it
	var w := _orb.get_string_size(shown, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var cw := maxf(48.0, _orb.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x + 20)
	var x := 960 - (w + cw) * 0.5
	_text(Vector2(x, 450), shown, size, ICE, _orb, -1, false)
	var cur := Rect2(x + w + 6, 410, cw, 80)
	_box(cur, ORANGE, PANEL_HOT, 2, 8, true)
	_text(cur.get_center(), ch, 44 if ch == "END" else size, AMBER, _orb, 0, false)
	_text(Vector2(960, 560), str(state.get("char_kind", "")), 32, ORANGE, _raj, 0, false, 1100)
	var count: Array = state.get("count", [0, 0])
	_text(Vector2(960, 620), "%d OF %d CHARACTERS" % [int(count[0]), int(count[1])], 26, SOFT, _raj, 0, false)


func _short(text: String) -> String:
	return text.trim_prefix("GO TO ").trim_suffix(" MENU")


func _paint_main_menu() -> void:
	var items: Array = state.get("items", [])
	var sel := int(state.get("sel", 0))
	_text(Vector2(960, 222), "SERVICE MENU", 44, ICE, _orb, 0, true, 0, CYAN)
	var cols := 3
	var rows := maxi(1, ceili(items.size() / float(cols)))
	var gap := 18.0
	var tw := 400.0
	var th := minf(274.0, (TOP - 8 - 252 - gap * (rows - 1)) / rows)
	var x0 := (DESIGN.x - cols * tw - (cols - 1) * 30.0) * 0.5
	for i in items.size():
		var item: Dictionary = items[i]
		var on := i == sel
		var r := Rect2(x0 + (i % cols) * (tw + 30), 252 + (i / cols) * (th + gap), tw, th)
		_box(r, CYAN if on else DIM, PANEL_ON if on else PANEL, 4 if on else 2, 10, on)
		var col := ICE if on else DIM
		var scale := clampf(floor(th * 0.5 / 23.0), 2.0, 6.0)
		var icon_h := 23.0 * scale
		if str(item.get("text", "")) == "EXIT SERVICE MENU":
			_power(Vector2(r.get_center().x, r.position.y + 18 + icon_h * 0.5), icon_h * 0.36, col)
		else:
			var n := int(item.get("icon", 18))
			_icon(n if on else n + 1, Vector2(r.get_center().x - 8.5 * scale, r.position.y + 18), scale,
				Color8(120, 220, 255) if on else Color8(60, 120, 160))
		_text(Vector2(r.get_center().x, r.position.y + 40 + icon_h), _short(str(item.get("text", ""))), 34, col,
			_orb, 0, on, tw - 30)
		_text(Vector2(r.get_center().x, r.position.y + 92 + icon_h), str(item.get("info", "")), 25,
			ICE if on else DIM, _raj, 0, false, tw - 30)


func _paint_menu() -> void:
	var items: Array = state.get("items", [])
	var sel := int(state.get("sel", 0))
	_text(Vector2(330, 220), _short(str(state.get("title", ""))), 44, ICE, _orb, -1, true, 580, CYAN)
	var step := minf(42.0, (TOP - 256) / maxf(1.0, items.size()))
	for i in items.size():
		var y := 256 + i * step
		var on := i == sel
		if on:
			_box(Rect2(318, y - 2, 590, step - 4), CYAN, PANEL_ON, 2, 6, true)
		_text(Vector2(340, y + step * 0.5 - 2), str(items[i].get("text", "")), minf(30, step * 0.72),
			ICE if on else SOFT, _raj, -1, on, 556)
	if items.is_empty():
		return
	# what the selected item holds
	var item: Dictionary = items[clampi(sel, 0, items.size() - 1)]
	var panel := Rect2(950, 252, 660, TOP - 6 - 252)
	_box(panel, DIM, PANEL, 2, 10, false)
	_text(Vector2(panel.get_center().x, 294), str(item.get("text", "")).trim_prefix("GO TO "), 36, ICE, _orb, 0, true, 620, CYAN)
	var children: Array = item.get("children", [])
	if children.is_empty():
		var scale := 6.0
		var n := int(item.get("icon", 18))
		_icon(n, Vector2(panel.get_center().x - 8.5 * scale, 350), scale, Color8(120, 220, 255))
		_text(Vector2(panel.get_center().x, 540), str(item.get("info", "")), 30, ICE, _raj, 0, false, 620)
		return
	var line := minf(74.0, (panel.end.y - 352) / children.size())
	for k in children.size():
		var y := 357 + k * line
		_text(Vector2(990, y), str(children[k][0]), minf(32, line * 0.45), ICE, _raj, -1, false, 590)
		if line >= 56:
			_text(Vector2(990, y + 33), str(children[k][1]), 25, SOFT, _raj, -1, false, 590)


func _page_text() -> String:
	var page: Array = state.get("page", [1, 1, 1])
	return "%d-%d OF %d" % [int(page[0]), int(page[1]), int(page[2])]


func _paint_rows() -> void:
	var rows: Array = state.get("rows", [])
	var sel := int(state.get("sel", 0))
	_text(Vector2(330, 220), str(state.get("title", "")), 44, ICE, _orb, -1, true, 1000, CYAN)
	_text(Vector2(1610, 220), _page_text(), 28, DIM, _raj, 1, false)
	for i in rows.size():
		var y := 254.0 + i * 40
		var on := i == sel
		if on:
			_box(Rect2(318, y, 1292, 36), CYAN, PANEL_ON, 2, 6, true)
		var col := ICE if on else SOFT
		_text(Vector2(340, y + 18), "%2d" % int(rows[i][0]), 28, ICE if on else DIM, _raj, -1, false)
		_text(Vector2(400, y + 18), str(rows[i][1]), 30, col, _raj, -1, on, 900)
		_text(Vector2(1580, y + 18), str(rows[i][2]), 30, col, _raj, 1, on, 260)


func _paint_adjust() -> void:
	var rows: Array = state.get("rows", [])
	var sel := int(state.get("sel", 0))
	var editing := bool(state.get("editing", false))
	_text(Vector2(330, 220), str(state.get("title", "")), 44, ICE, _orb, -1, true, 1000, CYAN)
	_text(Vector2(1610, 220), _page_text(), 28, DIM, _raj, 1, false)
	for i in rows.size():
		var row: Dictionary = rows[i]
		var y := 254.0 + i * 47
		var on := i == sel
		var changed := bool(row.get("changed", false))
		if on:
			_box(Rect2(318, y, 1292, 44), ORANGE if editing else CYAN, PANEL_HOT if editing else PANEL_ON, 2, 6, true)
		var col := ICE if on else SOFT
		_text(Vector2(340, y + 22), "%2d  %s" % [int(row.get("number", 0)), str(row.get("name", ""))], 30, col, _raj,
			-1, on, 760)
		_text(Vector2(1130, y + 22), str(row.get("value", "")), 30, ORANGE if changed else col, _raj, 1, on, 250)
		var frac = row.get("frac")
		if frac != null:
			var bar := Rect2(1160, y + 18, 240, 8)
			_fill(bar, Color8(20, 50, 70), 4)
			_fill(Rect2(bar.position, Vector2(maxf(8.0, 240.0 * float(frac)), 8)),
				ORANGE if changed else CYAN, 4)
			var dflt = row.get("default_frac")
			if dflt != null:
				var x := 1160 + 240 * float(dflt)
				_paper.draw_line(Vector2(x, y + 10), Vector2(x, y + 34), ICE, 2)
		if changed:
			_text(Vector2(1596, y + 22), "DEFAULT " + str(row.get("factory", "")), 22, ORANGE, _raj, 1, false, 175)


# ------------------------------------------------------------------ device views

func _dev(kind: String, name: String) -> Dictionary:
	return devices.get(kind, {}).get(name, {}) if name != "" else {}


## A name from the description, "" for none (null).
func _name(value) -> String:
	return "" if value == null else str(value)


func _pf_panel(dim: float = 0.85) -> void:
	if _pf_tex == null:
		_box(PF_AREA, DIM, PANEL, 2, 6, false)
		return
	_paper.draw_texture_rect(_pf_tex, _pf_rect, false, Color(dim, dim, dim))
	_box(_pf_rect.grow(4), CYAN, Color(0, 0, 0, 0), 2, 6, true)


## A playfield position (fractions of the picture) on the panel; null when the device has no place.
func _at(device: Dictionary):
	var at = device.get("at")
	if at == null or not (at is Array) or at.size() < 2:
		return null
	var r := _pf_rect if _pf_tex else PF_AREA
	return r.position + Vector2(float(at[0]) * r.size.x, float(at[1]) * r.size.y)


func _leader(p: Vector2, to_y: float) -> void:
	var knee := Vector2(p.x + 40, to_y)
	for pass_ in [[7.0, 0.25], [3.0, 1.0]]:
		var c := Color(ORANGE, pass_[1])
		_paper.draw_polyline(PackedVector2Array([p, knee, Vector2(CARD.position.x, to_y)]), c, pass_[0], true)


func _card(title: String, right: String, big: String, line1: String, line2: String = "",
		line2_col: Color = SOFT) -> void:
	_box(CARD, ORANGE, Color(0.12, 0.07, 0.016, 0.86), 2, 10, true)
	_text(Vector2(770, 228), title, 30, ICE, _orb, -1, false, 520)
	_text(Vector2(1585, 228), right, 26, ORANGE, _raj, 1, false, 300)
	_text(Vector2(770, 290), big, 50, AMBER, _orb, -1, true, 810, ORANGE)
	_text(Vector2(770, 352), line1, 30, ICE, _raj, -1, false, 810)
	if line2 != "":
		_text(Vector2(770, 392), line2, 26, line2_col, _raj, -1, false, 810)


func _cell_text(cell) -> String:
	if cell == null or not (cell is Array):
		return "Not in the matrix"
	if str(cell[0]) == "D":
		return "Dedicated switch %d" % int(cell[1])
	return "Column %d  /  Row %d" % [int(cell[0]), int(cell[1])]


## A matrix: cols x rows cells of cell(i, j) -> [fill, outline or null, text].
func _matrix(r: Rect2, title: String, cols: int, rows: int, cell: Callable) -> void:
	_text(Vector2(r.position.x + 18, r.position.y - 15), title, 22, DIM, _orb, -1, false)
	var cw := (r.size.x - 40) / cols
	var ch := (r.size.y - 34) / rows
	for i in cols:
		_text(Vector2(r.position.x + 40 + cw * (i + 0.5), r.position.y + 12), str(i + 1), 20, DIM, _raj, 0, false)
	for j in rows:
		_text(Vector2(r.position.x + 16, r.position.y + 34 + ch * (j + 0.5)), str(j + 1), 20, DIM, _raj, 0, false)
	for i in cols:
		for j in rows:
			var spec: Array = cell.call(i, j)
			var b := Rect2(r.position.x + 40 + cw * i + 2, r.position.y + 34 + ch * j + 2, cw - 4, ch - 4)
			var out = spec[1]
			if out != null:
				_box(b, out, spec[0], 2, 4, true)
			else:
				_fill(b, spec[0], 4)
			_text(b.get_center(), str(spec[2]), 17, Color8(60, 100, 125) if spec[0] == CELL_OFF else Color8(200, 230, 245),
				_raj, 0, false)


func _number(device: Dictionary) -> String:
	return "#%s  %s" % [str(device.get("n", "?")), str(device.get("label", ""))]


func _paint_switches() -> void:
	var mode := str(state.get("mode", "test"))
	var active: Array = state.get("active", [])
	var alerts: Array = state.get("alerts", [])
	var focus := _name(state.get("focus"))
	var switches: Dictionary = devices.get("switches", {})
	_pf_panel()
	for name in switches:
		var p = _at(switches[name])
		if p == null or name == focus:
			continue
		if name in active:
			_dot(p, 8, GREEN, true)
		elif name in alerts:
			_dot(p, 7, RED, true)
		else:
			_dot(p, 5, Color8(40, 120, 160), false, Color8(120, 200, 230))
	var dev := _dev("switches", focus)
	var titles := {"test": "SWITCH TEST", "active": "ACTIVE SWITCHES", "alerts": str(state.get("title", "ALERTS"))}
	var lines: Array = state.get("lines", [])
	if dev.is_empty():
		var none := "NO ALERTS" if mode == "alerts" else ("NONE CLOSED" if mode == "active" else "HIT A SWITCH")
		_card(titles.get(mode, ""), "", none, "Closed now: %d switches" % active.size())
	else:
		var p = _at(dev)
		if p != null:
			_ring(p, 20, ORANGE, 4)
			_ring(p, 34, ORANGE, 2)
			_leader(p, CARD.position.y + 60)
		var right := "LAST HIT"
		if mode != "test":
			right = str(lines[-1]) if mode == "alerts" and lines.size() > 2 else str(state.get("title", ""))
		var closed := []
		for name in active:
			if name != focus and switches.has(name):
				closed.append("#%s" % str(switches[name].get("n", "")))
		var where := _cell_text(dev.get("cell"))
		var now := "CLOSED" if focus in active else "OPEN"
		_card(titles.get(mode, ""), right, _number(dev), "%s  /  %s" % [where, now],
			("Closed now: " + ", ".join(closed)) if closed.size() else "Nothing else closed",
			GREEN if closed.size() else SOFT)
	# the 8 x 8 matrix
	var by_cell := {}
	for name in switches:
		var cell = switches[name].get("cell")
		if cell is Array and str(cell[0]) != "D":
			by_cell[Vector2i(int(cell[0]), int(cell[1]))] = name
	var cell_fn := func(i: int, j: int) -> Array:
		var n := i * 8 + j + 1
		var name = by_cell.get(Vector2i(i + 1, j + 1))
		if name == null:
			return [CELL_OFF, null, n]
		if name == focus:
			return [Color8(110, 60, 10), ORANGE, n]
		if name in active:
			return [Color8(20, 110, 80), GREEN, n]
		if name in alerts:
			return [Color8(100, 24, 20), RED, n]
		return [Color8(12, 46, 66), null, n]
	_matrix(Rect2(742, 470, 498, TOP - 470), "SWITCH MATRIX", 8, 8, cell_fn)
	var legend := Rect2(1270, 470, 340, TOP - 470)
	_box(legend, DIM, PANEL, 2, 10, false)
	_text(Vector2(1290, 500), "LEGEND", 22, DIM, _orb, -1, false)
	var keys := [[GREEN, "closed now"], [ORANGE, "selected switch"], [Color8(120, 200, 230), "open"],
		[Color8(60, 100, 125), "not used"]]
	if mode == "alerts":
		keys.insert(2, [RED, "not seen since power-on"])
	for k in keys.size():
		_dot(Vector2(1305, 548 + k * 44), 9, keys[k][0], false)
		_text(Vector2(1330, 548 + k * 44), keys[k][1], 26, ICE, _raj, -1, false, 270)
	var dedicated := []
	for name in active:
		var cell = switches.get(name, {}).get("cell")
		if cell is Array and str(cell[0]) == "D":
			dedicated.append("D%d" % int(cell[1]))
	_text(Vector2(1290, 780), ("Dedicated closed: " + ", ".join(dedicated)) if dedicated.size()
		else "Dedicated switches: none closed", 22, SOFT, _raj, -1, false, 300)


func _paint_lamps() -> void:
	var focus: Array = state.get("focus", [])
	var lit: Array = state.get("lit", [])
	var lamps: Dictionary = devices.get("lamps", {})
	_pf_panel()
	for name in lamps:
		if name in focus:
			continue
		var p = _at(lamps[name])
		if p != null:
			var col := Color.html(str(lamps[name].get("color", "#ffffff")))
			_dot(p, 6, col * Color(0.55, 0.55, 0.55), false, col)
	for name in focus:
		var p = _at(lamps.get(name, {}))
		if p == null:
			continue
		var col := Color.html(str(lamps[name].get("color", "#ffffff")))
		if name in lit:
			_dot(p, 11, Color.WHITE, true)
		else:
			_dot(p, 8, col * Color(0.4, 0.4, 0.4), false, col)
		_ring(p, 20 if focus.size() == 1 else 14, col, 3)
	var position: Array = state.get("position", [1, 1])
	var right := ("ON" if bool(state.get("on", false)) else "BLINKING") + "   %d OF %d" % [int(position[0]),
		int(position[1])]
	if focus.size() == 1:
		var dev := _dev("lamps", str(focus[0]))
		var p = _at(dev)
		if p != null:
			_ring(p, 36, ORANGE, 2)
			_leader(p, CARD.position.y + 60)
		_card(str(state.get("title", "")), right, _number(dev), _cell_text(dev.get("cell")) + "  /  insert colour")
		var col := Color.html(str(dev.get("color", "#ffffff")))
		var sw := Rect2(1330, 338, 80, 28)
		_fill(sw, col, 6)
	else:
		_card(str(state.get("title", "")), right, str(state.get("group", "")), "%d lamps blinking" % focus.size())
	var by_n := {}
	for name in lamps:
		if str(lamps[name].get("n", "")).is_valid_int():
			by_n[int(lamps[name]["n"])] = name
	var cell_fn := func(i: int, j: int) -> Array:
		var n := i * 8 + j + 1
		var name = by_n.get(n)
		if name == null:
			return [CELL_OFF, null, n]
		var col := Color.html(str(lamps[name].get("color", "#ffffff")))
		if name in focus:
			return [Color.WHITE if name in lit else col * Color(0.6, 0.6, 0.6), ORANGE, n]
		return [col * Color(0.45, 0.45, 0.45), null, n]
	_matrix(Rect2(742, 470, 868, TOP - 470), "LAMP MATRIX (insert colours)", 10, 8, cell_fn)


func _wire(pos: Vector2, spec: String, w: float = 110, h: float = 26) -> void:
	var parts := spec.split("-")
	var a: Color = WIRES.get(parts[0], Color8(90, 90, 90))
	var b: Color = WIRES.get(parts[1] if parts.size() > 1 else parts[0], Color8(90, 90, 90))
	var r := Rect2(pos, Vector2(w, h))
	_box(r, Color8(200, 200, 200), a, 1, 6, false)
	var x := pos.x + 12
	while x < pos.x + w - 12:
		_paper.draw_rect(Rect2(x, pos.y + 2, 9, h - 4), b)
		x += 26


func _paint_coils() -> void:
	var names: Array = state.get("list", [])
	var sel := clampi(int(state.get("sel", 0)), 0, maxi(0, names.size() - 1))
	var flashers := bool(state.get("flashers", false))
	var coils: Dictionary = devices.get("coils", {})
	var current := str(names[sel]) if names.size() else ""
	var fired := _name(state.get("fired"))
	_pf_panel()
	for name in names:
		var p = _at(coils.get(name, {}))
		if p == null or name == current:
			continue
		if flashers:
			_dot(p, 9, Color8(90, 160, 200), false)
		else:
			_paper.draw_rect(Rect2(p - Vector2(6, 6), Vector2(12, 12)), Color8(30, 90, 120))
			_paper.draw_rect(Rect2(p - Vector2(6, 6), Vector2(12, 12)), Color8(120, 200, 230), false, 2)
	var dev := _dev("coils", current)
	var p = _at(dev)
	var hot := fired != "" and fired == current
	if p != null:
		if flashers:
			_dot(p, 16, Color.WHITE if hot else Color8(140, 210, 240), hot)
			_ring(p, 40, Color8(120, 220, 255), 3)
		else:
			_paper.draw_rect(Rect2(p - Vector2(10, 10), Vector2(20, 20)), ORANGE)
			_ring(p, 28, ORANGE, 4)
		_leader(p, CARD.position.y + 60)
	var pulse = dev.get("pulse")
	var right := ("FIRED" if hot else ("CYCLING" if bool(state.get("cycling", false)) else "READY"))
	if pulse != null:
		right += "  /  %d ms" % int(pulse)
	var wires: Array = dev.get("wires", [])
	_card(str(state.get("title", "")), right, _number(dev) if not dev.is_empty() else "",
		"Wires" if wires.size() else ("Flash lamp" if flashers else "Coil"),
		"%d OF %d   /   %s" % [sel + 1, names.size(), "flash lamp" if dev.get("flasher", false) else "coil driver"])
	for k in wires.size():
		_wire(Vector2(860 + k * 240, 339), str(wires[k]))
		_text(Vector2(982 + k * 240, 352), str(wires[k]), 26, ICE, _raj, -1, false)
	# the drivers round the selected one
	_text(Vector2(760, 455), "FLASH LAMPS" if flashers else "DRIVERS", 22, DIM, _orb, -1, false)
	var shown := mini(9, names.size())
	var first := clampi(sel - 4, 0, maxi(0, names.size() - shown))
	for k in shown:
		var name := str(names[first + k])
		var d: Dictionary = coils.get(name, {})
		var y := 476.0 + k * 39
		var on := name == current
		if on:
			_box(Rect2(742, y, 868, 36), ORANGE, PANEL_HOT, 2, 6, true)
		var col := ICE if on else SOFT
		_text(Vector2(770, y + 18), "#" + str(d.get("n", "")), 26, col, _raj, -1, false)
		_text(Vector2(840, y + 18), str(d.get("label", name)), 26, col, _raj, -1, false, 430)
		var w: Array = d.get("wires", [])
		if w.size() > 1:
			_wire(Vector2(1290, y + 6), str(w[1]), 90, 24)
		var ms = d.get("pulse")
		_text(Vector2(1585, y + 18), ("%d ms" % int(ms)) if ms != null else "hold", 24, col, _raj, 1, false)


func _paint_trough() -> void:
	var switches: Dictionary = devices.get("switches", {})
	var rows: Array = state.get("switches", [])
	_pf_panel()
	var panel := Rect2(742, 190, 868, TOP - 6 - 190)
	_box(panel, DIM, PANEL, 2, 10, false)
	_text(Vector2(panel.get_center().x, 236), str(state.get("title", "BALL TROUGH TEST")), 40, ICE, _orb, 0, true,
		820, CYAN)
	var balls := []
	var others := []
	for row in rows:
		var name := str(row.get("name", ""))
		if name.begins_with("s_trough_") and name != "s_trough_jam":
			balls.append(row)
		else:
			others.append(row)
		var p = _at(switches.get(name, {}))
		if p != null:
			_dot(p, 7, GREEN if row.get("active", false) else Color8(120, 200, 230), bool(row.get("active", false)))
	# the trough: trough 4 (left) .. 1 (right) on a sloped floor
	var a := Vector2(800, 470)
	var b := Vector2(1450, 560)
	_paper.draw_line(a, b, Color(CYAN, 0.3), 12, true)
	_paper.draw_line(a, b, CYAN, 5, true)
	balls.reverse()                                   # left to right: 4, 3, 2, 1
	var home := 0
	for k in balls.size():
		var row: Dictionary = balls[k]
		var on := bool(row.get("active", false))
		home += 1 if on else 0
		var x := 880.0 + k * 150
		var y := a.y + (x - a.x) * (b.y - a.y) / (b.x - a.x) - 48
		var d: Dictionary = switches.get(str(row.get("name", "")), {})
		_dot(Vector2(x, y), 42, Color8(190, 200, 210) if on else Color8(30, 40, 50), false, Color.WHITE)
		_text(Vector2(x, y), "#" + str(d.get("n", "")), 26, Color8(10, 20, 30) if on else DIM, _raj, 0, false)
		_text(Vector2(x, y + 92), str(d.get("label", "")), 22, GREEN if on else DIM, _raj, 0, false, 145)
	var parts := ["%d ball%s home" % [home, "" if home == 1 else "s"]]
	for row in others:
		var d: Dictionary = switches.get(str(row.get("name", "")), {})
		parts.append("%s #%s %s" % [str(d.get("label", row.get("name", ""))).to_lower(), str(d.get("n", "")),
			"closed" if row.get("active", false) else "open"])
	_text(Vector2(panel.get_center().x, 700), "  /  ".join(parts), 28, GREEN, _raj, 0, false, 820)
	_text(Vector2(panel.get_center().x, 760), "SELECT ejects one ball to the shooter lane", 30, ICE, _raj, 0, false)

# ------------------------------------------------------------------ drawing helpers

## Text at pos: h_align -1 left edge, 0 centred, 1 right edge; centred on pos.y. max_w > 0 shrinks it to fit.
func _text(pos: Vector2, s: String, font_size: float, col: Color, font: Font, h_align: int, glow: bool,
		max_w: float = 0.0, glow_col = null) -> void:
	if s == "":
		return
	var fs := int(font_size)
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	while max_w > 0 and w > max_w and fs > 12:
		fs -= 1
		w = font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var x := pos.x - (w * 0.5 if h_align == 0 else (w if h_align > 0 else 0.0))
	var base := Vector2(x, pos.y + (font.get_ascent(fs) - font.get_descent(fs)) * 0.5)
	if glow:
		var g: Color = glow_col if glow_col != null else col
		_paper.draw_string_outline(font, base, s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 14, Color(g, 0.12))
		_paper.draw_string_outline(font, base, s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 6, Color(g, 0.28))
	_paper.draw_string(font, base, s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)


## A rounded box with a neon border; glow adds a soft halo outside it.
func _box(r: Rect2, border: Color, fill: Color, width: int, radius: int, glow: bool) -> void:
	if glow:
		for g in [[9.0, 0.07], [5.0, 0.14], [2.0, 0.28]]:
			var halo := StyleBoxFlat.new()
			halo.draw_center = false
			halo.border_color = Color(border, g[1])
			halo.set_border_width_all(width + 3)
			halo.set_corner_radius_all(radius + int(g[0]))
			halo.anti_aliasing = true
			_paper.draw_style_box(halo, r.grow(g[0]))
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = border
	sb.set_border_width_all(width)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	_paper.draw_style_box(sb, r)


func _fill(r: Rect2, col: Color, radius: int) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = col
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	_paper.draw_style_box(sb, r)


func _dot(p: Vector2, r: float, col: Color, glow: bool, outline = null) -> void:
	if glow:
		_paper.draw_circle(p, r + 8, Color(col, 0.1))
		_paper.draw_circle(p, r + 4, Color(col, 0.22))
	_paper.draw_circle(p, r, col)
	if outline != null:
		_paper.draw_arc(p, r, 0, TAU, 32, outline, 2, true)


func _ring(p: Vector2, r: float, col: Color, width: float) -> void:
	_paper.draw_arc(p, r, 0, TAU, 64, Color(col, 0.25), width + 6, true)
	_paper.draw_arc(p, r, 0, TAU, 64, col, width, true)


## The EXIT tile's power symbol (the ROM has no icon of its own for it in the main menu).
func _power(c: Vector2, r: float, col: Color) -> void:
	_paper.draw_arc(c, r, deg_to_rad(-60), deg_to_rad(240), 48, col, 10, true)
	_paper.draw_line(c - Vector2(0, r * 1.15), c - Vector2(0, r * 0.25), col, 10, true)


## A ROM image (a menu icon) scaled up, in colour col: the ROM's dot levels become its alpha.
func _icon(n: int, pos: Vector2, scale: float, col: Color) -> void:
	if not _icons.has(n):
		if _zip == null:
			_zip = ZIPReader.new()
			if _zip.open(ProjectSettings.globalize_path("res://").path_join(IMAGES_ZIP)) != OK:
				push_warning("service backglass: no %s" % IMAGES_ZIP)
		var bytes := _zip.read_file("%04d.png" % n) if _zip.get_files().size() else PackedByteArray()
		var img := Image.new()
		var out: Texture2D = null
		if bytes.size() and img.load_png_from_buffer(bytes) == OK:
			img.convert(Image.FORMAT_RGBA8)
			for y in img.get_height():
				for x in img.get_width():
					img.set_pixel(x, y, Color(1, 1, 1, img.get_pixel(x, y).get_luminance()))
			out = ImageTexture.create_from_image(img)
		_icons[n] = out
	var t: Texture2D = _icons[n]
	if t:
		_paper.draw_texture_rect(t, Rect2(pos, t.get_size() * scale), false, col)


## The button hints: [["MINUS", "PLUS", "move"], ["SELECT", "open"]] as key caps and their labels; a group of one
## is a plain line.
func _keys(cx: float, cy: float, groups: Array) -> void:
	var parts := []
	var total := 0.0
	for g in groups:
		if g.size() == 1:
			var w1 := _raj.get_string_size(str(g[0]), HORIZONTAL_ALIGNMENT_LEFT, -1, 28).x + 34
			parts.append(["t", str(g[0]), w1])
			total += w1
			continue
		for k in range(g.size() - 1):
			var wk := _orb.get_string_size(str(g[k]), HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x + 24
			parts.append(["k", str(g[k]), wk])
			total += wk
		var wl := _raj.get_string_size(str(g[-1]), HORIZONTAL_ALIGNMENT_LEFT, -1, 28).x + 30
		parts.append(["l", str(g[-1]), wl])
		total += wl
	var x := cx - total * 0.5
	for part in parts:
		match part[0]:
			"k":
				_box(Rect2(x, cy - 18, part[2] - 6, 36), CYAN, Color8(10, 50, 75), 2, 6, false)
				_text(Vector2(x + (part[2] - 6) * 0.5, cy), part[1], 18, ICE, _orb, 0, false)
			"l":
				_text(Vector2(x + 6, cy), part[1], 28, Color8(150, 200, 225), _raj, -1, false)
			_:
				_text(Vector2(x + part[2] * 0.5, cy), part[1], 28, ICE, _raj, 0, false)
		x += part[2]
