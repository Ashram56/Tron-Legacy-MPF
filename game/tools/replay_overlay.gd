extends Node
## The game's random seed and the replay clock (game/tron/recording.py, not in the ROM).
## MPF sends "tron_seed" at each game start: Godot's own picks (clip variants, clip files) use it, so the same seed and the same
## switches give the same display. "tron_replay" starts a clock (mm:ss.s) in a corner of the window, the one of the
## `<file>.timeline.txt` the replay writes, to match what is seen with the effect the game started.

const DmdEffect := preload("res://tron/dmd_effect.gd")

var _label: Label
var _layer: CanvasLayer
var _t0 := 0


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	MPF.server.registered_handlers["tron_seed"] = [Callable(self, "_on_seed")]
	MPF.server.registered_handlers["tron_replay"] = [Callable(self, "_on_replay")]


func _on_seed(message = null) -> void:
	var s := 0
	if message is Dictionary:
		s = int(message.get("seed", 0))
	DmdEffect.seed_game(s)
	print("tron_seed ", s)


func _dmd_is_the_window() -> bool:
	## The classic DMD IS the root viewport when a PIN2DMD, a ZeDMD, the P-ROC DMD or a frame dump reads it (dmd_mode.gd): a clock
	## drawn over it would be sent to the DMD, and Serum would not know those frames (blue).
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--pin2dmd") or a.begins_with("--zedmd") or a == "--proc-dmd" or a.begins_with("--dmd-dump=") \
				or a == "--dmd=classic":
			return true
	return OS.get_environment("TRON_DMD") == "classic"


func _on_replay(_message = null) -> void:
	if _label != null or _dmd_is_the_window():
		return
	_layer = CanvasLayer.new()
	_layer.layer = 200
	add_child(_layer)
	_label = Label.new()
	_label.position = Vector2(8, 8)
	_label.add_theme_font_size_override("font_size", 28)
	_label.add_theme_color_override("font_color", Color(1, 1, 0.3))
	_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_label.add_theme_constant_override("outline_size", 6)
	_layer.add_child(_label)
	_t0 = Time.get_ticks_msec()


func _process(_d: float) -> void:
	if _label == null:
		return
	var t := (Time.get_ticks_msec() - _t0) / 1000.0
	_label.text = "%02d:%04.1f" % [int(t / 60.0), fmod(t, 60.0)]
