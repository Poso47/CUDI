class_name Market
extends RefCounted
## Markt einer Stadt – Übertragung von rpg/core/economy.py (dort wird balanciert).
## Grundregel: Geld wird nicht erzeugt. Zahlt der Händler dir etwas, kommt es
## aus dem Geld der Bürger; kaufst du etwas, fließt dein Geld in die Stadt.

const BASE_PRICES := {
	"Getreide": 20, "Holz": 30, "Wolle": 40, "Tuch": 120, "Salz": 60,
	"Fell": 35, "Goblinzahn": 60, "Heiltrank": 150,
	"Eisenhelm": 700, "Lederrüstung": 900, "Streitaxt": 1200, "Eisenschild": 800,
}
const STOCK_TARGET_DAYS := 10.0
const REFERENCE_WEALTH := 400.0
const MERCHANT_MARGIN := 0.8   # Ankaufspreis = 80 % des Marktpreises

var city_name: String
var population: int
var households: int            # Kupfer im Besitz der Bürger
var stock: Dictionary = {}     # Ware -> Menge
var production: Dictionary = {}  # Ware -> Menge pro Tag
var needs: Dictionary = {}     # Ware -> Bedarf pro Tag


func _init(p_name: String, p_population: int, p_households: int) -> void:
	city_name = p_name
	population = p_population
	households = p_households


static func village() -> Market:
	var m := Market.new("Grünau", 1500, 250_000)
	m.stock = {
		"Getreide": 400.0, "Holz": 200.0, "Wolle": 120.0, "Tuch": 10.0, "Salz": 8.0,
		"Fell": 6.0, "Goblinzahn": 2.0, "Heiltrank": 6.0,
		"Eisenhelm": 2.0, "Lederrüstung": 1.0, "Streitaxt": 1.0, "Eisenschild": 1.0,
	}
	m.production = {
		"Getreide": 130.0, "Holz": 40.0, "Wolle": 30.0, "Heiltrank": 3.0,
		"Eisenhelm": 0.1, "Lederrüstung": 0.1, "Streitaxt": 0.05, "Eisenschild": 0.1,
	}
	m.needs = {
		"Getreide": 15.0, "Holz": 5.0, "Tuch": 1.5, "Salz": 1.5,
		"Fell": 2.0, "Goblinzahn": 1.0, "Heiltrank": 1.0,
		"Eisenhelm": 0.05, "Lederrüstung": 0.05, "Streitaxt": 0.03, "Eisenschild": 0.05,
	}
	return m


func price(good: String) -> int:
	var base: float = BASE_PRICES[good]
	var target := maxf(float(needs.get(good, 0.1)) * STOCK_TARGET_DAYS, 2.0)
	var scarcity := sqrt(target / maxf(float(stock.get(good, 0.0)), 0.5))
	scarcity = clampf(scarcity, 0.35, 4.0)
	var wealth := pow(maxf(float(households) / population, 1.0) / REFERENCE_WEALTH, 0.3)
	wealth = clampf(wealth, 0.5, 2.5)
	return maxi(1, roundi(base * scarcity * wealth))


func sell_price(good: String) -> int:
	return maxi(1, int(price(good) * MERCHANT_MARGIN))


func has_stock(good: String) -> bool:
	return float(stock.get(good, 0.0)) >= 1.0


## Spieler kauft eine Einheit. Gibt die Kosten zurück oder -1.
func player_buy(good: String, wallet: int) -> int:
	var cost := price(good)
	if not has_stock(good) or cost > wallet:
		return -1
	stock[good] = float(stock[good]) - 1.0
	households += cost
	return cost


## Spieler verkauft eine Einheit. Gibt den Erlös zurück oder -1.
func player_sell(good: String) -> int:
	var revenue := sell_price(good)
	if households < revenue:
		return -1
	households -= revenue
	stock[good] = float(stock.get(good, 0.0)) + 1.0
	return revenue


## Eine Spielstunde: Produktion und Verbrauch laufen weiter.
func tick_hour() -> void:
	for good in production:
		stock[good] = float(stock.get(good, 0.0)) + float(production[good]) / 24.0
	for good in needs:
		var have := float(stock.get(good, 0.0))
		stock[good] = maxf(have - float(needs[good]) / 24.0, 0.0)
