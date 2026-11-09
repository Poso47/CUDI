"""Wem gehört das Medium? – Eigentümer, Geldgeber, Agentur, Staatsnähe; Unabhängigkeit zweier Quellen.

Grundsatz (nie lügen, nie raten): Zwei Quellen gelten nur dann als voneinander unabhängige Bestätigung, wenn hinter ihnen nicht
dieselben Eigentümer, Anteilseigner, Geldgeber oder dieselbe Nachrichtenagentur stehen. Unbekannt bleibt „unbekannt“.

Grundlage A: gepflegte Tabelle `data/medien_eigentuemer.json` (nur Belegtes, jeweils mit Link).
Grundlage B: Wikidata (offizielle Website P856 -> Objekt, Eigentümer P127 / Mutterorganisation P749 bis 3 Ebenen, Geldgeber P8324),
zwischengespeichert in `eigentuemer_cache.json` (Firma-Datenordner; `CUDI_EIGENTUEMER_CACHE` überschreibt), 1,5 s Pause,
höchstens 10 neue Abfragen je Lauf, aus mit `CUDI_EIGENTUEMER_WIKIDATA=0`.

Benutzung:  eigentuemer("welt.de"), unabhaengig(a, b), pruefe(a, b) (mit Grund), gruppiere(items) (für Meldungsgruppen).
„Quelle“ darf Domain, Adresse oder ein Dict mit link/quelle/betreiber/titel/kurz sein."""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

TABELLE = Path(__file__).resolve().parent / "data" / "medien_eigentuemer.json"
MAX_NEU = 10                       # neue Wikidata-Abfragen je Lauf
PAUSE = 1.5
CACHE_TAGE = 30                    # auch „unbekannt“ wird so lange nicht neu erfragt
SPARQL = "https://query.wikidata.org/sparql"
_ZWEITE_EBENE = {"co", "com", "org", "net", "gov", "ac", "edu"}
_RECHTSFORM = {"se", "ag", "gmbh", "inc", "ltd", "plc", "sa", "kgaa", "co", "company", "corp", "corporation", "llc", "the", "die", "der"}
_lauf = {"neu": 0, "cache": None}


# --------------------------------------------------------------------------- Hilfen

def host_von(quelle) -> str:
    """Domain ohne www aus Adresse/Domain/Dict."""
    if isinstance(quelle, dict):
        for key in ("link", "domain", "quelle", "betreiber"):
            h = host_von(quelle.get(key) or "")
            if "." in h:
                return h
        return host_von(quelle.get("betreiber") or quelle.get("quelle") or "")
    text = str(quelle or "").strip().lower()
    h = (urlparse(text).netloc if "//" in text else text).split("/")[0].split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _labels(host: str) -> list[str]:
    return [p for p in host.split(".") if p]


def registrierbar(host: str) -> str:
    """bbc.co.uk -> bbc.co.uk; feeds.bbci.co.uk -> bbci.co.uk; rss.dw.com -> dw.com."""
    lab = _labels(host)
    if len(lab) >= 3 and lab[-2] in _ZWEITE_EBENE:
        return ".".join(lab[-3:])
    return ".".join(lab[-2:])


def betreiber_von(host: str) -> str:
    lab = _labels(registrierbar(host))
    if len(lab) > 1:
        lab.pop()
    while len(lab) > 1 and lab[-1] in _ZWEITE_EBENE:
        lab.pop()
    return lab[-1] if lab else host


def norm(name: str) -> str:
    """Vergleichsform eines Namens: ohne Klammern, Akzente, Rechtsform, Satzzeichen."""
    text = re.sub(r"\([^)]*\)", " ", str(name or ""))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    words = [w for w in re.findall(r"[a-z0-9]+", text) if w not in _RECHTSFORM]
    return " ".join(words)


@lru_cache(maxsize=1)
def tabelle() -> dict:
    return json.loads(TABELLE.read_text("utf-8"))


