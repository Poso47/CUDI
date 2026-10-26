class_name Props
extends RefCounted
## Objekte der Welt im weichen, stilisierten Look: Bäume mit runden Kronen,
## glatte Felsen, Häuser mit geschwungenen Details, Lagerfeuer …

static var _cache := {}


static func _at(pos: Vector3, rot := Vector3.ZERO, scale := Vector3.ONE) -> Transform3D:
	return MeshKit.at(pos, rot, scale)


static func pine_mesh() -> ArrayMesh:
	if not _cache.has("pine"):
		var b := MeshKit.Builder.new()
		var bark := Color(0.45, 0.3, 0.2)
		b.add(MeshKit.cylinder(0.16, 0.3, 2.0, 10), _at(Vector3(0, 1.0, 0)), bark)
		var greens := [Color(0.18, 0.45, 0.3), Color(0.22, 0.52, 0.32), Color(0.27, 0.58, 0.34)]
		for i in 3:
			var radius := 1.6 - i * 0.42
			b.add(MeshKit.cylinder(0.05, radius, 1.9, 14), _at(Vector3(0, 2.3 + i * 1.05, 0)), greens[i])
			# runde Unterkante jeder Etage
			b.add(MeshKit.sphere(radius * 0.95, 14, 4), _at(Vector3(0, 1.4 + i * 1.05, 0), Vector3.ZERO, Vector3(1, 0.22, 1)), greens[i].darkened(0.1))
		_cache["pine"] = b.commit()
	return _cache["pine"]


static func oak_mesh() -> ArrayMesh:
	if not _cache.has("oak"):
		var b := MeshKit.Builder.new()
		var bark := Color(0.42, 0.28, 0.18)
		b.add(MeshKit.cylinder(0.22, 0.38, 2.4, 10), _at(Vector3(0, 1.2, 0)), bark)
		b.add(MeshKit.cylinder(0.08, 0.14, 1.2, 8), _at(Vector3(0.45, 2.4, 0), Vector3(0, 0, -0.7)), bark)
		b.add(MeshKit.cylinder(0.08, 0.14, 1.1, 8), _at(Vector3(-0.4, 2.3, 0.2), Vector3(0.3, 0, 0.7)), bark)
		var leaf := Color(0.36, 0.66, 0.28)
		b.add(MeshKit.sphere(1.7), _at(Vector3(0, 3.6, 0), Vector3.ZERO, Vector3(1, 0.85, 1)), leaf)
		b.add(MeshKit.sphere(1.2), _at(Vector3(1.1, 3.4, 0.5)), leaf.lightened(0.08))
		b.add(MeshKit.sphere(1.15), _at(Vector3(-1.0, 3.3, -0.4)), leaf.darkened(0.06))
		b.add(MeshKit.sphere(1.0), _at(Vector3(0.2, 4.4, -0.6)), leaf.lightened(0.15))
		_cache["oak"] = b.commit()
	return _cache["oak"]


static func bush_mesh() -> ArrayMesh:
	if not _cache.has("bush"):
		var b := MeshKit.Builder.new()
		var leaf := Color(0.3, 0.58, 0.26)
		b.add(MeshKit.sphere(0.7), _at(Vector3(0, 0.45, 0), Vector3.ZERO, Vector3(1, 0.8, 1)), leaf)
		b.add(MeshKit.sphere(0.5), _at(Vector3(0.55, 0.35, 0.2)), leaf.lightened(0.1))
		b.add(MeshKit.sphere(0.45), _at(Vector3(-0.5, 0.3, -0.2)), leaf.darkened(0.05))
		for p in [Vector3(0.3, 0.8, 0.4), Vector3(-0.2, 0.75, 0.5), Vector3(0.5, 0.6, -0.3)]:
			b.add(MeshKit.sphere(0.07, 8, 4), _at(p), Color(0.9, 0.25, 0.3))   # Beeren
		_cache["bush"] = b.commit()
	return _cache["bush"]


