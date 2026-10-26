class_name Player
extends CharacterBody3D
## Direkte Steuerung (WASD/Controller) mit freier Verfolgerkamera.

signal stats_changed
signal message(text: String)

const WALK_SPEED := 5.0
const SPRINT_SPEED := 8.5
const SWIM_SPEED := 3.0
const JUMP_VELOCITY := 7.0
const GRAVITY := 20.0
const DODGE_SPEED := 13.0
const DODGE_TIME := 0.35
const MOUSE_SENSITIVITY := 0.0025
const STICK_SENSITIVITY := 2.5
const ATTACK_RANGE := 2.4

var max_health := 100.0
var health := 100.0
var max_stamina := 100.0
var stamina := 100.0
var coins := 200                     # Du startest als Niemand – mit 2 Silber.
var inventory := {}                  # Ware -> Anzahl
var alive := true
var input_locked := false
var spawn_point := Vector3.ZERO
var water_level := 0.0

var model: CharacterModel
var camera_pivot: Node3D
var spring_arm: SpringArm3D
var camera: Camera3D

var _attack_timer := 0.0
var _dodge_timer := 0.0
var _dodge_dir := Vector3.ZERO
var _stamina_delay := 0.0
var _blocking := false


func _ready() -> void:
	add_to_group("player")
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.35
	capsule.height = 1.8
	shape.shape = capsule
	shape.position.y = 0.9
	add_child(shape)

	model = CharacterModel.new()
	add_child(model)
	model.build()
	model.equip("Rostiges Schwert")
	model.equip("Holzschild")

	camera_pivot = Node3D.new()
	camera_pivot.position.y = 1.6
	add_child(camera_pivot)
	spring_arm = SpringArm3D.new()
	spring_arm.spring_length = 5.5
	spring_arm.margin = 0.3
	spring_arm.add_excluded_object(get_rid())
	camera_pivot.add_child(spring_arm)
	camera = Camera3D.new()
	camera.fov = 70.0
	camera.far = 600.0
	spring_arm.add_child(camera)
	camera_pivot.rotation.x = -0.3

	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	spawn_point = global_position


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_mouse") and not input_locked:
		var captured := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if captured else Input.MOUSE_MODE_CAPTURED
	if input_locked:
		return
	var motion := event as InputEventMouseMotion
	if motion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_rotate_camera(-motion.relative.x * MOUSE_SENSITIVITY, -motion.relative.y * MOUSE_SENSITIVITY)
	var click := event as InputEventMouseButton
	if click and click.pressed:
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
			get_viewport().set_input_as_handled()
			return
		if click.button_index == MOUSE_BUTTON_WHEEL_UP:
			spring_arm.spring_length = maxf(spring_arm.spring_length - 0.5, 2.0)
		elif click.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			spring_arm.spring_length = minf(spring_arm.spring_length + 0.5, 12.0)
	if not alive:
		return
	if event.is_action_pressed("attack"):
		_try_attack()
	if event.is_action_pressed("dodge"):
		_try_dodge()
	if event.is_action_pressed("use_potion"):
		use_potion()


func _rotate_camera(yaw: float, pitch: float) -> void:
	camera_pivot.rotation.y += yaw
	camera_pivot.rotation.x = clampf(camera_pivot.rotation.x + pitch, -1.2, 0.6)


func _physics_process(delta: float) -> void:
	if not input_locked and alive:
		var look := Input.get_vector("look_left", "look_right", "look_up", "look_down")
		_rotate_camera(-look.x * STICK_SENSITIVITY * delta, -look.y * STICK_SENSITIVITY * delta)

	var swimming := global_position.y < water_level - 1.1
	var input := Vector2.ZERO
	if not input_locked and alive:
		input = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := Vector3(input.x, 0.0, input.y).rotated(Vector3.UP, camera_pivot.rotation.y)

	_blocking = alive and not input_locked and Input.is_action_pressed("block") and not swimming
	model.set_blocking(_blocking)

	var sprinting := Input.is_action_pressed("sprint") and direction.length() > 0.1 and stamina > 1.0 and not _blocking
	var speed := WALK_SPEED
	if swimming:
		speed = SWIM_SPEED
	elif sprinting:
		speed = SPRINT_SPEED
		_use_stamina(22.0 * delta)
	if _blocking or _attack_timer > 0.0:
		speed *= 0.4

	# Schwerkraft / Schwimmen
	if swimming:
		velocity.y = lerpf(velocity.y, 2.0 * (water_level - 0.9 - global_position.y), 4.0 * delta)
	elif not is_on_floor():
		velocity.y -= GRAVITY * delta
	if Input.is_action_just_pressed("jump") and is_on_floor() and alive and not input_locked:
		velocity.y = JUMP_VELOCITY

	if _dodge_timer > 0.0:
		_dodge_timer -= delta
		velocity.x = _dodge_dir.x * DODGE_SPEED
		velocity.z = _dodge_dir.z * DODGE_SPEED
		model.rotation.x = -TAU * (1.0 - _dodge_timer / DODGE_TIME)
	else:
		model.rotation.x = 0.0 if alive else model.rotation.x
		velocity.x = lerpf(velocity.x, direction.x * speed, 12.0 * delta)
		velocity.z = lerpf(velocity.z, direction.z * speed, 12.0 * delta)
		if direction.length() > 0.1:
			var target_yaw := atan2(-direction.x, -direction.z)
			if _blocking:
				target_yaw = camera_pivot.rotation.y      # Beim Blocken in Blickrichtung
			model.rotation.y = lerp_angle(model.rotation.y, target_yaw, 12.0 * delta)
		elif _blocking:
			model.rotation.y = lerp_angle(model.rotation.y, camera_pivot.rotation.y, 12.0 * delta)

	move_and_slide()
	model.animate(Vector2(velocity.x, velocity.z).length(), delta)

	_attack_timer = maxf(_attack_timer - delta, 0.0)
	_stamina_delay = maxf(_stamina_delay - delta, 0.0)
	if _stamina_delay <= 0.0 and not sprinting:
		stamina = minf(stamina + 25.0 * delta, max_stamina)
	stats_changed.emit()

	if global_position.y < -40.0:
		respawn()


