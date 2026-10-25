extends Node
## Sends the 128x32 DMD to MPF as 24-bit RGB "rgb_dmd_frame" BCP messages, for a PIN2DMD on USB (game/config/pin2dmd.yaml)
## or a ZeDMD (game/config/zedmd.yaml); rgb_dmds: default. Inert unless Godot is started with the user arg --pin2dmd or
## --zedmd (the same frames, MPF's platform differs):
##   godot --path game -- --pin2dmd[=COLOUR]   or   --zedmd[=COLOUR]
## MPF's pin2dmd platform (mpf/platforms/pin2dmd.py) turns each 12288-byte frame (3 bytes per dot, row by row) into the
## PIN2DMD's "virtual pinball" bit planes. COLOUR is the colour of the full-brightness dot, "#RRGGBB" (default
## #ff730d, the original DMD's orange): the 16 shades of the DMD art, drawn in grey levels (ROM palette level / 15),
## scale it. The public game is monochrome only: the picture's own colours are never sent.
## The DMD stays classic (exact 128x32, dmd_mode.gd) like with --proc-dmd.

const WIDTH := 128
const HEIGHT := 32
const FPS := 30.0
const DEFAULT_COLOR := "#ff730d"
const FEED_ARG := "--zedmd-feed="      # path of game/native/zedmd_feed: frames go to it through a pipe, not to MPF

var _color := Color(DEFAULT_COLOR)
var _palette := PackedByteArray()      # 16 shades x 3 bytes
var _last := PackedByteArray()
var _elapsed := 0.0
var _feed: FileAccess = null     # the feeder's stdin (scripts/run.py starts the game with --zedmd-feed=PATH)
var _feed_pid := 0

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var on := false
	for a in args:
		if a == "--pin2dmd" or a == "--zedmd":
			on = true
		elif a.begins_with(FEED_ARG):
			_start_feed(a.trim_prefix(FEED_ARG))
		elif a.begins_with("--pin2dmd=") or a.begins_with("--zedmd="):
			on = true
			var v := a.substr(a.find("=") + 1).strip_edges().to_lower()
			if Color.html_is_valid(v):
				_color = Color(v)
	set_process(on)
	_palette = shade_palette(_color)

func _start_feed(path: String) -> void:
	var run := OS.execute_with_pipe(path, [])
	if run.is_empty():
		push_warning("zedmd_feed did not start: " + path)
		return
	_feed = run["stdio"]
	_feed_pid = run["pid"]

func _exit_tree() -> void:
	if _feed_pid:
		if _feed:
			_feed.close()          # the feeder ends when its stdin closes
		OS.kill(_feed_pid)

## 16 shades of one colour as 48 bytes (shade n = the colour at n / 15).
static func shade_palette(color: Color) -> PackedByteArray:
	var out := PackedByteArray()
	out.resize(48)
	for n in 16:
		var k := n / 15.0
		out[n * 3] = roundi(color.r * k * 255.0)
		out[n * 3 + 1] = roundi(color.g * k * 255.0)
		out[n * 3 + 2] = roundi(color.b * k * 255.0)
	return out

## The 12288-byte RGB frame of a 128x32 image: its shades through the palette.
static func rgb_frame(image: Image, palette: PackedByteArray) -> PackedByteArray:
	var frame := PackedByteArray()
	frame.resize(WIDTH * HEIGHT * 3)
	for y in HEIGHT:
		for x in WIDTH:
			var dot := image.get_pixel(x, y)
			var at := (y * WIDTH + x) * 3
			var shade := clampi(roundi(maxf(dot.r, maxf(dot.g, dot.b)) * 15.0), 0, 15)
			frame[at] = palette[shade * 3]
			frame[at + 1] = palette[shade * 3 + 1]
			frame[at + 2] = palette[shade * 3 + 2]
	return frame

func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed < 1.0 / FPS:
		return
	_elapsed = 0.0
	if not _feed and not MPF.server._client:
		return
	var image := get_viewport().get_texture().get_image()
	if image.get_width() != WIDTH or image.get_height() != HEIGHT:
		image.resize(WIDTH, HEIGHT, Image.INTERPOLATE_NEAREST)
	var frame := rgb_frame(image, _palette)
	if frame == _last:
		return
	_last = frame
	if _feed:
		if not OS.is_process_running(_feed_pid):
			push_warning("zedmd_feed stopped")
			_feed = null
			return
		_feed.store_buffer(frame)
		_feed.flush()
		return
	MPF.server.send_bytes("rgb_dmd_frame", frame, {"name": "default"})
