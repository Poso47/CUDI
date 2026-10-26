class_name Grass
extends Node3D
## Wiesen aus vielen tausend Halmen, in Stücke (Chunks) aufgeteilt.
## Nur Stücke in der Nähe der Kamera werden gezeichnet.

const CHUNK_SIZE := 32.0
const BLADES_PER_CHUNK := 2600
const VIEW_DISTANCE := 75.0

var terrain: Terrain


func _ready() -> void:
	var blade := _blade_mesh()
	var material := ShaderMaterial.new()
	material.shader = load("res://shaders/grass.gdshader")
	var rng := RandomNumberGenerator.new()
	rng.seed = 99
	var half := Terrain.SIZE * 0.5
	var chunks := int(Terrain.SIZE / CHUNK_SIZE)
	for cz in chunks:
		for cx in chunks:
			var origin := Vector3(-half + cx * CHUNK_SIZE, 0.0, -half + cz * CHUNK_SIZE)
			var transforms: Array[Transform3D] = []
			var colors: Array[Color] = []
			for i in BLADES_PER_CHUNK:
				var x := origin.x + rng.randf() * CHUNK_SIZE
				var z := origin.z + rng.randf() * CHUNK_SIZE
				var h := terrain.surface_height(x, z)
				var up := terrain.flatness(x, z)
				if h < 1.6 or h > 17.0 or up < 0.86:
					continue
				var size := Vector3(rng.randf_range(0.8, 1.3), rng.randf_range(0.35, 0.8), 1.0)
				var rot := Basis(Vector3.UP, rng.randf() * TAU) * Basis(Vector3.RIGHT, rng.randf_range(-0.2, 0.2))
				transforms.append(Transform3D(rot * Basis.from_scale(size), Vector3(x, h - 0.05, z)))
				colors.append(terrain.ground_color(h, up, x, z))
			if transforms.is_empty():
				continue
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.use_custom_data = true
			mm.mesh = blade
			mm.instance_count = transforms.size()
			for i in transforms.size():
				mm.set_instance_transform(i, transforms[i])
				mm.set_instance_custom_data(i, colors[i])
			var mmi := MultiMeshInstance3D.new()
			mmi.multimesh = mm
			mmi.material_override = material
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mmi.visibility_range_end = VIEW_DISTANCE
			mmi.visibility_range_end_margin = 10.0
			mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
			add_child(mmi)


## Ein Büschel aus drei gekreuzten, spitz zulaufenden Halmen (Höhe 0–1).
func _blade_mesh() -> ArrayMesh:
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	for k in 3:
		var rot := Basis(Vector3.UP, k * TAU / 3.0)
		var offset := rot * Vector3(0.05, 0, 0)
		var pts := [
			Vector3(-0.05, 0.0, 0.0), Vector3(0.05, 0.0, 0.0),
			Vector3(-0.035, 0.5, 0.0), Vector3(0.035, 0.5, 0.0),
			Vector3(0.02, 1.0, 0.0),
		]
		var w: Array[Vector3] = []
		for p in pts:
			w.append(rot * p + offset)
		for tri in [[0, 2, 1], [1, 2, 3], [2, 4, 3]]:
			for j in tri:
				verts.append(w[j])
				normals.append(Vector3.UP)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh
