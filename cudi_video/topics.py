"""Freie Themen ohne Sprachmodell: "die höchsten Wasserfälle Südamerikas" -> Vorgabe.

Der Planer kennt nur Themen, deren Wikidata-Daten wir geprüft haben (Klassen, Eigenschaften,
Filter). Alles andere wird mit einer verständlichen Meldung abgelehnt, statt zu raten.
"""

from __future__ import annotations

import re
import unicodedata

from .sources.wikidata import _sparql


class PlanError(ValueError):
    pass


# --------------------------------------------------------------------------- Wissen über Themen

CLASSES = {
    "countries": {
        "keywords": ["länder", "land", "staaten", "staat", "countries", "country", "nations", "states"],
        "source": {"class": "Q3624078"},
        "plural": {"de": "Länder", "en": "Countries"},
        "props": {"size": "P2046", "population": "P1082"},
        "default": "size",
        "continent_path": "P30", "country_path": None,
        "extras": {"capital": "P36", "continent": "P30"},
        "flags": True,
        "hashtags": ["länder", "geografie"],
    },
    "buildings": {
        "keywords": ["gebäude", "wolkenkratzer", "hochhäuser", "hochhaus", "buildings", "building",
                     "skyscrapers", "skyscraper"],
        "source": {"class": "Q11303", "extra_classes": ["Q18142"], "require_props": ["P1619"]},
        "plural": {"de": "Gebäude", "en": "Buildings"},
        "props": {"height": "P2048"},
        "default": "height",
        "continent_path": "P17/P30", "country_path": "P17",
        "extras": {"country": "P17", "year": "P1619", "floors": "P1101"},
        "hashtags": ["architektur", "wolkenkratzer"],
    },
    "mountains": {
        "keywords": ["berge", "berg", "gipfel", "mountains", "mountain", "peaks"],
        "source": {"class": "Q8502"},
        "plural": {"de": "Berge", "en": "Mountains"},
        "props": {"height": "P2044"},
        "default": "height",
        "continent_path": "P17/P30", "country_path": "P17", "range_path": "P4552/P361*",
        "extras": {"range": "P4552", "country": "P17"},
        "world_min": {"P2044": 7500},
        "hashtags": ["berge", "natur"],
    },
    "lakes": {
        "keywords": ["seen", "see", "lakes", "lake"],
        "source": {"class": "Q23397"},
        "plural": {"de": "Seen", "en": "Lakes"},
        "props": {"size": "P2046", "depth": "P4511"},
        "default": "size",
        "continent_path": "P17/P30", "country_path": "P17",
        "extras": {"basin": "P205"},
        "world_min": {"P2046": 1e10, "P4511": 400},
        "compare": {"P2046": {"de": {"qid": "Q4127", "name": "der Bodensee"},
                              "en": {"qid": "Q6403", "name": "Lake Geneva"}}},
        "hashtags": ["seen", "natur"],
    },
    "islands": {
        "keywords": ["inseln", "insel", "islands", "island"],
        "source": {"class": "Q23442", "extra_classes": ["Q17308006"], "exclude_props": ["P297"]},
        "plural": {"de": "Inseln", "en": "Islands"},
        "props": {"size": "P2046"},
        "default": "size",
        "continent_path": "P17/P30", "country_path": "P17",
        "extras": {"country": "P17"},
        "world_min": {"P2046": 1.5e11},
        "hashtags": ["inseln", "natur"],
    },
    "waterfalls": {
        "keywords": ["wasserfälle", "wasserfall", "waterfalls", "waterfall"],
        "source": {"class": "Q34038"},
        "plural": {"de": "Wasserfälle", "en": "Waterfalls"},
        "props": {"height": "P2048"},
        "default": "height",
        "continent_path": "P17/P30", "country_path": "P17",
        "extras": {"country": "P17"},
        "hashtags": ["wasserfall", "natur"],
    },
}

# Adjektiv-Stämme -> (Eigenschafts-Schlüssel, Reihenfolge)
ADJECTIVES = [
    (r"bevölkerungsreich|einwohnerreich|meisten einwohner|meiste einwohner|most populous|populous|population|einwohner",
     ("population", "desc")),
    (r"höchst|hoechst|höher|hohe|tallest|highest|\btall\b|\bhigh\b", ("height", "desc")),
    (r"tiefst|tiefe|deepest|\bdeep\b", ("depth", "desc")),
    (r"kleinst|kleine|smallest|\bsmall\b|tiniest", ("size", "asc")),
    (r"größt|groesst|grösst|große|largest|biggest|\bbig\b|\blarge\b", ("size", "desc")),
]

