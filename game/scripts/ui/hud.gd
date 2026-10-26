class_name Hud
extends CanvasLayer
## Anzeige: Leben, Ausdauer, Geld, Uhrzeit, Meldungen und Handelsfenster.

var player: Player
var day_night: DayNight

var _health_bar: ProgressBar
var _stamina_bar: ProgressBar
var _coins_label: Label
var _clock_label: Label
var _prompt_label: Label
var _inventory_label: Label
var _messages: VBoxContainer
var _shop_panel: PanelContainer
var _shop_title: Label
var _shop_info: Label
var _shop_grid: GridContainer
var _merchant: Merchant
var _interact_target: Node3D


func _ready() -> void:
	add_to_group("hud")
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	var bars := VBoxContainer.new()
	bars.position = Vector2(24, 20)
	bars.add_theme_constant_override("separation", 6)
	root.add_child(bars)
	_health_bar = _bar(Color(0.85, 0.2, 0.2))
	_stamina_bar = _bar(Color(0.3, 0.75, 0.3))
	bars.add_child(_health_bar)
	bars.add_child(_stamina_bar)
	_coins_label = _label(20)
	bars.add_child(_coins_label)
	_inventory_label = _label(15)
	bars.add_child(_inventory_label)

	_clock_label = _label(20)
	_clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_place(_clock_label, Vector4(1, 0, 1, 0), Vector4(-280, 20, -24, 50))
	root.add_child(_clock_label)

	var help := _label(14)
	help.text = "WASD Laufen · Maus Kamera · Shift Sprinten · Leertaste Springen\n" \
		+ "Linksklick Angreifen · Rechtsklick Blocken · C Ausweichrolle\n" \
		+ "E Interagieren · R Heiltrank · Mausrad Zoom · Esc Maus freigeben"
	_place(help, Vector4(0, 1, 0, 1), Vector4(24, -90, 760, -16))
	help.modulate = Color(1, 1, 1, 0.75)
	root.add_child(help)

	_prompt_label = _label(22)
	_prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_place(_prompt_label, Vector4(0.5, 1, 0.5, 1), Vector4(-300, -190, 300, -150))
	root.add_child(_prompt_label)

	_messages = VBoxContainer.new()
	_messages.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_place(_messages, Vector4(0.5, 0, 0.5, 0), Vector4(-300, 60, 300, 320))
	root.add_child(_messages)

	_build_shop(root)


## Verankert ein Element: anchors/offsets jeweils als (links, oben, rechts, unten).
func _place(control: Control, anchors: Vector4, offsets: Vector4) -> void:
	control.anchor_left = anchors.x
	control.anchor_top = anchors.y
	control.anchor_right = anchors.z
	control.anchor_bottom = anchors.w
	control.offset_left = offsets.x
	control.offset_top = offsets.y
	control.offset_right = offsets.z
	control.offset_bottom = offsets.w


func _bar(color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(260, 18)
	bar.show_percentage = false
	var fill := StyleBoxFlat.new()
	fill.bg_color = color
	fill.set_corner_radius_all(4)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.5)
	bg.set_corner_radius_all(4)
	bar.add_theme_stylebox_override("fill", fill)
	bar.add_theme_stylebox_override("background", bg)
	return bar


func _label(size: int) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 6)
	return label


func _process(_delta: float) -> void:
	if player == null:
		return
	_health_bar.max_value = player.max_health
	_health_bar.value = player.health
	_stamina_bar.max_value = player.max_stamina
	_stamina_bar.value = player.stamina
	_coins_label.text = "Geld: %s" % format_coins(player.coins)
	var items := []
	for item in player.inventory:
		items.append("%s ×%d" % [item, player.inventory[item]])
	_inventory_label.text = "Tasche: " + (", ".join(items) if not items.is_empty() else "leer")
	if day_night:
		_clock_label.text = day_night.clock_text()
	_update_interaction()


func _update_interaction() -> void:
	_interact_target = null
	if _shop_panel.visible or not player.alive:
		_prompt_label.text = ""
		return
	var best := 3.0
	for node in get_tree().get_nodes_in_group("interactable"):
		var n := node as Node3D
		var d := n.global_position.distance_to(player.global_position)
		if d < best:
			best = d
			_interact_target = n
	_prompt_label.text = _interact_target.call("prompt") if _interact_target else ""


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("interact"):
		if _shop_panel.visible:
			close_shop()
		elif _interact_target:
			_interact_target.call("interact", player)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("toggle_mouse") and _shop_panel.visible:
		close_shop()
		get_viewport().set_input_as_handled()


