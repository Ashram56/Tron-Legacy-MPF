extends Node
## Plays display effects in real time and saves the DMD picture (the autoload DmdScreen's viewport) at given times, to see
## the PuP clips and the HD icons behind and with the text (tron/dmd_effect.gd):
##   godot --path game --rendering-driver opengl3 --resolution 1920x480 res://tools/clip_capture.tscn -- --dmd=hd \
##         --job=/abs/job.json
## job.json: [{"slide": "deff_064", "kwargs": {"line1": "..."}, "times_ms": [200, 1000, 2000], "out": "/abs/dir"}, ...]
## Real time, not seeked: the clip is a video. Files out/clip_NNNNN.png. Quits when done.


func _ready() -> void:
	var job_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--job="):
			job_path = arg.trim_prefix("--job=")
	if job_path:
		_run.call_deferred(JSON.parse_string(FileAccess.get_file_as_string(job_path)))


func _run(jobs: Array) -> void:
	await get_tree().process_frame
	for job in jobs:
		DirAccess.make_dir_recursive_absolute(job["out"])
		var slide = load("res://slides/deffs/%s.tscn" % job["slide"]).instantiate()
		slide.initialize(job["slide"], {"key": job["slide"]}, "capture", 0, job.get("kwargs", {}))
		add_child(slide)
		var start := Time.get_ticks_msec()
		var n := 0
		for t in job["times_ms"]:
			while Time.get_ticks_msec() - start < int(t):
				await get_tree().process_frame
			await RenderingServer.frame_post_draw
			var screen = get_tree().root.get_node("DmdScreen")
			screen.texture().get_image().save_png("%s/clip_%05d.png" % [job["out"], n])
			n += 1
		slide.queue_free()
		await get_tree().process_frame
	get_tree().quit()
