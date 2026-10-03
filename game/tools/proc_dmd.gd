extends Node
## Sends the 128x32 DMD to MPF as 16-shade "dmd_frame" BCP messages, for the original DMD on the P-ROC
## (game/config/hw_proc.yaml, dmds: dmd). Inert unless Godot is started with the user arg --proc-dmd:
##   godot --path game -- --proc-dmd
## MPF's dmds device passes each 4096-byte frame (one byte per dot, row by row, shade 0-15) to the P-ROC
## (mpf/platforms/p_roc.py, PROCDMD.update). The DMD art is drawn in grey levels (ROM palette level / 15),
## so a dot's shade is its brightest channel.

const WIDTH := 128
const HEIGHT := 32
const FPS := 30.0

var _last := PackedByteArray()
var _elapsed := 0.0

func _ready() -> void:
	set_process("--proc-dmd" in OS.get_cmdline_user_args())

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
	var frame := PackedByteArray()
	frame.resize(WIDTH * HEIGHT)
	for y in HEIGHT:
		for x in WIDTH:
			var dot := image.get_pixel(x, y)
			frame[y * WIDTH + x] = clampi(roundi(maxf(dot.r, maxf(dot.g, dot.b)) * 15.0), 0, 15)
	if frame == _last:
		return
	_last = frame
	MPF.server.send_bytes("dmd_frame", frame, {"name": "dmd"})
