class_name Goblin
extends CharacterBody3D
## Einfacher Gegner: streift umher, verfolgt den Spieler, holt aus und schlägt zu.

signal died(goblin: Goblin)

const GRAVITY := 20.0
const CHASE_RANGE := 15.0
const ATTACK_RANGE := 1.7
const WINDUP := 0.45

var max_health := 35.0
var health := 35.0
var damage := 9.0
var home := Vector3.ZERO
var target: Player
var dead := false
var model: CharacterModel

var _attack_cooldown := 0.0
var _wander_target := Vector3.ZERO
var _wander_timer := 0.0
var _hit_flash := 0.0


func _ready() -> void:
	add_to_group("enemies")
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.3
	capsule.height = 1.4
	shape.shape = capsule
	shape.position.y = 0.7
	add_child(shape)

	model = CharacterModel.new()
	model.skin = Color(0.45, 0.65, 0.3)
	model.shirt = Color(0.4, 0.3, 0.2)
	model.pants = Color(0.3, 0.25, 0.18)
	model.hair = Color(0.2, 0.3, 0.12)
	model.scale = Vector3.ONE * 0.78
	add_child(model)
	model.build()
	model.equip("Keule")
	_wander_target = home


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	if dead:
		velocity.x = 0.0
		velocity.z = 0.0
		move_and_slide()
		return

	_attack_cooldown = maxf(_attack_cooldown - delta, 0.0)
	var move := Vector3.ZERO
	var to_player := Vector3.ZERO
	var dist := INF
	if target != null and target.alive:
		to_player = target.global_position - global_position
		to_player.y = 0.0
		dist = to_player.length()

	if dist < CHASE_RANGE:
		if dist > ATTACK_RANGE * 0.85:
			move = to_player.normalized() * 3.8
		else:
			_face(to_player)
			if _attack_cooldown <= 0.0:
				_attack()
	else:
		_wander_timer -= delta
		if _wander_timer <= 0.0:
			_wander_timer = randf_range(2.0, 5.0)
			_wander_target = home + Vector3(randf_range(-8, 8), 0, randf_range(-8, 8))
		var to_target := _wander_target - global_position
		to_target.y = 0.0
		if to_target.length() > 0.5:
			move = to_target.normalized() * 1.5

	velocity.x = move.x
	velocity.z = move.z
	if move.length() > 0.1:
		_face(move)
	move_and_slide()
	model.animate(Vector2(velocity.x, velocity.z).length(), delta)

	if _hit_flash > 0.0:
		_hit_flash -= delta
		model.scale = Vector3.ONE * (0.78 + _hit_flash * 0.3)


func _face(dir: Vector3) -> void:
	model.rotation.y = lerp_angle(model.rotation.y, atan2(-dir.x, -dir.z), 0.25)


func _attack() -> void:
	_attack_cooldown = 1.6
	model.play_attack()
	await get_tree().create_timer(WINDUP).timeout
	if dead or target == null:
		return
	var to_player := target.global_position - global_position
	to_player.y = 0.0
	if to_player.length() < ATTACK_RANGE + 0.4:
		target.take_damage(damage, self)


func take_damage(amount: float, source: Node3D) -> void:
	if dead:
		return
	health -= amount
	_hit_flash = 0.2
	if source != null:
		var push := global_position - source.global_position
		push.y = 0.0
		global_position += push.normalized() * 0.4
	if health <= 0.0:
		_die(source)


func _die(source: Node3D) -> void:
	dead = true
	remove_from_group("enemies")
	collision_layer = 0
	model.play_death()
	if source is Player:
		var player := source as Player
		player.add_item("Goblinzahn", 1)
		player.message.emit("Goblin besiegt! +1 Goblinzahn")
		if randf() < 0.5:
			player.add_item("Fell", 1)
			player.message.emit("+1 Fell")
	died.emit(self)
	await get_tree().create_timer(4.0).timeout
	queue_free()
