shader_type spatial;
render_mode unshaded;

// The light cycle arena's floor (game/pup/lightcycles.gd): a cyan grid on cell edges, brighter every 4 cells,
// fading into the distance. A few lines, picked at random along x and z, glow up and fade out again (above the
// environment's glow threshold, so the bloom gives them their halo): all in this shader, nothing per frame on
// the CPU.
uniform vec3 line_color = vec3(0.1, 0.75, 0.9);
uniform float pulse_chance = 0.06;   // share of the lines that glow in each of their cycles
uniform float pulse_seconds = 4.0;   // a line's cycle (each line has its own phase and length, +-50%)
uniform float pulse_energy = 2.2;    // the brightest a glowing line gets, over the line colour

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// How lit the line numbered id (axis 0: lines of constant x, 1: constant z) is now, 0..1.
float pulse(float id, float axis) {
	float len = pulse_seconds * (0.5 + hash(vec2(id, axis + 7.0)));
	float t = TIME / len + hash(vec2(id, axis + 3.0));
	float cycle = floor(t);
	if (hash(vec2(id * 1.37 + cycle, axis)) > pulse_chance) {
		return 0.0;
	}
	float s = sin(fract(t) * PI);
	return s * s;
}

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 d = abs(fract(wp.xz - 0.5) - 0.5);          // world distance to the nearest line, x and z
	vec2 g = d / fwidth(wp.xz);
	float minor = 1.0 - min(min(g.x, g.y), 1.0);
	vec2 g4 = abs(fract(wp.xz / 4.0 - 0.5) - 0.5) / fwidth(wp.xz / 4.0);
	float major = 1.0 - min(min(g4.x, g4.y), 1.0);
	float fade = clamp(1.0 - length(wp.xz) / 60.0, 0.15, 1.0);
	vec2 id = floor(wp.xz + 0.5);
	vec2 lit = vec2(pulse(id.x, 0.0), pulse(id.y, 1.0));
	vec2 core = 1.0 - min(g * 0.7, 1.0);                // a little wider than the line itself
	vec2 halo = exp(-d * 18.0) * 0.25;
	float glow = dot(lit, core + halo);
	ALBEDO = vec3(0.0, 0.015, 0.03) + line_color * ((minor * 0.35 + major * 0.9) * fade + glow * pulse_energy);
}
