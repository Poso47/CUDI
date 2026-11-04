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
        "hashtags": {"de": data.get("hashtags", [])[:4]},
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


# --------------------------------------------------------------------------- Claude in der App-Sitzung

CLAUDE_PLAN = (
    "Deute den Video-Wunsch aus „wunsch“ als Ranking: alle Dinge EINER Art (eine Wikidata-Klasse), sortiert nach "
    "EINER Zahl-Eigenschaft aus „eigenschaften“. Antworte mit einem JSON-Objekt: "
    "{\"klasse_qid\": \"Q…\", \"klasse_en\": \"englischer Wikidata-Name der Klasse\", "
    "\"weitere_klassen\": [{\"qid\": \"Q…\", \"en\": \"…\"}] (höchstens 6 wichtige Unterklassen, unter denen "
    "die Spitzenreiter oft eingetragen sind, z. B. Viadukt und Eisenbahnbrücke zu Brücke), \"eigenschaft\": \"P…\", \"reihenfolge\": \"desc\" oder \"asc\", "
    "\"land_qid\": \"Q…\" und \"land_en\": \"…\" (nur wenn auf ein Land begrenzt), "
    "\"kontinent\": \"Europa|Asien|Afrika|Nordamerika|Südamerika|Ozeanien\" (nur wenn auf einen Kontinent begrenzt), "
    "\"spitzenreiter\": [{\"qid\": \"Q…\", \"en\": \"…\"}] (bis zu 12 Einträge, von denen du sicher weißt, dass sie "
    "bei diesem Ranking ganz vorne liegen – z. B. die bekannten Rekordhalter; der Code prüft ihre Werte), "
    "\"titel_de\": \"Die {count} … \", \"titel_en\": \"The {count} …\", \"wert_de\": \"z. B. Länge\", "
    "\"wert_en\": \"z. B. Length\", \"hashtags_de\": [3 Wörter], \"hashtags_en\": [3 words]}. Nimm nur Wikidata-IDs, "
    "bei denen du dir sicher bist – der Code prüft jede ID gegen ihren englischen Namen. Passt der Wunsch nicht zu "
    "einem Zahlen-Ranking, antworte {\"fehler\": \"kurze Erklärung auf Deutsch mit einem passenden Vorschlag\"}."
)


class PlanFailed(ValueError):          # Eingabe passt nicht -> nicht wiederholen
    pass


def _search(label: str) -> str | None:
    """Wikidata-ID zu einem englischen Namen (erster Treffer mit passendem Namen)."""
    from . import net

    variants = list(dict.fromkeys([label, re.sub(r"[‐-―−]", "-", label), re.sub(r"[‐-―−-]", " ", label)]))
    for search in variants:                       # „Changhua–Kaohsiung“ findet die Suche nur mit normalem Bindestrich
        try:
            data = net.get_json("https://www.wikidata.org/w/api.php",
                                params={"action": "wbsearchentities", "search": search, "language": "en",
                                        "type": "item", "limit": 5, "format": "json"}, cache_hours=24 * 7)
        except net.FetchError:
            return None
        for hit in data.get("search", []):
            if _norm(hit.get("label", "")) & _norm(label):
                return hit["id"]
    return None


def _checked_qid(qid, label) -> str | None:
    """ID nur übernehmen, wenn ihr englischer Name zum angegebenen passt – sonst nach dem Namen suchen."""
    label = str(label or "").strip()
    if isinstance(qid, str) and re.fullmatch(r"Q\d+", qid) and label and _norm(_label(qid)) & _norm(label):
        return qid
    return _search(label) if label else None


CONTINENT_QIDS = {"europa": "Q46", "asien": "Q48", "afrika": "Q15", "nordamerika": "Q49", "südamerika": "Q18",
                  "suedamerika": "Q18", "ozeanien": "Q55643"}


def plan_with_claude(topic: str, count: int) -> dict | None:
    """Freies Thema, das der Stichwort-Planer nicht kennt: Claude (Auftrags-Sitzung) deutet es, der Code prüft
    Klasse, Eigenschaft und Region gegen Wikidata. None = Claude nicht verfügbar."""
    from . import handoff
    from .topics import _slug

    props = {pid: name for pid, (name, _) in PROPERTIES.items()}
    answer = handoff.request("planen", CLAUDE_PLAN, {"wunsch": topic, "plaetze": count, "eigenschaften": props})
    if not isinstance(answer, dict):
        return None
    if answer.get("fehler"):
        raise PlanFailed(str(answer["fehler"])[:300])
    pid = answer.get("eigenschaft")
    if pid not in PROPERTIES:
        raise PlanFailed("Zu diesem Wunsch fand sich keine passende Zahl zum Sortieren.")
    cls = _checked_qid(answer.get("klasse_qid"), answer.get("klasse_en"))
    if not cls:
        raise PlanFailed(f"Die Art „{answer.get('klasse_en', '')}“ gibt es bei Wikidata so nicht.")
    extra = [q for q in (_checked_qid(c.get("qid"), c.get("en")) for c in (answer.get("weitere_klassen") or [])[:6]
                         if isinstance(c, dict)) if q and q != cls]
    source = {"type": "wikidata", "class": cls, "property": pid,
              "order": "asc" if answer.get("reihenfolge") == "asc" else "desc",
              "extras": {"country": "P17"}, "min_sitelinks": 2}
    if extra:
        source["extra_classes"] = list(dict.fromkeys(extra))
    seeds = [q for q in (_checked_qid(c.get("qid"), c.get("en")) for c in (answer.get("spitzenreiter") or [])[:12]
                         if isinstance(c, dict)) if q]
    if seeds:
        source["seed_items"] = list(dict.fromkeys(seeds))
    if answer.get("land_en"):
        country = _checked_qid(answer.get("land_qid"), answer.get("land_en"))
        if not country:
            raise PlanFailed(f"Das Land „{answer['land_en']}“ wurde nicht gefunden.")
        source["country"] = country
        source["extras"] = {}
    continent = CONTINENT_QIDS.get(str(answer.get("kontinent") or "").strip().lower())
    if continent and not source.get("country"):
        source["where"] = {"P17/P30": continent}

    def title(key: str, fallback: str) -> str:
        text = re.sub(r"\s+", " ", str(answer.get(key) or fallback)).strip()[:90]
        return text if "{count}" in text else re.sub(r"^(Die|The)\s+", r"\1 {count} ", text, count=1)

    tags = {lang: [re.sub(r"[^\wäöüß]", "", str(t).lower()) for t in (answer.get(f"hashtags_{lang}") or [])[:4]]
            for lang in ("de", "en")}
    title_de = title("titel_de", f"Die {{count}} Plätze: {topic}")
    return {
        "id": _slug(title_de.replace("{count}", str(count)))[:50] or "thema",
        "title": {"de": title_de, "en": title("titel_en", f"The {{count}}: {topic}")},
        "count": count,
        "value_label": {"de": str(answer.get("wert_de") or "")[:30], "en": str(answer.get("wert_en") or "")[:30]},
        "unit": PROPERTIES[pid][1],
        "hashtags": {lang: ["ranking", *[t for t in tags[lang] if t]] for lang in tags},
        "source": source,
        "confirmed_only": True,
    }
