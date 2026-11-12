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
    "Du bist Redakteur eines Fakten-Kanals für TikTok/YouTube Shorts. „wunsch“ ist oft nur ein einfacher Satz oder "
    "ein Stichwort („mach was über Berge“, „riesige Schiffe“, „Video über Wüsten in Afrika“). Denke mit: Was will "
    "die Person sehen, und welcher EINDEUTIG MESSBARE Blickwinkel daraus ist am spannendsten? Nicht messbare Wünsche "
    "(„gefährlichste“, „schönste“, „berühmteste“) übersetzt du in die nächstliegende messbare Zahl (z. B. Höhe, Länge, "
    "Fläche, Tiefe, Einwohner, Geschwindigkeit, Kapazität) und nennst sie im Titel ehrlich. Nennt der Wunsch eine "
    "Anzahl („Top 7“, „fünf“), gib sie als „anzahl“ zurück. Der Titel soll neugierig machen, konkret und kurz sein "
    "(höchstens 50 Zeichen) und darf nichts versprechen, was die Zahl nicht zeigt. "
    "Deute den Video-Wunsch als Ranking: alle Dinge EINER Art (eine Wikidata-Klasse), sortiert nach "
    "EINER Zahl-Eigenschaft aus „eigenschaften“. Antworte mit einem JSON-Objekt: "
    "{\"blickwinkel\": \"ein Satz: was du daraus machst und warum\", \"anzahl\": Zahl oder null, "
    "\"themenkern_de\": \"die eigentliche Zuschauerfrage hinter dem Wunsch\", \"themenkern_en\": \"…\", "
    "\"aspekte\": [3–6 Unterthemen als kurze Stichworte mit 1–3 Wörtern, z. B. „Priming“, „Gewohnheiten“], "
    "\"nicht_gemeint\": [Randthemen, die nicht "
    "gefragt sind, z. B. Begriffsgeschichte], "
    "{\"klasse_qid\": \"Q…\", \"klasse_en\": \"englischer Wikidata-Name der Klasse\", "
    "\"weitere_klassen\": [{\"qid\": \"\", \"en\": \"…\"}] (2–6 wichtige Unterklassen, unter denen "
    "die Spitzenreiter oft eingetragen sind, z. B. viaduct und railway bridge zu bridge), \"eigenschaft\": \"P…\", \"reihenfolge\": \"desc\" oder \"asc\", "
    "\"land_qid\": \"Q…\" und \"land_en\": \"…\" (nur wenn auf ein Land begrenzt), "
    "\"kontinent\": \"Europa|Asien|Afrika|Nordamerika|Südamerika|Ozeanien\" (nur wenn auf einen Kontinent begrenzt), "
    "\"spitzenreiter\": [{\"qid\": \"\", \"en\": \"…\"}] (WICHTIG: 5–12 Einträge, die nach deinem Wissen bei diesem "
    "Ranking ganz vorne liegen – z. B. die bekannten Rekordhalter; der Code prüft ihre Werte mit unabhängigen Quellen), "
    "\"titel_de\": \"Die {count} … \", \"titel_en\": \"The {count} …\", \"wert_de\": \"z. B. Länge\", "
    "\"wert_en\": \"z. B. Length\", \"hashtags_de\": [3 Wörter], \"hashtags_en\": [3 words]}. Bei „qid“ nur IDs, "
    "bei denen du dir sicher bist, sonst leer lassen – der englische Name (wie in der englischen Wikipedia) reicht, "
    "der Code sucht und prüft die ID selbst. "
    "JEDES Thema lässt sich ranken: Passt der Wunsch NICHT zu einem Zahlen-Ranking (z. B. „5 coole Fakten über das "
    "Unterbewusstsein“, „Gründe, warum …“, „Mythen über …“, „unglaubliche Fakten über Haie“), antworte als "
    "Fakten-Ranking: {\"art\": \"fakten\", \"blickwinkel\": \"…\", \"anzahl\": Zahl oder null, "
    "\"themenkern_de\": \"…\", \"themenkern_en\": \"…\", \"aspekte\": […], \"nicht_gemeint\": […] (wie oben), "
    "\"artikel_de\": [2–4 Titel deutscher Wikipedia-Artikel – je Aspekt ein SPEZIFISCHER Fachartikel über ein "
    "Phänomen oder einen Mechanismus (z. B. zu „Unterbewusstsein“: Priming, Implizites Gedächtnis, Gewohnheit, "
    "Intuition) statt nur des Oberbegriffs], \"artikel_en\": [2–4 Titel englischer Wikipedia-Artikel, ebenso], \"kriterium_de\": \"z. B. verblüffendste\", "
    "\"kriterium_en\": \"z. B. most surprising\", \"titel_de\": \"Die {count} verblüffendsten Fakten über …\", "
    "\"titel_en\": \"The {count} most surprising facts about …\", \"hashtags_de\": [3 Wörter], "
    "\"hashtags_en\": [3 words]}. Nur wenn ein Wunsch gar nicht umsetzbar ist (z. B. verletzend oder ohne jede "
    "Faktengrundlage), antworte {\"fehler\": \"kurze Erklärung auf Deutsch mit einem passenden Vorschlag\"}."
)


