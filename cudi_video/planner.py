"""Freies Thema -> Vorgabe (VideoSpec). Braucht ein Sprachmodell.

Das Modell darf nur Eigenschaften aus einer festen Liste wählen. Die vorgeschlagene
Wikidata-Klasse wird gegen Wikidata geprüft (Name muss passen), damit keine
erfundenen IDs durchrutschen.
"""

from __future__ import annotations

import json
import re

from . import llm
from .sources.wikidata import _sparql

# Mengen-Eigenschaften, die sich für Rankings eignen.
PROPERTIES = {
    "P2048": ("height", "m"), "P2044": ("elevation above sea level", "m"), "P2046": ("area", "km2"),
    "P1082": ("population", None), "P2043": ("length", "km"), "P2067": ("mass", "t"),
    "P2052": ("speed", "km/h"), "P4511": ("vertical depth", "m"), "P2049": ("width", "m"),
    "P1083": ("maximum capacity (seats)", None), "P2386": ("diameter", "m"), "P2120": ("radius", "km"),
}

SYSTEM = (
    "You turn a video topic into a Wikidata ranking specification. Answer ONLY with JSON. "
    "Use well-known Wikidata class QIDs you are certain about. If the topic cannot be expressed "
    "as 'all instances of one class sorted by one numeric property', answer {\"error\": \"...\"}."
)


def _label(qid: str) -> str:
    rows = _sparql(f'SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l FILTER(LANG(?l) = "en") }}', cache_hours=24)
    return rows[0]["l"]["value"] if rows else ""


def _norm(s: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]+", s.lower())}


def plan(topic: str, count: int = 10) -> dict:
    if not llm.available():
        raise RuntimeError("Für freie Themen wird ein Sprachmodell benötigt (CUDI_LLM_* setzen). Nutze sonst eine Vorlage.")
    props = "\n".join(f"{pid}: {name}" for pid, (name, _) in PROPERTIES.items())
    user = (
        f"Topic: {topic}\nNumber of places: {count}\n\nAllowed properties:\n{props}\n\n"
        'JSON keys: id (lowercase-slug), title_de, title_en, class_qid, class_label_en, property, '
        'order ("desc"|"asc"), value_label_de, value_label_en, country_qid (optional, only if the '
        'topic is limited to one country), country_label_en (optional), hashtags (list of 3-4 German words).'
    )
    data = llm.chat_json(SYSTEM, user, temperature=0.0)
    if "error" in data:
        raise RuntimeError(f"Thema nicht als Ranking darstellbar: {data['error']}")
    if data.get("property") not in PROPERTIES:
        raise RuntimeError(f"Unzulässige Eigenschaft: {data.get('property')}")
    for key, label_key in (("class_qid", "class_label_en"), ("country_qid", "country_label_en")):
        qid = data.get(key)
        if not qid:
            continue
        if not re.fullmatch(r"Q\d+", qid):
            raise RuntimeError(f"Ungültige ID {qid}")
        real = _label(qid)
        if not (_norm(real) & _norm(data.get(label_key, ""))):
            raise RuntimeError(f"Wikidata-ID {qid} heißt '{real}', nicht '{data.get(label_key)}' – bitte Vorlage nutzen.")
    unit = PROPERTIES[data["property"]][1]
    spec = {
        "id": re.sub(r"[^a-z0-9-]+", "-", data.get("id", "thema").lower()).strip("-")[:50] or "thema",
        "title": {"de": data["title_de"], "en": data["title_en"]},
        "count": count,
        "value_label": {"de": data.get("value_label_de", ""), "en": data.get("value_label_en", "")},
        "unit": unit,
        "hashtags": data.get("hashtags", [])[:4],
        "source": {
            "type": "wikidata", "class": data["class_qid"], "property": data["property"],
            "order": data.get("order", "desc"), "extras": {"country": "P17"},
        },
    }
    if data.get("country_qid"):
        spec["source"]["country"] = data["country_qid"]
    return spec


def describe(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2)
