extends Node
## Starts the platform's DMD output (MPF-Godot-Packaging addons/dmd_out: frames to a PIN2DMD or a ZeDMD) when Godot is
## given --pin2dmd or --zedmd, and does nothing otherwise. The add-on is the platform's, not this game's:
## scripts/dmd_out.py copies it into game/addons/dmd_out before the start (docs/hardware.md, "PIN2DMD and ZeDMD").
## The game's DMD stays classic then (dmd_mode.gd): the add-on sends the root viewport, the exact 128x32 dots.


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--pin2dmd" or a.begins_with("--pin2dmd=") or a == "--zedmd" or a.begins_with("--zedmd="):
			_start()
			return


func _start() -> void:
	var script := load("res://addons/dmd_out/dmd_out.gd") as GDScript
	if script == null:
		push_warning("dmd_out: res://addons/dmd_out is missing (scripts/dmd_out.py installs the platform's)")
		return
	var out := script.new() as Node
	out.name = "DmdOut"
	get_tree().root.add_child.call_deferred(out)
