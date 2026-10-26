import random
import unittest

from rpg.core.economy import default_world
from rpg.core.skills import BASE_ELEMENTS, MASTERY_REQUIRED, MUTATION_ELEMENTS, default_registry


def fuse_until_success(reg, a, b, rng, intelligence=20, tries=30):
    for _ in range(tries):
        result = reg.fuse(a, b, mastery_a=90, mastery_b=90,
                          intelligence=intelligence, discoverer="Test", rng=rng)
        if result.success:
            return result
    raise AssertionError("Fusion nie erfolgreich")


class SkillFusionTest(unittest.TestCase):
    def test_recipe_gives_designed_skill(self):
        reg = default_registry()
        result = fuse_until_success(reg, "schwerthieb", "feuerball", random.Random(1))
        self.assertEqual(result.skill.id, "flammenschwert")

    def test_unknown_combination_creates_new_skill(self):
        reg = default_registry()
        before = len(reg.skills)
        result = fuse_until_success(reg, "feuerball", "frostnova", random.Random(1))
        self.assertIn(result.skill.origin, ("Emergent", "Mutation"))
        self.assertIn("Dampf", result.skill.elements)
        self.assertEqual(result.skill.tier, 2)
        self.assertEqual(len(reg.skills), before + 1)
        self.assertTrue(result.world_first)

    def test_same_pair_always_gives_same_skill(self):
        reg = default_registry()
        first = fuse_until_success(reg, "heiliges_licht", "schattenschritt", random.Random(1))
        again = fuse_until_success(reg, "schattenschritt", "heiliges_licht", random.Random(2))
        self.assertEqual(first.skill.id, again.skill.id)
        self.assertFalse(again.world_first)

    def test_fused_skills_can_be_fused_again(self):
        reg = default_registry()
        rng = random.Random(3)
        a = fuse_until_success(reg, "feuerball", "frostnova", rng).skill
        b = fuse_until_success(reg, "axtwurf", "blitzstrahl", rng).skill
        c = fuse_until_success(reg, a.id, b.id, rng).skill
        self.assertEqual(c.tier, 3)
        self.assertGreater(c.power, max(a.power, b.power) * 0.75)

    def test_mutation_creates_building_blocks_not_in_base_skills(self):
        reg = default_registry()
        rng = random.Random(0)
        base_ids = list(reg.skills)
        mutated = None
        # Viele Paare mit hoher Intelligenz – mindestens eine Mutation muss auftauchen.
        for i, a in enumerate(base_ids):
            for b in base_ids[i + 1:]:
                result = fuse_until_success(reg, a, b, rng, intelligence=60)
                if result.skill.origin == "Mutation":
                    mutated = result.skill
                    break
            if mutated:
                break
        self.assertIsNotNone(mutated)
        new_elements = set(mutated.elements) - set(BASE_ELEMENTS)
        self.assertTrue(new_elements & set(MUTATION_ELEMENTS))

    def test_mastery_required(self):
        reg = default_registry()
        result = reg.fuse("feuerball", "frostnova", mastery_a=MASTERY_REQUIRED - 1,
                          mastery_b=90, intelligence=50, rng=random.Random(1))
        self.assertFalse(result.success)
        self.assertIsNone(result.skill)


class EconomyTest(unittest.TestCase):
    def test_money_is_conserved(self):
        world = default_world(seed=7)
        world.player_coins = 10_000
        start = world.total_money()
        for _ in range(150):
            world.tick()
        world.player_buy("Grünau", "Getreide", 30)
        world.player_sell("Kronhafen", "Getreide", 30)
        expected = start + world.minted_total - world.destroyed_total
        self.assertEqual(world.total_money(), expected)

    def test_prices_follow_supply(self):
        world = default_world(seed=1)
        farm, fortress = world.cities["Grünau"], world.cities["Sturmwacht"]
        self.assertLess(farm.price("Getreide"), fortress.price("Getreide"))

    def test_rich_city_has_higher_prices_for_same_supply(self):
        world = default_world(seed=1)
        rich, poor = world.cities["Kronhafen"], world.cities["Grünau"]
        for city in (rich, poor):
            city.stock["Eisen"] = 100
            city.workshops.pop("Waffen", None)
        self.assertGreater(rich.price("Eisen"), poor.price("Eisen"))

    def test_trade_moves_money_between_cities(self):
        world = default_world(seed=42)
        start = world.cities["Grünau"].money
        for _ in range(200):
            world.tick()
        # Das Bauerndorf exportiert Nahrung und wird dadurch reicher.
        self.assertGreater(world.cities["Grünau"].money, start)


if __name__ == "__main__":
    unittest.main()
