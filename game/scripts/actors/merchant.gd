class_name Merchant
extends StaticBody3D
## Händlerin am Marktstand. Nutzt den Markt des Dorfes (echte Geldmenge).

var market: Market
var display_name := "Händlerin Berta"
var model: CharacterModel


func _ready() -> void:
	add_to_group("interactable")
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.35
	capsule.height = 1.8
	shape.shape = capsule
	shape.position.y = 0.9
	add_child(shape)

	model = CharacterModel.new()
	model.shirt = Color(0.25, 0.45, 0.65)
	model.pants = Color(0.2, 0.3, 0.45)
	model.hair = Color(0.85, 0.7, 0.3)
	add_child(model)
	model.build()


func _process(delta: float) -> void:
	model.animate(0.0, delta)
	var player := get_tree().get_first_node_in_group("player") as Node3D
	if player and player.global_position.distance_to(global_position) < 6.0:
		var dir := player.global_position - global_position
		model.rotation.y = lerp_angle(model.rotation.y, atan2(-dir.x, -dir.z), 4.0 * delta)


func prompt() -> String:
	return "[E] Mit %s handeln" % display_name


func interact(player: Player) -> void:
	var hud := get_tree().get_first_node_in_group("hud")
	if hud:
		hud.call("open_shop", self, player)
