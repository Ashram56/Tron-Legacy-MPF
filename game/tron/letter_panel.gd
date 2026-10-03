extends Node
## The four letters of a target bank in a display effect (scripts/gen_media.py LETTER_DEFFS), drawn like
## the ROM's deff_091_zuse_collect (0x01033b3c), deff_092_zuse_more (0x01033fbc) and deff_107_collect
## (0x0102c870): sibling sprites Solid0-3 (letter collected) and Hollow0-3 (letter still to get, dim).
## The letters come from the event args (tron/media_bridge.py): lit_key = the collected letters, new_key =
## the letter just hit (bit 0 = first letter). The new letter blinks solid: shown on effect frames where
## (frame >> blink_shift) & 1, and on every frame after solid_after; nothing is drawn in its place
## between blinks. all_new: every letter blinks that way. Seekable for scripts/render_diff.py (seek_ms).

@export var lit_key := "lit"
@export var new_key := "new"
@export var all_new := false
@export var frame_ms := 46.23
@export var blink_shift := 1
@export var solid_after := 21
## hide_after_ms: no letter from then on (0 = never; deff 94 moves on to its next screen)
@export var hide_after_ms := 0

var _elapsed_ms := 0.0
var _seeked := false
var _values := {}


func _ready() -> void:
	add_to_group("rom_timed")
	var slide = MPF.util.find_parent_slide_or_widget(self)
	if slide:
		slide.register_updater(self)
	_apply()


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
