class_name CharacterModel
extends Node3D
## Kantige Figur im RuneScape-Stil mit Ausrüstungsplätzen.
## Jede Ausrüstung ist ein eigenes Mesh am Körper – was du trägst, sieht man.

const ITEMS := {
	"Rostiges Schwert": {"slot": "weapon", "damage": 10.0},
	"Streitaxt": {"slot": "weapon", "damage": 18.0},
	"Keule": {"slot": "weapon", "damage": 8.0},
	"Holzschild": {"slot": "shield", "armor": 2.0},
	"Eisenschild": {"slot": "shield", "armor": 5.0},
	"Eisenhelm": {"slot": "helmet", "armor": 4.0},
	"Lederrüstung": {"slot": "chest", "armor": 6.0},
}

var skin := Color(0.96, 0.78, 0.62)
var shirt := Color(0.55, 0.45, 0.3)
var pants := Color(0.35, 0.3, 0.25)
var hair := Color(0.35, 0.22, 0.1)

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
	leg_l = _limb(Vector3(-0.17, 0.9, 0), Vector3(0.24, 0.9, 0.26), pants)
	leg_r = _limb(Vector3(0.17, 0.9, 0), Vector3(0.24, 0.9, 0.26), pants)
	for leg in [leg_l, leg_r]:
		leg.add_child(LowPoly.instance(LowPoly.box(Vector3(0.26, 0.18, 0.36), Color(0.25, 0.17, 0.1), Vector3(0, -0.84, -0.05))))

	torso = Node3D.new()
	torso.position = Vector3(0, 1.25, 0)
	add_child(torso)
	torso.add_child(LowPoly.instance(LowPoly.box(Vector3(0.6, 0.72, 0.34), shirt)))
	torso.add_child(LowPoly.instance(LowPoly.box(Vector3(0.62, 0.1, 0.36), Color(0.3, 0.2, 0.12), Vector3(0, -0.3, 0))))

	head = Node3D.new()
	head.position = Vector3(0, 1.62, 0)
	add_child(head)
	head.add_child(LowPoly.instance(LowPoly.box(Vector3(0.4, 0.42, 0.4), skin, Vector3(0, 0.21, 0))))
	head.add_child(LowPoly.instance(LowPoly.box(Vector3(0.44, 0.14, 0.44), hair, Vector3(0, 0.44, 0.02))))
	for x in [-0.09, 0.09]:
		head.add_child(LowPoly.instance(LowPoly.box(Vector3(0.06, 0.06, 0.02), Color(0.1, 0.1, 0.15), Vector3(x, 0.24, -0.205))))

	arm_l = _limb(Vector3(-0.41, 1.55, 0), Vector3(0.18, 0.68, 0.2), shirt)
	arm_r = _limb(Vector3(0.41, 1.55, 0), Vector3(0.18, 0.68, 0.2), shirt)
	for arm in [arm_l, arm_r]:
		arm.add_child(LowPoly.instance(LowPoly.box(Vector3(0.16, 0.16, 0.16), skin, Vector3(0, -0.74, 0))))
	hand_r = Node3D.new()
	hand_r.position = Vector3(0, -0.74, 0)
	arm_r.add_child(hand_r)

	var current := equipment.duplicate()
	equipment.clear()
	_slot_nodes.clear()
	for slot in current:
		equip(current[slot])


func _limb(pivot: Vector3, size: Vector3, color: Color) -> Node3D:
	var node := Node3D.new()
	node.position = pivot
	add_child(node)
	node.add_child(LowPoly.instance(LowPoly.box(size, color, Vector3(0, -size.y * 0.5, 0))))
	return node


# --- Ausrüstung -------------------------------------------------------------

