shader_type spatial;
render_mode cull_disabled, diffuse_toon, specular_disabled;

// Grashalme, die sich im Wind wiegen. Die Farbe kommt pro Halm aus dem Boden
// (Instanzdaten), die Spitzen werden heller – wie in Breath of the Wild.

uniform float wind_strength = 0.22;
uniform float wind_speed = 1.6;
uniform vec3 tip_tint = vec3(1.18, 1.15, 0.9);
uniform vec3 base_tint = vec3(0.65, 0.72, 0.6);

varying float blade_height;
varying vec3 ground_color;

void vertex() {
	blade_height = VERTEX.y;
	// Bodenfarbe kommt als sRGB über die Instanzdaten -> linear umrechnen.
	ground_color = pow(INSTANCE_CUSTOM.rgb, vec3(2.2));
	vec3 world = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float gust = sin(TIME * wind_speed + world.x * 0.25 + world.z * 0.18)
		+ 0.5 * sin(TIME * wind_speed * 2.3 + world.x * 0.7);
	float bend = gust * wind_strength * blade_height * blade_height;
	// Wind weht in Weltrichtung, unabhängig von der Drehung des Halms.
	mat3 model_basis = mat3(MODEL_MATRIX);
	VERTEX += inverse(model_basis) * vec3(bend, 0.0, bend * 0.5);
	// Halme übernehmen das Licht des Bodens, damit die Wiese ruhig wirkt.
	NORMAL = normalize(transpose(model_basis) * vec3(0.0, 1.0, 0.0));
}

void fragment() {
	ALBEDO = ground_color * mix(base_tint, tip_tint, clamp(blade_height, 0.0, 1.0));
	ROUGHNESS = 1.0;
}
