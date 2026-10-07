extends Node
## The four letters of a target bank in a display effect (scripts/gen_media.py LETTER_DEFFS), drawn like
## the ROM's deff_091_zuse_collect (0x01033b3c), deff_092_zuse_more (0x01033fbc) and deff_107_collect
## (0x0102c870): sibling sprites Solid0-3 (letter collected) and Hollow0-3 (letter still to get, dim).
## The letters come from the event args (tron/media_bridge.py): lit_key = the collected letters, new_key =
## the letter just hit (bit 0 = first letter). The new letter blinks solid: shown on effect frames where
## (frame >> blink_shift) & 1, and on every frame after solid_after; nothing is drawn in its place
## between blinks. all_new: every letter blinks that way. Seekable for scripts/render_diff.py (seek_ms).
## HD mode (tools/dmd_mode.gd): the letters in the DMD text colour (same levels), each with a soft glow of
## the glow colour around its lit dots (a blurred copy of the letter, outside its strokes, added over it).

@export var lit_key := "lit"
@export var new_key := "new"
@export var all_new := false
@export var frame_ms := 46.23
@export var blink_shift := 1
@export var solid_after := 21
## hide_after_ms: no letter from then on (0 = never; deff 94 moves on to its next screen)
@export var hide_after_ms := 0

const RomTextHd = preload("res://tron/rom_text_hd.gd")
const GLOW_DOTS := 4            # glow margin around a letter, in dots
const GLOW_PX := 2              # glow texture pixels per dot (it is soft: filtering enlarges it cleanly)

static var _glow_textures: Dictionary = {}

var _elapsed_ms := 0.0
var _seeked := false
var _values := {}


func _ready() -> void:
	add_to_group("rom_timed")
	var slide = MPF.util.find_parent_slide_or_widget(self)
	if slide:
		slide.register_updater(self)
	_style_hd()
	_apply()


func _style_hd() -> void:
	var dmd = get_tree().root.get_node_or_null("DmdMode")
	if not (dmd and dmd.hd):
		return
	var st: Dictionary = dmd.text_style()
	var clean := not RomTextHd.clean().is_empty()
	for i in 4:
		for n in ["Solid%d" % i, "Hollow%d" % i]:
			var sprite := get_parent().get_node_or_null(n) as Sprite2D
			if sprite == null or sprite.texture == null:
				continue
			var level: float = sprite.get_meta("dmd_classic_tint", sprite.modulate).r   # orange times the palette level
			sprite.modulate = Color(1, 1, 1, 1)
			if clean and sprite.has_meta("letter"):
				sprite.self_modulate = Color(1, 1, 1, 0)       # the picture's place only: the letter is drawn
				var letter := CleanLetter.new(str(sprite.get_meta("letter")), n.begins_with("Solid"), level)
				letter.position = sprite.texture.get_size() / 2.0
				letter.scale = Vector2.ONE / sprite.scale
				sprite.add_child(letter, false, INTERNAL_MODE_FRONT)
				continue
			sprite.self_modulate = dmd.text_tint(Color(level, 0, 0, 1))
			var tex := glow_texture(sprite.texture)
			if tex == null or float(st["glow"]) <= 0.0:
				continue
			var glow := Sprite2D.new()
			glow.texture = tex
			glow.centered = false
			var per_dot: float = tex.get_width() / float(_dots(sprite).x + 2 * GLOW_DOTS)
			var dot_px: float = sprite.texture.get_width() / float(_dots(sprite).x)
			glow.scale = Vector2.ONE * dot_px / per_dot
			glow.position = -Vector2.ONE * GLOW_DOTS * dot_px
			var g: Color = st["glow_color"] * (float(st["glow"]) * level)
			g.a = 1.0
			glow.self_modulate = g
			var add := CanvasItemMaterial.new()
			add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			glow.material = add
			sprite.add_child(glow, false, INTERNAL_MODE_BACK)


## HD with a clean font (tron/rom_text_hd.gd): a target letter drawn in it, centred on the ROM letter's box,
## LETTER_CAP dots tall (times the text scale). Solid (collected): filled (FILL) inside a bright outline,
## as the ROM's letter, with the text glow; hollow (still to get): the outline only, at its dim level.
class CleanLetter extends Node2D:
	const LETTER_CAP := 20.0
	const EDGE_DOTS := 0.6
	const HOLLOW_DOTS := 0.8
	const FILL := 0.75             # the solid letter's inside, of its outline's brightness
	var ch: String
	var solid: bool
	var level: float
	var _glow: Node2D

	func _init(c: String, is_solid: bool, lv: float) -> void:
		ch = c
		solid = is_solid
		level = lv
		_glow = Node2D.new()
		var add := CanvasItemMaterial.new()
		add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		_glow.material = add
		_glow.draw.connect(_draw_glow)
		_glow.show_behind_parent = true
		add_child(_glow)

	func _place(item: CanvasItem) -> float:
		var c := RomTextHd.clean()
		var cap := LETTER_CAP * RomTextHd.text_scale()
		var k := cap / (float(c["cap"]) * RomTextHd.CLEAN_SIZE)
		var w: float = (c["font"] as Font).get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, RomTextHd.CLEAN_SIZE).x * k
		item.draw_set_transform(Vector2(-w / 2.0, cap / 2.0), 0.0, Vector2(k, k))
		return k

	func _outline(item: CanvasItem, dots: float, color: Color) -> void:
		var k := _place(item)
		item.draw_string_outline(RomTextHd.clean()["wide"], Vector2.ZERO, ch, HORIZONTAL_ALIGNMENT_LEFT, -1,
			RomTextHd.CLEAN_SIZE, maxi(1, roundi(2.0 * dots / k)), color)
		item.draw_set_transform(Vector2.ZERO)

	func _draw() -> void:
		var color: Color = RomTextHd.style()["color"] * level
		color.a = 1.0
		_outline(self, EDGE_DOTS if solid else HOLLOW_DOTS, color)
		if solid:                      # the inside, over the outline's inner half
			_place(self)
			draw_string(RomTextHd.clean()["font"], Vector2.ZERO, ch, HORIZONTAL_ALIGNMENT_LEFT, -1,
				RomTextHd.CLEAN_SIZE, Color(color.r * FILL, color.g * FILL, color.b * FILL, 1))
			draw_set_transform(Vector2.ZERO)

	func _draw_glow() -> void:
		var st := RomTextHd.style()
		if not solid or float(st["glow"]) <= 0.0:
			return
		var g: Color = st["glow_color"] * float(st["glow"]) * level
		for r in [2.4, 1.8, 1.3, 0.9]:
			_outline(_glow, r, Color(g.r * 0.3, g.g * 0.3, g.b * 0.3, 1))