func equip(item: String) -> void:
	if not ITEMS.has(item):
		return
	var slot: String = ITEMS[item]["slot"]
	unequip(slot)
	var mi := LowPoly.instance(_item_mesh(item))
	match slot:
		"weapon":
			hand_r.add_child(mi)
		"shield":
			mi.position = Vector3(-0.12, -0.45, 0)
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
	var b := LowPoly.Builder.new()
	var steel := Color(0.75, 0.78, 0.82)
	var rust := Color(0.6, 0.45, 0.35)
	var wood := Color(0.45, 0.3, 0.16)
	var leather := Color(0.5, 0.32, 0.18)
	match item:
		"Rostiges Schwert":
			b.add(_bm(Vector3(0.06, 0.06, 0.25)), _t(Vector3(0, 0, 0.02)), wood)
			b.add(_bm(Vector3(0.3, 0.05, 0.06)), _t(Vector3(0, 0, -0.12)), rust)
			b.add(_bm(Vector3(0.08, 0.03, 0.9)), _t(Vector3(0, 0, -0.6)), rust.lerp(steel, 0.4))
		"Streitaxt":
			b.add(_bm(Vector3(0.06, 0.06, 1.1)), _t(Vector3(0, 0, -0.4)), wood)
			b.add(_bm(Vector3(0.05, 0.4, 0.3)), _t(Vector3(0, 0.15, -0.85)), steel)
			b.add(_bm(Vector3(0.05, 0.2, 0.2)), _t(Vector3(0, -0.1, -0.85)), steel)
		"Keule":
			b.add(_bm(Vector3(0.07, 0.07, 0.6)), _t(Vector3(0, 0, -0.25)), wood)
			b.add(_bm(Vector3(0.18, 0.18, 0.35)), _t(Vector3(0, 0, -0.6)), wood.darkened(0.2))
		"Holzschild":
			b.add(_bm(Vector3(0.08, 0.7, 0.6)), _t(Vector3.ZERO), wood)
			b.add(_bm(Vector3(0.1, 0.12, 0.12)), _t(Vector3(-0.05, 0, 0)), rust)
		"Eisenschild":
			b.add(_bm(Vector3(0.08, 0.85, 0.7)), _t(Vector3.ZERO), steel.darkened(0.15))
			b.add(_bm(Vector3(0.1, 0.85, 0.12)), _t(Vector3(-0.02, 0, 0)), Color(0.75, 0.15, 0.15))
			b.add(_bm(Vector3(0.1, 0.12, 0.7)), _t(Vector3(-0.02, 0.1, 0)), Color(0.75, 0.15, 0.15))
		"Eisenhelm":
			b.add(_bm(Vector3(0.48, 0.3, 0.48)), _t(Vector3(0, 0.4, 0)), steel)
			b.add(_bm(Vector3(0.08, 0.22, 0.08)), _t(Vector3(0, 0.24, -0.23)), steel)
			b.add(_bm(Vector3(0.1, 0.12, 0.1)), _t(Vector3(0, 0.6, 0)), Color(0.8, 0.15, 0.15))
		"Lederrüstung":
			b.add(_bm(Vector3(0.66, 0.6, 0.4)), _t(Vector3(0, 0.05, 0)), leather)
			b.add(_bm(Vector3(0.74, 0.14, 0.42)), _t(Vector3(0, 0.33, 0)), leather.darkened(0.2))
			b.add(_bm(Vector3(0.1, 0.62, 0.42)), _t(Vector3(0, 0.05, 0)), leather.darkened(0.3))
	return b.commit()


func _bm(size: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = size
	return m


func _t(pos: Vector3) -> Transform3D:
	return Transform3D(Basis(), pos)


# --- Animation --------------------------------------------------------------

func animate(speed: float, delta: float) -> void:
	var amount := clampf(speed / 5.0, 0.0, 1.4)
	_walk_phase += delta * (4.0 + speed * 1.6)
	var swing := sin(_walk_phase) * 0.7 * amount
	leg_l.rotation.x = lerpf(leg_l.rotation.x, swing, 12.0 * delta)
	leg_r.rotation.x = lerpf(leg_r.rotation.x, -swing, 12.0 * delta)
	var bob := absf(sin(_walk_phase)) * 0.06 * amount
	torso.position.y = 1.25 + bob
	head.position.y = 1.62 + bob
	if not _blocking:
		arm_l.rotation = arm_l.rotation.lerp(Vector3(-swing * 0.8, 0, 0), 12.0 * delta)
	else:
		arm_l.rotation = arm_l.rotation.lerp(Vector3(1.2, 0, 0.5), 18.0 * delta)
	if _slot_nodes.has("shield"):
		# Beim Blocken dreht sich der Schild mit der Fläche nach vorn.
		var shield: Node3D = _slot_nodes["shield"]
		shield.rotation.y = lerpf(shield.rotation.y, -PI * 0.5 if _blocking else 0.0, 18.0 * delta)
	if not _attacking:
		arm_r.rotation = arm_r.rotation.lerp(Vector3(swing * 0.8 + 0.25, 0, 0), 12.0 * delta)


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
