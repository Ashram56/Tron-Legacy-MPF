extends Node
## Sends the 128x32 DMD to MPF as 24-bit RGB "rgb_dmd_frame" BCP messages, for a PIN2DMD on USB (game/config/pin2dmd.yaml,
## rgb_dmds: default). Inert unless Godot is started with the user arg --pin2dmd:
##   godot --path game -- --pin2dmd[=COLOUR]
## MPF's pin2dmd platform (mpf/platforms/pin2dmd.py) turns each 12288-byte frame (3 bytes per dot, row by row) into the
## PIN2DMD's "virtual pinball" bit planes. COLOUR is the colour of the full-brightness dot, "#RRGGBB" (default
## #ff730d, the original DMD's orange): the 16 shades of the DMD art, drawn in grey levels (ROM palette level / 15),
## scale it. "rgb" sends the picture's own colours instead, for art that is already coloured.
## The DMD stays classic (exact 128x32, dmd_mode.gd) like with --proc-dmd.

const WIDTH := 128
const HEIGHT := 32
const FPS := 30.0
const DEFAULT_COLOR := "#ff730d"

var _color := Color(DEFAULT_COLOR)
var _rgb := false
var _palette := PackedByteArray()      # 16 shades x 3 bytes
var _last := PackedByteArray()
var _elapsed := 0.0

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var on := false
	for a in args:
		if a == "--pin2dmd":
			on = true
		elif a.begins_with("--pin2dmd="):
			on = true
			var v := a.trim_prefix("--pin2dmd=").strip_edges().to_lower()
			if v == "rgb":
				_rgb = true
			elif Color.html_is_valid(v):
				_color = Color(v)
	set_process(on)
	_palette = shade_palette(_color)

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

## The 12288-byte RGB frame of a 128x32 image (colours, or the shades through the palette).
static func rgb_frame(image: Image, palette: PackedByteArray, rgb: bool) -> PackedByteArray:
	var frame := PackedByteArray()
	frame.resize(WIDTH * HEIGHT * 3)
	for y in HEIGHT:
		for x in WIDTH:
			var dot := image.get_pixel(x, y)
			var at := (y * WIDTH + x) * 3
			if rgb:
				frame[at] = roundi(dot.r * 255.0)
				frame[at + 1] = roundi(dot.g * 255.0)
				frame[at + 2] = roundi(dot.b * 255.0)
			else:
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
	if not MPF.server._client:
		return
	var image := get_viewport().get_texture().get_image()
	if image.get_width() != WIDTH or image.get_height() != HEIGHT:
		image.resize(WIDTH, HEIGHT, Image.INTERPOLATE_NEAREST)
	var frame := rgb_frame(image, _palette, _rgb)
	if frame == _last:
		return
	_last = frame
	MPF.server.send_bytes("rgb_dmd_frame", frame, {"name": "default"})
