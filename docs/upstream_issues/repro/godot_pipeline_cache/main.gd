extends Node3D
# Vulkan pipeline cache with the separate render thread (rendering/driver/threads/thread_model=2).
# Run the project twice. Expected: the second run finds the pipeline cache saved by the first.
# Actual: "finalize can only be called from the render thread" at exit, no cache file, and every run compiles
# every pipeline again (the long first frame below on every run).
# With rendering/rendering_device/pipeline_cache/save_chunk_size_mb=0.1 the cache is written during the run.

var t0 := 0
var frames := 0


func _ready() -> void:
	var dir := OS.get_user_data_dir() + "/vulkan"
	var found := DirAccess.get_files_at(dir) if DirAccess.dir_exists_absolute(dir) else PackedStringArray()
	print("pipeline cache files in %s at start: %s" % [dir, ", ".join(found) if found.size() else "none"])
	var cam := Camera3D.new()
	cam.position = Vector3(0, 1, 6)
	add_child(cam)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.glow_enabled = true
	add_child(env)
	# a handful of materials and a particle system with a light: enough pipelines to compile
	for i in 12:
		var m := MeshInstance3D.new()
		m.mesh = [BoxMesh.new(), SphereMesh.new(), CylinderMesh.new(), TorusMesh.new()][i % 4]
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color.from_hsv(i / 12.0, 0.8, 1.0)
		mat.emission_enabled = i % 2 == 0
		mat.emission = mat.albedo_color
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if i % 3 == 0 else BaseMaterial3D.TRANSPARENCY_DISABLED
		mat.albedo_color.a = 0.7
		m.material_override = mat
		m.position = Vector3((i % 4) * 1.5 - 2.25, (i / 4) * 1.2 - 0.6, 0)
		add_child(m)
	var p := GPUParticles3D.new()
	p.amount = 64
	p.process_material = ParticleProcessMaterial.new()
	var pm := QuadMesh.new()
	pm.size = Vector2(0.1, 0.1)
	var pmat := StandardMaterial3D.new()
	pmat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	pmat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	pm.material = pmat
	p.draw_pass_1 = pm
	add_child(p)
	var light := OmniLight3D.new()
	light.position = Vector3(0, 2, 2)
	light.shadow_enabled = true
	add_child(light)
	t0 = Time.get_ticks_msec()


func _process(_delta: float) -> void:
	frames += 1
	if frames == 5:
		print("first 5 frames took %d ms" % (Time.get_ticks_msec() - t0))
	if frames == 120:
		get_tree().quit()