PROPERTY_INFO = {
    "P2048": {"unit": "m", "label": {"de": "Höhe", "en": "Height"}},
    "P2044": {"unit": "m", "label": {"de": "Höhe", "en": "Elevation"}},
    "P2046": {"unit": "km2", "label": {"de": "Fläche", "en": "Area"}},
    "P4511": {"unit": "m", "label": {"de": "Tiefe", "en": "Depth"}},
    "P1082": {"unit": None, "label": {"de": "Einwohner", "en": "Population"}},
}

TITLE_ADJ = {
    ("height", "desc"): {"de": "höchsten", "en": {"P2044": "Highest", "default": "Tallest"}},
    ("size", "desc"): {"de": "größten", "en": "Largest"},
    ("size", "asc"): {"de": "kleinsten", "en": "Smallest"},
    ("depth", "desc"): {"de": "tiefsten", "en": "Deepest"},
    ("population", "desc"): {"de": "bevölkerungsreichsten", "en": "Most Populous"},
}

CONTINENTS = [
    (r"nordamerika|north america", ["Q49"], "Nordamerikas", "in North America"),
    (r"südamerika|suedamerika|south america|lateinamerika", ["Q18"], "Südamerikas", "in South America"),
    (r"europa|europe|europäisch", ["Q46"], "Europas", "in Europe"),
    (r"asien|asia\b|asiatisch", ["Q48"], "Asiens", "in Asia"),
    (r"afrika|africa|afrikanisch", ["Q15"], "Afrikas", "in Africa"),
    (r"ozeanien|oceania", ["Q55643", "Q538"], "Ozeaniens", "in Oceania"),
    (r"antarktis|antarktika|antarctica", ["Q51"], "der Antarktis", "in Antarctica"),
]
RANGES = [
    (r"alpen|\balps\b", "Q1286", "der Alpen", "in the Alps"),
    (r"himalaya", "Q5451", "des Himalaya", "in the Himalayas"),
    (r"anden|andes", "Q5456", "der Anden", "in the Andes"),
    (r"rocky mountains|rockies", "Q5463", "der Rocky Mountains", "in the Rocky Mountains"),
]
WORLD = r"\bwelt\b|weltweit|\bworld\b|\berde\b|global"

NUMBER_WORDS = {
    "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "fünfzehn": 15, "zwanzig": 20,
    "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}
STOPWORDS = {"die", "der", "das", "des", "den", "dem", "the", "of", "in", "im", "von", "vom", "auf", "top", "and", "und",
             "mit", "with", "most", "meisten", "meiste", "ranking", "liste", "list", "a", "an", "zu", "nach", "aus",
             "überhaupt", "aller", "zeiten", "heute", "aktuell", "ever", "all", "time", "today", "current", "video",
             "fakten", "facts", "erstelle", "mach", "mache", "über", "about", "zum", "thema"}

# Länder, die im Englischen "the" brauchen
EN_THE = ("United", "Netherlands", "Philippines", "Bahamas", "Maldives", "Gambia", "Czech Republic",
          "Dominican Republic", "Central African Republic", "Democratic Republic", "Republic of the Congo",
          "Marshall Islands", "Solomon Islands", "Comoros", "Seychelles")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text.lower())


def _slug(text: str) -> str:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60] or "thema"


# Gängige Kurzformen, die Wikidata nicht als Alias führt
ALIASES = {
    "usa": "Q30", "us": "Q30", "amerika": "Q30", "america": "Q30",
    "uk": "Q145", "großbritannien": "Q145", "grossbritannien": "Q145", "britain": "Q145", "great britain": "Q145",
    "holland": "Q55", "china": "Q148", "russia": "Q159", "südkorea": "Q884", "south korea": "Q884",
    "nordkorea": "Q423", "north korea": "Q423", "tschechien": "Q213",
}


