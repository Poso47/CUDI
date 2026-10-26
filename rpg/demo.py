"""Konsolen-Demo der Kernsysteme.

    python -m rpg.demo            (aus dem Repo-Hauptordner)
"""

from __future__ import annotations

import random

from rpg.core.economy import default_world, format_coins
from rpg.core.skills import default_registry


def demo_skills() -> None:
    print("=" * 70)
    print("SKILL-FUSION")
    print("=" * 70)
    reg = default_registry()
    rng = random.Random(7)
    pairs = [
        ("schwerthieb", "feuerball"),       # bekanntes Rezept
        ("feuerball", "frostnova"),         # Feuer + Eis -> Dampf, instabil
        ("heiliges_licht", "schattenschritt"),  # Licht + Schatten -> Zwielicht
        ("axtwurf", "blitzstrahl"),
        ("dolchstich", "schattenschritt"),
        ("erdstoss", "sprungangriff"),
        ("windklinge", "blutopfer"),
    ]
    fused = []
    for a, b in pairs:
        print(f"\n> Fusion: {reg.get(a).name} + {reg.get(b).name}")
        for attempt in range(1, 6):
            result = reg.fuse(a, b, mastery_a=80, mastery_b=75, intelligence=18,
                              discoverer="Niemand", rng=rng)
            if result.success:
                break
            print(f"  Versuch {attempt}: {result.message}")
        print(f"  {result.message}")
        if result.skill:
            print("  " + result.skill.describe().replace("\n", "\n  "))
            fused.append(result.skill.id)

    # Fusionen weiter fusionieren: Stufe 3 – Skills, die niemand entworfen hat.
    if len(fused) >= 3:
        print("\n> Stufe-3-Fusion aus zwei bereits fusionierten Skills")
        result = None
        for _ in range(10):
            result = reg.fuse(fused[1], fused[2], mastery_a=90, mastery_b=90,
                              intelligence=25, discoverer="Niemand", rng=rng)
            if result.success:
                break
        print(f"  {result.message}")
        if result.skill:
            print("  " + result.skill.describe().replace("\n", "\n  "))


def demo_economy() -> None:
    print("\n" + "=" * 70)
    print("WIRTSCHAFT & CASHFLOW (50 Tage)")
    print("=" * 70)
    world = default_world(seed=42)
    world.player_coins = 5_000
    start_money = world.total_money()

    def report(title: str) -> None:
        print(f"\n{title}")
        print(f"  {'Stadt':<11}{'Einw.':>7}{'Wohlst.':>9}{'Geld':>16}  "
              f"{'Getreide':>9}{'Eisen':>8}{'Waffen':>8}{'Gewürze':>9}")
        for c in world.cities.values():
            print(f"  {c.name:<11}{c.population:>7}{c.prosperity:>9.2f}"
                  f"{format_coins(c.money):>16}  "
                  + "".join(f"{c.price(g):>{w}}" for g, w in
                            (("Getreide", 9), ("Eisen", 8), ("Waffen", 8), ("Gewürze", 9))))

    report("Tag 0 – Preise in Kupfer")
    for _ in range(50):
        world.tick()
    report("Tag 50 – Preise in Kupfer")

    print("\nLetzte Handelsereignisse:")
    for line in world.log[-6:]:
        print("  " + line)

    # Spieler handelt: kauft Getreide billig in Grünau, verkauft in Sturmwacht.
    bought, cost = world.player_buy("Grünau", "Getreide", 50)
    sold, revenue = world.player_sell("Sturmwacht", "Getreide", bought)
    result = revenue - cost
    print(f"\nDu kaufst {bought}× Getreide in Grünau für {format_coins(cost)} "
          f"und verkaufst {sold} in Sturmwacht für {format_coins(revenue)} "
          f"→ {'Gewinn' if result >= 0 else 'Verlust'} {format_coins(abs(result))}")

    expected = start_money + world.minted_total - world.destroyed_total
    print(f"\nGeldmenge: Start {format_coins(start_money)} | geprägt "
          f"{format_coins(world.minted_total)} | vernichtet "
          f"{format_coins(world.destroyed_total)}")
    print(f"Jetzt {format_coins(world.total_money())} – Bilanz stimmt: "
          f"{world.total_money() == expected}")


if __name__ == "__main__":
    demo_skills()
    demo_economy()