func forward() -> Vector3:
	return -model.global_transform.basis.z


func _use_stamina(amount: float) -> bool:
	if stamina < amount:
		return false
	stamina -= amount
	_stamina_delay = 0.8
	return true


func _try_attack() -> void:
	if _attack_timer > 0.0 or _dodge_timer > 0.0 or _blocking:
		return
	if not _use_stamina(12.0):
		message.emit("Zu erschöpft zum Angreifen!")
		return
	# Zur Kamera-Blickrichtung drehen, falls man still steht.
	if Vector2(velocity.x, velocity.z).length() < 0.5:
		model.rotation.y = camera_pivot.rotation.y
	_attack_timer = model.play_attack()
	await get_tree().create_timer(0.18).timeout
	var damage := model.stat_total("damage")
	for enemy in get_tree().get_nodes_in_group("enemies"):
		var e := enemy as Node3D
		var to_enemy := e.global_position - global_position
		to_enemy.y = 0.0
		if to_enemy.length() < ATTACK_RANGE and forward().dot(to_enemy.normalized()) > 0.25:
			e.call("take_damage", damage, self)


func _try_dodge() -> void:
	if _dodge_timer > 0.0 or not is_on_floor() or not _use_stamina(20.0):
		return
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	_dodge_dir = Vector3(input.x, 0, input.y).rotated(Vector3.UP, camera_pivot.rotation.y)
	if _dodge_dir.length() < 0.1:
		_dodge_dir = forward()
	_dodge_dir = _dodge_dir.normalized()
	model.rotation.y = atan2(-_dodge_dir.x, -_dodge_dir.z)
	_dodge_timer = DODGE_TIME


func take_damage(amount: float, source: Node3D) -> void:
	if not alive or _dodge_timer > 0.0:
		return                           # Ausweichrolle macht kurz unverwundbar
	if _blocking and source != null:
		var to_source := source.global_position - global_position
		to_source.y = 0.0
		if forward().dot(to_source.normalized()) > 0.3 and _use_stamina(10.0):
			amount *= 0.15
			message.emit("Geblockt!")
	amount = maxf(amount - model.stat_total("armor") * 0.5, 1.0)
	health -= amount
	if health <= 0.0:
		_die()
	stats_changed.emit()


func use_potion() -> void:
	if int(inventory.get("Heiltrank", 0)) <= 0:
		message.emit("Du hast keinen Heiltrank.")
		return
	if health >= max_health:
		message.emit("Du bist bereits gesund.")
		return
	remove_item("Heiltrank")
	health = minf(health + 45.0, max_health)
	message.emit("Heiltrank getrunken (+45 Leben)")


func add_item(item: String, amount := 1) -> void:
	if CharacterModel.ITEMS.has(item):
		model.equip(item)
		message.emit("%s angelegt" % item)
	else:
		inventory[item] = int(inventory.get(item, 0)) + amount
	stats_changed.emit()


func remove_item(item: String, amount := 1) -> void:
	inventory[item] = int(inventory.get(item, 0)) - amount
	if int(inventory[item]) <= 0:
		inventory.erase(item)
	stats_changed.emit()


func _die() -> void:
	alive = false
	health = 0.0
	model.play_death()
	var lost := int(coins * 0.1)
	coins -= lost
	message.emit("Du bist gestorben … (%d Kupfer verloren)" % lost)
	await get_tree().create_timer(3.0).timeout
	respawn()


func respawn() -> void:
	global_position = spawn_point
	velocity = Vector3.ZERO
	health = max_health
	stamina = max_stamina
	alive = true
	model.rotation = Vector3.ZERO
	model.position = Vector3.ZERO
	stats_changed.emit()
