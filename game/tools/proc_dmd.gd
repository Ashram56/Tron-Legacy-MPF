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
var _last_data := PackedByteArray()
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
	if image.get_format() != Image.FORMAT_RGBA8:
		image.convert(Image.FORMAT_RGBA8)
	# An unchanged picture (most of the time) is one memcmp, not 4096 dots converted.
	var data := image.get_data()
	if data == _last_data:
		return
	_last_data = data
	var frame := PackedByteArray()
	frame.resize(WIDTH * HEIGHT)
	for i in WIDTH * HEIGHT:
		var o := i * 4
		var v := maxi(data[o], maxi(data[o + 1], data[o + 2]))
		frame[i] = (v * 15 + 127) / 255       # shade 0-15: the brightest channel, rounded
	if frame == _last:
		return
	_last = frame
	MPF.server.send_bytes("dmd_frame", frame, {"name": "dmd"})
