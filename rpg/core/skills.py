"""Skill-System mit Fusion.

Jeder Skill besteht aus Bausteinen (Elemente, Form, Effekte, Waffenbindung).
Zwei gemeisterte Skills lassen sich fusionieren:

1. Existiert ein handgemachtes Rezept, entsteht der vorgesehene Skill.
2. Existiert keins, wird das System gezwungen, aus den Bausteinen einen
   neuen Skill zu erschaffen: Elemente reagieren, Formen verschmelzen,
   Effekte werden kombiniert und Werte neu berechnet.
3. Mit etwas Glück mutiert der Skill und erhält einen Baustein, den es in
   keinem Grund-Skill gibt.

Jeder neu entstandene Skill wird in der Welt-Registry gespeichert. Wer die
gleiche Kombination später erneut fusioniert, erhält denselben Skill.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

# --- Bausteine --------------------------------------------------------------

BASE_ELEMENTS = (
    "Physisch", "Feuer", "Eis", "Wasser", "Blitz", "Erde",
    "Wind", "Licht", "Schatten", "Gift", "Blut",
)

# Elementreaktionen: zwei Elemente verschmelzen zu einem neuen.
ELEMENT_REACTIONS: dict[frozenset[str], str] = {
    frozenset({"Feuer", "Eis"}): "Dampf",
    frozenset({"Feuer", "Wasser"}): "Dampf",
    frozenset({"Feuer", "Blitz"}): "Plasma",
    frozenset({"Feuer", "Erde"}): "Magma",
    frozenset({"Feuer", "Wind"}): "Feuersturm",
    frozenset({"Feuer", "Licht"}): "Sonnenglut",
    frozenset({"Eis", "Wind"}): "Blizzard",
    frozenset({"Eis", "Erde"}): "Kristall",
    frozenset({"Wasser", "Erde"}): "Schlamm",
    frozenset({"Wasser", "Blitz"}): "Sturmflut",
    frozenset({"Wasser", "Gift"}): "Säure",
    frozenset({"Blitz", "Wind"}): "Gewitter",
    frozenset({"Erde", "Wind"}): "Sandsturm",
    frozenset({"Licht", "Schatten"}): "Zwielicht",
    frozenset({"Schatten", "Gift"}): "Verderbnis",
    frozenset({"Schatten", "Blut"}): "Nekrose",
    frozenset({"Licht", "Blut"}): "Lebensquell",
    frozenset({"Blitz", "Blut"}): "Raserei",
}

# Gegensätze machen eine Fusion instabil – riskanter, aber stärker.
OPPOSED_ELEMENTS = (
    frozenset({"Feuer", "Eis"}),
    frozenset({"Feuer", "Wasser"}),
    frozenset({"Licht", "Schatten"}),
    frozenset({"Erde", "Wind"}),
)

# Elemente, die durch Reaktion entstehen, bringen eigene Effekte mit.
ELEMENT_EFFECTS: dict[str, tuple[str, ...]] = {
    "Feuer": ("Brennen",),
    "Eis": ("Verlangsamen",),
    "Blitz": ("Betäuben",),
    "Gift": ("Vergiften",),
    "Blut": ("Blutung",),
    "Dampf": ("Blenden",),
    "Plasma": ("Brennen", "Betäuben"),
    "Magma": ("Brennen", "Rückstoß"),
    "Feuersturm": ("Brennen",),
    "Sonnenglut": ("Brennen", "Blenden"),
    "Blizzard": ("Verlangsamen", "Blenden"),
    "Kristall": ("Schild",),
    "Schlamm": ("Verlangsamen",),
    "Sturmflut": ("Betäuben", "Rückstoß"),
    "Säure": ("Rüstungsbruch",),
    "Gewitter": ("Betäuben",),
    "Sandsturm": ("Blenden",),
    "Zwielicht": ("Furcht", "Lebensraub"),
    "Verderbnis": ("Vergiften", "Furcht"),
    "Nekrose": ("Lebensraub", "Blutung"),
    "Lebensquell": ("Heilung",),
    "Raserei": ("Tempo",),
}

FORMS = (
    "Hieb", "Stich", "Wucht", "Geschoss", "Strahl",
    "Aura", "Zone", "Sprung", "Ruf",
)

# Formen verschmelzen zu neuen Formen.
FORM_FUSIONS: dict[frozenset[str], str] = {
    frozenset({"Hieb", "Geschoss"}): "Welle",
    frozenset({"Hieb", "Sprung"}): "Sturzhieb",
    frozenset({"Hieb", "Aura"}): "Klingenwirbel",
    frozenset({"Hieb", "Zone"}): "Rundumschlag",
    frozenset({"Stich", "Geschoss"}): "Lanze",
    frozenset({"Stich", "Sprung"}): "Durchbruch",
    frozenset({"Wucht", "Zone"}): "Beben",
    frozenset({"Wucht", "Sprung"}): "Einschlag",
    frozenset({"Geschoss", "Zone"}): "Regen",
    frozenset({"Geschoss", "Sprung"}): "Komet",
    frozenset({"Strahl", "Zone"}): "Säule",
    frozenset({"Strahl", "Aura"}): "Nova",
    frozenset({"Aura", "Zone"}): "Domäne",
    frozenset({"Ruf", "Zone"}): "Heerruf",
    frozenset({"Ruf", "Aura"}): "Wächtergeist",
}
SAME_FORM_FUSION = {
    "Hieb": "Klingensturm", "Stich": "Stichhagel", "Wucht": "Zermalmer",
    "Geschoss": "Salve", "Strahl": "Doppelstrahl", "Aura": "Überladung",
    "Zone": "Großzone", "Sprung": "Sprungkette", "Ruf": "Chor",
}

# Bausteine, die in keinem Grund-Skill existieren – nur durch Mutation.
MUTATION_ELEMENTS = ("Leere", "Äther", "Chaos", "Zeit", "Seele", "Sternenfeuer")
MUTATION_EFFECTS = (
    "Zeitlupe", "Seelenriss", "Spiegelung", "Kettenreaktion",
    "Echo", "Phasenschritt", "Manaraub",
)
MUTATION_ELEMENT_EFFECTS = {
    "Leere": ("Manaraub",), "Äther": ("Phasenschritt",), "Chaos": ("Kettenreaktion",),
    "Zeit": ("Zeitlupe",), "Seele": ("Seelenriss",), "Sternenfeuer": ("Brennen", "Echo"),
}
ELEMENT_EFFECTS.update(MUTATION_ELEMENT_EFFECTS)

MAX_ELEMENTS = 2
MAX_EFFECTS = 4
MASTERY_REQUIRED = 50   # Meisterschaft (0–100), ab der ein Skill fusionierbar ist


# --- Datenmodell ------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    elements: tuple[str, ...]
    form: str
    effects: tuple[str, ...]
    weapons: tuple[str, ...] = ()       # leer = keine Waffe nötig
    power: float = 10.0
    cost: float = 10.0                  # Stamina/Mana
    cooldown: float = 3.0               # Sekunden
    tier: int = 1
    origin: str = "Grund-Skill"         # Grund-Skill | Rezept | Emergent | Mutation
    parents: tuple[str, ...] = ()

    @property
    def signature(self) -> tuple:
        """Eindeutiger Fingerabdruck der Bausteine (unabhängig vom Namen)."""
        return (
            tuple(sorted(self.elements)),
            self.form,
            tuple(sorted(self.effects)),
            tuple(sorted(self.weapons)),
        )

    def describe(self) -> str:
        weapons = ", ".join(self.weapons) if self.weapons else "keine"
        return (
            f"{self.name} [Stufe {self.tier}, {self.origin}]\n"
            f"  Elemente: {', '.join(self.elements)} | Form: {self.form}\n"
            f"  Effekte:  {', '.join(self.effects)}\n"
            f"  Waffe:    {weapons}\n"
            f"  Kraft {self.power:.0f} · Kosten {self.cost:.0f} · Abklingzeit {self.cooldown:.1f}s"
        )


@dataclass
class FusionResult:
    success: bool
    message: str
    skill: Skill | None = None
    world_first: bool = False
    instability: float = 0.0


@dataclass
class SkillRegistry:
    """Alle Skills der Welt – Grund-Skills, Rezepte und Entdeckungen."""

    skills: dict[str, Skill] = field(default_factory=dict)
    recipes: dict[frozenset[str], Skill] = field(default_factory=dict)
    _by_signature: dict[tuple, str] = field(default_factory=dict)
    # Entdeckte Fusionen pro Elternpaar, damit dieselbe Kombination
    # immer denselben Skill ergibt – auch wenn er mutiert war.
    _fusions: dict[frozenset[str], str] = field(default_factory=dict)
    discoverers: dict[str, str] = field(default_factory=dict)

    def add(self, skill: Skill) -> Skill:
        existing = self._by_signature.get(skill.signature)
        if existing:
            return self.skills[existing]
        self.skills[skill.id] = skill
        self._by_signature[skill.signature] = skill.id
        return skill

    def add_recipe(self, a: str, b: str, result: Skill) -> None:
        self.recipes[frozenset({a, b})] = result

    def get(self, skill_id: str) -> Skill:
        return self.skills[skill_id]

    # --- Fusion -------------------------------------------------------------

    def fuse(
        self,
        a_id: str,
        b_id: str,
        *,
        mastery_a: float,
        mastery_b: float,
        intelligence: int,
        discoverer: str = "Unbekannt",
        rng: random.Random | None = None,
    ) -> FusionResult:
        rng = rng or random.Random()
        if a_id == b_id:
            return FusionResult(False, "Ein Skill kann nicht mit sich selbst fusioniert werden.")
        if min(mastery_a, mastery_b) < MASTERY_REQUIRED:
            return FusionResult(
                False,
                f"Beide Skills brauchen mindestens {MASTERY_REQUIRED} Meisterschaft.",
            )

        a, b = self.get(a_id), self.get(b_id)
        pair = frozenset({a_id, b_id})
        instability = _instability(a, b)

        chance = 0.55 + intelligence * 0.01 + (mastery_a + mastery_b - 2 * MASTERY_REQUIRED) / 250
        chance = max(0.05, min(0.97, chance - instability))
        if rng.random() > chance:
            return FusionResult(
                False,
                "Die Energien stoßen sich ab – die Fusion misslingt. "
                "Du spürst aber, dass du der Lösung näher kommst.",
                instability=instability,
            )

        if pair in self.recipes:
            result = self.add(self.recipes[pair])
        elif pair in self._fusions:
            result = self.skills[self._fusions[pair]]
        else:
            mutation_chance = 0.02 + intelligence * 0.002 + instability * 0.25
            mutate = rng.random() < mutation_chance
            result = self.add(_forge_new_skill(a, b, instability, mutate))
            self._fusions[pair] = result.id

        world_first = result.id not in self.discoverers
        if world_first:
            self.discoverers[result.id] = discoverer
            message = f"Du bist der Erste in der Welt, der „{result.name}“ entdeckt hat!"
        else:
            message = (
                f"Du hast „{result.name}“ erlernt "
                f"(zuerst entdeckt von {self.discoverers[result.id]})."
            )
        return FusionResult(True, message, result, world_first, instability)


# --- Erschaffung neuer Skills -----------------------------------------------

def _instability(a: Skill, b: Skill) -> float:
    value = 0.0
    for ea in a.elements:
        for eb in b.elements:
            if frozenset({ea, eb}) in OPPOSED_ELEMENTS:
                value += 0.15
    if {"Heilung"} & set(a.effects) and {"Vergiften", "Nekrose"} & set(b.effects + b.elements):
        value += 0.1
    if {"Heilung"} & set(b.effects) and {"Vergiften", "Nekrose"} & set(a.effects + a.elements):
        value += 0.1
    return round(min(value, 0.4), 2)


def _combine_elements(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[list[str], int]:
    """Lässt Elemente reagieren. Gibt Elemente und Anzahl Reaktionen zurück."""
    pool = [e for e in dict.fromkeys(a + b) if e != "Physisch"] or ["Physisch"]
    reactions = 0
    changed = True
    while changed:
        changed = False
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                product = ELEMENT_REACTIONS.get(frozenset({pool[i], pool[j]}))
                if product:
                    pool = [e for k, e in enumerate(pool) if k not in (i, j)] + [product]
                    reactions += 1
                    changed = True
                    break
            if changed:
                break
    pool = list(dict.fromkeys(pool))
    if len(pool) > MAX_ELEMENTS:
        # Zu viele Kräfte auf einmal: sie kollabieren zu Chaos.
        pool = [pool[0], "Chaos"]
    return pool, reactions


def _combine_forms(a: Skill, b: Skill) -> str:
    if a.form == b.form:
        return SAME_FORM_FUSION.get(a.form, a.form)
    fused = FORM_FUSIONS.get(frozenset({a.form, b.form}))
    if fused:
        return fused
    stronger = a if a.power >= b.power else b
    return stronger.form


def _combine_weapons(a: Skill, b: Skill) -> tuple[str, ...]:
    return tuple(sorted(set(a.weapons) | set(b.weapons)))


def _seed_for(a: Skill, b: Skill) -> int:
    key = "|".join(sorted((a.id, b.id))).encode()
    return int(hashlib.sha256(key).hexdigest()[:12], 16)


def _forge_new_skill(a: Skill, b: Skill, instability: float, mutate: bool) -> Skill:
    elements, reactions = _combine_elements(a.elements, b.elements)
    form = _combine_forms(a, b)

    # Mutation ist pro Elternpaar festgelegt, damit die Welt konsistent bleibt.
    pair_rng = random.Random(_seed_for(a, b))
    mutation_effect = None
    if mutate:
        mutant = pair_rng.choice(MUTATION_ELEMENTS)
        elements = (elements[:MAX_ELEMENTS - 1] + [mutant])
        mutation_effect = pair_rng.choice(MUTATION_EFFECTS)

    effects: list[str] = []
    for element in elements:
        effects.extend(ELEMENT_EFFECTS.get(element, ()))
    effects.extend(a.effects + b.effects)
    if mutation_effect:
        effects.insert(0, mutation_effect)
    effects = list(dict.fromkeys(effects))
    # Schaden bleibt immer erhalten, wenn ein Elternteil Schaden machte.
    priority = [e for e in effects if e != "Schaden"][: MAX_EFFECTS - 1]
    if "Schaden" in effects:
        priority.insert(0, "Schaden")
    effects = priority[:MAX_EFFECTS]

    synergy = 1.0 + 0.15 * reactions + instability * 0.8 + (0.35 if mutate else 0.0)
    if form not in (a.form, b.form):
        synergy += 0.1
    power = (a.power + b.power) * 0.75 * synergy
    cost = (a.cost + b.cost) * 0.7 * (1 + instability)
    cooldown = max(a.cooldown, b.cooldown) * (1.0 + 0.1 * len(effects))

    name = _generate_name(elements, form, mutation_effect)
    skill_id = "f_" + hashlib.sha1(name.encode()).hexdigest()[:10]
    return Skill(
        id=skill_id,
        name=name,
        elements=tuple(elements),
        form=form,
        effects=tuple(effects),
        weapons=_combine_weapons(a, b),
        power=round(power, 1),
        cost=round(cost, 1),
        cooldown=round(cooldown, 1),
        tier=max(a.tier, b.tier) + 1,
        origin="Mutation" if mutate else "Emergent",
        parents=(a.id, b.id),
    )


_EFFECT_SUFFIX = {
    "Zeitlupe": "der stehenden Zeit", "Seelenriss": "des Seelenrisses",
    "Spiegelung": "der Spiegel", "Kettenreaktion": "der tausend Funken",
    "Echo": "des Widerhalls", "Phasenschritt": "des Phantoms",
    "Manaraub": "der Leere",
}


def _generate_name(elements: list[str], form: str, mutation_effect: str | None) -> str:
    prefix = "-".join(e for e in elements if e != "Physisch")
    name = f"{prefix}-{form}" if prefix else form
    if mutation_effect:
        name += " " + _EFFECT_SUFFIX[mutation_effect]
    return name


# --- Startbestand -----------------------------------------------------------

def default_registry() -> SkillRegistry:
    reg = SkillRegistry()
    base = [
        Skill("schwerthieb", "Schwerthieb", ("Physisch",), "Hieb", ("Schaden",), ("Schwert",), 12, 8, 1.5),
        Skill("axtwurf", "Axtwurf", ("Physisch",), "Geschoss", ("Schaden", "Blutung"), ("Axt",), 14, 10, 4),
        Skill("schildstoss", "Schildstoß", ("Physisch",), "Wucht", ("Schaden", "Rückstoß"), ("Schild",), 8, 8, 5),
        Skill("sprungangriff", "Sprungangriff", ("Physisch",), "Sprung", ("Schaden",), (), 10, 12, 6),
        Skill("dolchstich", "Hinterhältiger Stich", ("Gift",), "Stich", ("Schaden", "Vergiften"), ("Dolch",), 11, 7, 3),
        Skill("schattenschritt", "Schattenschritt", ("Schatten",), "Sprung", ("Tarnung",), (), 4, 15, 10),
        Skill("feuerball", "Feuerball", ("Feuer",), "Geschoss", ("Schaden", "Brennen"), (), 16, 14, 3),
        Skill("frostnova", "Frostnova", ("Eis",), "Zone", ("Schaden", "Verlangsamen"), (), 12, 16, 8),
        Skill("blitzstrahl", "Blitzstrahl", ("Blitz",), "Strahl", ("Schaden", "Betäuben"), (), 15, 15, 5),
        Skill("heiliges_licht", "Heiliges Licht", ("Licht",), "Aura", ("Heilung",), (), 10, 18, 12),
        Skill("erdstoss", "Erdstoß", ("Erde",), "Wucht", ("Schaden", "Rückstoß"), (), 13, 12, 5),
        Skill("windklinge", "Windklinge", ("Wind",), "Hieb", ("Schaden",), (), 11, 9, 2),
        Skill("blutopfer", "Blutopfer", ("Blut",), "Aura", ("Tempo",), (), 6, 0, 20),
        Skill("kriegsschrei", "Kriegsschrei", ("Physisch",), "Ruf", ("Furcht",), (), 5, 10, 15),
    ]
    for skill in base:
        reg.add(skill)

    # Handgemachte Rezepte: besondere Kombinationen mit festem Ergebnis.
    reg.add_recipe("schwerthieb", "feuerball", Skill(
        "flammenschwert", "Flammenklinge", ("Feuer",), "Welle", ("Schaden", "Brennen"),
        ("Schwert",), 26, 18, 3, tier=2, origin="Rezept", parents=("schwerthieb", "feuerball"),
    ))
    reg.add_recipe("schildstoss", "kriegsschrei", Skill(
        "bollwerk", "Unerschütterliches Bollwerk", ("Physisch",), "Wächtergeist",
        ("Schild", "Furcht", "Rückstoß"), ("Schild",), 18, 16, 14, tier=2, origin="Rezept",
        parents=("schildstoss", "kriegsschrei"),
    ))
    return reg
