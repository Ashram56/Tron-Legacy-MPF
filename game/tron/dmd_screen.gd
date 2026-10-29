extends Node
## The display effects' picture (autoload DmdScreen): one fixed set of canvas items in its own SubViewport draws the
## effect on top of GMC's slide stack from its data (tron/dmd_effect.gd), and the viewport renders only when that
## picture changes (a new frame, a line blinking, new values), not at every frame. Each effect's GMC slide
## (tron/dmd_effect_slide.gd, one node) shows this picture. Nothing is built or freed when an effect starts or stops:
## its show only changes the draw list.
## Size: classic, the 128x32 dots; HD, the 128x32 area of the window in pixels (the window's content scale), kept in
## step when the window is resized. Layers, as the node scenes draw them: the pictures, rectangles and the black under
## the text; the glows (added); the lit text. A zoomed line (deff 100) has its own three, clipped.

const RomTextHd = preload("res://tron/rom_text_hd.gd")
const GROUP := "dmd_effect_slides"     # tron/dmd_effect_slide.gd in data mode

var hd := false
var redraws := 0                       # pictures rendered (the perf probe and tests read it)
var _vp: SubViewport
var _layers: Array[Node2D] = []        # base, glow, ink, then the clipped base, glow, ink
var _list: Array = []
var _top: Node = null
var _dirty := true
var _clip := Rect2()
var _colour := false                   # tools/dmd_mode.gd color: the colour pictures (2x) shown with crisp dots
var _clip_player: Control = null       # a PuP clip behind the picture (a CanvasLayer under it: the viewport's scale does not touch it)
var _clip_black: ColorRect = null
var _clip_still: TextureRect = null
var _stills := {}
const CLIP_GRACE_MS := 350
var _clip_gone := -1                   # ms when the clip left the list, -1 while it is in it
var _clip_key := ""                    # path and show of the clip open
var _always := false                   # a clip plays: the viewport renders at every frame
var _runs: Array[Node2D] = []          # colour: the base drawn as runs of the list, colour pictures nearest
var _run_ranges: Array = []            # [from, to] of the list per run


func _ready() -> void:
	process_priority = 1000            # after the effects' slides advanced their time
	var dmd = get_tree().root.get_node_or_null("DmdMode")
	hd = dmd != null and dmd.hd
	_vp = SubViewport.new()
	_vp.name = "DmdPicture"
	_vp.disable_3d = true
	_vp.transparent_bg = false
	_vp.gui_disable_input = true
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_LINEAR if hd \
		else Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_colour = hd and dmd.color
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(_vp)
	for k in 6:
		var layer := Node2D.new()
		layer.name = ["Base", "Glow", "Ink", "ZoomBase", "ZoomGlow", "ZoomInk"][k]
		if k % 3 == 1:
			var add := CanvasItemMaterial.new()
			add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			layer.material = add
		layer.draw.connect(_draw_layer.bind(layer, k))
		_vp.add_child(layer)
		_layers.append(layer)
	for k in range(3, 6):
		RenderingServer.canvas_item_set_clip(_layers[k].get_canvas_item(), true)
	add_to_group(RomTextHd.GROUP)       # restyle(): the service menu changed the text glow or size
	_resize()
	get_tree().root.size_changed.connect(_resize)


func _exit_tree() -> void:
	preload("res://tron/letter_panel.gd").clear_glows()


## The picture the effects' slides show (128x32 dots).
func texture() -> Texture2D:
	return _vp.get_texture()


func _resize() -> void:
	var size := Vector2i(128, 32)
	var k := 1.0
	if hd:
		var win := Vector2(get_tree().root.size)
		k = maxf(minf(win.x / 128.0, win.y / 32.0), 1.0)
		size = Vector2i(roundi(128.0 * k), roundi(32.0 * k))
	if size != _vp.size:
		_vp.size = size
		_vp.canvas_transform = Transform2D.IDENTITY.scaled(Vector2(k, k))
		_dirty = true
		if _clip_player:
			_clip_player.size = Vector2(size)
			_clip_black.size = Vector2(size)
			_clip_still.size = Vector2(size)


func restyle() -> void:
	_dirty = true


## The effect on top: the last effect slide in the tree's drawing order that shows.
func _top_slide() -> Node:
	var slides := get_tree().get_nodes_in_group(GROUP)
	for i in range(slides.size() - 1, -1, -1):
		var s = slides[i]
		if s.state != null and s.is_visible_in_tree():
			return s
	return null


## The PuP clip of the effect on top (tron/dmd_effect.gd "clip" entry), played by GDE GoZen behind the picture; "" stops it.
func _set_clip(list: Array) -> void:
	var path := ""
	var show := 0
	var loop := false
	for e in list:
		if e[0] == "clip":
			path = e[1]
			show = e[2]
			loop = e[3]
			break
	var key := "" if path == "" else "%s#%d" % [path, show]
	if path == "" and _clip_key != "":       # the effect is shown again a moment later (a new counter value): keep the video
		if _clip_gone < 0:
			_clip_gone = Time.get_ticks_msec()
		if Time.get_ticks_msec() - _clip_gone < CLIP_GRACE_MS:
			return
	_clip_gone = -1
	if key == _clip_key:
		return
	_clip_key = key
	if path == "":
		if _clip_player:
			_clip_player.stop()
			_clip_player.visible = false
			_clip_black.visible = false
			_clip_still.visible = false
		return
	if _clip_player == null:
		var layer := CanvasLayer.new()
		layer.layer = -1
		_vp.add_child(layer)
		var black := ColorRect.new()          # the viewport's own clear colour is grey: black until the first frame
		black.color = Color.BLACK
		black.size = Vector2(_vp.size)
		layer.add_child(black)
		_clip_black = black
		_clip_still = TextureRect.new()       # the clip's first picture until the player shows its own
		_clip_still.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		_clip_still.stretch_mode = TextureRect.STRETCH_SCALE
		_clip_still.size = Vector2(_vp.size)
		layer.add_child(_clip_still)
		_clip_player = preload("res://pup/gozen_player.gd").new()
		_clip_player.size = Vector2(_vp.size)
		layer.add_child(_clip_player)
	_clip_player.visible = true
	_clip_black.visible = true
	_clip_still.texture = _still(path)
	_clip_still.visible = _clip_still.texture != null
	_clip_player.open(path, loop, 0.0)


