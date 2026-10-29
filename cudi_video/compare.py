"""Belegte Vergleiche: "Das ist rund 5-mal so hoch wie der Kölner Dom."

Der Vergleichswert wird live aus Wikidata geholt (und wie die Ranking-Werte mit
unabhängigen Quellen abgeglichen); das Verhältnis wird nur berechnet – nichts wird geschätzt.
Die Sätze beziehen sich auf den zuvor genannten Wert ("Das ist …"), damit sie für jeden
Namen grammatisch korrekt sind (kein Artikel-Problem wie bei "Vereinigte Staaten ist …").
"""

from __future__ import annotations

import logging

from .models import RankItem
from .spec import VideoSpec
from .units import fmt_number

log = logging.getLogger(__name__)

# Standard-Vergleichsobjekte je Eigenschaft und Sprache: (QID, Name im Nominativ, Ortsform)
DEFAULT_REFS: dict[str, dict[str, dict]] = {
    "P2046": {"de": {"qid": "Q183", "name": "Deutschland"}, "en": {"qid": "Q145", "name": "the UK"}},
    "P1082": {"de": {"qid": "Q183", "name": "Deutschland", "in": "in Deutschland"},
              "en": {"qid": "Q145", "name": "the UK", "in": "in the UK"}},
    "P2048": {"de": {"qid": "Q4176", "name": "der Kölner Dom"}, "en": {"qid": "Q243", "name": "the Eiffel Tower"}},
    "P2044": {"de": {"qid": "Q3375", "name": "die Zugspitze"}, "en": {"qid": "Q583", "name": "Mont Blanc"}},
    "P4511": {"de": {"qid": "Q49650", "name": "Loch Ness"}, "en": {"qid": "Q49650", "name": "Loch Ness"}},
    "P1083": {"de": {"qid": "Q150928", "name": "der Signal Iduna Park"},
              "en": {"qid": "Q128468", "name": "Wembley Stadium"}},
}

# Satzmuster: times/pct/same sind Satz-Fragmente, die an den Wert angehängt werden
# ("Fläche: 2,7 Millionen Quadratkilometer – 7,6-mal so groß wie Deutschland."),
# inv ist ein eigener Satz für den Fall, dass das Vergleichsobjekt größer ist.
PHRASES = {
    "de": {
        "P2046": {"times": "{r}-mal so groß wie {ref}", "pct": "{p} Prozent größer als {ref}",
                  "same": "etwa so groß wie {ref}", "half": "etwa halb so groß wie {ref}", "inv": "Zum Vergleich: {Ref} ist {r}-mal so groß."},
        "P2048": {"times": "{r}-mal so hoch wie {ref}", "pct": "{p} Prozent höher als {ref}",
                  "same": "etwa so hoch wie {ref}", "half": "etwa halb so hoch wie {ref}", "inv": "Zum Vergleich: {Ref} ist {r}-mal so hoch."},
        "P2044": {"times": "{r}-mal so hoch wie {ref}", "pct": "{p} Prozent höher als {ref}",
                  "same": "etwa so hoch wie {ref}", "half": "etwa halb so hoch wie {ref}", "inv": "Zum Vergleich: {Ref} ist {r}-mal so hoch."},
        "P4511": {"times": "{r}-mal so tief wie {ref}", "pct": "{p} Prozent tiefer als {ref}",
                  "same": "etwa so tief wie {ref}", "half": "etwa halb so tief wie {ref}", "inv": "Zum Vergleich: {Ref} ist {r}-mal so tief."},
        "P1082": {"times": "{r}-mal so viele wie {ref_in}", "pct": "{p} Prozent mehr als {ref_in}",
                  "same": "etwa so viele wie {ref_in}", "half": "etwa halb so viele wie {ref_in}", "inv": "Zum Vergleich: {Ref_in} leben {r}-mal so viele Menschen."},
        "P1083": {"times": "{r}-mal so viele wie im {ref_short}", "pct": "{p} Prozent mehr als im {ref_short}",
                  "same": "etwa so viele wie im {ref_short}", "half": "etwa halb so viele wie im {ref_short}", "inv": "Zum Vergleich: {Ref} hat {r}-mal so viele Plätze."},
    },
    "en": {
        "P2046": {"times": "{r} times the size of {ref}", "pct": "{p} percent bigger than {ref}",
                  "same": "about the size of {ref}", "half": "about half the size of {ref}", "inv": "For comparison: {Ref} is {r} times bigger."},
        "P2048": {"times": "{r} times as tall as {ref}", "pct": "{p} percent taller than {ref}",
                  "same": "about as tall as {ref}", "half": "about half as tall as {ref}", "inv": "For comparison: {Ref} is {r} times taller."},
        "P2044": {"times": "{r} times as high as {ref}", "pct": "{p} percent higher than {ref}",
                  "same": "about as high as {ref}", "half": "about half as high as {ref}", "inv": "For comparison: {Ref} is {r} times higher."},
        "P4511": {"times": "{r} times as deep as {ref}", "pct": "{p} percent deeper than {ref}",
                  "same": "about as deep as {ref}", "half": "about half as deep as {ref}", "inv": "For comparison: {Ref} is {r} times deeper."},
        "P1082": {"times": "{r} times as many people as {ref_in}", "pct": "{p} percent more people than {ref_in}",
                  "same": "about as many people as {ref_in}", "half": "about half as many people as {ref_in}",
                  "inv": "For comparison: {Ref_in}, there are {r} times as many people."},
        "P1083": {"times": "{r} times the capacity of {ref}", "pct": "{p} percent more seats than {ref}",
                  "same": "about the capacity of {ref}", "half": "about half the capacity of {ref}", "inv": "For comparison: {Ref} holds {r} times as many."},
    },
}


