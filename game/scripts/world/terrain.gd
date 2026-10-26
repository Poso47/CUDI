class_name Terrain
extends StaticBody3D
## Prozedurale Insel mit sanften Hügeln, Stränden und flachen Bauplätzen.
## Weiche Normalen und fließende Farbübergänge statt harter Kanten.

const SIZE := 320.0
const RESOLUTION := 192
const WATER_LEVEL := 0.0

## Flache Zonen: [Mittelpunkt, Innenradius, Außenradius, Höhe]
var flat_zones := [
	[Vector2(30, 20), 18.0, 34.0, 4.0],      # Dorf Grünau
	[Vector2(-60, -45), 8.0, 18.0, 7.0],     # Goblin-Lager
]
var noise := FastNoiseLite.new()
var detail := FastNoiseLite.new()
var _heights := PackedFloat32Array()
var _normals := PackedVector3Array()


func _init(seed_value := 1337) -> void:
	noise.seed = seed_value
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	noise.frequency = 0.009
	noise.fractal_octaves = 3
	detail.seed = seed_value + 1
	detail.frequency = 0.05


func _ready() -> void:
	var mesh := _build_mesh()
	add_child(MeshKit.instance(mesh))
	var shape := CollisionShape3D.new()
	shape.shape = mesh.create_trimesh_shape()
	add_child(shape)


func height_at(x: float, z: float) -> float:
	var d := Vector2(x, z).length() / (SIZE * 0.5)
	var island := clampf(1.0 - pow(d, 2.4), 0.0, 1.0)
	var hills := noise.get_noise_2d(x, z) * 0.5 + 0.5
	var h := lerpf(-8.0, 2.0 + hills * hills * 34.0, smoothstep(0.0, 1.0, island))
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


## Höhe der tatsächlichen Mesh-Oberfläche (bilinear aus dem Raster).
func surface_height(x: float, z: float) -> float:
	var step := SIZE / RESOLUTION
	var fx := clampf((x + SIZE * 0.5) / step, 0.0, RESOLUTION - 0.001)
	var fz := clampf((z + SIZE * 0.5) / step, 0.0, RESOLUTION - 0.001)
	var ix := int(fx)
	var iz := int(fz)
	var tx := fx - ix
	var tz := fz - iz
	var h00 := _heights[_i(ix, iz)]
	var h10 := _heights[_i(ix + 1, iz)]
	var h01 := _heights[_i(ix, iz + 1)]
	var h11 := _heights[_i(ix + 1, iz + 1)]
	return lerpf(lerpf(h00, h10, tx), lerpf(h01, h11, tx), tz)


## Wie flach ist der Boden? 1 = eben, 0 = senkrecht.
func flatness(x: float, z: float) -> float:
	var step := SIZE / RESOLUTION
	var ix := clampi(roundi((x + SIZE * 0.5) / step), 0, RESOLUTION)
	var iz := clampi(roundi((z + SIZE * 0.5) / step), 0, RESOLUTION)
	return _normals[_i(ix, iz)].y


## Bodenfarbe an einer Stelle – auch für Gras, damit es zum Boden passt.
func ground_color(h: float, up: float, x: float, z: float) -> Color:
	var variation := detail.get_noise_2d(x, z) * 0.5 + 0.5
	var grass := Color(0.36, 0.66, 0.26).lerp(Color(0.52, 0.76, 0.3), variation)
	var meadow := Color(0.48, 0.6, 0.32)
	var sand := Color(0.93, 0.85, 0.62)
	var wet_sand := Color(0.7, 0.64, 0.46)
	var rock := Color(0.52, 0.5, 0.5).lerp(Color(0.62, 0.58, 0.54), variation)
	var snow := Color(0.95, 0.97, 1.0)

	var c := wet_sand.lerp(sand, smoothstep(-1.5, 0.2, h))
	c = c.lerp(grass, smoothstep(0.6, 1.8, h))
	c = c.lerp(meadow, smoothstep(13.0, 18.0, h))
	c = c.lerp(rock, smoothstep(0.86, 0.7, up) * smoothstep(0.0, 1.0, h))
	c = c.lerp(snow, smoothstep(22.0, 26.0, h) * smoothstep(0.55, 0.75, up))
	return c


func _i(ix: int, iz: int) -> int:
	return iz * (RESOLUTION + 1) + ix


func _build_mesh() -> ArrayMesh:
	var step := SIZE / RESOLUTION
	var half := SIZE * 0.5
	var count := (RESOLUTION + 1) * (RESOLUTION + 1)
	_heights.resize(count)
	_normals.resize(count)
	for iz in RESOLUTION + 1:
		for ix in RESOLUTION + 1:
			_heights[_i(ix, iz)] = height_at(ix * step - half, iz * step - half)

	var verts := PackedVector3Array()
	var colors := PackedColorArray()
	verts.resize(count)
	colors.resize(count)
	for iz in RESOLUTION + 1:
		for ix in RESOLUTION + 1:
			var h := _heights[_i(ix, iz)]
			var h_l := _heights[_i(maxi(ix - 1, 0), iz)]
			var h_r := _heights[_i(mini(ix + 1, RESOLUTION), iz)]
			var h_d := _heights[_i(ix, maxi(iz - 1, 0))]
			var h_u := _heights[_i(ix, mini(iz + 1, RESOLUTION))]
			var n := Vector3(h_l - h_r, 2.0 * step, h_d - h_u).normalized()
			var x := ix * step - half
			var z := iz * step - half
			_normals[_i(ix, iz)] = n
			verts[_i(ix, iz)] = Vector3(x, h, z)
			colors[_i(ix, iz)] = ground_color(h, n.y, x, z)

	var indices := PackedInt32Array()
	for iz in RESOLUTION:
		for ix in RESOLUTION:
			# Im Uhrzeigersinn = Vorderseite oben
			for corner in [_i(ix, iz), _i(ix + 1, iz), _i(ix, iz + 1),
					_i(ix + 1, iz), _i(ix + 1, iz + 1), _i(ix, iz + 1)]:
				indices.append(corner)

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = _normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh
