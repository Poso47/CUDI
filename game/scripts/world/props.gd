class_name Props
extends RefCounted
## Low-Poly-Objekte der Welt: Bäume, Felsen, Häuser, Lagerfeuer …

static var _cache := {}


static func _cyl(top: float, bottom: float, height: float, segments := 6) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = top
	m.bottom_radius = bottom
	m.height = height
	m.radial_segments = segments
	m.rings = 0
	return m


static func _sphere(radius: float, segments := 6, rings := 3) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = radius
	m.height = radius * 2.0
	m.radial_segments = segments
	m.rings = rings
	return m


static func _boxm(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


static func _at(pos: Vector3, rot_y := 0.0, scale := Vector3.ONE) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, rot_y).scaled(scale), pos)


static func pine_mesh() -> ArrayMesh:
	if not _cache.has("pine"):
		var b := LowPoly.Builder.new()
		b.add(_cyl(0.18, 0.28, 1.6), _at(Vector3(0, 0.8, 0)), Color(0.45, 0.3, 0.18))
		b.add(_cyl(0.0, 1.5, 2.2, 7), _at(Vector3(0, 2.4, 0)), Color(0.2, 0.5, 0.28))
		b.add(_cyl(0.0, 1.15, 1.9, 7), _at(Vector3(0, 3.5, 0), 0.4), Color(0.24, 0.56, 0.3))
		b.add(_cyl(0.0, 0.75, 1.5, 7), _at(Vector3(0, 4.5, 0), 0.8), Color(0.28, 0.62, 0.32))
		_cache["pine"] = b.commit()
	return _cache["pine"]


static func oak_mesh() -> ArrayMesh:
	if not _cache.has("oak"):
		var b := LowPoly.Builder.new()
		b.add(_cyl(0.22, 0.35, 2.2), _at(Vector3(0, 1.1, 0)), Color(0.42, 0.28, 0.17))
		b.add(_sphere(1.6), _at(Vector3(0, 3.2, 0)), Color(0.35, 0.65, 0.25))
		b.add(_sphere(1.1), _at(Vector3(0.9, 3.7, 0.4)), Color(0.4, 0.7, 0.28))
		b.add(_sphere(1.0), _at(Vector3(-0.8, 3.5, -0.5)), Color(0.32, 0.6, 0.24))
		_cache["oak"] = b.commit()
	return _cache["oak"]


static func rock_mesh(variant: int) -> ArrayMesh:
	var key := "rock%d" % variant
	if not _cache.has(key):
		var rng := RandomNumberGenerator.new()
		rng.seed = variant * 7919
		var b := LowPoly.Builder.new()
		b.jitter = 0.1
		for i in 3:
			var s := Vector3(rng.randf_range(0.8, 1.6), rng.randf_range(0.6, 1.2), rng.randf_range(0.8, 1.6))
			var p := Vector3(rng.randf_range(-0.5, 0.5), s.y * 0.35, rng.randf_range(-0.5, 0.5))
			b.add(_sphere(1.0, 5, 2), _at(p, rng.randf() * TAU, s), Color(0.55, 0.54, 0.52))
		_cache[key] = b.commit()
	return _cache[key]


## Fachwerkhaus. Gibt einen StaticBody mit Kollision zurück.
static func house(color: Color, size := Vector3(6, 3, 5)) -> StaticBody3D:
	var b := LowPoly.Builder.new()
	b.add(_boxm(size), _at(Vector3(0, size.y * 0.5, 0)), color)
	var roof := PrismMesh.new()
	roof.size = Vector3(size.z + 0.8, 2.2, size.x + 0.8)   # nach Drehung: First entlang X
	b.add(roof, Transform3D(Basis(Vector3.UP, PI * 0.5), Vector3(0, size.y + 1.1, 0)), Color(0.62, 0.25, 0.18))
	# Balken und Tür
	for x in [-size.x * 0.5, size.x * 0.5]:
		b.add(_boxm(Vector3(0.25, size.y, 0.25)), _at(Vector3(x, size.y * 0.5, size.z * 0.5 + 0.02)), Color(0.35, 0.22, 0.12))
	b.add(_boxm(Vector3(size.x, 0.25, 0.25)), _at(Vector3(0, size.y - 0.1, size.z * 0.5 + 0.02)), Color(0.35, 0.22, 0.12))
	b.add(_boxm(Vector3(1.1, 2.0, 0.15)), _at(Vector3(0, 1.0, size.z * 0.5 + 0.05)), Color(0.4, 0.26, 0.14))
	b.add(_boxm(Vector3(0.9, 0.8, 0.15)), _at(Vector3(size.x * 0.3, 1.8, size.z * 0.5 + 0.05)), Color(0.95, 0.85, 0.4))
	b.add(_boxm(Vector3(0.6, 1.6, 0.6)), _at(Vector3(size.x * 0.3, size.y + 1.4, -size.z * 0.2)), Color(0.5, 0.48, 0.46))
	return _static_body(b.commit(), BoxShape3D.new(), size, Vector3(0, size.y * 0.5, 0))