static func rock_mesh(variant: int) -> ArrayMesh:
	var key := "rock%d" % variant
	if not _cache.has(key):
		var rng := RandomNumberGenerator.new()
		rng.seed = variant * 7919
		var b := MeshKit.Builder.new()
		var stone := Color(0.56, 0.55, 0.53).lerp(Color(0.62, 0.6, 0.55), rng.randf())
		for i in 3:
			var s := Vector3(rng.randf_range(0.9, 1.5), rng.randf_range(0.55, 1.0), rng.randf_range(0.9, 1.5))
			var p := Vector3(rng.randf_range(-0.5, 0.5), s.y * 0.3, rng.randf_range(-0.5, 0.5))
			b.add(MeshKit.sphere(1.0, 12, 6), _at(p, Vector3(0, rng.randf() * TAU, 0), s), stone)
		# Moos obendrauf
		b.add(MeshKit.sphere(0.8, 12, 4), _at(Vector3(0, 0.85, 0), Vector3.ZERO, Vector3(1.1, 0.25, 1.0)), Color(0.4, 0.6, 0.3))
		_cache[key] = b.commit()
	return _cache[key]


## Fachwerkhaus mit Strohdach. Gibt einen StaticBody mit Kollision zurück.
static func house(color: Color, size := Vector3(6, 3, 5)) -> StaticBody3D:
	var b := MeshKit.Builder.new()
	var beam := Color(0.38, 0.24, 0.14)
	b.add(MeshKit.box(size), _at(Vector3(0, size.y * 0.5, 0)), color, false)
	# Steinsockel
	b.add(MeshKit.box(Vector3(size.x + 0.2, 0.5, size.z + 0.2)), _at(Vector3(0, 0.25, 0)), Color(0.55, 0.53, 0.5), false)
	# Abgerundetes Strohdach: gestreckter halber Zylinder
	# (Zylinderachse liegt nach der Drehung entlang X; lokales X = Höhe, Z = Tiefe)
	var roof := MeshKit.cylinder(1.0, 1.0, size.x + 1.0, 18)
	b.add(roof, _at(Vector3(0, size.y + 0.3, 0), Vector3(0, 0, PI * 0.5), Vector3(1.7, 1.0, (size.z + 1.2) * 0.5)), Color(0.82, 0.66, 0.36))
	# Fachwerkbalken
	for x in [-size.x * 0.5, size.x * 0.5]:
		b.add(MeshKit.box(Vector3(0.22, size.y, 0.22)), _at(Vector3(x, size.y * 0.5, size.z * 0.5 + 0.02)), beam, false)
	b.add(MeshKit.box(Vector3(size.x, 0.22, 0.22)), _at(Vector3(0, size.y - 0.1, size.z * 0.5 + 0.02)), beam, false)
	# Runde Tür und Fenster mit Laden
	b.add(MeshKit.box(Vector3(1.1, 1.6, 0.15)), _at(Vector3(0, 0.8, size.z * 0.5 + 0.05)), Color(0.45, 0.28, 0.15), false)
	b.add(MeshKit.cylinder(0.55, 0.55, 0.15, 16), _at(Vector3(0, 1.6, size.z * 0.5 + 0.05), Vector3(PI * 0.5, 0, 0)), Color(0.45, 0.28, 0.15))
	b.add(MeshKit.cylinder(0.4, 0.4, 0.12, 16), _at(Vector3(size.x * 0.3, 1.9, size.z * 0.5 + 0.06), Vector3(PI * 0.5, 0, 0)), Color(1.0, 0.86, 0.45))
	b.add(MeshKit.torus(0.38, 0.48), _at(Vector3(size.x * 0.3, 1.9, size.z * 0.5 + 0.08), Vector3(PI * 0.5, 0, 0)), beam)
	# Schornstein
	b.add(MeshKit.cylinder(0.32, 0.38, 1.8, 12), _at(Vector3(size.x * 0.3, size.y + 1.0, -size.z * 0.15)), Color(0.55, 0.5, 0.48))
	return _static_body(b.commit(), BoxShape3D.new(), size, Vector3(0, size.y * 0.5, 0))


static func well() -> StaticBody3D:
	var b := MeshKit.Builder.new()
	b.add(MeshKit.cylinder(1.0, 1.1, 1.0, 20), _at(Vector3(0, 0.5, 0)), Color(0.6, 0.58, 0.55))
	b.add(MeshKit.torus(0.85, 1.12, 24), _at(Vector3(0, 1.0, 0)), Color(0.66, 0.63, 0.6))
	b.add(MeshKit.cylinder(0.85, 0.85, 0.05, 20), _at(Vector3(0, 0.92, 0)), Color(0.25, 0.5, 0.8))
	for x in [-0.9, 0.9]:
		b.add(MeshKit.cylinder(0.08, 0.1, 2.0, 8), _at(Vector3(x, 1.5, 0)), Color(0.4, 0.26, 0.14))
	b.add(MeshKit.cylinder(0.06, 0.06, 1.9, 8), _at(Vector3(0, 2.2, 0), Vector3(0, 0, PI * 0.5)), Color(0.4, 0.26, 0.14))
	b.add(MeshKit.cylinder(0.12, 0.15, 0.3, 10), _at(Vector3(0, 1.7, 0)), Color(0.5, 0.35, 0.2))   # Eimer
	b.add(MeshKit.cylinder(1.0, 1.0, 2.4, 18), _at(Vector3(0, 2.6, 0), Vector3(0, 0, PI * 0.5), Vector3(0.7, 1, 0.5)), Color(0.75, 0.32, 0.22))
	var shape := CylinderShape3D.new()
	shape.radius = 1.1
	shape.height = 1.0
	return _static_body(b.commit(), shape, Vector3.ZERO, Vector3(0, 0.5, 0))


