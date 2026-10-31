extends Node
## Harness (conformance checks against PinMAME): writes every change of the classic 128x32 DMD, with its time, to a file.
## Inert unless Godot is started with the user arg --dmd-dump=PATH (and the DMD classic, --dmd classic).
## Record format, the same as tron_ref's TRON_DMDLOG: <double t><int32 w><int32 h><int32 depth=4> then w*h shades 0-15,
## t = Unix time in seconds (the harness aligns it with the MPF trace).

const WIDTH := 128
const HEIGHT := 32

var _file: FileAccess
var _last := PackedByteArray()

func _ready() -> void:
	set_process(false)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dmd-dump="):
			_file = FileAccess.open(a.trim_prefix("--dmd-dump="), FileAccess.WRITE)
	set_process(_file != null)

func _process(_delta: float) -> void:
	var image := get_viewport().get_texture().get_image()
	if image.get_width() != WIDTH or image.get_height() != HEIGHT:
		image.resize(WIDTH, HEIGHT, Image.INTERPOLATE_NEAREST)
	var data := image.get_data()
	var step := 4 if image.get_format() == Image.FORMAT_RGBA8 else 3
	var frame := PackedByteArray()
	frame.resize(WIDTH * HEIGHT)
	for i in WIDTH * HEIGHT:
		var m := maxi(data[i * step], maxi(data[i * step + 1], data[i * step + 2]))
		frame[i] = clampi(roundi(m / 255.0 * 15.0), 0, 15)
	if frame == _last:
		return
	_last = frame
	_file.store_double(Time.get_unix_time_from_system())
	_file.store_32(WIDTH)
	_file.store_32(HEIGHT)
	_file.store_32(4)
	_file.store_buffer(frame)
	_file.flush()

func _exit_tree() -> void:
	if _file:
		_file.close()