from .themen import parse_focus  # noqa: E402


class PlanFailed(ValueError):          # Eingabe passt nicht -> nicht wiederholen
    pass


CLAUDE_SEEDS = (
    "Für ein Ranking-Video fehlen noch die bekannten Spitzenreiter. Nenne 5–12 Einträge, die nach deinem Wissen bei "
    "diesem Ranking („wunsch“: Art „art“, sortiert nach „eigenschaft“, Richtung „reihenfolge“, Region „region“) ganz "
    "vorne liegen – nur die englischen Namen wie in der englischen Wikipedia, keine Zahlen. Antwort: "
    "{\"spitzenreiter\": [\"Name 1\", \"Name 2\"]}. Der Code sucht die Einträge bei Wikidata und prüft ihre Werte "
    "mit unabhängigen Quellen – ein falscher Name schadet also nicht."
)


def _seed_names(answer) -> list[tuple[str, str]]:
    """(qid, englischer Name) aus Objekten {"qid","en"} oder reinen Namen."""
    out = []
    for c in (answer or [])[:12]:
        if isinstance(c, dict):
            out.append((c.get("qid") or "", str(c.get("en") or "")))
        elif isinstance(c, str):
            out.append(("", c))
    return [(q, n.strip()) for q, n in out if n.strip()]


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


FACTS_ONLY = (" WICHTIG: Der Auftrag ist ausdrücklich ein FAKTEN-Ranking. Antworte IMMER mit dem Fakten-Format "
              "(\"art\": \"fakten\" …), nie mit einem Zahlen-Ranking.")


_SUPERLATIVE = re.compile(r"\b(verblüffendsten|erstaunlichsten|überraschendsten|faszinierendsten|spannendsten|krassesten|"
                          r"unglaublichsten|interessantesten|beeindruckendsten|besten|(?:most|top)\s+(?:surprising|amazing|"
                          r"astonishing|fascinating|interesting|incredible|impressive)|best)\s+", re.I)


def neutral_title(text: str) -> str:
    """Titel ohne Superlative („Die 3 verblüffendsten Fakten“ -> „Die 3 Fakten“): Der Wahrheits-Prüfer lehnt Wertungen
    ab, die der Beleg nicht stützt – im Notbetrieb liest ein freies Modell gegen, das hier strenger urteilt."""
    return re.sub(r"\s{2,}", " ", _SUPERLATIVE.sub("", text or "")).strip()