def _lookup_country(name: str) -> dict | None:
    """Staat per Name/Alias (de/en) finden – liefert QID und Namen."""
    safe = name.replace('"', "").replace("\\", "").strip()
    if len(safe) < 2:
        return None
    alias = ALIASES.get(safe.lower())
    match = (f"VALUES ?c {{ wd:{alias} }}" if alias else
             f'''{{ ?c rdfs:label ?l }} UNION {{ ?c skos:altLabel ?l }}
  FILTER(LANG(?l) IN ("de", "en") && LCASE(STR(?l)) = "{safe.lower()}")''')
    query = f'''SELECT ?c ?de ?en WHERE {{
  ?c wdt:P31 wd:Q3624078 .
  {match}
  OPTIONAL {{ ?c rdfs:label ?de FILTER(LANG(?de) = "de") }}
  OPTIONAL {{ ?c rdfs:label ?en FILTER(LANG(?en) = "en") }}
  FILTER NOT EXISTS {{ ?c wdt:P576 [] }}
}} LIMIT 1'''
    rows = _sparql(query, cache_hours=24 * 30)
    if not rows:
        return None
    b = rows[0]
    return {"qid": b["c"]["value"].rsplit("/", 1)[-1], "de": b.get("de", {}).get("value", name),
            "en": b.get("en", {}).get("value", name)}


def _find_country(words: list[str]) -> tuple[dict, str, str] | None:
    """Längste Wortfolge, die ein Staat ist (auch im Genitiv: 'Deutschlands').

    Gibt (Staat, getippte Wortfolge, gefundener Name ohne Genitiv-s) zurück."""
    for size in (3, 2, 1):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i + size])
            candidates = [phrase]
            if phrase.endswith("es"):
                candidates.append(phrase[:-2])
            if phrase.endswith("s"):
                candidates.append(phrase[:-1])            # Deutschlands -> Deutschland
            for cand in candidates:
                found = _lookup_country(cand)
                if found:
                    return found, phrase, cand
    return None


def _country_display(country: dict, matched: str) -> str:
    """Getippten Namen in schöner Schreibweise: 'usa' -> 'USA', 'deutschland' -> 'Deutschland'."""
    if matched == country["de"].lower():
        return country["de"]
    if matched == country["en"].lower():
        return country["en"]
    return matched.upper() if len(matched) <= 4 else matched.title()


# Übliche englische Kurznamen statt offizieller Langformen
EN_SHORT = {"Q148": "China", "Q30": "the United States", "Q145": "the United Kingdom", "Q884": "South Korea",
            "Q423": "North Korea", "Q159": "Russia", "Q55": "the Netherlands", "Q213": "the Czech Republic"}


# Deutsche Genitivformen für Länder mit Artikel oder üblichem Kurznamen
DE_GENITIVE = {
    "Q30": "der USA", "Q145": "Großbritanniens", "Q148": "Chinas", "Q39": "der Schweiz", "Q43": "der Türkei",
    "Q55": "der Niederlande", "Q711": "der Mongolei", "Q214": "der Slowakei", "Q212": "der Ukraine",
    "Q794": "des Iran", "Q796": "des Irak", "Q1049": "des Sudan", "Q822": "des Libanon", "Q928": "der Philippinen",
    "Q826": "der Malediven", "Q878": "der Vereinigten Arabischen Emirate", "Q884": "Südkoreas", "Q423": "Nordkoreas",
    "Q237": "des Vatikans", "Q805": "des Jemen", "Q657": "des Tschad", "Q974": "der Demokratischen Republik Kongo",
}


def _de_region(country: dict) -> str:
    if country["qid"] in DE_GENITIVE:
        return DE_GENITIVE[country["qid"]]
    name = country["de"]
    return f"von {name}" if name.endswith(("s", "x", "z", "ß")) else f"{name}s"


def _en_country(country: dict) -> str:
    if country["qid"] in EN_SHORT:
        return EN_SHORT[country["qid"]]
    name = country["en"]
    return f"the {name}" if name.startswith(EN_THE) else name


# --------------------------------------------------------------------------- Planer

def supported_topics() -> str:
    return ("Länder (Fläche, Einwohner), Gebäude, Berge, Seen (Fläche, Tiefe), Inseln, Wasserfälle – "
            "weltweit, je Kontinent, je Land oder (Berge) je Gebirge")