static func well() -> StaticBody3D:
	var b := LowPoly.Builder.new()
	b.add(_cyl(1.0, 1.1, 1.0, 8), _at(Vector3(0, 0.5, 0)), Color(0.6, 0.58, 0.55))
	b.add(_cyl(0.85, 0.85, 0.05, 8), _at(Vector3(0, 0.98, 0)), Color(0.2, 0.4, 0.7))
	for x in [-0.9, 0.9]:
		b.add(_boxm(Vector3(0.15, 2.0, 0.15)), _at(Vector3(x, 1.5, 0)), Color(0.4, 0.26, 0.14))
	var roof := PrismMesh.new()
	roof.size = Vector3(2.4, 0.8, 1.6)
	b.add(roof, _at(Vector3(0, 2.8, 0)), Color(0.62, 0.25, 0.18))
	var shape := CylinderShape3D.new()
	shape.radius = 1.1
	shape.height = 1.0
	return _static_body(b.commit(), shape, Vector3.ZERO, Vector3(0, 0.5, 0))


static func market_stall() -> StaticBody3D:
	var b := LowPoly.Builder.new()
	b.add(_boxm(Vector3(3.0, 1.0, 1.2)), _at(Vector3(0, 0.5, 0)), Color(0.5, 0.33, 0.18))
	for x in [-1.4, 1.4]:
		for z in [-0.5, 0.5]:
			b.add(_boxm(Vector3(0.12, 2.6, 0.12)), _at(Vector3(x, 1.3, z)), Color(0.4, 0.26, 0.14))
	b.add(_boxm(Vector3(3.4, 0.12, 1.8)), _at(Vector3(0, 2.6, 0)), Color(0.85, 0.2, 0.2))
	b.add(_sphere(0.3), _at(Vector3(-0.8, 1.2, 0)), Color(0.9, 0.7, 0.2))
	b.add(_sphere(0.25), _at(Vector3(0.6, 1.15, 0.1)), Color(0.8, 0.3, 0.2))
	b.add(_boxm(Vector3(0.5, 0.4, 0.4)), _at(Vector3(0.1, 1.2, -0.2)), Color(0.7, 0.6, 0.4))
	return _static_body(b.commit(), BoxShape3D.new(), Vector3(3.0, 1.0, 1.2), Vector3(0, 0.5, 0))


static func campfire() -> Node3D:
	var root := Node3D.new()
	var b := LowPoly.Builder.new()
	for i in 6:
		var a := i * TAU / 6.0
		b.add(_sphere(0.25, 5, 2), _at(Vector3(cos(a) * 0.8, 0.1, sin(a) * 0.8)), Color(0.5, 0.5, 0.5))
	for i in 3:
		b.add(_cyl(0.08, 0.08, 1.2), Transform3D(Basis(Vector3.UP, i * 1.0) * Basis(Vector3.RIGHT, 1.3), Vector3(0, 0.15, 0)), Color(0.35, 0.22, 0.12))
	root.add_child(LowPoly.instance(b.commit()))

	var flame := MeshInstance3D.new()
	flame.mesh = _cyl(0.0, 0.45, 1.1, 5)
	flame.position.y = 0.6
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.55, 0.1)
	mat.emission_enabled = true
	mat.emission = Color(1.0, 0.45, 0.05)
	mat.emission_energy_multiplier = 3.0
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	flame.material_override = mat
	root.add_child(flame)

	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.6, 0.25)
	light.light_energy = 2.5
	light.omni_range = 10.0
	light.position.y = 1.2
	root.add_child(light)
	return root


static func tent() -> StaticBody3D:
	var b := LowPoly.Builder.new()
	var cloth := PrismMesh.new()
	cloth.size = Vector3(3.0, 2.2, 3.5)
	b.add(cloth, _at(Vector3(0, 1.1, 0)), Color(0.45, 0.38, 0.25))
	b.add(_boxm(Vector3(0.1, 2.6, 0.1)), _at(Vector3(0, 1.3, 1.8)), Color(0.35, 0.22, 0.12))
	return _static_body(b.commit(), BoxShape3D.new(), Vector3(3.0, 2.2, 3.5), Vector3(0, 1.1, 0))


static func _static_body(mesh: ArrayMesh, shape: Shape3D, size: Vector3, shape_offset: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.add_child(LowPoly.instance(mesh))
	if shape is BoxShape3D:
		(shape as BoxShape3D).size = size
	var col := CollisionShape3D.new()
	col.shape = shape
	col.position = shape_offset
	body.add_child(col)
	return body