def _eintrag_fuer(host: str) -> dict | None:
    best, best_len = None, 0
    for e in tabelle()["medien"]:
        for d in e["domains"]:
            if (host == d or host.endswith("." + d)) and len(d) > best_len:
                best, best_len = e, len(d)
    return best


# --------------------------------------------------------------------------- Wikidata (Grundlage B)

def _cache_pfad() -> Path:
    env = os.environ.get("CUDI_EIGENTUEMER_CACHE")
    if env:
        return Path(env)
    from .firma import common
    return Path(common.DATA_DIR) / "eigentuemer_cache.json"


def _cache() -> dict:
    if _lauf["cache"] is None:
        try:
            _lauf["cache"] = json.loads(_cache_pfad().read_text("utf-8"))
        except (OSError, ValueError):
            _lauf["cache"] = {}
    return _lauf["cache"]


def _cache_speichern() -> None:
    path = _cache_pfad()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(_lauf["cache"], ensure_ascii=False, indent=1, sort_keys=True)
        if not path.exists() or path.read_text("utf-8") != text:
            path.write_text(text, "utf-8")
    except OSError:
        pass


def neuer_lauf() -> None:
    """Zähler der Wikidata-Abfragen zurücksetzen (am Anfang eines Firma-Laufs aufrufen)."""
    _lauf["neu"] = 0
    _lauf["cache"] = None


def _sparql(query: str) -> list[dict]:
    from .firma import common
    resp = common.fetch(SPARQL, params={"query": query, "format": "json"}, timeout=40, retries=1)
    return resp.json()["results"]["bindings"]


def _wikidata(host: str) -> dict | None:
    """Eigentümer/Geldgeber laut Wikidata oder None (nicht gefunden/mehrdeutig). Wirft bei Netzfehlern."""
    reg = registrierbar(host)
    urls = " ".join(f"<{p}{d}{s}>" for d in {host, reg, "www." + reg} for p in ("https://", "http://") for s in ("", "/"))
    rows = _sparql("SELECT DISTINCT ?item WHERE { VALUES ?u { %s } ?item wdt:P856 ?u . } LIMIT 12" % urls)
    items = sorted({r["item"]["value"].rsplit("/", 1)[-1] for r in rows})
    if not items:
        return None
    eig: list[str] = []
    geld: list[str] = []
    links = [f"https://www.wikidata.org/wiki/{q}" for q in items[:3]]
    frontier, seen = items, set(items)
    for level in range(3):
        time.sleep(PAUSE)
        vals = " ".join(f"wd:{q}" for q in frontier)
        rows = _sparql(
            "SELECT ?x ?rel ?o ?oLabel WHERE { VALUES ?x { %s } "
            "{ ?x p:P127 ?s . ?s ps:P127 ?o . FILTER NOT EXISTS { ?s pq:P582 ?e } BIND('e' AS ?rel) } UNION "
            "{ ?x p:P749 ?s . ?s ps:P749 ?o . FILTER NOT EXISTS { ?s pq:P582 ?e } BIND('e' AS ?rel) } "
            "%s SERVICE wikibase:label { bd:serviceParam wikibase:language 'de,en'. } }"
            % (vals, "UNION { ?x wdt:P8324 ?o . BIND('g' AS ?rel) }" if level == 0 else ""))
        frontier = []
        for r in rows:
            label = r.get("oLabel", {}).get("value", "")
            qid = r["o"]["value"].rsplit("/", 1)[-1]
            if not label or re.fullmatch(r"Q\d+", label):
                continue                                   # Objekt ohne Namen: nichts behaupten
            (geld if r["rel"]["value"] == "g" else eig).append(label)
            if r["rel"]["value"] == "e" and qid not in seen:
                seen.add(qid)
                frontier.append(qid)
        if not frontier:
            break
    if len(items) > 3 or not (eig or geld):
        return None if len(items) > 3 else {"eigentuemer": [], "geldgeber": [], "quelle": links}
    return {"eigentuemer": list(dict.fromkeys(eig)), "geldgeber": list(dict.fromkeys(geld)), "quelle": links}


