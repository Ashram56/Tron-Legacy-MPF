extends SceneTree
## Pictures of the service menu on the backglass (game/pup/service_backglass.gd) from saved descriptions, for the
## docs and for checking a change by eye without a cabinet:
##
##   godot --path game -s res://tools/service_backglass_shots.gd -- --states=DIR --out=DIR [--still=PNG]
##
## DIR holds one JSON per screen (tron/service_backglass.py's description, with "devices"); each becomes
## OUT/<name>.png at 1920x1080. --still defaults to the converted PuP media's (scripts/pup/gen_pup.py). Needs a
## real renderer (a display, or Xvfb on Linux): --headless draws nothing.

const ServiceBackglass := preload("res://pup/service_backglass.gd")


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var states := ""
	var out := ""
	var still := ProjectSettings.globalize_path("res://").path_join("../pup_media/trn_174h/service/backglass_still.png")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--states="):
			states = arg.split("=", true, 1)[1]
		elif arg.begins_with("--out="):
			out = arg.split("=", true, 1)[1]
		elif arg.begins_with("--still="):
			still = arg.split("=", true, 1)[1]
	if states == "" or out == "":
		push_error("usage: -- --states=DIR --out=DIR [--still=PNG]")
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(out)
	var view := ServiceBackglass.new()
	root.add_child(view)
	view.setup(still.simplify_path(), "fit", 0.5)
	var names := Array(DirAccess.get_files_at(states)).filter(func(n): return n.ends_with(".json"))
	names.sort()
	for name in names:
		var state = JSON.parse_string(FileAccess.get_file_as_string(states.path_join(name)))
		if not (state is Dictionary):
			push_warning("not a description: " + name)
			continue
		view.show_state(state)
		for i in 3:
			await process_frame
		await RenderingServer.frame_post_draw
		var path := out.path_join(name.get_basename() + ".png")
		view._viewport.get_texture().get_image().save_png(path)
		print("wrote ", path)
	quit(0)
