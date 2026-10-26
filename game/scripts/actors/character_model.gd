class_name CharacterModel
extends Node3D
## Stilisierte Figur aus runden Formen (großer Kopf, weiche Silhouette) mit
## Ausrüstungsplätzen. Jede Ausrüstung ist ein eigenes Mesh – was du trägst, sieht man.

const ITEMS := {
	"Rostiges Schwert": {"slot": "weapon", "damage": 10.0},
	"Streitaxt": {"slot": "weapon", "damage": 18.0},
	"Keule": {"slot": "weapon", "damage": 8.0},
	"Holzschild": {"slot": "shield", "armor": 2.0},
	"Eisenschild": {"slot": "shield", "armor": 5.0},
	"Eisenhelm": {"slot": "helmet", "armor": 4.0},
	"Lederrüstung": {"slot": "chest", "armor": 6.0},
}

const HIP_Y := 0.85
const TORSO_Y := 1.2
const NECK_Y := 1.5

var skin := Color(0.98, 0.8, 0.66)
var shirt := Color(0.36, 0.52, 0.32)
var pants := Color(0.42, 0.34, 0.26)
var hair := Color(0.45, 0.28, 0.14)
var boots := Color(0.32, 0.22, 0.14)
var ears_pointed := false        # Goblins haben spitze Ohren

var equipment := {}             # Slot -> Gegenstandsname
var _slot_nodes := {}           # Slot -> MeshInstance3D
var _walk_phase := 0.0
var _blocking := false
var _attacking := false

var torso: Node3D
var head: Node3D
var arm_l: Node3D
var arm_r: Node3D
var leg_l: Node3D
var leg_r: Node3D
var hand_r: Node3D


func build() -> void:
	for child in get_children():
		child.queue_free()

	leg_l = _pivot(self, Vector3(-0.13, HIP_Y, 0))
	leg_r = _pivot(self, Vector3(0.13, HIP_Y, 0))
	for leg in [leg_l, leg_r]:
		var b := MeshKit.Builder.new()
		b.add(MeshKit.capsule(0.11, 0.8), MeshKit.at(Vector3(0, -0.38, 0)), pants)
		b.add(MeshKit.capsule(0.12, 0.34), MeshKit.at(Vector3(0, -0.72, -0.04), Vector3(PI * 0.5, 0, 0)), boots)
		leg.add_child(MeshKit.instance(b.commit()))

	torso = _pivot(self, Vector3(0, TORSO_Y, 0))
	var tb := MeshKit.Builder.new()
	tb.add(MeshKit.capsule(0.25, 0.72), MeshKit.at(Vector3.ZERO, Vector3.ZERO, Vector3(1.0, 1.0, 0.75)), shirt)
	tb.add(MeshKit.torus(0.2, 0.27), MeshKit.at(Vector3(0, -0.2, 0), Vector3.ZERO, Vector3(1.0, 1.0, 0.78)), Color(0.35, 0.22, 0.12))   # Gürtel
	tb.add(MeshKit.cylinder(0.05, 0.05, 0.05, 10), MeshKit.at(Vector3(0, -0.2, -0.2), Vector3(PI * 0.5, 0, 0)), Color(0.85, 0.7, 0.3))  # Schnalle
	torso.add_child(MeshKit.instance(tb.commit()))

	head = _pivot(self, Vector3(0, NECK_Y, 0))
	var hb := MeshKit.Builder.new()
	hb.add(MeshKit.cylinder(0.07, 0.08, 0.12, 10), MeshKit.at(Vector3(0, 0.02, 0)), skin)
	hb.add(MeshKit.sphere(0.24, 20, 12), MeshKit.at(Vector3(0, 0.26, 0), Vector3.ZERO, Vector3(1.0, 1.05, 1.0)), skin)
	# Haare: Kappe hinten/oben, leicht größer als der Kopf
	hb.add(MeshKit.sphere(0.255, 20, 12), MeshKit.at(Vector3(0, 0.34, 0.07), Vector3.ZERO, Vector3(1.04, 0.92, 1.0)), hair)
	# Augen, Nase, Ohren
	for x in [-0.085, 0.085]:
		hb.add(MeshKit.sphere(0.045, 10, 6), MeshKit.at(Vector3(x, 0.26, -0.2), Vector3.ZERO, Vector3(0.8, 1.2, 0.5)), Color(1, 1, 1))
		hb.add(MeshKit.sphere(0.027, 8, 6), MeshKit.at(Vector3(x, 0.255, -0.222)), Color(0.12, 0.1, 0.15))
	hb.add(MeshKit.sphere(0.035, 8, 6), MeshKit.at(Vector3(0, 0.2, -0.235)), skin.darkened(0.08))
	for side in [-1.0, 1.0]:
		if ears_pointed:
			hb.add(MeshKit.cylinder(0.0, 0.07, 0.26, 8), MeshKit.at(Vector3(0.26 * side, 0.3, 0.02), Vector3(0, 0, -side * 1.2)), skin)
		else:
			hb.add(MeshKit.sphere(0.06, 8, 6), MeshKit.at(Vector3(0.235 * side, 0.25, 0.02), Vector3.ZERO, Vector3(0.5, 1, 0.8)), skin)
	head.add_child(MeshKit.instance(hb.commit()))

	arm_l = _pivot(self, Vector3(-0.33, NECK_Y - 0.06, 0))
	arm_r = _pivot(self, Vector3(0.33, NECK_Y - 0.06, 0))
	for arm in [arm_l, arm_r]:
		var ab := MeshKit.Builder.new()
		ab.add(MeshKit.sphere(0.1), MeshKit.at(Vector3.ZERO), shirt)   # Schulter
		ab.add(MeshKit.capsule(0.075, 0.62), MeshKit.at(Vector3(0, -0.3, 0)), shirt)
		ab.add(MeshKit.sphere(0.075), MeshKit.at(Vector3(0, -0.64, 0)), skin)
		arm.add_child(MeshKit.instance(ab.commit()))
	hand_r = _pivot(arm_r, Vector3(0, -0.64, 0))

	var current := equipment.duplicate()
	equipment.clear()
	_slot_nodes.clear()
	for slot in current:
		equip(current[slot])


