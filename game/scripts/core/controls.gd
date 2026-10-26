class_name Controls
extends RefCounted
## Tastenbelegung (Tastatur/Maus + Controller). Physische Tasten, damit
## QWERTZ und QWERTY gleich funktionieren.


static func setup() -> void:
	_bind("move_forward", [_key(KEY_W), _axis(JOY_AXIS_LEFT_Y, -1.0)])
	_bind("move_back", [_key(KEY_S), _axis(JOY_AXIS_LEFT_Y, 1.0)])
	_bind("move_left", [_key(KEY_A), _axis(JOY_AXIS_LEFT_X, -1.0)])
	_bind("move_right", [_key(KEY_D), _axis(JOY_AXIS_LEFT_X, 1.0)])
	_bind("look_left", [_axis(JOY_AXIS_RIGHT_X, -1.0)])
	_bind("look_right", [_axis(JOY_AXIS_RIGHT_X, 1.0)])
	_bind("look_up", [_axis(JOY_AXIS_RIGHT_Y, -1.0)])
	_bind("look_down", [_axis(JOY_AXIS_RIGHT_Y, 1.0)])
	_bind("jump", [_key(KEY_SPACE), _joy(JOY_BUTTON_A)])
	_bind("sprint", [_key(KEY_SHIFT), _joy(JOY_BUTTON_LEFT_STICK)])
	_bind("dodge", [_key(KEY_C), _joy(JOY_BUTTON_B)])
	_bind("attack", [_mouse(MOUSE_BUTTON_LEFT), _joy(JOY_BUTTON_X)])
	_bind("block", [_mouse(MOUSE_BUTTON_RIGHT), _joy(JOY_BUTTON_LEFT_SHOULDER)])
	_bind("interact", [_key(KEY_E), _joy(JOY_BUTTON_Y)])
	_bind("use_potion", [_key(KEY_R), _joy(JOY_BUTTON_RIGHT_SHOULDER)])
	_bind("toggle_mouse", [_key(KEY_ESCAPE), _joy(JOY_BUTTON_START)])


static func _bind(action: String, events: Array) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.2)
	for event in events:
		InputMap.action_add_event(action, event)


static func _key(code: Key) -> InputEventKey:
	var e := InputEventKey.new()
	e.physical_keycode = code
	return e


static func _mouse(button: MouseButton) -> InputEventMouseButton:
	var e := InputEventMouseButton.new()
	e.button_index = button
	return e


static func _joy(button: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.button_index = button
	return e


static func _axis(axis: JoyAxis, value: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new()
	e.axis = axis
	e.axis_value = value
	return e
