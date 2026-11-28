extends SceneTree
## The deff's clip named by the game (Python draws random_below(n) with the ROM's generator and sends `clip`): the show plays
## exactly that variant, whatever the random pick made when it started. Run: godot --headless --path game --script res://../tests/godot/...
## (tests/test_godot_variant_clip.py).

func _initialize() -> void:
	var frames := []
	for k in 3:
		var v := []
		for i in (k + 2):
			v.append(["res://none.png", 50.0])
		frames.append(v)
	var items := [{"type": "frames", "frames": [["res://none.png", 50.0]], "variants": frames}]
	var failed := 0
	var effect = load("res://tron/dmd_effect.gd")
	for want in [0, 1, 2, 1, 0]:
		var st = effect.State.new(items, false, "deff_068_quorra_jackpot")
		st.update({}, {"clip": want})
		var got: int = st._variant
		var total: float = st._total_ms
		print("CLIP want=", want, " got=", got, " total_ms=", total)
		if got != want or absf(total - 50.0 * (want + 2)) > 0.01:
			failed += 1
	print("CLIPCHECK ", "FAIL" if failed else "OK")
	quit(1 if failed else 0)