## The still of a clip (clip.mp4 -> clip.jpg, scripts/pup/gen_dmd_clips.py), or null.
func _still(path: String) -> Texture2D:
	var jpg := path.get_basename() + ".jpg"
	if not _stills.has(jpg):
		var img: Image = Image.load_from_file(jpg) if FileAccess.file_exists(jpg) else null
		_stills[jpg] = ImageTexture.create_from_image(img) if img else null
	return _stills[jpg]


func _process(_delta: float) -> void:
	if _clip_still and _clip_still.visible and _clip_player.showing():
		_clip_still.visible = false
	var top := _top_slide()
	var list: Array = top.state.build() if top else []
	_set_clip(list)
	if (_clip_key != "") != _always:
		_always = _clip_key != ""
		var dmd = get_node_or_null("/root/DmdMode")
		if dmd and dmd.has_method("set_dots_visible"):
			dmd.set_dots_visible(not _always)         # no dot mask over a video
		_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if _always else SubViewport.UPDATE_ONCE
		_dirty = true
	if top == _top and list == _list and not _dirty:
		return
	_top = top
	_list = list
	_dirty = false
	if OS.get_environment("TRON_DMD_DEBUG") != "":
		for e in _list:
			if e[0] == "htext":
				print("DMD htext %s flags=%s width=%s xf=%s clip=%s k=%s vp=%s" % [e[1][0], e[1][5], e[1][4], e[2],
						e[4], _vp.canvas_transform.x.x, _vp.size])
	_clip = Rect2()
	for e in _list:
		if e[0] == "htext" and e[4] != Rect2():
			_clip = e[4]
			break
	for k in range(3, 6):                 # the clipped layers sit at the clip's corner
		_layers[k].position = _clip.position
		RenderingServer.canvas_item_set_custom_rect(_layers[k].get_canvas_item(), true, Rect2(Vector2.ZERO, _clip.size))
	if _colour:
		_split_runs()
	for layer in _layers:
		layer.queue_redraw()
	if not _always:
		_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	redraws += 1


static func _line(p: Array) -> RomTextHd.Line:
	var l := RomTextHd.Line.new()
	l.set_line(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7])
	return l


## Colour: the base layer's entries in runs, each a child of the base with its own texture filter (nearest for the
## pictures of media/dmd_color/, the HD default for the rest), drawn in the list's order.
func _split_runs() -> void:
	_run_ranges = []
	var last = null
	for i in _list.size():
		var e: Array = _list[i]
		var crisp: bool = e[0] == "tex" and e[1] != null and e[1].resource_path.begins_with("res://media/dmd_color/")
		if crisp != last:
			_run_ranges.append([i, i + 1, crisp])
			last = crisp
		else:
			_run_ranges[-1][1] = i + 1
	while _runs.size() < _run_ranges.size():
		var run := Node2D.new()
		var n := _runs.size()
		run.draw.connect(func():
			if n < _run_ranges.size():
				_draw_layer(run, 0, _run_ranges[n][0], _run_ranges[n][1]))
		_layers[0].add_child(run)
		_runs.append(run)
	for n in _runs.size():
		if n < _run_ranges.size():
			_runs[n].texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST if _run_ranges[n][2] \
				else CanvasItem.TEXTURE_FILTER_PARENT_NODE
		_runs[n].queue_redraw()


func _draw_layer(item: Node2D, k: int, from := 0, to := -1) -> void:
	var zoom := k >= 3
	var part := k % 3
	if _colour and item == _layers[0]:
		return                             # drawn by its runs
	for i in range(from, _list.size() if to < 0 else to):
		var e: Array = _list[i]
		match e[0]:
			"tex":
				if part == 0 and not zoom:
					item.draw_texture_rect(e[1], e[2], false, e[3])
			"rect":
				if part == 0 and not zoom:
					item.draw_rect(e[1], e[2])
			"ctext":
				if part == 0 and not zoom:
					item.draw_string(e[1], e[3], e[2], HORIZONTAL_ALIGNMENT_LEFT, -1, e[4], e[5])
			"glowtex":
				if part == 1 and not zoom:
					item.draw_texture_rect(e[1], e[2], false, e[3])
			"htext":
				if (e[4] != Rect2()) != zoom:
					continue
				var xf: Transform2D = e[2]
				if zoom:
					xf = Transform2D(0.0, -e[4].position) * xf
				var line := _line(e[1])
				if e.size() > 5:
					line.ink = e[5]
				if e.size() > 6:
					line.score = e[6]
				line.tight = e.size() > 7 and e[7]
				if part == 0:
					line.draw_cell(item, xf, e[3])
				elif part == 1:
					line.draw_glow(item, xf, e[3])
				else:
					line.draw_ink(item, xf, e[3])
