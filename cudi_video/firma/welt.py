"""Welt-Blick: Wie berichten ausländische Medien über Deutschland? -> firma_daten/welt.json.

Quellen: RSS ausländischer Medien (jede einzeln abgesichert; `art: "staatsnah"` kennzeichnet staatlich getragene Sender,
kein RT/Sputnik – EU-sanktioniert) und GDELT (Artikel über Germany, deutsche Quellen herausgefiltert). Nur Titel, Kurzzeile, Link.
Abgleich mit news.json (deutsche Medien): `nur_ausland` = im Ausland >= 2 Betreiber, in Deutschland keine passende Meldung.
Belegte Verbindungen nur aus Wikidata (jede mit Link, max. 5 neue Abfragen je Lauf, zwischengespeichert).
Keine Deutung: was nicht belegt ist, wird hier nicht behauptet."""

from __future__ import annotations

import re
import time
from datetime import timedelta

from .. import eigentuemer as eig
from . import common, news
from .common import fetch, iso, now, run_source

MAX_AGE_H = 48
MAX_GROUPS = 40
MAX_LOOKUPS = 5
# (Name, Betreiber, Sprache, Land, Art, Adresse)
FEEDS = [
    ("BBC Europe", "bbc", "en", "Großbritannien", "öffentlich-rechtlich", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    ("Guardian Germany", "guardian", "en", "Großbritannien", "privat", "https://www.theguardian.com/world/germany/rss"),
    ("Al Jazeera", "aljazeera", "en", "Katar", "staatsnah", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("France 24", "france24", "en", "Frankreich", "staatsnah", "https://www.france24.com/en/europe/rss"),
    ("Le Monde (en)", "lemonde", "en", "Frankreich", "privat", "https://www.lemonde.fr/en/international/rss_full.xml"),
    ("El País", "elpais", "es", "Spanien", "privat", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
    ("NZZ", "nzz", "de", "Schweiz", "privat", "https://www.nzz.ch/recent.rss"),
    ("Der Standard", "derstandard", "de", "Österreich", "privat", "https://www.derstandard.at/rss"),
    ("Anadolu", "aa", "en", "Türkei", "staatsnah", "https://www.aa.com.tr/en/rss/default?cat=world"),
    ("Dawn", "dawn", "en", "Pakistan", "privat", "https://www.dawn.com/feeds/home"),
    ("SCMP", "scmp", "en", "Hongkong/China", "privat", "https://www.scmp.com/rss/4/feed"),
    ("Times of India", "timesofindia", "en", "Indien", "privat", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),
    # bewusst auch ferne, unbeteiligte Länder (kein eigener Bezug zu den meisten Meldungen)
    ("The Hindu", "thehindu", "en", "Indien", "privat", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("Rappler", "rappler", "en", "Philippinen", "privat", "https://www.rappler.com/feed/"),
    ("Philstar", "philstar", "en", "Philippinen", "privat", "https://www.philstar.com/rss/world"),
    ("Daily Nation", "nation", "en", "Kenia", "privat", "https://nation.africa/kenya/rss.xml"),
    ("Punch", "punchng", "en", "Nigeria", "privat", "https://punchng.com/feed/"),
    ("Daily Maverick", "dailymaverick", "en", "Südafrika", "privat", "https://www.dailymaverick.co.za/dmrss/"),
    ("Post-Courier", "postcourier", "en", "Papua-Neuguinea", "privat", "https://postcourier.com.pg/feed/"),
    ("La Nación", "lanacion", "es", "Argentinien", "privat", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/"),
    ("Agência Brasil", "agenciabrasil", "pt", "Brasilien", "staatsnah", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
]
MIN_LAENDER = 3                       # „übereinstimmend bestätigt“ = Medien aus >= 3 verschiedenen, nicht beteiligten Ländern
# Länder, die in einer Meldung selbst vorkommen (Namen/Adjektive de/en/es/fr/pt/id) -> deren Medien sind „beteiligt“
LAND_WORTE = {
    "Großbritannien": "britain|british|uk|england|english|großbritannien|britisch|reino unido|británic|royaume-uni|britannique|inggris",
    "Katar": "qatar|katar|qatari|catar|qatarien",
    "Frankreich": "france|french|frankreich|französisch|francia|francés|français|prancis",
    "Spanien": "spain|spanish|spanien|spanisch|españa|español|espagne|espagnol|spanyol",
    "Schweiz": "switzerland|swiss|schweiz|schweizer|suiza|suizo|suisse|swiss",
    "Österreich": "austria|austrian|österreich|österreichisch|austriaco|autriche|autrichien",
    "Türkei": "turkey|turkish|türkei|türkisch|turquía|turco|turquie|turc|turki|türkiye",
    "Pakistan": "pakistan|pakistani|pakistanisch|paquistán|pakistanais",
    "Hongkong/China": "china|chinese|chinesisch|hong kong|hongkong|beijing|peking|chino|chine|chinois|tiongkok",
    "Indien": "india|indian|indien|indisch|inde|indien|indian",
    "Philippinen": "philippines|philippine|filipino|philippinen|filipinas|philippines|filipina",
    "Kenia": "kenya|kenyan|kenia|kenianisch",
    "Nigeria": "nigeria|nigerian|nigerianisch",
    "Südafrika": "south africa|südafrika|südafrikanisch|sudáfrica|afrique du sud|afrika selatan",
    "Papua-Neuguinea": "papua new guinea|papua-neuguinea|papúa nueva guinea|papouasie",
    "Argentinien": "argentina|argentine|argentinien|argentinisch|argentino|argentin",
    "Brasilien": "brazil|brazilian|brasilien|brasilianisch|brasil|brasileño|brésil|brasileiro|brasil",
    "Indonesien": "indonesia|indonesian|indonesien|indonesisch|indonésie|indonesio",
    "Paraguay": "paraguay|paraguayan|paraguayisch|paraguayo",
    "Russland": "russia|russian|russland|russisch|rusia|ruso|russie|russe",
    "Ukraine": "ukraine|ukrainian|ukraine|ukrainisch|ucrania|ucraniano",
    "USA": "united states|american|usa|u\\.s\\.|vereinigte staaten|amerikanisch|estados unidos|états-unis",
    "Israel": "israel|israeli|israelisch|israélien",
    "Iran": "iran|iranian|iranisch|irán|iraní",
}
_LAND_RE = {k: re.compile(r"\b(?:" + v + r")\b", re.I) for k, v in LAND_WORTE.items()}
_GDELT_LANG = {"portuguese": "pt", "english": "en", "german": "de", "french": "fr", "spanish": "es", "italian": "it", "turkish": "tr"}
DE_WORDS = re.compile(
    r"\b(germany|german|germans|deutschland|allemagne|allemand|allemands|alemania|alemán|alemana|alemanes|germania|tedesco|"
    r"almanya|alman|berlin|berlín|bundestag|bundesregierung|bundeskanzler|bundeswehr|bundesrat|merz|scholz|"
    r"berliner|alemanha|alemão|alemã)\b", re.I)
_GENERIC = {"germany", "german", "deutschland", "allemagne", "alemania", "germania", "almanya", "berlin", "berlín",
            "europe", "europa", "union", "state", "states", "united", "news", "live", "says", "year", "country"}
_NOT_NAME = set("""The This That These Those New Old After Before Over Under Why How What When Who Where Der Die Das Den Dem Ein
Eine Wie Was Wer Wenn Mit Von Für Nach Los Las El La Le Les Un Une Una Del Des Et Au Aux Dans Pour Sur North South East West
Breaking Opinion Live Video Photos Watch Analysis Kanzler Bundeskanzler Minister Ministerin Präsident Präsidentin
Chancellor President Prime Five Four Three Two Seven Several Many""".split())


# --------------------------------------------------------------------------- Quellen

def feed(name, pub, lang, land, art, url) -> list[dict]:
    items = news.rss(name, pub, lang, url)
    for i in items:
        i["land"], i["art"] = land, art
    return items


def gdelt() -> list[dict]:
    """GDELT DOC API: ein Abruf (Rate-Limit), Artikel über Germany; deutsche Quellen werden ausgesortiert."""
    data = fetch(news.GDELT, params={"query": "Germany", "mode": "artlist", "format": "json", "maxrecords": 100,
                                     "timespan": "12h", "sort": "datedesc"}, timeout=30, retries=1).json()
    out = []
    for art in data.get("articles") or []:
        country = (art.get("sourcecountry") or "").strip()
        if country.lower() == "germany" or (art.get("domain") or "").endswith(".de"):
            continue
        title, url, domain = news.clean(art.get("title", ""), 160), art.get("url", ""), art.get("domain", "")
        lang = _GDELT_LANG.get((art.get("language") or "").lower())
        if not (title and url and domain and lang):
            continue
        try:
            from datetime import datetime, timezone
            when = datetime.strptime(art.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        out.append({"titel": title, "kurz": "", "link": url, "quelle": domain, "betreiber": news.publisher_of(domain),
                    "sprache": lang, "zeit": iso(when) if when else "", "land": country or "?", "art": "unbekannt", "gdelt": True})
    return out


# --------------------------------------------------------------------------- Auswerten

def about_germany(it: dict) -> bool:
    return bool(DE_WORDS.search(f"{it['titel']} {it.get('kurz', '')}"))


def entities(text: str) -> set[str]:
    """Eigennamen (groß geschrieben, nicht am Satzanfang) und Zahlen: tragen über Sprachgrenzen hinweg."""
    words = re.findall(r"[^\W\d_][\w'’-]*|\d[\d.,]*", text)
    out = set()
    for n, w in enumerate(words):
        if w[0].isdigit():
            if len(w.strip(".,")) >= 2:
                out.add(w.strip(".,"))
        elif w[0].isupper() and len(w) >= 4 and w not in _NOT_NAME and w.lower() not in news._STOP:
            out.add(w.lower()[:6])
    return {e for e in out if e not in _GENERIC and e[:6] not in _GENERIC}


def match_german(group: dict, de_news: list[dict]) -> list[dict]:
    ents = set().union(*(entities(i["titel"]) for i in group["items"]))
    out = []
    for m in de_news:
        if len(ents & entities(m["titel"])) >= 2 or (m.get("kurz") and len(ents & entities(m["titel"] + " " + m["kurz"])) >= 3):
            out.append({"quelle": m["quelle"], "titel": m["titel"], "link": m["link"]})
    return out[:4]


def involved_countries(text: str) -> set[str]:
    return {land for land, rx in _LAND_RE.items() if rx.search(text)}


def summary(items) -> list[str]:
    """Höchstens 5 Zeilen, nur aus Titeln/Kurzzeilen der Quellen (nichts hinzugefügt)."""
    lines, seen = [], set()
    for i in items:
        line = f"{i['quelle']} ({i['land']}): {news.clean(i['titel'], 140)}"
        if i["titel"].lower() not in seen:
            seen.add(i["titel"].lower())
            lines.append(line)
    return lines[:5]


def merge_languages(groups: list[dict]) -> list[dict]:
    """Dieselbe Meldung in anderer Sprache: Gruppen mit >= 3 gemeinsamen Eigennamen/Zahlen zusammenführen."""
    ents = [set().union(*(entities(i["titel"]) for i in g["items"])) for g in groups]
    merged: list[int] = []
    for a in range(len(groups)):
        if a in merged:
            continue
        for b in range(a + 1, len(groups)):
            if b not in merged and groups[a]["sprache"] != groups[b]["sprache"] and len(ents[a] & ents[b]) >= 3:
                groups[a]["items"] += groups[b]["items"]
                groups[a]["toks"] += groups[b]["toks"]
                merged.append(b)
    return [g for n, g in enumerate(groups) if n not in merged]


def build_groups(items: list[dict], de_news: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for it in items:
        tok = news.tokens(it["titel"])
        if len(tok) < 2:
            continue
        for g in groups:
            if g["sprache"] == it["sprache"] and any(news.similar(tok, t) for t in g["toks"]):
                g["items"].append(it)
                g["toks"].append(tok)
                break
        else:
            groups.append({"toks": [tok], "sprache": it["sprache"], "items": [it]})
    groups = merge_languages(groups)
    out = []
    for g in groups:
        its = g["items"]
        by_pub = {i["betreiber"]: i for i in its}
        involved = involved_countries(" ".join(i["titel"] + " " + i.get("kurz", "") for i in its))
        for i in by_pub.values():
            i["beteiligt"] = i["land"] in involved
        reps = list(by_pub.values())
        ana = eig.gruppiere(reps)
        # Länder zählen nur mit unabhängigen Quellen: je Gruppe (gleicher Eigentümer/Geldgeber/Agentur/Staat) die erste nicht beteiligte
        nb = [i for i in reps if not i["beteiligt"] and i["land"] != "?"]
        ana_nb = eig.gruppiere(nb)
        einig = sorted({i["land"] for k, i in enumerate(nb) if not ana_nb["zaehlt_nicht"][k]})
        first = next((i for i in its if not i.get("gdelt")), its[0])
        de = match_german(g, de_news)
        n = len(by_pub)
        out.append({
            "titel": first["titel"], "kurz": first["kurz"], "link": first["link"], "sprache": g["sprache"],
            "zeit": max([i["zeit"] for i in its if i["zeit"]] or [""]),
            "ausland_quellen": n, "laender": sorted({i["land"] for i in by_pub.values()}),
            "laender_einig": einig, "bestaetigt_laender": len(einig) >= MIN_LAENDER,
            "beteiligte_laender": sorted(involved), "zusammenfassung": summary(by_pub.values()),
            "staatsnah": sorted({i["quelle"] for i in by_pub.values() if i.get("art") == "staatsnah"}),
            "deutsch_quellen": de, "nur_ausland": n >= 2 and not de,
            "unabhaengig_n": ana["n"], "abhaengig": ana["abhaengig"][:6], "eigentuemer_unbekannt": ana["unbekannt"][:6],
            "quellen": [{"quelle": i["quelle"], "land": i["land"], "art": i.get("art", ""), "beteiligt": i["beteiligt"], "titel": i["titel"],
                         "link": i["link"], "eigentuemer": ana["eigentuemer"][k], "zaehlt_nicht": ana["zaehlt_nicht"][k]}
                        for k, i in enumerate(reps)][:5],
        })
    out.sort(key=lambda g: (g["bestaetigt_laender"], len(g["laender_einig"]), g["nur_ausland"], g["ausland_quellen"], g["zeit"]), reverse=True)
    return out[:MAX_GROUPS]


# --------------------------------------------------------------------------- Wikidata (belegte Verbindungen)

WD = "https://www.wikidata.org/w/api.php"
PROPS = {"P39": "Amt", "P102": "Partei", "P108": "Arbeitgeber", "P127": "Eigentümer", "P463": "Mitglied von"}
NAME_RE = re.compile(r"\b(?=([A-ZÄÖÜ][a-zäöüéß]{2,}(?:-[A-ZÄÖÜ][a-zäöüß]+)?) ([A-ZÄÖÜ][a-zäöüéß]{2,})\b)")


def candidate_names(groups: list[dict]) -> list[tuple[str, list[str]]]:
    found: dict[str, list[str]] = {}
    for g in groups:
        for first, last in NAME_RE.findall(g["titel"]):
            if first in _NOT_NAME or last in _NOT_NAME or first.lower() in _GENERIC or last.lower() in _GENERIC:
                continue
            found.setdefault(f"{first} {last}", []).append(g["titel"])
    return sorted(found.items(), key=lambda kv: -len(kv[1]))


def _entity(qid: str, props: str = "claims|descriptions|labels") -> dict:
    data = fetch(WD, params={"action": "wbgetentities", "ids": qid, "props": props, "languages": "de|en", "format": "json"},
                 timeout=20, retries=1).json()
    return (data.get("entities") or {}).get(qid, {})


def wikidata_lookup(name: str) -> dict | None:
    """Deutsche Person/Organisation mit belegten Ämtern/Parteien/Arbeitgebern/Eigentümern/Mitgliedschaften; sonst None."""
    hits = fetch(WD, params={"action": "wbsearchentities", "search": name, "language": "de", "format": "json", "limit": 3},
                 timeout=20, retries=1).json().get("search") or []
    for hit in hits:
        desc = ((hit.get("display") or {}).get("description") or {}).get("value", "") or hit.get("description", "")
        label = hit.get("label", "")
        if label.lower() != name.lower() or not re.search(r"german|deutsch", desc, re.I):
            continue
        ent = _entity(hit["id"])
        claims, rows, want = ent.get("claims") or {}, [], set()
        for prop, kind in PROPS.items():
            for st in claims.get(prop, [])[:6]:
                val = ((st.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if not isinstance(val, dict) or "id" not in val:
                    continue
                end = ((st.get("qualifiers") or {}).get("P582") or [{}])[0].get("datavalue", {}).get("value", {}).get("time", "")
                rows.append((kind, val["id"], end[1:5] if end else ""))
                want.add(val["id"])
        if not rows:
            return {"name": name, "wikidata": f"https://www.wikidata.org/wiki/{hit['id']}", "beschreibung": desc, "verbindungen": []}
        labels = {}
        data = fetch(WD, params={"action": "wbgetentities", "ids": "|".join(sorted(want)[:40]), "props": "labels",
                                 "languages": "de|en", "format": "json"}, timeout=20, retries=1).json()
        for qid, e in (data.get("entities") or {}).items():
            lab = e.get("labels") or {}
            labels[qid] = (lab.get("de") or lab.get("en") or {}).get("value", "")
        links = [{"eigenschaft": kind, "wert": labels.get(q, ""), "link": f"https://www.wikidata.org/wiki/{q}",
                  "beendet": end or None} for kind, q, end in dict.fromkeys(rows) if labels.get(q)]
        return {"name": name, "wikidata": f"https://www.wikidata.org/wiki/{hit['id']}", "beschreibung": desc, "verbindungen": links[:12]}
    return None


def connections(groups: list[dict], cache: dict, notes: list[str]) -> list[dict]:
    lookups = 0
    for name, _titles in candidate_names(groups):
        if name in cache or lookups >= MAX_LOOKUPS:
            continue
        lookups += 1
        time.sleep(1.5)                             # Wikidata drosselt schnelle Folgen (429)
        try:
            cache[name] = wikidata_lookup(name) or {"keine_treffer": True}
        except Exception as exc:                    # noqa: BLE001 – Quelle einzeln abgesichert
            notes.append(f"Wikidata {name}: nicht erreichbar ({common.short_error(exc)})")
    out = []
    for name, titles in candidate_names(groups):
        c = cache.get(name)
        if c and c.get("verbindungen"):
            out.append({**c, "themen": titles[:3]})
    return out[:8]


# --------------------------------------------------------------------------- Lauf

def run() -> dict:
    started = time.monotonic()
    eig.neuer_lauf()
    notes: list[str] = []
    items: list[dict] = []
    for f in FEEDS:
        items += run_source(f[0], lambda f=f: feed(*f), notes)
    items += run_source("GDELT", gdelt, notes)
    limit = now() - timedelta(hours=MAX_AGE_H)
    items = [i for i in items if about_germany(i) and (not i["zeit"] or (common.parse_time(i["zeit"]) or now()) >= limit)]
    old = common.read_json("welt.json") or {}
    if not items and old:
        common.record_status("welt", started, False, "alle Quellen ausgefallen", notes)
        return old
    de_news = [m for m in (common.read_json("news.json", {}) or {}).get("meldungen", []) if m.get("sprache") == "de"]
    groups = build_groups(items, de_news)
    cache = dict(old.get("wikidata_cache") or {})
    links = connections(groups, cache, notes)
    only = sum(g["nur_ausland"] for g in groups)
    data = {"erzeugt": iso(), "anzahl": len(groups), "nur_ausland": only, "hinweise": notes,
            "regel": "Ausland-Betreiber zählen einzeln, aber Quellen mit gleichem Eigentümer/Geldgeber/Agentur/Staat nur einmal (Länder nur mit unabhängigen Quellen); nur_ausland = >= 2 ausländische Betreiber, keine passende Meldung in news.json; "
                     "Verbindungen nur mit Wikidata-Link; staatsnahe Sender sind gekennzeichnet",
            "themen": groups, "verbindungen": links, "wikidata_cache": dict(list(cache.items())[-200:])}
    changed = common.write_json("welt.json", data)
    common.record_status("welt", started, bool(items), f"{len(groups)} Themen, {only} nur im Ausland, {len(links)} Verbindungen"
                         + ("" if changed else " (unverändert)"), notes)
    return data
