extends Node
## Saves the 128x32 DMD to PNG files in real time, for checks run without a screen.
## Inert unless Godot is started with user args, for example:
##   godot --path game -- --capture-dir=/abs/path --capture-every-ms=250 --capture-for-ms=15000
## Frames are written as frame_00000.png, frame_00001.png, ...; Godot quits after capture-for-ms.

var _dir := ""
var _count := 0

func _ready() -> void:
	var args := {}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-") and "=" in arg:
			var parts := arg.trim_prefix("--").split("=", true, 1)
			args[parts[0]] = parts[1]
	if not args.has("capture-dir"):
		return
	_dir = args["capture-dir"]
	DirAccess.make_dir_recursive_absolute(_dir)
	var timer := Timer.new()
	timer.wait_time = int(args.get("capture-every-ms", "250")) / 1000.0
	timer.timeout.connect(_capture)
	add_child(timer)
	timer.start()
	get_tree().create_timer(int(args.get("capture-for-ms", "15000")) / 1000.0).timeout.connect(get_tree().quit)

func _capture() -> void:
	var image := get_viewport().get_texture().get_image()
	image.save_png("%s/frame_%05d.png" % [_dir, _count])
	_count += 1
