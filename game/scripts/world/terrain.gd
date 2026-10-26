class_name Terrain
extends StaticBody3D
## Prozedurale Low-Poly-Insel mit Bergen, Stränden und flachen Bauplätzen.

const SIZE := 320.0
const RESOLUTION := 128
const WATER_LEVEL := 0.0

## Flache Zonen: [Mittelpunkt, Innenradius, Außenradius, Höhe]
var flat_zones := [
	[Vector2(30, 20), 18.0, 34.0, 4.0],      # Dorf Grünau
	[Vector2(-60, -45), 8.0, 18.0, 7.0],     # Goblin-Lager
]
var noise := FastNoiseLite.new()


func _init(seed_value := 1337) -> void:
	noise.seed = seed_value
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 0.011
	noise.fractal_octaves = 4


func _ready() -> void:
	var mesh := _build_mesh()
	add_child(LowPoly.instance(mesh))
	var shape := CollisionShape3D.new()
	shape.shape = mesh.create_trimesh_shape()
	add_child(shape)


func height_at(x: float, z: float) -> float:
	var d := Vector2(x, z).length() / (SIZE * 0.5)
	var island := clampf(1.0 - pow(d, 2.4), 0.0, 1.0)
	var hills := noise.get_noise_2d(x, z) * 0.5 + 0.5
	var h := lerpf(-8.0, 2.0 + hills * hills * 34.0, island)
	for zone in flat_zones:
		var center: Vector2 = zone[0]
		var flat := 1.0 - smoothstep(float(zone[1]), float(zone[2]), Vector2(x, z).distance_to(center))
		h = lerpf(h, float(zone[3]), flat)
	return h


func is_flat_zone(x: float, z: float, margin := 0.0) -> bool:
	for zone in flat_zones:
		var center: Vector2 = zone[0]
		if Vector2(x, z).distance_to(center) < float(zone[2]) + margin:
			return true
	return false


func _build_mesh() -> ArrayMesh:
	var step := SIZE / RESOLUTION
	var half := SIZE * 0.5
	var heights := PackedFloat32Array()
	heights.resize((RESOLUTION + 1) * (RESOLUTION + 1))
	for iz in RESOLUTION + 1:
		for ix in RESOLUTION + 1:
			heights[iz * (RESOLUTION + 1) + ix] = height_at(ix * step - half, iz * step - half)

	var builder := LowPoly.Builder.new()
	builder.jitter = 0.07
	for iz in RESOLUTION:
		for ix in RESOLUTION:
			var x0 := ix * step - half
			var z0 := iz * step - half
			var p00 := Vector3(x0, heights[iz * (RESOLUTION + 1) + ix], z0)
			var p10 := Vector3(x0 + step, heights[iz * (RESOLUTION + 1) + ix + 1], z0)
			var p01 := Vector3(x0, heights[(iz + 1) * (RESOLUTION + 1) + ix], z0 + step)
			var p11 := Vector3(x0 + step, heights[(iz + 1) * (RESOLUTION + 1) + ix + 1], z0 + step)
			builder.add_triangle(p00, p10, p01, _color_for(p00, p10, p01))
			builder.add_triangle(p10, p11, p01, _color_for(p10, p11, p01))
	return builder.commit()


func _color_for(a: Vector3, b: Vector3, c: Vector3) -> Color:
	var h := (a.y + b.y + c.y) / 3.0
	var up := (c - a).cross(b - a).normalized().y
	if h < WATER_LEVEL - 0.5:
		return Color(0.72, 0.66, 0.46)
	if h < WATER_LEVEL + 0.8:
		return Color(0.93, 0.86, 0.6)          # Strand
	if h > 24.0:
		return Color(0.95, 0.96, 1.0)          # Schnee
	if up < 0.72:
		return Color(0.55, 0.52, 0.5)          # Fels
	if h > 16.0:
		return Color(0.45, 0.55, 0.35)         # Bergwiese
	return Color(0.42, 0.72, 0.3)              # Gras
