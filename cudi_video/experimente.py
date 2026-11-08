"""Experimente: je Video eine Variante pro Stellschraube – gewählt per Bandit (Thompson Sampling) aus dem Gelernten.

Wunsch des Nutzers: mehrere Wege parallel laufen lassen und dort ausbauen, wo es funktioniert. Stellschrauben sind
Format, Farben (Design), Bewegung, Musik-Stil und Maskottchen (wirken sofort) sowie Hook-Typ und Längenziel
(vorbereitet: `KNOBS[..]["aktiv"]`, bis `retention.py` sie liest – `wunsch("hook")`).

Regeln
- Feste Wünsche im Auftrag (Format, Design, Maskottchen) haben immer Vorrang und zählen nicht als Experiment.
- Mindestens `EXPLORE` (20 %) der Wahlen sind reine Erkundung (gleichverteilt, wie vor den Experimenten).
- Ohne Daten (kein `firma_daten/lernen.json`, keine Bewertungen) bleibt alles bei der Erkundung – genau das alte
  Verhalten (md5 je Video-ID): gleiches Video -> gleiche Wahl, auch nach Neustart und beim Bearbeiten.
- Gelernt wird aus (a) `firma_daten/lernen.json` (Lern-Analyst: YouTube-/TikTok-Zahlen) und (b) den Bewertungen der
  App, die als `vorlieben.varianten_gut/_schlecht` mit dem Auftrag kommen (Env `CUDI_VORLIEBEN_VARIANTEN`).
- Abschaltbar: `CUDI_EXPERIMENTE=0`.
"""

from __future__ import annotations

import hashlib
import json
import os
import random

EXPLORE = 0.2                  # Mindestanteil reiner Erkundung je Wahl
PREF_WEIGHT = 2.0              # eine App-Bewertung zählt wie zwei gemessene Videos (direkter Wunsch des Nutzers)
PREFS_ENV = "CUDI_VORLIEBEN_VARIANTEN"
VARIANT_ENV = "CUDI_VARIANTE_"  # + Stellschraube in Großbuchstaben, z. B. CUDI_VARIANTE_MUSIK

MUSIC_ARMS = ["passend", "pad", "warm", "beat", "pulse"]      # „passend“ = bisherige Wahl nach Videoart/Format/Thema
# aktiv=False: wird erfasst und ausgewertet, sobald das Modul, das sie liest, sie abfragt (retention.py)
KNOBS = {
    "format": {"aktiv": True}, "design": {"aktiv": True}, "bewegung": {"aktiv": True},
    "musik": {"aktiv": True, "arme": MUSIC_ARMS}, "maskottchen": {"aktiv": True, "arme": ["an", "aus"]},
    "hook": {"aktiv": False, "arme": ["frage", "zahl", "kontrast", "behauptung"]},
    "laenge": {"aktiv": False, "arme": ["kurz", "mittel", "lang"]},
}
CURRENT: dict[str, dict] = {}   # Wahlen des laufenden Auftrags: {Stellschraube: {"wahl", "grund"}}


def enabled() -> bool:
    return os.environ.get("CUDI_EXPERIMENTE", "1").strip().lower() not in ("0", "aus", "off", "false", "nein")


def _h(*parts: str) -> int:
    return int(hashlib.md5("".join(parts).encode()).hexdigest(), 16)


# --------------------------------------------------------------------------- Gelerntes

def learned() -> dict:
    """gewichte aus firma_daten/lernen.json: {Stellschraube: {Variante: {"gut": x, "schlecht": y}}}."""
    try:
        from .firma import common
        data = common.read_json("lernen.json", {}) or {}
    except Exception:                                         # noqa: BLE001 – kein Gelerntes = Erkundung
        return {}
    weights = data.get("gewichte")
    return weights if isinstance(weights, dict) else {}


def preference_variants() -> dict:
    try:
        raw = json.loads(os.environ.get(PREFS_ENV) or "{}")
    except ValueError:
        return {}
    return raw if isinstance(raw, dict) else {}


def counts(knob: str, arm: str, weights: dict | None = None, prefs: dict | None = None) -> tuple[float, float]:
    """(gut, schlecht) für eine Variante: Messwerte des Analysten plus App-Bewertungen (schwerer gewichtet)."""
    weights = learned() if weights is None else weights
    prefs = preference_variants() if prefs is None else prefs
    cell = (weights.get(knob) or {}).get(arm) or {}
    good, bad = float(cell.get("gut") or 0), float(cell.get("schlecht") or 0)
    for key, is_good in (("gut", True), ("schlecht", False)):
        for variants in prefs.get(key) or []:
            if isinstance(variants, dict) and variants.get(knob) == arm:
                if is_good:
                    good += PREF_WEIGHT
                else:
                    bad += PREF_WEIGHT
    return good, bad


# --------------------------------------------------------------------------- Wahl

def begin() -> None:
    """Neuer Auftrag: bisherige Wahlen vergessen."""
    CURRENT.clear()


def choose(seed: str, knob: str, arms: list[str], fixed: str = "", legacy: int | None = None) -> str:
    """Variante für `knob` wählen. Gleiche (seed, Gelerntes) -> gleiche Wahl.
    `fixed` = fester Wunsch (Vorrang). `legacy` = Index der früheren md5-Wahl (bleibt die Erkundungs-Wahl)."""
    if not arms:
        return fixed
    if fixed:
        CURRENT[knob] = {"wahl": fixed, "grund": "wunsch"}
        return fixed
    old = arms[(legacy if legacy is not None else _h(seed, knob)) % len(arms)]
    pick, reason = old, "erkundung"
    if enabled():
        weights, prefs = learned(), preference_variants()
        stats = {a: counts(knob, a, weights, prefs) for a in arms}
        has_data = any(g + s > 0 for g, s in stats.values())
        explore = (_h(seed, knob, "erkunden") % 1000) / 1000 < EXPLORE
        if has_data and not explore:
            rng = random.Random(_h(seed, knob, "bandit"))
            samples = {a: rng.betavariate(1 + g, 1 + s) for a, (g, s) in stats.items()}
            pick, reason = max(arms, key=lambda a: (samples[a], -arms.index(a))), "bandit"
    CURRENT[knob] = {"wahl": pick, "grund": reason}
    return pick


def current() -> dict:
    """Ergebnis-Feld `varianten`: {Stellschraube: Variante} plus `_grund` (Erkundung/Bandit/Wunsch je Schraube)."""
    out = {k: v["wahl"] for k, v in CURRENT.items()}
    if out:
        out["_grund"] = {k: v["grund"] for k, v in CURRENT.items()}
    return out


def wunsch(knob: str) -> str:
    """Von anderen Modulen abgefragt (z. B. Hook-Typ): die für diesen Auftrag gewählte Variante oder ''. """
    return os.environ.get(VARIANT_ENV + knob.upper(), "")


def begin_order(order: dict) -> None:
    """Auftragsweite Stellschrauben wählen (Maskottchen, Musik, Hook, Länge) und als Umgebungsvariablen setzen."""
    begin()
    seed = str(order.get("id", ""))
    for knob, spec in KNOBS.items():
        os.environ.pop(VARIANT_ENV + knob.upper(), None)
    if order.get("art") == "reportage":
        return                                               # sachliche Reportage: keine Experimente mit Maskottchen/Musik
    env = os.environ.get("CUDI_MASCOT")
    if order.get("maskottchen") is not None:                # fester Wunsch im Auftrag (job.py hat die Umgebung schon gesetzt)
        CURRENT["maskottchen"] = {"wahl": "an" if order["maskottchen"] else "aus", "grund": "wunsch"}
    elif env is not None and env != _SET["MASCOT"]:         # vom Nutzer selbst gesetzt = fester Wunsch
        CURRENT["maskottchen"] = {"wahl": "aus" if env == "0" else "an", "grund": "wunsch"}
    else:
        _SET["MASCOT"] = "1" if choose(seed, "maskottchen", KNOBS["maskottchen"]["arme"]) == "an" else "0"
        os.environ["CUDI_MASCOT"] = _SET["MASCOT"]
    from .render import audio
    if audio.enabled():
        os.environ[VARIANT_ENV + "MUSIK"] = choose(seed, "musik", KNOBS["musik"]["arme"])
    for knob in ("hook", "laenge"):
        if KNOBS[knob]["aktiv"]:
            os.environ[VARIANT_ENV + knob.upper()] = choose(seed, knob, KNOBS[knob]["arme"])


_SET: dict[str, str | None] = {"MASCOT": None}              # was wir selbst in CUDI_MASCOT geschrieben haben


def end_order() -> None:
    """Auftrag beendet: nur die selbst gesetzte Umgebung entfernen (feste Wünsche des Nutzers bleiben)."""
    if _SET["MASCOT"] is not None and os.environ.get("CUDI_MASCOT") == _SET["MASCOT"]:
        os.environ.pop("CUDI_MASCOT", None)
    _SET["MASCOT"] = None
    os.environ.pop(VARIANT_ENV + "MUSIK", None)


def music_override(kind: str) -> str | None:
    """Musik-Stil dieser Variante (Ranking/Fakten) oder None = bisherige Wahl."""
    if kind not in ("ranking", "numbers", "facts"):
        return None
    value = wunsch("musik")
    return value if value and value != "passend" else None