func _pivot(parent: Node3D, pos: Vector3) -> Node3D:
	var node := Node3D.new()
	node.position = pos
	parent.add_child(node)
	return node


# --- Ausrüstung -------------------------------------------------------------

func equip(item: String) -> void:
	if not ITEMS.has(item):
		return
	var slot: String = ITEMS[item]["slot"]
	unequip(slot)
	var mi := MeshKit.instance(_item_mesh(item))
	match slot:
		"weapon":
			hand_r.add_child(mi)
		"shield":
			mi.position = Vector3(-0.1, -0.4, 0)
			arm_l.add_child(mi)
		"helmet":
			head.add_child(mi)
		"chest":
			torso.add_child(mi)
	equipment[slot] = item
	_slot_nodes[slot] = mi


func unequip(slot: String) -> void:
	if _slot_nodes.has(slot):
		_slot_nodes[slot].queue_free()
		_slot_nodes.erase(slot)
	equipment.erase(slot)


func stat_total(stat: String) -> float:
	var total := 0.0
	for slot in equipment:
		total += float(ITEMS[equipment[slot]].get(stat, 0.0))
	return total


func _item_mesh(item: String) -> ArrayMesh:
	var b := MeshKit.Builder.new()
	var steel := Color(0.78, 0.8, 0.85)
	var rust := Color(0.62, 0.48, 0.38)
	var wood := Color(0.5, 0.33, 0.18)
	var leather := Color(0.55, 0.35, 0.2)
	var gold := Color(0.9, 0.72, 0.3)
	var forward := Vector3(PI * 0.5, 0, 0)    # Zylinderachse nach vorn (-Z)
	match item:
		"Rostiges Schwert":
			b.add(MeshKit.cylinder(0.03, 0.03, 0.22, 10), MeshKit.at(Vector3(0, 0, 0.0), forward), leather)
			b.add(MeshKit.sphere(0.045), MeshKit.at(Vector3(0, 0, 0.12)), rust)
			b.add(MeshKit.capsule(0.035, 0.34), MeshKit.at(Vector3(0, 0, -0.12), Vector3(0, 0, PI * 0.5)), rust)
			var blade := rust.lerp(steel, 0.45)
			b.add(MeshKit.box(Vector3(0.075, 0.02, 0.78)), MeshKit.at(Vector3(0, 0, -0.52)), blade, false)
			b.add(MeshKit.box(Vector3(0.053, 0.02, 0.053)), MeshKit.at(Vector3(0, 0, -0.91), Vector3(0, PI * 0.25, 0)), blade, false)
		"Streitaxt":
			b.add(MeshKit.cylinder(0.032, 0.036, 1.1, 10), MeshKit.at(Vector3(0, 0, -0.38), forward), wood)
			# Halbmondförmige Klinge aus einer flachen Scheibe
			b.add(MeshKit.cylinder(0.24, 0.24, 0.04, 20), MeshKit.at(Vector3(0, 0.12, -0.82), Vector3(0, 0, PI * 0.5)), steel)
			b.add(MeshKit.cylinder(0.06, 0.06, 0.1, 10), MeshKit.at(Vector3(0, 0, -0.82), Vector3(0, 0, PI * 0.5)), steel.darkened(0.3))
		"Keule":
			b.add(MeshKit.cylinder(0.035, 0.05, 0.55, 10), MeshKit.at(Vector3(0, 0, -0.22), forward), wood)
			b.add(MeshKit.sphere(0.13), MeshKit.at(Vector3(0, 0, -0.56), Vector3.ZERO, Vector3(1, 1, 1.4)), wood.darkened(0.2))
		"Holzschild":
			b.add(MeshKit.cylinder(0.36, 0.36, 0.06, 24), MeshKit.at(Vector3.ZERO, Vector3(0, 0, PI * 0.5)), wood)
			b.add(MeshKit.torus(0.33, 0.39, 28), MeshKit.at(Vector3.ZERO, Vector3(0, 0, PI * 0.5)), wood.darkened(0.25))
			b.add(MeshKit.sphere(0.08), MeshKit.at(Vector3(-0.04, 0, 0), Vector3.ZERO, Vector3(0.6, 1, 1)), rust)
		"Eisenschild":
			b.add(MeshKit.cylinder(0.42, 0.42, 0.06, 28), MeshKit.at(Vector3.ZERO, Vector3(0, 0, PI * 0.5)), Color(0.7, 0.18, 0.18))
			b.add(MeshKit.torus(0.39, 0.46, 32), MeshKit.at(Vector3.ZERO, Vector3(0, 0, PI * 0.5)), steel)
			b.add(MeshKit.sphere(0.1), MeshKit.at(Vector3(-0.05, 0, 0), Vector3.ZERO, Vector3(0.6, 1, 1)), gold)
		"Eisenhelm":
			b.add(MeshKit.dome(0.27, 20, 8), MeshKit.at(Vector3(0, 0.3, 0.01)), steel)
			b.add(MeshKit.torus(0.25, 0.29, 24), MeshKit.at(Vector3(0, 0.31, 0.01)), steel.darkened(0.2))
			b.add(MeshKit.capsule(0.022, 0.2), MeshKit.at(Vector3(0, 0.24, -0.255)), steel)
			b.add(MeshKit.sphere(0.05), MeshKit.at(Vector3(0, 0.58, 0.01), Vector3.ZERO, Vector3(1, 0.6, 1)), gold)
		"Lederrüstung":
			b.add(MeshKit.capsule(0.27, 0.62), MeshKit.at(Vector3(0, 0.04, 0), Vector3.ZERO, Vector3(1.0, 1.0, 0.8)), leather)
			for side in [-1.0, 1.0]:
				b.add(MeshKit.sphere(0.14), MeshKit.at(Vector3(0.3 * side, 0.27, 0), Vector3.ZERO, Vector3(1, 0.7, 1)), leather.darkened(0.2))
			b.add(MeshKit.torus(0.22, 0.29), MeshKit.at(Vector3(0, -0.18, 0), Vector3.ZERO, Vector3(1.0, 1.0, 0.8)), leather.darkened(0.35))
	return b.commit()


