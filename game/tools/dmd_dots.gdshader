// Dot-matrix look over the HD DMD (game/tools/dmd_mode.gd, --dmd-dots=N): the picture under each dot of
// a `grid` of round dots, sampled at the dot's centre, with unlit dots faintly visible.
shader_type canvas_item;

uniform vec2 grid = vec2(256.0, 64.0);
uniform float dot_size = 0.84;          // dot diameter / dot pitch
uniform vec3 unlit = vec3(0.07, 0.03, 0.0);
uniform sampler2D screen : hint_screen_texture, filter_linear;

void fragment() {
	vec2 centre = (floor(UV * grid) + 0.5) / grid;
	vec2 per_uv = vec2(dFdx(SCREEN_UV.x) / dFdx(UV.x), dFdy(SCREEN_UV.y) / dFdy(UV.y));
	vec3 lit = texture(screen, SCREEN_UV + (centre - UV) * per_uv).rgb;
	float r = length(fract(UV * grid) - 0.5) * 2.0;
	float aa = max(fwidth(r), 0.001);
	float dot_mask = 1.0 - smoothstep(dot_size - aa, dot_size + aa, r);
	COLOR = vec4(max(lit, unlit) * dot_mask, 1.0);
}