def plan_facts(topic: str, count: int) -> dict:
    """Auftrag „fakten“: Fakten-Ranking zu einem freien Thema. Claude bzw. das freie Sprachmodell wählt die Fachartikel;
    ohne Antwort gilt das Thema selbst als Artikelsuche (facts.gather_sources prüft jeden Titel bei Wikipedia)."""
    from . import handoff

    answer = handoff.request("planen_fakten", CLAUDE_PLAN + FACTS_ONLY,
                             {"wunsch": topic, "plaetze": count, "eigenschaften": {}})
    if isinstance(answer, dict) and answer.get("fehler"):
        raise PlanFailed(str(answer["fehler"])[:300])
    if isinstance(answer, dict) and answer.get("art") == "fakten":
        try:
            return _fact_plan(topic, count, {**answer, "anzahl": count})
        except PlanFailed:
            pass
    return _fact_plan(topic, count, {"artikel_de": [topic], "artikel_en": [topic], "anzahl": count})


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
    if answer.get("art") == "fakten":
        return _fact_plan(topic, count, answer)
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
    named = _seed_names(answer.get("spitzenreiter"))
    if not named:                                 # vergessen? einmal gezielt nachfragen (nur Namen)
        region = answer.get("land_en") or answer.get("kontinent") or "world"
        extra_answer = handoff.request("spitzenreiter", CLAUDE_SEEDS, {
            "wunsch": topic, "art": answer.get("klasse_en"), "eigenschaft": PROPERTIES[pid][0],
            "reihenfolge": source["order"], "region": region})
        named = _seed_names(extra_answer.get("spitzenreiter") if isinstance(extra_answer, dict) else extra_answer)
    seeds = [q for q in (_checked_qid(qid, name) for qid, name in named) if q]
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
        if "{count}" in text:
            return text
        if re.match(r"^(Die|The|Top)\s+\d+\b", text):          # „Die 5 längsten …“ -> Zahl durch {count} ersetzen
            return re.sub(r"^(Die|The|Top)\s+\d+", r"\1 {count}", text, count=1)
        return re.sub(r"^(Die|The)\s+", r"\1 {count} ", text, count=1)

    tags = {lang: [re.sub(r"[^\wäöüß]", "", str(t).lower()) for t in (answer.get(f"hashtags_{lang}") or [])[:4]]
            for lang in ("de", "en")}
    title_de = title("titel_de", f"Die {{count}} Plätze: {topic}")
    wanted = answer.get("anzahl")
    if isinstance(wanted, int) and 3 <= wanted <= 30:       # „Top 7 …“ im Wunsch hat Vorrang vor der Einstellung
        count = wanted
    return {
        "id": _slug(title_de.replace("{count}", str(count)))[:50] or "thema",
        "title": {"de": title_de, "en": title("titel_en", f"The {{count}}: {topic}")},
        "count": count,
        "value_label": {"de": str(answer.get("wert_de") or "")[:30], "en": str(answer.get("wert_en") or "")[:30]},
        "unit": PROPERTIES[pid][1],
        "hashtags": {lang: ["ranking", *[t for t in tags[lang] if t]] for lang in tags},
        "source": source,
        "confirmed_only": True,
        "angle": str(answer.get("blickwinkel") or "")[:300],
        "focus": parse_focus(answer),     # Claudes Deutung – steht im Prüfbericht
    }


def _fact_plan(topic: str, count: int, answer: dict) -> dict:
    """Fakten-Ranking: Artikeltitel werden erst beim Laden geprüft (facts.gather_sources), Titel/Anzahl wie oben."""
    from .topics import _slug

    articles = {lang: [str(t)[:120] for t in (answer.get(f"artikel_{lang}") or [])[:4] if str(t).strip()]
                for lang in ("de", "en")}
    if not any(articles.values()):
        raise PlanFailed("Zu diesem Wunsch fanden sich keine passenden Fachartikel.")
    wanted = answer.get("anzahl")
    if isinstance(wanted, int) and 3 <= wanted <= 30:
        count = wanted

    def title(key: str, fallback: str) -> str:
        text = re.sub(r"\s+", " ", str(answer.get(key) or fallback)).strip()[:90]
        if "{count}" in text:
            return text
        return re.sub(r"^(Die|The|Top)\s+\d+", r"\1 {count}", text, count=1) if re.match(r"^(Die|The|Top)\s+\d+", text) \
            else re.sub(r"^(Die|The)\s+", r"\1 {count} ", text, count=1)

    title_de = title("titel_de", f"Die {{count}} verblüffendsten Fakten: {topic}")
    tags = {lang: [re.sub(r"[^\wäöüß]", "", str(t).lower()) for t in (answer.get(f"hashtags_{lang}") or [])[:4]]
            for lang in ("de", "en")}
    return {
        "id": _slug(title_de.replace("{count}", str(count)))[:50] or "fakten",
        "title": {"de": title_de, "en": title("titel_en", f"The {{count}} most surprising facts: {topic}")},
        "count": count,
        "kind": "facts",
        "facts": {"articles": articles, "criterion": {"de": str(answer.get("kriterium_de") or "verblüffendste")[:40],
                                                      "en": str(answer.get("kriterium_en") or "most surprising")[:40]}},
        "source": {"type": "wikidata", "class": "Q0", "property": "P0"},   # Zahlen-Quelle hier unbenutzt
        "hashtags": {lang: ["fakten" if lang == "de" else "facts", *[t for t in tags[lang] if t]] for lang in tags},
        "angle": str(answer.get("blickwinkel") or "")[:300],
        "focus": parse_focus(answer),
    }