def _aus_wikidata(host: str) -> dict | None:
    if os.environ.get("CUDI_EIGENTUEMER_WIKIDATA", "1") == "0":
        return None
    cache, key = _cache(), registrierbar(host)
    alt = cache.get(key)
    if alt:
        try:
            if (date.today() - datetime.strptime(alt.get("geprueft", "2000-01-01"), "%Y-%m-%d").date()).days < CACHE_TAGE:
                return alt if (alt.get("eigentuemer") or alt.get("geldgeber")) else None
        except ValueError:
            pass
    if _lauf["neu"] >= MAX_NEU:
        return None
    _lauf["neu"] += 1
    time.sleep(PAUSE)
    try:
        res = _wikidata(host)
    except Exception:                                      # noqa: BLE001 – Ausfall = unbekannt, nicht cachen
        return None
    cache[key] = {**(res or {"eigentuemer": [], "geldgeber": [], "quelle": []}), "geprueft": date.today().isoformat()}
    _cache_speichern()
    return cache[key] if (cache[key]["eigentuemer"] or cache[key]["geldgeber"]) else None


# --------------------------------------------------------------------------- Auskunft

def eigentuemer(domain) -> dict:
    """{"name", "eigentuemer", "geldgeber", "agentur", "staatsnah", "quelle", "stand", ...}; unbekannt = leere Listen."""
    host = host_von(domain)
    tab = tabelle()
    e = _eintrag_fuer(host)
    if e:
        return {"name": e["name"], "domain": host, "eigentuemer": list(e["eigentuemer"]), "geldgeber": list(e["geldgeber"]),
                "agentur": e.get("agentur"), "staatsnah": bool(e.get("staatsnah")), "staat": e.get("staat"),
                "quelle": list(e["quelle"]), "stand": tab["stand"], "bekannt": bool(e["eigentuemer"] or e["geldgeber"]),
                "herkunft": "Tabelle", "hinweis": e.get("hinweis", ""), "id": e["name"]}
    wd = _aus_wikidata(host) if host and "." in host else None
    if wd:
        return {"name": host, "domain": host, "eigentuemer": list(wd["eigentuemer"]), "geldgeber": list(wd["geldgeber"]),
                "agentur": None, "staatsnah": False, "staat": None, "quelle": list(wd["quelle"]),
                "stand": wd.get("geprueft", date.today().isoformat()), "bekannt": True, "herkunft": "Wikidata",
                "hinweis": "laut Wikidata, nicht gegengeprüft", "id": host}
    return {"name": host, "domain": host, "eigentuemer": [], "geldgeber": [], "agentur": None, "staatsnah": False, "staat": None,
            "quelle": [], "stand": tab["stand"], "bekannt": False, "herkunft": "unbekannt", "hinweis": "Eigentümer unbekannt", "id": host}


_AGENTUR_WORTE = {"AFP": ["AFP", "Agence France-Presse"], "dpa": ["dpa"], "Reuters": ["Reuters"], "AP": ["AP", "Associated Press"],
                  "APA": ["APA"], "SDA": ["SDA", "Keystone-SDA"], "Xinhua": ["Xinhua"], "EFE": ["EFE"], "ANSA": ["ANSA"],
                  "TASS": ["TASS"], "Anadolu": ["Anadolu"], "PTI": ["PTI"], "IANS": ["IANS"], "Kyodo": ["Kyodo"]}
_ALIAS = {w: a for a, ws in _AGENTUR_WORTE.items() for w in ws}
_ALT = "|".join(sorted((re.escape(w) for w in _ALIAS), key=len, reverse=True))
_MARKER = re.compile(r"(?:\(|\[|\bvia\s+|\bvon\s+|\bmit\s+|\bby\s+|/|\||[–—-]\s*|^)(" + _ALT + r")(?=[\s)\].,:;/|]|$)")
_WORT = re.compile(r"(?<![\w])(" + _ALT + r")(?![\w])")


