"""Recherche wie ein Mensch: Frage zerlegen -> mehrere Suchanfragen (auch englisch) -> Treffer sichten -> Seiten lesen ->
Aussagen mit WÖRTLICHEM Zitat + Adresse + Datum sammeln -> nach Aktualität ordnen -> abgleichen. „Bestätigt“ gilt eine Aussage nur,
wenn mindestens zwei unabhängige Betreiber (eigentuemer.gruppiere) sie stützen; Widersprüche und ältere Stände werden ausgewiesen,
nie geglättet. Jeder Schritt landet im Protokoll (`schritte`)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .. import eigentuemer, handoff
from . import cache, fachquellen, lesen, suche as suchmodul, wikipedia

BEREICHE = ("fakten", "geschichte", "rankings", "reportage", "satire", "ideen", "briefing", "wissen", "clips", "news")
MAX_ALTER = {"news": 14, "reportage": 30, "satire": 14, "ideen": 30, "briefing": 3, "fakten": 730, "rankings": 730,
             "wissen": 365, "clips": 60, "geschichte": None}
MIN_GRUPPEN = 2
STOP = set("""der die das den dem des ein eine einen einem einer eines und oder aber ist sind war waren wird werden wurde wurden hat haben
hatte hatten wie was wer wo wann warum wieso welche welcher welches welchen wieviel viele viel hoch groß gross aktuelle aktuellen aktueller
aktuell aktuelles derzeit derzeitige derzeitigen momentan heute neueste neuesten neuester im in am an auf aus bei mit nach von vom zu zum zur
über ueber unter für fuer gegen ohne um bis seit als auch noch nur schon mal gibt es man sich ich mir mein wir ihr sie er the a an of in on
at to for is are was were be been what which who when where why how much many does do did current currently latest recent now today and or
with from by about as that this these those it its has have had will would can could""".split())
GLOSSAR = {  # deutsche Stichwörter -> englische Suchwörter
    "inflationsrate": "inflation rate", "inflation": "inflation", "arbeitslosenquote": "unemployment rate", "arbeitslosigkeit": "unemployment",
    "bevölkerung": "population", "einwohner": "population", "wirtschaftswachstum": "economic growth", "bip": "GDP",
    "lebenserwartung": "life expectancy", "zinsen": "interest rates", "leitzins": "key interest rate", "klimawandel": "climate change",
    "studie": "study", "wirkung": "effect", "krankheit": "disease", "impfung": "vaccination", "wahl": "election", "regierung": "government",
    "deutschland": "Germany", "österreich": "Austria", "schweiz": "Switzerland", "frankreich": "France", "italien": "Italy",
    "spanien": "Spain", "usa": "USA", "china": "China", "japan": "Japan", "indien": "India", "europa": "Europe", "rekord": "record",
    "preise": "prices", "energie": "energy", "strompreis": "electricity price", "miete": "rent", "mieten": "rents",
}
OFFIZIELL = [  # (Muster in der Frage, Domain der zuständigen Behörde) – nur als zusätzliche Suchanfrage
    (r"inflation|verbraucherpreis|bevölkerung|einwohner|arbeitslos|erwerbs|bip\b|wirtschaftsleistung", "destatis.de"),
    (r"leitzins|zinsen|geldpolitik", "bundesbank.de"),
    (r"arbeitslos", "arbeitsagentur.de"),
    (r"corona|infektion|impf|grippe", "rki.de"),
]
ZAHLFRAGE = re.compile(r"wie (hoch|viel|viele|groß|gross|lang|alt|teuer|schnell|oft)|wieviel|anzahl|höhe|quote|\brate\b|prozent|betrag|"
                       r"how (much|many|high|big|long|old|fast|often)|number of|\bpercent|\bamount\b|\bpreis|\bkosten", re.I)
MON = lesen._MON
DATUM_MUSTER = re.compile(r"\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{1,2}\.?\s+(?:" + MON + r")\.?\s*\d{0,4}|(?:" + MON + r")\.?\s+\d{1,2},?\s*\d{4}|"
                          r"\d{4}-\d{2}(?:-\d{2})?", re.I)
NUM = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"
                 r"(?:\s*(%|prozent|percent|per cent|mio\.?|millionen|million|mrd\.?|milliarden|billion|bn|tausend|thousand))?(?![\w])", re.I)
EINHEIT = {"%": "%", "prozent": "%", "percent": "%", "per cent": "%", "mio": "mio", "mio.": "mio", "millionen": "mio", "million": "mio",
           "mrd": "mrd", "mrd.": "mrd", "milliarden": "mrd", "billion": "mrd", "bn": "mrd", "tausend": "tsd", "thousand": "tsd"}


def jetzt() -> date:
    return date.today()


# --------------------------------------------------------------------------- Zerlegen

def stichwoerter(frage: str) -> list[str]:
    woerter = re.findall(r"[0-9A-Za-zÄÖÜäöüß][0-9A-Za-zÄÖÜäöüß-]{2,}", frage)
    out, seen = [], set()
    for w in woerter:
        k = w.lower()
        if k in STOP or k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


def anfragen_planen(frage: str, sprache: str = "de", bereich: str = "fakten", heute: date | None = None, regeln: bool = True) -> list[str]:
    """Bis zu 4 Suchanfragen: Frage selbst, Stichwörter + Jahr, englische Fassung, Behördenseite."""
    heute = heute or jetzt()
    frage = " ".join(frage.replace("?", " ").split())
    kw = stichwoerter(frage)
    out = [frage]
    if kw:
        jahr = str(heute.year) if (MAX_ALTER.get(bereich) or 999) <= 730 or bereich in ("fakten", "rankings") else ""
        out.append(" ".join(kw + (["aktuell"] if sprache == "de" else ["latest"]) + ([jahr] if jahr else [])))
    if sprache == "de" and kw:
        en = [GLOSSAR[w.lower()] for w in kw if w.lower() in GLOSSAR]
        if en:
            out.append(" ".join(dict.fromkeys(en)) + f" latest {heute.year}")
    for muster, domain in OFFIZIELL:
        if sprache == "de" and re.search(muster, frage, re.I) and kw:
            out.append(" ".join(kw[:4]) + f" site:{domain}")
            break
    uniq = []
    for a in out:
        if a and a.lower() not in {u.lower() for u in uniq}:
            uniq.append(a)
    return uniq[:4]


# --------------------------------------------------------------------------- Aussagen

def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", str(t or "").replace("„", '"').replace("“", '"').replace("”", '"').replace("’", "'")).strip().casefold()


def saetze(text: str) -> list[str]:
    out = []
    for block in re.split(r"\n+", text):
        for s in re.split(r"(?<=[^\d\s][.!?])\s+(?=[A-ZÄÖÜ0-9„\"'(])", block):
            s = " ".join(s.split())
            if 40 <= len(s) <= 420:
                out.append(s)
    return out


def zahlen(satz: str) -> dict[float, str]:
    """Hauptzahlen eines Satzes {Wert: Einheit}: Daten/Jahre werden vorher entfernt; Zahlen mit Einheit gehen vor."""
    s = DATUM_MUSTER.sub(" ", satz)
    mit, ohne = {}, {}
    for m in NUM.finditer(s):
        raw, unit = m.group(1), EINHEIT.get((m.group(2) or "").lower(), "")
        try:
            if "," in raw and "." in raw:
                v = float(raw.replace(".", "").replace(",", ".")) if raw.rfind(",") > raw.rfind(".") else float(raw.replace(",", ""))
            elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
                v = float(raw.replace(".", ""))
            elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
                v = float(raw.replace(",", ""))
            else:
                v = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not unit and v == int(v) and (1900 <= v <= 2100 or v < 1000):
            continue                                      # Jahre und kleine Zählzahlen („15 Städte“) sind keine Messwerte
        (mit if unit else ohne)[round(v, 4)] = unit
    return mit or ohne


def _kern(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[^\W\d_]{4,}", text.casefold()) if w not in STOP}


def relevante_saetze(text: str, kw: list[str], zahlfrage: bool, n: int = 3) -> list[tuple[float, str]]:
    stems = {k.casefold()[:5] for k in kw}
    need = max(1, (len(stems) + 1) // 2)
    scored = []
    for s in saetze(text):
        low = s.casefold()
        hits = sum(1 for st in stems if st in low)
        if hits < need:
            continue
        z = zahlen(s)
        if zahlfrage and not z:
            continue
        if len(z) > 3:
            continue
        scored.append((hits + (0.5 if z else 0) - len(s) / 2000, s))
    scored.sort(key=lambda x: -x[0])
    return scored[:n]


def _in_text(zitat: str, text: str) -> bool:
    z = _norm(zitat)
    return len(z.split()) >= 3 and z in _norm(text)


def llm_aussagen(frage: str, seiten: list[dict], kw: list[str], zahlfrage: bool, aufgabe: str) -> list[dict]:
    """Optional: Claude/Modell formuliert Aussagen aus den GELESENEN Seiten; Zitat muss wörtlich auf der Seite stehen, Zahlen im Zitat."""
    daten = []
    for i, s in enumerate(seiten, 1):
        auszug = " ".join(x for _, x in relevante_saetze(s["text"], kw, False, 6))[:1500] or s["text"][:800]
        daten.append({"id": f"S{i}", "url": s["url"], "titel": s["titel"], "datum": s["datum"], "text": auszug})
    antwort = handoff.request(aufgabe, (
        "Beantworte „frage“ NUR aus den gelieferten Seiten (Feld „text“). Formuliere 1 bis 6 knappe Aussagen. Jede Aussage braucht „quelle“ "
        "(Kennung wie S1) und „zitat“ = eine WÖRTLICH kopierte Textstelle (mindestens 3 Wörter) aus dieser Seite, die die Aussage stützt. "
        "Zahlen und Zeiträume der Aussage müssen im Zitat stehen. Nichts ergänzen, nichts schätzen, keine Wertung. Antwort NUR als JSON: "
        "{\"aussagen\": [{\"text\": \"…\", \"quelle\": \"S1\", \"zitat\": \"…\"}]}"), {"frage": frage, "seiten": daten})
    rows = antwort.get("aussagen") if isinstance(antwort, dict) else None
    by_id = {f"S{i}": s for i, s in enumerate(seiten, 1)}
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        s = by_id.get(str(r.get("quelle")))
        zitat, text = str(r.get("zitat") or ""), " ".join(str(r.get("text") or "").split())
        if not s or not text or not _in_text(zitat, s["text"]):
            continue
        if not set(zahlen(text)) <= set(zahlen(zitat)):
            continue                                      # Zahl in der Aussage ohne Beleg im Zitat
        out.append({"seite": s, "text": text, "zitat": " ".join(zitat.split()), "weg": "Schreibaufgabe + Zitatprüfung"})
    return out


# --------------------------------------------------------------------------- Abgleich

QUALIFIER = re.compile(r"kerninflation|ohne\s+(?:nahrungsmittel|energie)|excluding|core\b|vorläufig|endgültig|prognose|forecast", re.I)


def _thema_gleich(a: str, b: str) -> bool:
    """Gleicher Gegenstand? Gleiche Einschränkungen (z. B. „Kerninflation“) und genug gemeinsame Inhaltswörter."""
    if bool(QUALIFIER.search(a)) != bool(QUALIFIER.search(b)):
        return False
    ka, kb = _kern(a), _kern(b)
    return len(ka & kb) >= 2 and len(ka & kb) / max(1, min(len(ka), len(kb))) >= 0.3


def _gleich(a: dict, b: dict) -> bool:
    za, zb = a["zahlen"], b["zahlen"]
    if za or zb:
        return bool(za and zb and set(za) & set(zb) and _thema_gleich(a["zitat"], b["zitat"]))
    ka, kb = _kern(a["zitat"]), _kern(b["zitat"])
    return len(ka & kb) >= 3 and len(ka & kb) / max(1, len(ka | kb)) >= 0.5


def _rang(typ: str) -> int:
    return {"Behörde/Primärquelle": 0, "Studie/Fachquelle": 1, "Medium": 2, "Unbekannt": 3, "Blog": 4, "Wikipedia": 3}.get(typ, 5)


def abgleichen(kandidaten: list[dict], bereich: str, heute: date, wiki_pruefung: dict | None = None) -> tuple[list[dict], list[dict]]:
    """-> (aussagen, widersprueche). Jede Aussage trägt Status bestaetigt/einzeln/widersprochen/veraltet und alle Belege."""
    wiki_pruefung = wiki_pruefung if wiki_pruefung is not None else {}
    cl: list[list[dict]] = []
    for k in sorted(kandidaten, key=lambda c: c["seite"].get("datum") or "", reverse=True):
        for c in cl:
            if any(_gleich(k, m) for m in c):
                c.append(k)
                break
        else:
            cl.append([k])
    aussagen = []
    for c in cl:
        belege, gesehen = [], set()
        for m in c:
            s = m["seite"]
            if s["url"] in gesehen:
                continue
            gesehen.add(s["url"])
            belege.append({"url": s["url"], "titel": s["titel"], "quelle": s["betreiber"], "link": s["url"],
                           "eigentuemer": s["eigentuemer"], "typ": s["typ"], "datum": s.get("datum"),
                           "veroeffentlicht": s.get("veroeffentlicht"), "geaendert": s.get("geaendert"),
                           "datum_quelle": s.get("datum_quelle", ""), "zitat": m["zitat"], "weg": m.get("weg", "Regeln")})
        belege.sort(key=lambda b: (_rang(b["typ"]), -(int((b["datum"] or "0000-00-00").replace("-", "")))))
        nicht_wiki = [b for b in belege if not wikipedia.ist_wikipedia(b["url"])]
        zaehlen, abgelehnt = [], []
        for b in belege:
            ok, grund = wikipedia.darf_belegen(bereich, b["url"], bool(nicht_wiki),
                                               wiki_pruefung.get(b["url"]) if wikipedia.ist_wikipedia(b["url"]) else None)
            (zaehlen if ok else abgelehnt).append(b)
            if not ok:
                b["zaehlt_nicht"] = grund
        grp = eigentuemer.gruppiere(zaehlen) if zaehlen else {"n": 0, "zaehlt_nicht": [], "abhaengig": [], "unbekannt": []}
        for b, g in zip(zaehlen, grp["zaehlt_nicht"]):
            if g:
                b["zaehlt_nicht"] = "gleiche Gruppe: " + g
        datums = [b["datum"] for b in belege if b["datum"] and b.get("datum_quelle") != "HTTP-Header"]   # Header-Datum = nur Seitenänderung
        zeigen = next((m for m in c if m["seite"]["url"] == (zaehlen or belege)[0]["url"]), c[0])
        aussagen.append({"text": zeigen["text"], "zitat": zeigen["zitat"], "zahlen": {str(k): v for k, v in zeigen["zahlen"].items()},
                         "bezug": next((m["bezug"] for m in c if m.get("bezug")), None),
                         "n_gruppen": grp["n"], "abhaengig": grp["abhaengig"], "unbekannt_eigentuemer": grp["unbekannt"],
                         "status": "bestaetigt" if grp["n"] >= MIN_GRUPPEN else "einzeln",
                         "neuestes_datum": max(datums) if datums else None, "datum_unbekannt": not datums,
                         "belege": belege, "_zahlen": set(zeigen["zahlen"])})
    # Widersprüche / ältere Stände zwischen Zahl-Aussagen
    widersprueche: list[dict] = []
    num = [a for a in aussagen if a["_zahlen"]]
    for i, a in enumerate(num):
        for b in num[i + 1:]:
            if (a["_zahlen"] & b["_zahlen"] or not _thema_gleich(a["zitat"], b["zitat"])
                    or set(a["zahlen"].values()) != set(b["zahlen"].values())
                    or {x["url"] for x in a["belege"]} == {x["url"] for x in b["belege"]}):
                continue                                   # gleiche Zahl bzw. anderer Gegenstand: kein Widerspruch
            da, db = a["neuestes_datum"], b["neuestes_datum"]
            art = "widerspruch"
            if bool(a["bezug"]) != bool(b["bezug"]):
                art = "andere Zeitspanne"                  # z. B. Monatswert gegen Jahreswert: nicht vergleichbar
            elif not (a["bezug"] or (da and db)):
                continue                                   # kein Zeitbezug erkennbar: nicht vergleichbar, nichts behaupten
            elif a["bezug"] and b["bezug"] and a["bezug"] != b["bezug"]:
                art = "zeitlich verschieden"
            elif da and db and abs((date.fromisoformat(da) - date.fromisoformat(db)).days) >= 20:
                art = "zeitlich verschieden"
            if art == "andere Zeitspanne":
                pass
            elif art == "zeitlich verschieden":
                alt, neu = (a, b) if (a["bezug"] or a["neuestes_datum"] or "") < (b["bezug"] or b["neuestes_datum"] or "") \
                    else (b, a)
                if (a["bezug"] and b["bezug"]) or (da and db):
                    alt["status"] = "veraltet"
                    alt["hinweis"] = f"älterer Stand ({alt['bezug'] or alt['neuestes_datum']}); neuer: {neu['bezug'] or neu['neuestes_datum']}"
            else:
                for x, y in ((a, b), (b, a)):
                    if x["status"] == "bestaetigt" and y["status"] != "bestaetigt":
                        x.setdefault("gegenstimmen", []).append(y["text"])
                    elif x["status"] != "veraltet":
                        x["status"] = "widersprochen"
            widersprueche.append({"art": art, "thema": "Zahlenangaben", "varianten": [
                {"text": v["text"], "zahlen": v["zahlen"], "datum": v["neuestes_datum"], "bezug": v["bezug"], "n_gruppen": v["n_gruppen"],
                 "quellen": [x["quelle"] for x in v["belege"]]} for v in (a, b)],
                "hinweis": "verschiedene Zeiträume, Zeitspannen bzw. Stände – kein Widerspruch" if art != "widerspruch" else
                           "gleicher Zeitraum, verschiedene Werte – nicht geglättet, beide Angaben stehen im Bericht"})
    limit = MAX_ALTER.get(bereich)
    for a in aussagen:
        if limit and a["neuestes_datum"] and (heute - date.fromisoformat(a["neuestes_datum"])).days > limit and a["status"] != "veraltet":
            a["status"] = "veraltet"
            a["hinweis"] = f"älter als {limit} Tage (Stand {a['neuestes_datum']})"
        a.pop("_zahlen", None)
    aussagen.sort(key=lambda a: (a["status"] == "veraltet", a["status"] != "bestaetigt", -(int((a["neuestes_datum"] or "0").replace("-", "") or 0))))
    return aussagen, widersprueche


# --------------------------------------------------------------------------- Ablauf

def _fach_seite(t: dict) -> dict:
    info = eigentuemer.eigentuemer(t["url"])
    return {"ok": True, "url": t["url"], "titel": t["titel"], "text": t["text"], "veroeffentlicht": t.get("datum"), "geaendert": None,
            "datum": t.get("datum"), "datum_quelle": "Schnittstelle (API)", "betreiber": info["name"], "eigentuemer": eigentuemer.anzeige(info),
            "typ": "Behörde/Primärquelle" if t.get("weg") != "Europe PMC" else "Studie/Fachquelle", "fehler": "", "host": info["domain"]}


def _reihenfolge(treffer: list[dict], bereich: str) -> list[dict]:
    def key(t):
        host = eigentuemer.host_von(t["url"])
        return (0 if t.get("text") else 1, lesen.seitentyp(host) == "Forum/Soziales Netz",
                _rang(lesen.seitentyp(host)), -(int((t.get("datum") or "0").replace("-", "") or 0)))
    return sorted(treffer, key=key)


def recherchiere(frage: str, bereich: str = "fakten", sprache: str = "de", zeitraum=None, max_seiten: int = 6, llm: bool = True,
                 heute: date | None = None, wiki_api=None) -> dict:
    """-> {frage, bereich, stand, aussagen[], widersprueche[], quellen[], hinweise[], schritte[]}. Fehlt Internet oder jede Quelle,
    bleibt die Antwort ehrlich leer (aussagen=[]) – nichts wird erfunden."""
    heute = heute or jetzt()
    bereich = bereich if bereich in BEREICHE else "fakten"
    schritte: list[str] = [f"Frage: „{frage}“ (Bereich {bereich}, Stand {heute.isoformat()})"]
    hinweise: list[str] = []
    kw = stichwoerter(frage)
    zahlfrage = bool(ZAHLFRAGE.search(frage))
    schritte.append(f"Zerlegt in Stichwörter: {', '.join(kw) or '–'}" + (" – gesucht wird eine Zahl" if zahlfrage else ""))
    anfragen = anfragen_planen(frage, sprache, bereich, heute)
    schritte.append("Suchanfragen: " + " | ".join(anfragen))
    if zeitraum is None and (MAX_ALTER.get(bereich) or 999) <= 31:
        zeitraum = "monat"
    suffix = "" if bereich == "fakten" else "_" + bereich
    res = suchmodul.suche(anfragen, sprache, zeitraum, bereich, aufgabe=suchmodul.TASK + suffix)
    schritte += res["schritte"]
    treffer = res["treffer"]
    seiten, quellen, wiki_pruefung = [], [], {}
    lesen_limit = max(0, min(max_seiten, cache.limit("seiten")))
    wiki_skip = 0
    gelesen = 0
    kandidaten: list[dict] = []
    domains: dict[str, int] = {}
    for t in _reihenfolge(treffer, bereich):
        host = eigentuemer.host_von(t["url"])
        if wikipedia.ist_wikipedia(t["url"]) and bereich not in wikipedia.BEREICHE:
            wiki_skip += 1
            continue
        reg = eigentuemer.registrierbar(host)
        if domains.get(reg, 0) >= (3 if t.get("text") else 1):
            continue
        if lesen.seitentyp(host) == "Forum/Soziales Netz":
            hinweise.append(f"{host}: Forum/soziales Netz wird nicht als Beleg gelesen")
            continue
        if t.get("text"):
            seite = _fach_seite(t)
            schritte.append(f"Fachquelle übernommen: {seite['betreiber']} – {t['titel']} (Stand {seite['datum'] or '?'})")
        else:
            if gelesen >= lesen_limit:
                break
            seite = lesen.lese(t["url"])
            if seite.get("begrenzt"):
                hinweise.append("Seitenbegrenzung für diesen Lauf erreicht")
                break
            gelesen += 1
            if seite["ok"]:
                schritte.append(f"Gelesen: {seite['betreiber']} ({seite['typ']}, {seite['eigentuemer']}) – {seite['titel'][:70]}; "
                                f"Datum {seite['datum'] or 'unbekannt'}" + (f" ({seite['datum_quelle']})" if seite["datum"] else ""))
            else:
                schritte.append(f"Nicht lesbar: {host} – {seite['fehler']}")
        domains[reg] = domains.get(reg, 0) + 1
        quelle = {k: seite.get(k) for k in ("url", "titel", "betreiber", "eigentuemer", "typ", "datum", "veroeffentlicht", "geaendert", "datum_quelle")}
        quelle.update(gelesen=bool(seite["ok"]), fehler=seite.get("fehler", ""), weg=t.get("weg", ""), aussagen=0)
        quellen.append(quelle)
        if not seite["ok"]:
            continue
        if wikipedia.ist_wikipedia(seite["url"]):
            wiki_pruefung[seite["url"]] = wikipedia.pruefe_seite(seite["url"], sprache, api=wiki_api)
            p = wiki_pruefung[seite["url"]]
            schritte.append("Wikipedia-Prüfung " + ("bestanden" if p["ok"] else "NICHT bestanden: " + "; ".join(p["zeichen"])))
            if not p["ok"]:
                hinweise.append(f"Wikipedia ({p.get('titel', '')}) zählt nicht: " + "; ".join(p["zeichen"]))
        seiten.append(seite)
        for score, s in relevante_saetze(seite["text"], kw, zahlfrage):
            z = zahlen(s)
            kandidaten.append({"seite": seite, "text": s, "zitat": s, "zahlen": z, "bezug": lesen.parse_monat(s), "weg": "Regeln"})
            quelle["aussagen"] += 1
        if gelesen >= 3 and _fertig(kandidaten, bereich, heute, wiki_pruefung):
            schritte.append("Genug unabhängige, aktuelle Bestätigung – weitere Seiten werden nicht gelesen")
            break
    if wiki_skip:
        schritte.append(f"{wiki_skip} Wikipedia-Treffer nicht gelesen: im Bereich „{bereich}“ nur Suchhinweis, kein Beleg")
    if llm and handoff.active() and seiten:
        try:
            neu = llm_aussagen(frage, seiten[:8], kw, zahlfrage, "recherche_aussagen" + suffix)
            for n in neu:
                n.update(zahlen=zahlen(n["zitat"]), bezug=lesen.parse_monat(n["zitat"]) or lesen.parse_monat(n["text"]))
            if neu:
                schritte.append(f"Schreibaufgabe: {len(neu)} Aussagen mit wörtlichem Zitat bestätigt")
                kandidaten = neu + kandidaten
        except handoff.WritingNeeded:
            raise
        except Exception as exc:                                   # noqa: BLE001
            hinweise.append(f"Aussagen-Schreibaufgabe nicht nutzbar ({type(exc).__name__}) – Regelweg")
    aussagen, widersprueche = abgleichen(kandidaten, bereich, heute, wiki_pruefung)
    if not treffer:
        hinweise.append("Keine Treffer – kein Internet oder alle Suchwege blockiert. Es wird nichts ergänzt.")
    elif not aussagen:
        hinweise.append("Seiten gelesen, aber keine Aussage zur Frage gefunden. Es wird nichts ergänzt.")
    schritte.append(f"Abgleich: {len(aussagen)} Aussagen, davon {sum(a['status'] == 'bestaetigt' for a in aussagen)} bestätigt "
                    f"(≥ {MIN_GRUPPEN} unabhängige Betreiber), {sum(a['status'] == 'veraltet' for a in aussagen)} veraltet, "
                    f"{sum(w['art'] == 'widerspruch' for w in widersprueche)} Widersprüche")
    return {"frage": frage, "bereich": bereich, "sprache": sprache, "stand": heute.isoformat(), "aussagen": aussagen,
            "widersprueche": widersprueche, "quellen": quellen, "hinweise": hinweise, "schritte": schritte,
            "seiten_gelesen": gelesen, "texte": {s["url"]: s["text"][:6000] for s in seiten}}


def _fertig(kandidaten: list[dict], bereich: str, heute: date, wiki_pruefung: dict) -> bool:
    aussagen, _ = abgleichen(kandidaten, bereich, heute, wiki_pruefung)
    return any(a["status"] == "bestaetigt" for a in aussagen)


def seiten_als_quellen(ergebnis: dict, max_n: int = 6) -> list[dict]:
    """Für Reportage/Satire: gelesene, nicht-Wikipedia-Seiten als Quellen {name, titel, link, text, art, datum} (Text = relevante Sätze)."""
    kw = stichwoerter(ergebnis.get("frage", ""))
    out = []
    for q in ergebnis.get("quellen", []):
        text = (ergebnis.get("texte") or {}).get(q["url"])
        if not q.get("gelesen") or not text or wikipedia.ist_wikipedia(q["url"]):
            continue
        rel = " ".join(s for _, s in relevante_saetze(text, kw, False, 8)) or text[:1200]
        out.append({"name": q["betreiber"], "titel": q["titel"], "link": q["url"], "text": rel[:1800], "art": "seite", "datum": q.get("datum")})
        if len(out) >= max_n:
            break
    return out


def bericht(ergebnis: dict) -> str:
    """Prüfbericht-Abschnitt „Recherche“ (Markdown): Schritte, Quellen mit Datum/Eigentümer, Aussagen, Widersprüche."""
    e = ergebnis
    z = ["## Recherche", "", f"Frage: {e['frage']} · Bereich {e['bereich']} · Stand {e['stand']}", "", "### Schritte", ""]
    z += [f"{i}. {s}" for i, s in enumerate(e["schritte"], 1)]
    z += ["", "### Quellen", ""]
    for q in e["quellen"]:
        z.append(f"- {q['betreiber']} ({q['typ']}; {q['eigentuemer'] or 'Eigentümer unbekannt'}) – Datum {q['datum'] or 'unbekannt'}"
                 + (f", geändert {q['geaendert']}" if q.get("geaendert") and q["geaendert"] != q["datum"] else "")
                 + f" – {q['url']}" + ("" if q["gelesen"] else f" [nicht gelesen: {q['fehler']}]"))
    z += ["", "### Aussagen", ""]
    for a in e["aussagen"]:
        z.append(f"- [{a['status']}] {a['text']}" + (f" ({a['hinweis']})" if a.get("hinweis") else ""))
        z += [f"    - {b['quelle']} ({b['datum'] or 'ohne Datum'}): „{b['zitat'][:200]}“ {b['url']}"
              + (f" – zählt nicht: {b['zaehlt_nicht']}" if b.get("zaehlt_nicht") else "") for b in a["belege"]]
    if not e["aussagen"]:
        z.append("- (keine belegten Aussagen)")
    if e["widersprueche"]:
        z += ["", "### Widersprüche / Stände", ""]
        for w in e["widersprueche"]:
            z.append(f"- {w['art']}: " + " ↔ ".join(f"{v['zahlen']} ({v['bezug'] or v['datum'] or '?'}; {', '.join(dict.fromkeys(v['quellen']))})"
                                                    for v in w["varianten"]) + f" – {w['hinweis']}")
    if e["hinweise"]:
        z += ["", "### Hinweise", ""] + [f"- {h}" for h in e["hinweise"]]
    return "\n".join(z) + "\n"
