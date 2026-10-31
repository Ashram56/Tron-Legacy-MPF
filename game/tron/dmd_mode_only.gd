extends Control
## A part of a slide drawn only on the classic DMD (the ROM's 128x32 dots) or only in HD, whichever `only_classic` says:
## text_page.tscn keeps the ROM's status panel (the line at x 40 and the points) on the classic DMD, where it is the ROM's
## output, and leaves it off in HD, which draws the pages over its picture without the panel (tron/rom_text.gd hd_x).
const RomText = preload("res://tron/rom_text.gd")

@export var only_classic := true


func _process(_delta: float) -> void:
	visible = RomText.hd() != only_classic