def load_references(spec: VideoSpec) -> dict[str, dict]:
    """Vergleichsobjekte je Sprache holen; Werte wie die Ranking-Werte abgleichen."""
    from .sources.wikidata import fetch_identifiers, fetch_item_value
    from .verify import checkers_for, verify_item

    refs: dict[str, dict] = {}
    for lang in spec.langs:
        cfg = reference_config(spec, lang)
        if not cfg:
            continue
        try:
            item = fetch_item_value(cfg["qid"], spec.source.property)
            if item is None:
                log.warning("Vergleichsobjekt %s hat keinen Wert für %s", cfg["qid"], spec.source.property)
                continue
            fetch_identifiers([item], [])
            result = verify_item(spec, item, checkers_for(spec, with_wikipedia=False))
        except Exception as exc:   # Vergleich ist optional
            log.warning("Vergleichsobjekt %s nicht verfügbar: %s", cfg["qid"], exc)
            continue
        refs[lang] = {**cfg, "value": item.value, "unit": item.unit, "date": item.value_date,
                      "status": result["status"], "sources": result["sources"],
                      "url": f"https://www.wikidata.org/wiki/{cfg['qid']}"}
    return refs


def reference_config(spec: VideoSpec, lang: str) -> dict | None:
    custom = (spec.compare or {}).get(lang)
    if custom == "none" or (spec.compare or {}).get("off"):
        return None
    return custom or DEFAULT_REFS.get(spec.source.property, {}).get(lang)


def _factor(r: float, lang: str) -> str:
    """2.54 -> '2,5'; 27.48 -> '27,5'; 47.7 -> 'rund 48' (en: 'about 48')."""
    if r >= 30:
        rounded = round(r)
        text = fmt_number(rounded, lang, 0)
        exact = abs(r - rounded) / r < 0.002
        return text if exact else (f"rund {text}" if lang == "de" else f"about {text}")
    text = fmt_number(r, lang, 1)
    return text.removesuffix(",0").removesuffix(".0")


def _short(name: str) -> str:
    """'der Kölner Dom' -> 'Kölner Dom', 'the UK' -> 'UK'."""
    for article in ("der ", "die ", "das ", "the "):
        if name.lower().startswith(article):
            return name[len(article):]
    return name


def comparison(item: RankItem, ref: dict | None, prop: str, lang: str) -> dict | None:
    """Vergleich als {"kind": fragment|sentence, "text": …, "chip": …} oder None.

    fragment = wird an den Wert angehängt, sentence = eigener Satz, chip = Kurzform fürs Bild."""
    if not ref or not ref.get("value") or item.qid == ref.get("qid") or item.unit != ref.get("unit"):
        return None
    patterns = PHRASES.get(lang, {}).get(prop)
    if not patterns:
        return None
    r = abs(item.value) / abs(ref["value"])
    if r > 1000 or r < 0.001:
        return None   # "13.650-mal so groß" ist nicht mehr anschaulich
    name = ref["name"]
    loc = ref.get("in", name)
    short = ref.get("short") or _short(name)
    fields = {
        "ref": name, "Ref": name[:1].upper() + name[1:],
        "ref_in": loc, "Ref_in": loc[:1].upper() + loc[1:],
        "ref_short": short,
    }
    if r >= 1.95:
        factor = _factor(r, lang)
        number = factor.split(" ")[-1]
        return {"kind": "fragment", "text": patterns["times"].format(r=factor, **fields), "chip": f"{number}× {short}"}
    if r >= 1.05:
        p = round((r - 1) * 100)
        return {"kind": "fragment", "text": patterns["pct"].format(p=p, **fields), "chip": f"+{p} % vs. {short}"}
    if r > 0.95:
        return {"kind": "fragment", "text": patterns["same"].format(**fields), "chip": f"≈ {short}"}
    if 0.42 <= r <= 0.58:
        return {"kind": "fragment", "text": patterns["half"].format(**fields), "chip": f"≈ ½ {short}"}
    # Vergleichsobjekt ist größer: "Zum Vergleich: Der Kölner Dom ist 1,6-mal so hoch."
    return {"kind": "sentence", "text": patterns["inv"].format(r=_factor(1 / r, lang), **fields), "chip": None}
