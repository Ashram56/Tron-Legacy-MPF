shader_type canvas_item;
// The glow of a plain DMD label in the HD mode (tools/dmd_mode.gd LabelGlow): the label's text, drawn white
// on a transparent picture, blurred (Gaussian, `sigma` texture pixels) and added to what is under it in the
// glow colour.
render_mode blend_add;

uniform vec4 glow_color : source_color = vec4(0.13, 0.72, 1.0, 1.0);
uniform float strength = 0.8;
uniform float sigma = 2.0;

void fragment() {
	float acc = 0.0;
	float total = 0.0;
	for (int y = -4; y <= 4; y++) {
		for (int x = -4; x <= 4; x++) {
			vec2 o = vec2(float(x), float(y)) * 0.75 * sigma;
			float w = exp(-0.5 * dot(o, o) / (sigma * sigma));
			acc += texture(TEXTURE, UV + o * TEXTURE_PIXEL_SIZE).a * w;
			total += w;
		}
	}
	COLOR = vec4(glow_color.rgb, clamp(acc / total * strength * 1.6, 0.0, 1.0));
}
