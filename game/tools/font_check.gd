extends SceneTree
## Prints, as one JSON line, the advance Godot gives every character of every HD vector font (tron/rom_text_hd.gd)
## at the size the DMD draws it (font size = line height in dots), and the width of each font's whole character
## set as one string, for tests/test_dmd_hd.py:
##   godot --headless --path game --script res://tools/font_check.gd

const RomTextHd = preload("res://tron/rom_text_hd.gd")


func _initialize() -> void:
	var out := {}
	var metrics = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/fonts.json"))
	for m in metrics["fonts"]:
		var id := int(m["id"])
		var size := int(m["ascent"]) + int(m["descent"])
		var font := RomTextHd.vector_font(id)
		var glow := RomTextHd.glow_font(id)
		var adv := {}
		var all := ""
		for c in m["glyphs"]:
			adv[c] = [font.get_string_size(c, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x,
				font.get_string_size(String.chr(RomTextHd.CELL_PLANE + c.unicode_at(0)), HORIZONTAL_ALIGNMENT_LEFT, -1, size).x,
				glow.get_string_size(c, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x]
			all += c
		out[str(id)] = {"advances": adv, "all": font.get_string_size(all, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x,
			"ascent": font.get_ascent(size), "descent": font.get_descent(size)}
	print("FONT_CHECK " + JSON.stringify(out))
	quit()