func show_message(text: String) -> void:
	var label := _label(20)
	label.text = text
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_messages.add_child(label)
	var tw := create_tween()
	tw.tween_interval(2.5)
	tw.tween_property(label, "modulate:a", 0.0, 0.8)
	tw.tween_callback(label.queue_free)


@warning_ignore("integer_division")
static func format_coins(kupfer: int) -> String:
	var gold := kupfer / 10000
	var silber := (kupfer % 10000) / 100
	var rest := kupfer % 100
	if gold > 0:
		return "%dG %dS %dK" % [gold, silber, rest]
	if silber > 0:
		return "%dS %dK" % [silber, rest]
	return "%dK" % rest


# --- Handel -----------------------------------------------------------------

func _build_shop(root: Control) -> void:
	_shop_panel = PanelContainer.new()
	_place(_shop_panel, Vector4(0.5, 0.5, 0.5, 0.5), Vector4(-380, -280, 380, 280))
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.16, 0.12, 0.09, 0.95)
	style.border_color = Color(0.75, 0.6, 0.3)
	style.set_border_width_all(3)
	style.set_corner_radius_all(8)
	style.set_content_margin_all(16)
	_shop_panel.add_theme_stylebox_override("panel", style)
	_shop_panel.visible = false
	root.add_child(_shop_panel)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	_shop_panel.add_child(box)
	_shop_title = _label(24)
	box.add_child(_shop_title)
	_shop_info = _label(14)
	_shop_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_shop_info)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(scroll)
	_shop_grid = GridContainer.new()
	_shop_grid.columns = 6
	_shop_grid.add_theme_constant_override("h_separation", 14)
	_shop_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_shop_grid)

	var close := Button.new()
	close.text = "Schließen [E]"
	close.pressed.connect(close_shop)
	box.add_child(close)


func open_shop(merchant: Merchant, p: Player) -> void:
	_merchant = merchant
	player = p
	player.input_locked = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_shop_panel.visible = true
	_refresh_shop()


func close_shop() -> void:
	_shop_panel.visible = false
	if player:
		player.input_locked = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _refresh_shop() -> void:
	var market := _merchant.market
	_shop_title.text = "%s – Markt von %s" % [_merchant.display_name, market.city_name]
	_shop_info.text = "Dein Geld: %s   ·   Geld der Bürger: %s\n" % [format_coins(player.coins), format_coins(market.households)] \
		+ "Preise richten sich nach Vorrat, Bedarf und Wohlstand. Was du verkaufst, bezahlen die Bürger aus ihrer Tasche."
	for child in _shop_grid.get_children():
		child.queue_free()
	for header in ["Ware", "Vorrat", "Kaufen", "Verkaufen", "Besitz", ""]:
		var h := _label(15)
		h.text = header
		h.modulate = Color(0.95, 0.8, 0.45)
		_shop_grid.add_child(h)
	for good in Market.BASE_PRICES:
		var owned := int(player.inventory.get(good, 0))
		var equipped := player.model.equipment.values().has(good)
		_add_cell(good)
		_add_cell(str(int(market.stock.get(good, 0.0))))
		_add_cell(format_coins(market.price(good)))
		_add_cell(format_coins(market.sell_price(good)))
		_add_cell("angelegt" if equipped else str(owned))
		var buttons := HBoxContainer.new()
		var buy := Button.new()
		buy.text = "Kaufen"
		buy.disabled = equipped or not market.has_stock(good) or market.price(good) > player.coins
		buy.pressed.connect(_on_buy.bind(good))
		buttons.add_child(buy)
		var sell := Button.new()
		sell.text = "Verkaufen"
		sell.disabled = owned <= 0
		sell.pressed.connect(_on_sell.bind(good))
		buttons.add_child(sell)
		_shop_grid.add_child(buttons)


func _add_cell(text: String) -> void:
	var label := _label(15)
	label.text = text
	_shop_grid.add_child(label)


func _on_buy(good: String) -> void:
	var cost := _merchant.market.player_buy(good, player.coins)
	if cost < 0:
		show_message("Das kannst du dir nicht leisten.")
		return
	player.coins -= cost
	player.add_item(good)
	_refresh_shop()


func _on_sell(good: String) -> void:
	var revenue := _merchant.market.player_sell(good)
	if revenue < 0:
		show_message("Die Bürger von %s haben kein Geld mehr dafür." % _merchant.market.city_name)
		return
	player.remove_item(good)
	player.coins += revenue
	_refresh_shop()