def agenturen_in(quelle) -> set[str]:
    """Agenturen, die eine Quelle nennt: im Quellennamen (auch „Wikipedia · AFP via France 24“), in Titel/Kurzzeile nur mit
    Kennung („(AFP)“, „dpa/AFP“, „via Reuters“, „Reuters:“) – nie aus einem bloßen Wort im Satz."""
    found: set[str] = set()
    if isinstance(quelle, dict):
        found |= {_ALIAS[m] for m in _WORT.findall(str(quelle.get("quelle") or ""))}
        for key in ("titel", "kurz"):
            text = str(quelle.get(key) or "")
            found |= {_ALIAS[m] for m in _MARKER.findall(text)}
            found |= {_ALIAS[m] for m in re.findall(r"^(" + _ALT + r")\b\s*[:–—-]", text)}
    else:
        found |= {_ALIAS[m] for m in _WORT.findall(str(quelle or ""))}
    own = eigentuemer(host_von(quelle)).get("agentur") if host_von(quelle) else None
    if own:
        found.add(own)
    return found


def _namen(info: dict) -> tuple[dict, dict]:
    """(Eigentümer, Geldgeber) als {norm: Anzeigename}, Ketten über die Konzerntabelle bis zur Spitze."""
    konz = {norm(k): v["eigner"] for k, v in tabelle()["konzerne"].items()}

    def expand(namen: list[str]) -> dict:
        out, todo = {}, list(namen)
        while todo:
            n = todo.pop()
            k = norm(n)
            if not k or k in out:
                continue
            out[k] = n
            todo += konz.get(k, [])
        return out
    return expand(info["eigentuemer"]), expand(info["geldgeber"])


def pruefe(a, b) -> dict:
    """{"unabhaengig": bool, "grund": "…", "unbekannt": [Namen]} – Grund nur bei Abhängigkeit, „unbekannt“ nennt Quellen ohne Eigentümerangabe."""
    ia, ib = eigentuemer(host_von(a)), eigentuemer(host_von(b))
    unb = [i["name"] for i in (ia, ib) if not i["bekannt"]]
    ha, hb = host_von(a), host_von(b)
    same = ia.get("id") == ib.get("id") if (ia["herkunft"] == "Tabelle" and ib["herkunft"] == "Tabelle") else False
    if ha and hb and (registrierbar(ha) == registrierbar(hb) or betreiber_von(ha) == betreiber_von(hb) or same):
        wo = f"gleiche Domain {registrierbar(ha)}" if registrierbar(ha) == registrierbar(hb) else f"gleiche Quelle {ia['name']}"
        return {"unabhaengig": False, "grund": wo, "unbekannt": unb}
    ag = agenturen_in(a) & agenturen_in(b)
    if ag:
        return {"unabhaengig": False, "grund": f"gleiche Nachrichtenagentur {sorted(ag)[0]}", "unbekannt": unb}
    if ia["staatsnah"] and ib["staatsnah"] and ia.get("staat") and ia.get("staat") == ib.get("staat"):
        return {"unabhaengig": False, "grund": f"beide staatlich, gleicher Staat {ia['staat']}", "unbekannt": unb}
    ea, ga = _namen(ia)
    eb, gb = _namen(ib)
    gem = ea.keys() & eb.keys()
    if gem:
        return {"unabhaengig": False, "grund": f"gleicher Eigentümer {ea[sorted(gem)[0]]}", "unbekannt": unb}
    gem = (ea.keys() | ga.keys()) & (eb.keys() | gb.keys())
    if gem:
        k = sorted(gem)[0]
        return {"unabhaengig": False, "grund": f"gleicher Geldgeber {(ga.get(k) or ea.get(k))}", "unbekannt": unb}
    return {"unabhaengig": True, "grund": "", "unbekannt": unb}


def unabhaengig(a, b) -> bool:
    """Wahr, wenn kein gemeinsamer Eigentümer/Geldgeber/Agentur/Staat bekannt ist.
    Unbekannter Eigentümer: es zählt nur Domain/Agentur (Vermerk über `pruefe(...)["unbekannt"]`)."""
    return pruefe(a, b)["unabhaengig"]


