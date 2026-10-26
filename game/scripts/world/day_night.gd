class_name DayNight
extends Node
## Tag-/Nacht-Zyklus: Sonne, Himmelsfarben, Umgebungslicht.

signal hour_passed(hour: int)

const REAL_SECONDS_PER_DAY := 720.0   # ein Spieltag = 12 echte Minuten

var time_of_day := 8.0                # 0–24
var day := 1
var sun: DirectionalLight3D
var moon: DirectionalLight3D
var environment: Environment
var sky_material: ProceduralSkyMaterial
var _last_hour := 8


func _ready() -> void:
	sky_material = ProceduralSkyMaterial.new()
	sky_material.sky_curve = 0.12
	sky_material.ground_bottom_color = Color(0.2, 0.3, 0.4)
	var sky := Sky.new()
	sky.sky_material = sky_material

	environment = Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.glow_enabled = true
	environment.glow_intensity = 0.4
	environment.glow_bloom = 0.05
	# Weiche Umgebungsverdeckung lässt runde Formen plastischer wirken.
	environment.ssao_enabled = true
	environment.ssao_radius = 1.2
	environment.ssao_intensity = 1.5
	environment.fog_enabled = true
	environment.fog_density = 0.0025
	environment.fog_aerial_perspective = 0.6
	var world_env := WorldEnvironment.new()
	world_env.environment = environment
	add_child(world_env)

	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	sun.shadow_blur = 1.5
	sun.light_color = Color(1.0, 0.96, 0.88)
	add_child(sun)

	moon = DirectionalLight3D.new()
	moon.light_color = Color(0.55, 0.65, 1.0)
	moon.shadow_enabled = false
	add_child(moon)
	_apply()


func _process(delta: float) -> void:
	time_of_day += delta * 24.0 / REAL_SECONDS_PER_DAY
	if time_of_day >= 24.0:
		time_of_day -= 24.0
		day += 1
	var hour := int(time_of_day)
	if hour != _last_hour:
		_last_hour = hour
		hour_passed.emit(hour)
	_apply()


func clock_text() -> String:
	var minutes := int((time_of_day - floorf(time_of_day)) * 60.0)
	return "Tag %d  %02d:%02d" % [day, int(time_of_day), minutes]


func _apply() -> void:
	# Höhe der Sonne: 1 mittags, 0 bei Auf-/Untergang (6/18 Uhr), negativ nachts.
	var elevation := sin((time_of_day - 6.0) / 12.0 * PI)
	sun.rotation = Vector3(-asin(clampf(elevation, -1.0, 1.0)) - 0.05, deg_to_rad(-35.0) + (time_of_day - 12.0) * 0.12, 0.0)
	sun.light_energy = clampf(elevation * 1.6, 0.0, 1.3)
	sun.visible = elevation > -0.05
	moon.rotation = Vector3(deg_to_rad(-55.0), deg_to_rad(140.0), 0.0)
	moon.light_energy = clampf(-elevation * 0.6, 0.0, 0.25)

	var day_top := Color(0.25, 0.5, 0.9)
	var day_horizon := Color(0.65, 0.8, 0.95)
	var dusk_horizon := Color(1.0, 0.55, 0.3)
	var night_top := Color(0.02, 0.03, 0.1)
	var night_horizon := Color(0.08, 0.1, 0.2)
	var daylight := clampf(elevation * 2.0 + 0.3, 0.0, 1.0)
	var dusk := clampf(1.0 - absf(elevation) * 4.0, 0.0, 1.0)
	sky_material.sky_top_color = night_top.lerp(day_top, daylight)
	sky_material.sky_horizon_color = night_horizon.lerp(day_horizon, daylight).lerp(dusk_horizon, dusk * 0.7)
	sky_material.ground_horizon_color = sky_material.sky_horizon_color
	sun.light_color = Color(1.0, 0.96, 0.88).lerp(Color(1.0, 0.6, 0.35), dusk)
	environment.ambient_light_energy = lerpf(0.25, 1.0, daylight)
	environment.fog_light_color = sky_material.sky_horizon_color
