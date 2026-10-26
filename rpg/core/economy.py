"""Wirtschaft mit echter Geldmenge.

Grundregel: Geld entsteht nie aus dem Nichts.
- Münzen werden nur in Städten mit Münzstätte aus Silbererz geprägt.
- Münzen verschwinden nur über echte Senken (Abnutzung, verlorene Karawanen).
- Alles andere ist Umverteilung: Steuern, Löhne, Handel, Karawanen, Spieler.

Dadurch entsteht ein echter Cashflow: Städte, die viel importieren, verlieren
Geld an Städte, die exportieren. Reiche Städte haben höhere Preise und mehr
Kaufkraft, arme Städte sind billig, können sich aber wenig leisten.

Alle Beträge sind ganze Kupfermünzen (1 Gold = 100 Silber = 10.000 Kupfer).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

KUPFER_PRO_SILBER = 100
KUPFER_PRO_GOLD = 100 * KUPFER_PRO_SILBER

# Grundpreise in Kupfer
BASE_PRICES: dict[str, int] = {
    "Getreide": 20, "Holz": 30, "Wolle": 40, "Tuch": 120, "Eisenerz": 50,
    "Eisen": 150, "Waffen": 900, "Salz": 60, "Wein": 250, "Gewürze": 800,
    "Silbererz": 400,
}

# Werkstätten: Ausgabe -> benötigte Eingaben pro Einheit
WORKSHOP_RECIPES: dict[str, dict[str, int]] = {
    "Eisen": {"Eisenerz": 2, "Holz": 1},
    "Waffen": {"Eisen": 3, "Holz": 1},
    "Tuch": {"Wolle": 2},
}

# Bedarf pro 1000 Einwohner und Tick
NEEDS_PER_1000: dict[str, float] = {
    "Getreide": 10, "Holz": 3, "Tuch": 1, "Salz": 1, "Wein": 0.5, "Gewürze": 0.1,
}
# Wie wichtig eine Ware für die Zufriedenheit ist (Grundbedarf > Luxus)
NEED_WEIGHTS: dict[str, float] = {
    "Getreide": 5, "Holz": 2, "Salz": 1.5, "Tuch": 1, "Wein": 0.5, "Gewürze": 0.5,
}

# Verderbliche Waren verlieren pro Tick diesen Anteil ihres Vorrats.
SPOILAGE: dict[str, float] = {"Getreide": 0.01, "Wolle": 0.002, "Holz": 0.001}

STOCK_TARGET_TICKS = 10      # so viele Ticks Vorrat gilt als „ausreichend“
REFERENCE_WEALTH = 400       # Kupfer pro Einwohner, bei dem Preise = Grundpreis
COIN_WEAR_RATE = 0.0001      # Anteil des Bargelds, der pro Tick verschleißt
MINT_YIELD = 1500            # Kupfer pro Silbererz


def format_coins(kupfer: int) -> str:
    gold, rest = divmod(kupfer, KUPFER_PRO_GOLD)
    silber, kupfer = divmod(rest, KUPFER_PRO_SILBER)
    parts = []
    if gold:
        parts.append(f"{gold}G")
    if silber or gold:
        parts.append(f"{silber}S")
    parts.append(f"{kupfer}K")
    return " ".join(parts)


@dataclass
class City:
    name: str
    population: int
    treasury: int                       # Stadtkasse
    households: int                     # Geld der Bürger, Händler, Handwerker
    stock: dict[str, float] = field(default_factory=dict)
    production: dict[str, float] = field(default_factory=dict)   # Rohstoffe pro Tick
    workshops: dict[str, float] = field(default_factory=dict)    # Kapazität pro Tick
    tax_rate: float = 0.02              # Anteil des Bürgergelds pro Tick
    wage_per_1000: int = 4_000          # Löhne/Ausgaben der Stadt pro 1000 Einwohner
    has_mint: bool = False
    prosperity: float = 1.0             # 0.2 (Elend) … 3.0 (Blüte)
    tariff: float = 0.05                # Zoll auf Karawanenverkäufe
    last_satisfaction: float = 1.0

    # --- Kennzahlen ---------------------------------------------------------

    @property
    def money(self) -> int:
        return self.treasury + self.households

    @property
    def wealth_per_capita(self) -> float:
        return self.households / max(self.population, 1)

    def demand(self, good: str) -> float:
        """Bedarf pro Tick (Konsum + Werkstätten)."""
        need = NEEDS_PER_1000.get(good, 0.0) * self.population / 1000
        for output, capacity in self.workshops.items():
            need += WORKSHOP_RECIPES[output].get(good, 0) * capacity
        return need

    def price(self, good: str) -> int:
        """Aktueller Stückpreis: Angebot/Nachfrage × Wohlstand der Stadt."""
        base = BASE_PRICES[good]
        target = max(self.demand(good) * STOCK_TARGET_TICKS, 5.0)
        scarcity = (target / max(self.stock.get(good, 0.0), 0.5)) ** 0.5
        scarcity = min(max(scarcity, 0.35), 4.0)
        wealth = (max(self.wealth_per_capita, 1) / REFERENCE_WEALTH) ** 0.3
        wealth = min(max(wealth, 0.5), 2.5)
        return max(1, round(base * scarcity * wealth))

    # --- Simulation ---------------------------------------------------------

    def tick(self, rng: random.Random) -> tuple[int, int]:
        """Ein Simulationsschritt. Gibt (verschlissene, geprägte) Münzen zurück."""
        # 1. Rohstoffproduktion – Wohlstand steigert die Produktivität.
        factor = 0.6 + 0.4 * self.prosperity
        for good, amount in self.production.items():
            self.stock[good] = self.stock.get(good, 0.0) + amount * factor * rng.uniform(0.85, 1.15)

        for good, rate in SPOILAGE.items():
            if good in self.stock:
                self.stock[good] *= 1 - rate

        # 2. Werkstätten verarbeiten Rohstoffe.
        for output, capacity in self.workshops.items():
            recipe = WORKSHOP_RECIPES[output]
            possible = min(
                [capacity * factor] + [self.stock.get(g, 0.0) / n for g, n in recipe.items()]
            )
            for g, n in recipe.items():
                self.stock[g] = self.stock.get(g, 0.0) - possible * n
            self.stock[output] = self.stock.get(output, 0.0) + possible

        # 3. Münzstätte prägt neues Geld aus Silbererz.
        minted = 0
        if self.has_mint and self.stock.get("Silbererz", 0) >= 1:
            ore = int(self.stock["Silbererz"])
            self.stock["Silbererz"] -= ore
            minted = ore * MINT_YIELD
            self.treasury += minted

        # 4. Bürger verbrauchen Waren.
        satisfied, needed = 0.0, 0.0
        for good, per_1000 in NEEDS_PER_1000.items():
            need = per_1000 * self.population / 1000
            have = self.stock.get(good, 0.0)
            used = min(need, have)
            self.stock[good] = have - used
            satisfied += used / need * NEED_WEIGHTS[good] if need else 0.0
            needed += NEED_WEIGHTS[good] if need else 0.0
        self.last_satisfaction = satisfied / needed if needed else 1.0

        # 5. Steuern: Bürger -> Stadtkasse
        taxes = int(self.households * self.tax_rate)
        self.households -= taxes
        self.treasury += taxes

        # 6. Löhne & öffentliche Ausgaben: Stadtkasse -> Bürger
        wages = min(self.treasury, int(self.wage_per_1000 * self.population / 1000))
        self.treasury -= wages
        self.households += wages

        # 7. Münzverschleiß – die einzige stetige Geldsenke.
        worn = int(self.households * COIN_WEAR_RATE)
        self.households -= worn

        # 8. Wohlstand und Bevölkerung reagieren.
        wealth_signal = min(self.wealth_per_capita / REFERENCE_WEALTH, 2.0) - 1.0
        self.prosperity += 0.03 * (self.last_satisfaction - 0.85) + 0.004 * wealth_signal
        self.prosperity = min(max(self.prosperity, 0.2), 3.0)
        growth = 0.001 * (self.prosperity - 1.0)
        self.population = max(50, round(self.population * (1 + growth)))
        return worn, minted


@dataclass
class Caravan:
    """NPC-Händler: kauft billig, verkauft teuer und bewegt so Geld zwischen Städten."""

    name: str
    coins: int
    capacity: int = 40
    location: str = ""
    upkeep: int = 200                   # Lohn für Wachen/Fuhrleute, geht an die Stadt

    def best_trade(self, world: "World", origin: str | None = None) -> tuple[str, str, int, int] | None:
        """(Ware, Zielstadt, Menge, erwarteter Gewinn) ab `origin` oder None."""
        origin = origin or self.location
        here = world.cities[origin]
        best = None
        for good in BASE_PRICES:
            available = int(here.stock.get(good, 0) * 0.5)
            buy = here.price(good) * 1.2     # eigene Käufe treiben den Preis
            qty = min(self.capacity, available, int(self.coins // max(buy, 1)))
            if qty <= 0:
                continue
            for dest in world.cities.values():
                if dest.name == origin:
                    continue
                sell = dest.price(good) * 0.8 * (1 - dest.tariff)
                profit = int((sell - buy) * qty) - self.upkeep
                if profit > 0 and (best is None or profit > best[3]):
                    best = (good, dest.name, qty, profit)
        return best

    def best_origin(self, world: "World") -> str | None:
        """Lohnt es sich, leer zu einem anderen Markt zu reisen?"""
        here = self.best_trade(world)
        best_profit = here[3] if here else 0
        best_city = None
        for name in world.cities:
            if name == self.location:
                continue
            trade = self.best_trade(world, origin=name)
            # Leerfahrt kostet einen Tag Unterhalt und Zeit.
            if trade and trade[3] - 2 * self.upkeep > best_profit * 1.5:
                best_profit, best_city = trade[3], name
        return best_city


@dataclass
class World:
    cities: dict[str, City]
    caravans: list[Caravan] = field(default_factory=list)
    player_coins: int = 0
    minted_total: int = 0
    destroyed_total: int = 0
    log: list[str] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def total_money(self) -> int:
        return (
            sum(c.money for c in self.cities.values())
            + sum(k.coins for k in self.caravans)
            + self.player_coins
        )

    # --- Handel (für Karawanen und Spieler gleich) ------------------------

    def buy(self, city_name: str, good: str, qty: int, wallet: int) -> tuple[int, int]:
        """Kauft Ware aus einer Stadt. Gibt (gekaufte Menge, Kosten) zurück."""
        city = self.cities[city_name]
        bought, cost = 0, 0
        for _ in range(qty):
            price = city.price(good)
            if city.stock.get(good, 0) < 1 or cost + price > wallet:
                break
            city.stock[good] -= 1
            city.households += price
            cost += price
            bought += 1
        return bought, cost

    def sell(self, city_name: str, good: str, qty: int) -> tuple[int, int]:
        """Verkauft Ware an eine Stadt. Gibt (verkaufte Menge, Erlös) zurück."""
        city = self.cities[city_name]
        sold, revenue = 0, 0
        for _ in range(qty):
            price = city.price(good)
            if city.households < price:
                break                   # Die Stadt kann sich die Ware nicht leisten.
            toll = int(price * city.tariff)
            city.households -= price
            city.treasury += toll
            city.stock[good] = city.stock.get(good, 0) + 1
            revenue += price - toll
            sold += 1
        return sold, revenue

    def player_buy(self, city: str, good: str, qty: int) -> tuple[int, int]:
        bought, cost = self.buy(city, good, qty, self.player_coins)
        self.player_coins -= cost
        return bought, cost

    def player_sell(self, city: str, good: str, qty: int) -> tuple[int, int]:
        sold, revenue = self.sell(city, good, qty)
        self.player_coins += revenue
        return sold, revenue

    # --- Simulation ---------------------------------------------------------

    def tick(self) -> None:
        for city in self.cities.values():
            worn, minted = city.tick(self.rng)
            self.destroyed_total += worn
            self.minted_total += minted

        for caravan in self.caravans:
            here = self.cities[caravan.location]
            pay = min(caravan.upkeep, caravan.coins)
            caravan.coins -= pay
            here.households += pay

            reposition = caravan.best_origin(self)
            if reposition:
                caravan.location = reposition
                continue
            trade = caravan.best_trade(self)
            if trade is None:
                continue
            good, dest, qty, _ = trade
            bought, cost = self.buy(caravan.location, good, qty, caravan.coins)
            caravan.coins -= cost

            # Gefahren unterwegs: Banditen, Drachen …
            if self.rng.random() < 0.02:
                lost = caravan.coins // 4
                caravan.coins -= lost
                self.destroyed_total += lost
                self.log.append(f"Banditen überfallen {caravan.name} – Ladung {good} und "
                                f"{format_coins(lost)} verloren!")
                caravan.location = dest
                continue

            sold, revenue = self.sell(dest, good, bought)
            caravan.coins += revenue
            # Unverkaufte Reste landen als Kommissionsware im Stadtlager (kein Geldfluss).
            self.cities[dest].stock[good] = self.cities[dest].stock.get(good, 0) + (bought - sold)
            caravan.location = dest
            result = revenue - cost
            label = "Gewinn" if result >= 0 else "Verlust"
            self.log.append(f"{caravan.name}: {bought}× {good} {here.name} → {dest} "
                            f"({label} {format_coins(abs(result))})")


def default_world(seed: int | None = None) -> World:
    cities = {
        "Kronhafen": City(
            "Kronhafen", population=12_000, treasury=3_000_000, households=6_000_000,
            stock={"Getreide": 600, "Tuch": 200, "Wein": 150, "Gewürze": 60, "Salz": 100},
            production={"Gewürze": 2, "Salz": 25, "Wein": 9, "Getreide": 90, "Holz": 15},
            workshops={"Tuch": 10}, tax_rate=0.015, wage_per_1000=6_000, prosperity=1.6,
        ),
        "Eisenfels": City(
            "Eisenfels", population=4_000, treasury=400_000, households=900_000,
            stock={"Eisenerz": 300, "Eisen": 40, "Getreide": 150, "Silbererz": 0},
            production={"Eisenerz": 25, "Silbererz": 0.8, "Holz": 25, "Getreide": 20},
            workshops={"Eisen": 8, "Waffen": 1.5}, has_mint=True, prosperity=1.0,
        ),
        "Grünau": City(
            "Grünau", population=1_500, treasury=60_000, households=250_000,
            stock={"Getreide": 400, "Holz": 200, "Wolle": 120},
            production={"Getreide": 130, "Holz": 40, "Wolle": 30},
            workshops={"Tuch": 6},
            tax_rate=0.01, wage_per_1000=1_500, prosperity=0.8,
        ),
        "Sturmwacht": City(
            "Sturmwacht", population=3_000, treasury=500_000, households=700_000,
            stock={"Getreide": 120, "Waffen": 10},
            production={"Holz": 10, "Getreide": 25},
            workshops={"Waffen": 1}, tax_rate=0.03, wage_per_1000=7_000, prosperity=0.9,
        ),
    }
    world = World(cities=cities, rng=random.Random(seed))
    world.caravans = [
        Caravan("Karawane der Goldenen Waage", coins=80_000, location="Kronhafen"),
        Caravan("Zwergenhandel Eisenbart", coins=50_000, location="Eisenfels"),
        Caravan("Bauernkarren Hänsel", coins=15_000, capacity=25, location="Grünau"),
        Caravan("Kornhändlerin Mira", coins=30_000, capacity=60, location="Grünau"),
        Caravan("Salzkarawane Westwind", coins=40_000, location="Kronhafen"),
        Caravan("Söldnertross Rabenfels", coins=60_000, location="Sturmwacht"),
    ]
    return world