# --- Animation --------------------------------------------------------------

func animate(speed: float, delta: float) -> void:
	var amount := clampf(speed / 5.0, 0.0, 1.4)
	_walk_phase += delta * (4.0 + speed * 1.6)
	var swing := sin(_walk_phase) * 0.7 * amount
	leg_l.rotation.x = lerpf(leg_l.rotation.x, swing, 12.0 * delta)
	leg_r.rotation.x = lerpf(leg_r.rotation.x, -swing, 12.0 * delta)
	# leichtes Wippen und Atmen
	var bob := absf(sin(_walk_phase)) * 0.05 * amount + sin(Time.get_ticks_msec() * 0.002) * 0.006
	torso.position.y = TORSO_Y + bob
	head.position.y = NECK_Y + bob
	torso.rotation.y = sin(_walk_phase) * 0.08 * amount
	if not _blocking:
		arm_l.rotation = arm_l.rotation.lerp(Vector3(-swing * 0.8, 0, 0.08), 12.0 * delta)
	else:
		arm_l.rotation = arm_l.rotation.lerp(Vector3(1.2, 0, 0.5), 18.0 * delta)
	if _slot_nodes.has("shield"):
		# Beim Blocken dreht sich der Schild mit der Fläche nach vorn.
		var shield: Node3D = _slot_nodes["shield"]
		shield.rotation.y = lerpf(shield.rotation.y, -PI * 0.5 if _blocking else 0.0, 18.0 * delta)
	if not _attacking:
		arm_r.rotation = arm_r.rotation.lerp(Vector3(swing * 0.8 + 0.25, 0, -0.08), 12.0 * delta)


func set_blocking(value: bool) -> void:
	_blocking = value


## Hieb von oben nach unten. Gibt die Dauer in Sekunden zurück.
func play_attack() -> float:
	_attacking = true
	var tw := create_tween()
	tw.tween_property(arm_r, "rotation", Vector3(2.7, 0, -0.3), 0.12).set_ease(Tween.EASE_OUT)
	tw.tween_property(arm_r, "rotation", Vector3(0.2, 0, 0.2), 0.16).set_ease(Tween.EASE_IN)
	tw.tween_interval(0.12)
	tw.tween_callback(func() -> void: _attacking = false)
	return 0.4


func play_death() -> void:
	var tw := create_tween()
	tw.tween_property(self, "rotation:x", -PI * 0.5, 0.5).set_trans(Tween.TRANS_BOUNCE).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(self, "position:y", 0.2, 0.5)