## The letter's size in dots (its picture's size times the sprite's scale).
static func _dots(sprite: Sprite2D) -> Vector2i:
	return Vector2i((sprite.texture.get_size() * sprite.scale).round())


## A blurred copy of a letter's lit dots (white, the glow as alpha) with GLOW_DOTS of margin, GLOW_PX per dot.
static func glow_texture(tex: Texture2D) -> Texture2D:
	if _glow_textures.has(tex):
		return _glow_textures[tex]
	var img := tex.get_image()
	if img == null:
		return null
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGBA8)
	var src_dots := Vector2i(roundi(img.get_width() / 8.0), roundi(img.get_height() / 8.0))
	var dmd = (Engine.get_main_loop() as SceneTree).root.get_node_or_null("DmdMode")
	if dmd:
		src_dots = Vector2i(roundi(img.get_width() / float(dmd.frame_scale)), roundi(img.get_height() / float(dmd.frame_scale)))
	img.resize(src_dots.x * GLOW_PX, src_dots.y * GLOW_PX, Image.INTERPOLATE_LANCZOS)
	var w := (src_dots.x + 2 * GLOW_DOTS) * GLOW_PX
	var h := (src_dots.y + 2 * GLOW_DOTS) * GLOW_PX
	var a := PackedFloat32Array()
	a.resize(w * h)
	var m := GLOW_DOTS * GLOW_PX
	for y in img.get_height():
		for x in img.get_width():
			var c := img.get_pixel(x, y)
			a[(y + m) * w + x + m] = maxf(c.r, maxf(c.g, c.b)) * c.a
	var lit := a.duplicate()
	for r in [2, 2, 3]:                      # three box blurs: about a Gaussian of 1.2 dots
		a = _box(a, w, h, r, true)
		a = _box(a, w, h, r, false)
	var out := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:                          # around the strokes only: the letter keeps its own colour
			var i := y * w + x
			out.set_pixel(x, y, Color(1, 1, 1, clampf(a[i] * 1.8 * (1.0 - clampf(lit[i], 0.0, 1.0)), 0.0, 1.0)))
	var glow := ImageTexture.create_from_image(out)
	_glow_textures[tex] = glow
	return glow


static func _box(a: PackedFloat32Array, w: int, h: int, r: int, horizontal: bool) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(w * h)
	var n := w if horizontal else h
	var lines := h if horizontal else w
	for l in lines:
		var acc := 0.0
		var at := func(i: int) -> int: return l * w + i if horizontal else i * w + l
		for i in range(-r, r + 1):
			if i >= 0 and i < n:
				acc += a[at.call(i)]
		for i in n:
			out[at.call(i)] = acc / (2 * r + 1)
			var add := i + r + 1
			var sub := i - r
			if add < n:
				acc += a[at.call(add)]
			if sub >= 0:
				acc -= a[at.call(sub)]
	return out


func _exit_tree() -> void:
	var slide = MPF.util.find_parent_slide_or_widget(self)
	if slide:
		slide.remove_updater(self)


func update(_settings: Dictionary, kwargs: Dictionary = {}) -> void:
	for k in kwargs:
		_values[k] = kwargs[k]
	_apply()


func seek_ms(t: float) -> void:
	_seeked = true
	_elapsed_ms = t
	_apply()


func _process(delta: float) -> void:
	if not _seeked:
		_elapsed_ms += delta * 1000.0
		_apply()


func _mask(key: String) -> int:
	if key == "":
		return 0
	var v = _values.get(key, 0)
	return int(v) if v != null and str(v) != "" else 0


## What letter i shows on effect frame `frame`: "solid", "hollow" or "" (a new letter between blinks).
static func letter_state(i: int, lit: int, fresh: int, every_new: bool, frame: int, shift: int,
		after: int) -> String:
	if (lit >> i) & 1 == 1:
		return "solid"
	if every_new or (fresh >> i) & 1 == 1:
		return "solid" if frame > after or (frame >> shift) & 1 == 1 else ""
	return "hollow"


func _apply() -> void:
	var frame := int(_elapsed_ms / frame_ms) if frame_ms > 0 else 0
	var lit := _mask(lit_key)
	var fresh := _mask(new_key)
	for i in 4:
		var state := letter_state(i, lit, fresh, all_new, frame, blink_shift, solid_after)
		if hide_after_ms > 0 and _elapsed_ms >= hide_after_ms:
			state = ""
		var solid := get_parent().get_node_or_null("Solid%d" % i) as CanvasItem
		var hollow := get_parent().get_node_or_null("Hollow%d" % i) as CanvasItem
		if solid:
			solid.visible = state == "solid"
		if hollow:
			hollow.visible = state == "hollow"
