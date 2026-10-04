extends Control

## A PuP screen's video player on Linux: GDE GoZen's VideoPlayback (FFmpeg; pup_addons/gde_gozen), which plays the
## pack's mp4s as they are and uses the Jetson's hardware decoder when libnvmpi is installed (docs/pup.md). Offers
## the parts of VideoStreamPlayer that pup_screen.gd uses: open(), play() (from the start), stop(), finished.

signal finished

const PLAYBACK := "res://addons/gde_gozen/video_playback.gd"

var bus := "sfx"
var _playback: Control
var _loop := false


func _ready() -> void:
	_playback = load(PLAYBACK).new()
	_playback.set_anchors_preset(Control.PRESET_FULL_RECT)
	_playback.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_playback.enable_auto_play = true
	add_child(_playback)
	_playback.video_ended.connect(_on_ended)
	_playback.video_loaded.connect(func(): _playback.video_texture.show())
	# VideoPlayback adds an audio bus of its own (for its pitch effect): send it to this screen's bus
	var own := AudioServer.get_bus_index(_playback.audio_player.bus)
	if own >= 0 and AudioServer.get_bus_index(bus) >= 0:
		AudioServer.set_bus_send(own, bus)


func open(path: String, loop: bool, volume_db: float) -> void:
	_loop = loop
	_playback.loop = loop
	_playback.audio_player.volume_db = volume_db
	_playback.set_video_path(path)


## From the first frame again (pup_screen.gd's restart of a looping file or background).
func play() -> void:
	if _playback.is_open():
		_playback.seek_frame(0)
		_playback.play()


func stop() -> void:
	_playback.close()
	_playback.video_texture.hide()


func _on_ended() -> void:
	# VideoPlayback restarts a looping file itself
	if not _loop:
		finished.emit()
