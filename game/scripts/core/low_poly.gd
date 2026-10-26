class_name LowPoly
extends RefCounted
## Baukasten für den Low-Poly-Look: kantige, flach schattierte Meshes mit
## Vertex-Farben und einem gemeinsamen Toon-Material (Zelda-artiges Licht).

static var _material: StandardMaterial3D


static func material() -> StandardMaterial3D:
	if _material == null:
		_material = StandardMaterial3D.new()
		_material.vertex_color_use_as_albedo = true
		_material.vertex_color_is_srgb = true
		_material.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
		_material.specular_mode = BaseMaterial3D.SPECULAR_TOON
		_material.roughness = 1.0
		_material.metallic_specular = 0.2
		_material.rim_enabled = true
		_material.rim = 0.3
		_material.rim_tint = 0.6
	return _material


static func instance(mesh: Mesh) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = material()
	return mi


static func box(size: Vector3, color: Color, offset := Vector3.ZERO) -> ArrayMesh:
	var bm := BoxMesh.new()
	bm.size = size
	return Builder.new().add(bm, Transform3D(Basis(), offset), color).commit()


## Sammelt Dreiecke aus mehreren Grundformen zu einem einzigen Mesh.
## Jede Fläche bekommt eine eigene Normale -> kantiger Low-Poly-Look.
class Builder:
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var jitter := 0.05
	var rng := RandomNumberGenerator.new()

	func add(mesh: PrimitiveMesh, xform: Transform3D, color: Color) -> Builder:
		var arrays := mesh.get_mesh_arrays()
		var src: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var idx := PackedInt32Array()
		if arrays[Mesh.ARRAY_INDEX] != null:
			idx = arrays[Mesh.ARRAY_INDEX]
		if idx.is_empty():
			for i in src.size():
				idx.append(i)
		var mirrored := xform.basis.determinant() < 0.0
		for t in range(0, idx.size() - 2, 3):
			var a: Vector3 = xform * src[idx[t]]
			var b: Vector3 = xform * src[idx[t + 1]]
			var c: Vector3 = xform * src[idx[t + 2]]
			if mirrored:
				add_triangle(a, c, b, color)
			else:
				add_triangle(a, b, c, color)
		return self

	## Godot zeichnet Dreiecke im Uhrzeigersinn als Vorderseite.
	func add_triangle(a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
		var n := (c - a).cross(b - a)
		if n.length_squared() < 1e-12:
			return
		n = n.normalized()
		var shade := 1.0 + rng.randf_range(-jitter, jitter)
		var col := Color(color.r * shade, color.g * shade, color.b * shade, color.a)
		for v in [a, b, c]:
			verts.append(v)
			normals.append(n)
			colors.append(col)

	func commit() -> ArrayMesh:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = verts
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_COLOR] = colors
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		return mesh