def plan_from_text(text: str, count: int | None = None) -> dict:
    """Freitext -> Vorgabe als Dict (wie eine YAML-Vorlage). Wirft PlanError bei Unklarheit."""
    raw = text.strip()
    low = _norm(raw)
    if not low:
        raise PlanError("Bitte ein Thema eingeben.")

    # Anzahl
    n = count
    if n is None:
        m = re.search(r"\b(\d{1,2})\b", low)
        n = int(m.group(1)) if m else next((v for w, v in NUMBER_WORDS.items() if re.search(rf"\b{w}\b", low)), 10)
    n = max(3, min(20, n))

    # Klasse ("Länder"/"states" kann auch Teil eines Ländernamens sein -> andere Themen haben Vorrang)
    matches = [key for key, info in CLASSES.items()
               if any(re.search(rf"\b{re.escape(k)}\b", low) for k in info["keywords"])]
    if len(matches) > 1 and "countries" in matches:
        matches.remove("countries")
    if not matches:
        raise PlanError(f"Thema nicht erkannt. Möglich sind: {supported_topics()}.")
    cls_key = matches[0]
    info = CLASSES[cls_key]

    # Eigenschaft + Reihenfolge
    prop_key, order = info["default"], "desc"
    for pattern, (key, direction) in ADJECTIVES:
        if re.search(pattern, low):
            prop_key, order = key, direction
            break
    if prop_key not in info["props"]:
        possible = ", ".join(sorted(info["props"]))
        raise PlanError(f"Für {info['plural']['de']} kann ich nur nach {possible} sortieren.")
    pid = info["props"][prop_key]

    # Region
    where: dict = {}
    region_de, region_en = "der Welt", "in the World"
    scope = "world"
    for pattern, qids, de, en in CONTINENTS:
        if re.search(pattern, low):
            where[info["continent_path"]] = qids if len(qids) > 1 else qids[0]
            region_de, region_en, scope = de, en, "continent"
            break
    if scope == "world" and info.get("range_path"):
        for pattern, qid, de, en in RANGES:
            if re.search(pattern, low):
                where[info["range_path"]] = qid
                region_de, region_en, scope = de, en, "range"
                break
    vocab = set(info["keywords"]) | STOPWORDS | set(NUMBER_WORDS)
    leftover = [w for w in re.findall(r"[\w'-]+", low) if w not in vocab and not w.isdigit()
                and not any(re.search(p, w) for p, _ in ADJECTIVES) and not re.search(WORLD, w)]
    if scope == "world" and leftover and not info.get("country_path"):
        raise PlanError(f"Region „{' '.join(leftover)}“ passt nicht zu {info['plural']['de']}. "
                        "Möglich: weltweit oder ein Kontinent (z. B. Europa).")
    if scope == "world" and info.get("country_path") and not re.search(WORLD, low):
        words = leftover
        found = _find_country(words) if words else None
        if found:
            country, typed, matched = found
            where[info["country_path"]] = country["qid"]
            if matched == country["en"].lower() and matched != country["de"].lower():
                region_de = _de_region(country)          # englisch getippt -> deutsche Genitivform
            else:
                display = _country_display(country, matched) + ("s" if typed != matched else "")
                m = re.search(rf"((?:in|im|von|der|des|aus)\s+(?:der\s+|den\s+|dem\s+)?)?{re.escape(typed)}", low)
                prefix = (m.group(1) or "") if m else ""
                region_de = f"{prefix}{display}".strip() if (prefix or typed != matched) else _de_region(country)
            region_en = f"in {_en_country(country)}"
            scope = "country"
        elif words and not re.search(WORLD, low):
            raise PlanError(f"Region „{' '.join(words)}“ nicht gefunden. Beispiele: Deutschland, Europa, Alpen.")

    # Titel
    adj = TITLE_ADJ[(prop_key, order)]
    adj_en = adj["en"] if isinstance(adj["en"], str) else adj["en"].get(pid, adj["en"]["default"])
    title_de = f"Die {{count}} {adj['de']} {info['plural']['de']} {region_de}"
    title_en = f"The {{count}} {adj_en} {info['plural']['en']} {region_en}"

    source = {"type": "wikidata", "property": pid, "order": order, **info["source"]}
    if where:
        source["where"] = where
    if scope == "world" and order == "desc" and pid in info.get("world_min", {}):
        source["min_value"] = info["world_min"][pid]     # schnellere Abfrage, Top-Werte liegen sicher darüber
    extras = dict(info["extras"])
    if scope == "country":
        extras = {k: v for k, v in extras.items() if v != "P17"}   # Land steht schon im Titel
    if scope == "continent":
        extras = {k: v for k, v in extras.items() if v != "P30"}   # Kontinent steht schon im Titel
    source["extras"] = extras

    spec = {
        "id": _slug(title_de.replace("{count}", str(n))),
        "title": {"de": title_de, "en": title_en},
        "count": n,
        "value_label": PROPERTY_INFO[pid]["label"],
        "unit": PROPERTY_INFO[pid]["unit"],
        "source": source,
        "hashtags": ["fakten", "ranking", *info["hashtags"]],
    }
    compare = info.get("compare", {}).get(pid)
    if compare:
        spec["compare"] = compare
    if info.get("flags"):
        spec["image_prop"] = "P41"
    return spec