static func market_stall() -> StaticBody3D:
	var b := MeshKit.Builder.new()
	var wood := Color(0.5, 0.33, 0.18)
	b.add(MeshKit.box(Vector3(3.0, 1.0, 1.2)), _at(Vector3(0, 0.5, 0)), wood, false)
	for x in [-1.4, 1.4]:
		for z in [-0.5, 0.5]:
			b.add(MeshKit.cylinder(0.06, 0.07, 2.6, 8), _at(Vector3(x, 1.3, z)), wood.darkened(0.2))
	# Gestreiftes, gewölbtes Dach
	for i in 5:
		var col := Color(0.85, 0.22, 0.2) if i % 2 == 0 else Color(0.96, 0.92, 0.85)
		b.add(MeshKit.cylinder(0.4, 0.4, 1.9, 14), _at(Vector3(-1.36 + i * 0.68, 2.65, 0), Vector3(PI * 0.5, 0, 0), Vector3(0.85, 1, 0.45)), col)
	b.add(MeshKit.sphere(0.25), _at(Vector3(-0.9, 1.22, 0)), Color(0.95, 0.7, 0.2))
	b.add(MeshKit.sphere(0.22), _at(Vector3(-0.5, 1.2, 0.1)), Color(0.85, 0.25, 0.2))
	b.add(MeshKit.sphere(0.2), _at(Vector3(-0.7, 1.2, -0.25)), Color(0.4, 0.7, 0.25))
	b.add(MeshKit.cylinder(0.25, 0.3, 0.45, 12), _at(Vector3(0.6, 1.22, 0)), Color(0.65, 0.48, 0.3))
	return _static_body(b.commit(), BoxShape3D.new(), Vector3(3.0, 1.0, 1.2), Vector3(0, 0.5, 0))


static func campfire() -> Node3D:
	var root := Node3D.new()
	var b := MeshKit.Builder.new()
	for i in 8:
		var a := i * TAU / 8.0
		b.add(MeshKit.sphere(0.22, 10, 5), _at(Vector3(cos(a) * 0.8, 0.1, sin(a) * 0.8), Vector3.ZERO, Vector3(1, 0.7, 1)), Color(0.5, 0.5, 0.5))
	for i in 3:
		b.add(MeshKit.cylinder(0.08, 0.08, 1.2, 8), _at(Vector3(0, 0.15, 0), Vector3(1.3, i * 1.0, 0)), Color(0.35, 0.22, 0.12))
	root.add_child(MeshKit.instance(b.commit()))

	var flame := MeshInstance3D.new()
	flame.mesh = MeshKit.sphere(0.4, 12, 6)
	flame.scale = Vector3(1, 1.8, 1)
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
	var b := MeshKit.Builder.new()
	b.add(MeshKit.cylinder(0.05, 1.8, 2.4, 14), _at(Vector3(0, 1.2, 0)), Color(0.5, 0.42, 0.28))
	b.add(MeshKit.cylinder(0.04, 0.04, 2.8, 6), _at(Vector3(0, 1.4, 0)), Color(0.35, 0.22, 0.12))
	var shape := CylinderShape3D.new()
	shape.radius = 1.6
	shape.height = 2.4
	return _static_body(b.commit(), shape, Vector3.ZERO, Vector3(0, 1.2, 0))


static func _static_body(mesh: ArrayMesh, shape: Shape3D, size: Vector3, shape_offset: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.add_child(MeshKit.instance(mesh))
	if shape is BoxShape3D:
		(shape as BoxShape3D).size = size
	var col := CollisionShape3D.new()
	col.shape = shape
	col.position = shape_offset
	body.add_child(col)
	return body
