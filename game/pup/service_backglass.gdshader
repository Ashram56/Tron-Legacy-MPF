shader_type canvas_item;
// The service menu's backglass background (game/pup/service_backglass.gd): the still of the PuP Pack's backglass
// (scripts/pup/gen_pup.py) darkened inside its two neon frames, so text reads over it and both outlines stay lit
// (the main frame, the lower frame, and where the lower frame cuts the main one); the logo box and the two
// figures at the sides stay as they are. Without a still: black with the two frames drawn in neon.
// Positions in pixels of the 1920x1080 still, measured on it (lines: main frame top 78-87, bottom 898-907,
// sides 226-235 and 1696-1705; lower frame top 846-855, sides 542-551 and 1358-1367).

uniform bool has_still = true;
uniform vec4 shade : source_color = vec4(0.008, 0.031, 0.055, 1.0);
uniform float main_dark = 0.84;
uniform float lower_dark = 0.88;
uniform vec4 neon : source_color = vec4(0.25, 0.78, 1.0, 1.0);

const vec2 SIZE = vec2(1920.0, 1080.0);

float box(vec2 p, vec4 r, float radius) {
	vec2 c = (r.xy + r.zw) * 0.5;
	vec2 h = (r.zw - r.xy) * 0.5 - vec2(radius);
	vec2 q = abs(p - c) - h;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - radius;
}

float inside(vec2 p, vec4 r, float radius, float feather) {
	return 1.0 - smoothstep(-feather, feather, box(p, r, radius));
}

float line_glow(float d) {
	return exp(-abs(d) * 0.35) + 0.5 * exp(-abs(d) * 0.06);
}

void fragment() {
	vec2 p = UV * SIZE;
	float main_in = inside(p, vec4(254.0, 106.0, 1677.0, 879.0), 14.0, 4.0)
		* (1.0 - inside(p, vec4(522.0, 826.0, 1387.0, 1200.0), 0.0, 4.0));
	float lower_in = inside(p, vec4(570.0, 874.0, 1339.0, 1200.0), 10.0, 4.0);
	float logo = inside(p, vec4(712.0, -20.0, 1198.0, 196.0), 0.0, 4.0);
	float figures = step(200.0, p.y) * max(1.0 - smoothstep(291.0, 319.0, p.x - (p.y - 200.0) * 0.014),
		smoothstep(1606.0, 1634.0, p.x + (p.y - 200.0) * 0.014));
	float dark = max(main_in * main_dark, lower_in * lower_dark) * (1.0 - logo) * (1.0 - figures);
	vec4 base = has_still ? texture(TEXTURE, UV) : vec4(0.0, 0.0, 0.0, 1.0);
	if (!has_still) {
		// the two frames' neon lines: main (230, 82)-(1700, 902), lower (546, 850)-(1362, bottom)
		float in_lower = box(p, vec4(546.0, 850.0, 1363.0, 1200.0), 14.0);
		float d_main = in_lower < -4.0 ? 1e4 : abs(box(p, vec4(230.0, 82.0, 1701.0, 903.0), 18.0));
		float d_lower = abs(in_lower);
		float g = max(line_glow(d_main), line_glow(d_lower));
		base.rgb += neon.rgb * clamp(g, 0.0, 1.2);
	}
	COLOR = vec4(mix(base.rgb, shade.rgb, dark), 1.0);
}
