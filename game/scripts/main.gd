extends Node3D
## Baut die Testwelt: Insel, Dorf Grünau mit Händlerin, Goblin-Lager,
## Spieler, Tag/Nacht und Anzeige.

const VILLAGE := Vector3(30, 0, 20)
const CAMP := Vector3(-60, 0, -45)
const MAX_GOBLINS := 6

var terrain: Terrain
var day_night: DayNight
var player: Player
var hud: Hud
var market: Market
var rng := RandomNumberGenerator.new()


func _ready() -> void:
	Controls.setup()
	rng.seed = 2024

	day_night = DayNight.new()
	add_child(day_night)

	terrain = Terrain.new()
	add_child(terrain)
	_add_water()
	_scatter_nature()

	market = Market.village()
	day_night.hour_passed.connect(func(_h: int) -> void: market.tick_hour())
	_build_village()
	_build_camp()

	player = Player.new()
	player.water_level = Terrain.WATER_LEVEL
	add_child(player)
	player.global_position = _ground(VILLAGE + Vector3(0, 0, 8)) + Vector3.UP
	player.spawn_point = player.global_position

	hud = Hud.new()
	hud.player = player
	hud.day_night = day_night
	add_child(hud)
	player.message.connect(hud.show_message)
	hud.show_message("Du erwachst in Grünau. Niemand kennt deinen Namen.")

	for i in MAX_GOBLINS:
		_spawn_goblin()
	var timer := Timer.new()
	timer.wait_time = 25.0
	timer.autostart = true
	timer.timeout.connect(_respawn_goblins)
	add_child(timer)


func _ground(pos: Vector3) -> Vector3:
	return Vector3(pos.x, terrain.height_at(pos.x, pos.z), pos.z)


func _add_water() -> void:
	var plane := PlaneMesh.new()
	plane.size = Vector2(900, 900)
	var water := MeshInstance3D.new()
	water.mesh = plane
	water.position.y = Terrain.WATER_LEVEL
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.2, 0.55, 0.85, 0.75)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON
	mat.specular_mode = BaseMaterial3D.SPECULAR_TOON
	mat.roughness = 0.15
	mat.metallic_specular = 0.8
	water.material_override = mat
	add_child(water)


func _scatter_nature() -> void:
	var half := Terrain.SIZE * 0.5 - 10.0
	var placed := 0
	var attempts := 0
	while placed < 320 and attempts < 4000:
		attempts += 1
		var x := rng.randf_range(-half, half)
		var z := rng.randf_range(-half, half)
		var h := terrain.height_at(x, z)
		if h < 1.2 or h > 22.0 or terrain.is_flat_zone(x, z, 2.0):
			continue
		# Zu steile Hänge auslassen
		var slope := absf(terrain.height_at(x + 1.5, z) - h) + absf(terrain.height_at(x, z + 1.5) - h)
		if slope > 2.2:
			continue
		var body := StaticBody3D.new()
		var mesh: ArrayMesh = Props.pine_mesh() if (h > 9.0 or rng.randf() < 0.4) else Props.oak_mesh()
		var mi := LowPoly.instance(mesh)
		var s := rng.randf_range(0.8, 1.4)
		mi.scale = Vector3(s, s * rng.randf_range(0.9, 1.2), s)
		mi.rotation.y = rng.randf() * TAU
		body.add_child(mi)
		var col := CollisionShape3D.new()
		var trunk := CylinderShape3D.new()
		trunk.radius = 0.35 * s
		trunk.height = 3.0
		col.shape = trunk
		col.position.y = 1.5
		body.add_child(col)
		body.position = Vector3(x, h - 0.2, z)
		add_child(body)
		placed += 1

	for i in 90:
		var x := rng.randf_range(-half, half)
		var z := rng.randf_range(-half, half)
		var h := terrain.height_at(x, z)
		if h < -2.0 or terrain.is_flat_zone(x, z):
			continue
		var rock := StaticBody3D.new()
		var mi := LowPoly.instance(Props.rock_mesh(i % 4))
		var s := rng.randf_range(0.6, 2.2)
		mi.scale = Vector3.ONE * s
		rock.add_child(mi)
		var col := CollisionShape3D.new()
		var sphere := SphereShape3D.new()
		sphere.radius = 0.9 * s
		col.shape = sphere
		col.position.y = 0.3 * s
		rock.add_child(col)
		rock.position = Vector3(x, h - 0.3, z)
		rock.rotation.y = rng.randf() * TAU
		add_child(rock)


func _build_village() -> void:
	var colors := [Color(0.95, 0.9, 0.78), Color(0.9, 0.85, 0.7), Color(0.85, 0.82, 0.75)]
	var spots := [
		Vector3(-12, 0, -8), Vector3(0, 0, -13), Vector3(13, 0, -8),
		Vector3(-14, 0, 8), Vector3(14, 0, 9),
	]
	for i in spots.size():
		var offset: Vector3 = spots[i]
		var house := Props.house(colors[i % colors.size()], Vector3(rng.randf_range(5, 7), 3, rng.randf_range(4.5, 6)))
		house.position = _ground(VILLAGE + offset)
		# Haustür zeigt zum Dorfplatz
		house.rotation.y = atan2(-offset.x, -offset.z)
		add_child(house)

	var well := Props.well()
	well.position = _ground(VILLAGE)
	add_child(well)

	var stall := Props.market_stall()
	stall.position = _ground(VILLAGE + Vector3(5, 0, 2))
	stall.rotation.y = -PI * 0.5
	add_child(stall)

	var merchant := Merchant.new()
	merchant.market = market
	merchant.position = _ground(VILLAGE + Vector3(6.4, 0, 2))
	add_child(merchant)


func _build_camp() -> void:
	var fire := Props.campfire()
	fire.position = _ground(CAMP)
	add_child(fire)
	for i in 3:
		var a := i * TAU / 3.0 + 0.4
		var tent := Props.tent()
		tent.position = _ground(CAMP + Vector3(cos(a) * 6.0, 0, sin(a) * 6.0))
		tent.rotation.y = -a + PI * 0.5
		add_child(tent)


func _spawn_goblin() -> void:
	var goblin := Goblin.new()
	goblin.home = _ground(CAMP)
	goblin.target = player
	add_child(goblin)
	var spot := CAMP + Vector3(rng.randf_range(-7, 7), 0, rng.randf_range(-7, 7))
	goblin.global_position = _ground(spot) + Vector3.UP


func _respawn_goblins() -> void:
	var alive := get_tree().get_nodes_in_group("enemies").size()
	if alive < MAX_GOBLINS:
		_spawn_goblin()