def anzeige(info_oder_quelle) -> str:
    """„gehört Axel Springer SE“ / „Eigentümer unbekannt“ für Listen."""
    info = info_oder_quelle if isinstance(info_oder_quelle, dict) and "bekannt" in info_oder_quelle else eigentuemer(host_von(info_oder_quelle))
    if not info["bekannt"]:
        return "Eigentümer unbekannt"
    if info.get("staatsnah") and info.get("staat"):
        return f"staatlich ({info['staat']})"
    own = info["eigentuemer"] or info["geldgeber"]
    kurz = [re.sub(r"\s*\([^)]*\)", "", o).strip() for o in own[:2]]
    return ("gehört " if info["eigentuemer"] else "finanziert von ") + " und ".join(kurz)


def gruppiere(items: list[dict]) -> dict:
    """Quellen zu unabhängigen Gruppen zusammenfassen (Abhängigkeit gilt transitiv).
    -> {"gruppe": [Nr je Quelle], "n": Anzahl Gruppen, "abhaengig": [{a, b, grund}], "unbekannt": [Quellen],
        "zaehlt_nicht": [Grund oder ""], "eigentuemer": [Anzeigetext]}"""
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    grund = {}
    abh, unb = [], []
    for i in range(n):
        for j in range(i + 1, n):
            r = pruefe(items[i], items[j])
            for u in r["unbekannt"]:
                if u not in unb:
                    unb.append(u)
            if not r["unabhaengig"]:
                parent[find(j)] = find(i)
                grund[(i, j)] = r["grund"]
                abh.append({"a": items[i].get("quelle") or host_von(items[i]), "b": items[j].get("quelle") or host_von(items[j]), "grund": r["grund"]})
    roots = {}
    gruppe = []
    for i in range(n):
        gruppe.append(roots.setdefault(find(i), len(roots)))
    zn = []
    for i in range(n):
        first = next((k for k in range(i) if gruppe[k] == gruppe[i]), None)
        if first is None:
            zn.append("")
        else:
            g = grund.get((first, i)) or next((v for (x, y), v in grund.items() if y == i or x == i), "gleiche Gruppe")
            zn.append(g)
    return {"gruppe": gruppe, "n": len(roots), "abhaengig": abh, "unbekannt": unb, "zaehlt_nicht": zn,
            "eigentuemer": [anzeige(host_von(it)) for it in items]}


# --------------------------------------------------------------------------- Prüfliste (Tabelle gegen Wikidata)

def abgleich_tabelle(schreiben: bool = False) -> list[tuple[str, str]]:
    """Je Tabelleneintrag: „bestätigt“ (Wikidata nennt einen der Eigentümer), „nur Tabelle“ (Wikidata ohne Angabe),
    „abweichend“ (Wikidata nennt andere) – braucht Netz; höchstens ein Abruf je 1,5 s."""
    tab = json.loads(TABELLE.read_text("utf-8"))
    out = []
    for e in tab["medien"]:
        status = "nur Tabelle"
        try:
            time.sleep(PAUSE)
            wd = _wikidata(e["domains"][0])
        except Exception:                                  # noqa: BLE001
            wd, status = None, "nicht geprüft (Netz)"
        if wd and (wd["eigentuemer"] or wd["geldgeber"]):
            wk = {norm(x) for x in wd["eigentuemer"] + wd["geldgeber"]}
            mine = {norm(x) for x in e["eigentuemer"] + e["geldgeber"]}
            konz = {norm(k): [norm(v) for v in c["eigner"]] for k, c in tab["konzerne"].items()}
            mine |= {v for m in list(mine) for v in konz.get(m, [])}
            if not mine:
                status = "nur Wikidata (Tabelle leer)"
            else:
                status = "bestätigt" if wk & mine else "abweichend"
        e["wikidata"] = status
        out.append((e["name"], status))
    if schreiben:
        TABELLE.write_text(json.dumps(tab, ensure_ascii=False, indent=1), "utf-8")
        tabelle.cache_clear()
    return out
