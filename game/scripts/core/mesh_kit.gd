class_name MeshKit
extends RefCounted
## Baukasten für den Zelda-artigen Look: runde, weich schattierte Formen mit
## Vertex-Farben und einem gemeinsamen Toon-Material (Cel-Shading).

static var _material: StandardMaterial3D


static func material() -> StandardMaterial3D:
	if _material == null:
		_material = StandardMaterial3D.new()
		_material.vertex_color_use_as_albedo = true
		_material.vertex_color_is_srgb = true
		_material.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
		_material.specular_mode = BaseMaterial3D.SPECULAR_TOON
		_material.roughness = 0.85
		_material.metallic_specular = 0.25
		_material.rim_enabled = true
		_material.rim = 0.2
		_material.rim_tint = 0.7
	return _material


static func instance(mesh: Mesh) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = material()
	return mi


# --- Grundformen mit genug Segmenten für runde Silhouetten -------------------

static func sphere(radius: float, segments := 16, rings := 8) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = radius
	m.height = radius * 2.0
	m.radial_segments = segments
	m.rings = rings
	return m


static func dome(radius: float, segments := 16, rings := 6) -> SphereMesh:
	var m := sphere(radius, segments, rings)
	m.height = radius
	m.is_hemisphere = true
	return m


static func capsule(radius: float, height: float, segments := 16) -> CapsuleMesh:
	var m := CapsuleMesh.new()
	m.radius = radius
	m.height = maxf(height, radius * 2.0)
	m.radial_segments = segments
	m.rings = 6
	return m


static func cylinder(top: float, bottom: float, height: float, segments := 14) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = top
	m.bottom_radius = bottom
	m.height = height
	m.radial_segments = segments
	m.rings = 1
	return m


static func torus(inner: float, outer: float, segments := 20) -> TorusMesh:
	var m := TorusMesh.new()
	m.inner_radius = inner
	m.outer_radius = outer
	m.rings = segments
	m.ring_segments = 8
	return m


static func box(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


static func at(pos: Vector3, rot := Vector3.ZERO, scale := Vector3.ONE) -> Transform3D:
	return Transform3D(Basis.from_euler(rot) * Basis.from_scale(scale), pos)


## Sammelt mehrere Grundformen zu einem einzigen Mesh.
## smooth = true übernimmt die runden Normalen der Grundform (weiches Licht),
## smooth = false gibt jeder Fläche eine eigene Normale (für Kanten an Gebäuden).
class Builder:
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()

	func add(mesh: PrimitiveMesh, xform: Transform3D, color: Color, smooth := true) -> Builder:
		var arrays := mesh.get_mesh_arrays()
		var src: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var src_n: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var idx := PackedInt32Array()
		if arrays[Mesh.ARRAY_INDEX] != null:
			idx = arrays[Mesh.ARRAY_INDEX]
		if idx.is_empty():
			for i in src.size():
				idx.append(i)
		var normal_basis := xform.basis.inverse().transposed()
		var mirrored := xform.basis.determinant() < 0.0
		for t in range(0, idx.size() - 2, 3):
			var order := [idx[t], idx[t + 2], idx[t + 1]] if mirrored else [idx[t], idx[t + 1], idx[t + 2]]
			var p: Array[Vector3] = []
			for i in order:
				p.append(xform * src[i])
			var face := (p[2] - p[0]).cross(p[1] - p[0])
			if face.length_squared() < 1e-14:
				continue
			for k in 3:
				var n := face.normalized()
				if smooth:
					n = (normal_basis * src_n[order[k]]).normalized()
				verts.append(p[k])
				normals.append(n)
				colors.append(color)
		return self

	## Godot zeichnet Dreiecke im Uhrzeigersinn als Vorderseite.
	func add_triangle(a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
		var n := (c - a).cross(b - a).normalized()
		for v in [a, b, c]:
			verts.append(v)
			normals.append(n)
			colors.append(color)

	func commit() -> ArrayMesh:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = verts
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_COLOR] = colors
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		return mesh
