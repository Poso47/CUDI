"""Suchwege in Rangfolge, jeder einzeln abgesichert:
 (a) App-Lauf: Schreibaufgabe `recherche_suche` – die Claude-Sitzung sucht mit ihren Web-Werkzeugen und liefert NUR Gefundenes mit Adresse;
 (b) Brave Search API (kostenlose Stufe, `CUDI_BRAVE_API_KEY`, optional);
 (c) DuckDuckGo-HTML ohne Schlüssel (sparsam, mit Pause, robots.txt);
 (d) GDELT DOC (aktuelle Nachrichten);
 (e) Fachquellen je Bereich (Eurostat, Weltbank, Europe PMC).
Treffer: {url, titel, datum, auszug, weg}. Gelesen und belegt wird später nur, was der Code selbst von der Seite laden kann."""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .. import handoff
from . import cache, fachquellen, web
from .lesen import parse_datum

ZEITRAUM_TAGE = {"tag": 1, "woche": 7, "monat": 31, "jahr": 366}
NEWS_BEREICHE = ("news", "reportage", "satire", "briefing", "ideen")
DDG_PAUSE, GDELT_PAUSE = 2.0, 5.5
# Sprachfokus: deutsche Suche (Region DE; AT/CH per CUDI_RECHERCHE_REGION), Englisch nur ergänzend zum Abgleich von Fakten
KL = {"DE": "de-de", "AT": "at-de", "CH": "ch-de"}


def region() -> str:
    r = os.environ.get("CUDI_RECHERCHE_REGION", "DE").strip().upper()
    return r if r in KL else "DE"
_lock = threading.Lock()
_zuletzt: dict[str, float] = {}

TASK = "recherche_suche"
ANLEITUNG = (
    "Recherchiere im Internet mit deinen Web-Werkzeugen (WebSearch, WebFetch) zu den „anfragen“ (Stand = „heute“; bevorzuge "
    "die AKTUELLSTEN Seiten, im „zeitraum“ falls angegeben). Liefere NUR Seiten, die du wirklich gefunden hast, mit ihrer echten "
    "Adresse – niemals eine Adresse raten oder aus dem Gedächtnis ergänzen. Bevorzuge Primärquellen (Behörden, Statistikämter, "
    "Studien, Originalmitteilungen) und unabhängige Redaktionen verschiedener Eigentümer; Wikipedia nur als Hinweis, nicht als "
    "Treffer. Je Treffer: „url“, „titel“, „datum“ (Veröffentlichung/Änderung, JJJJ-MM-TT, leer wenn unbekannt), „auszug“ (höchstens "
    "300 Zeichen, wörtlich von der Seite). Höchstens 12 Treffer. Antwort NUR als JSON: "
    "{\"treffer\": [{\"url\": \"…\", \"titel\": \"…\", \"datum\": \"…\", \"auszug\": \"…\"}]}")


def _warte(name: str, sek: float) -> None:
    with _lock:
        wait = sek - (time.monotonic() - _zuletzt.get(name, 0.0))
        _zuletzt[name] = time.monotonic() + max(0.0, wait)
    if wait > 0:
        time.sleep(wait)


def _tage(zeitraum) -> int | None:
    if isinstance(zeitraum, int):
        return zeitraum
    return ZEITRAUM_TAGE.get(str(zeitraum or "").lower())


def _treffer(url, titel="", datum=None, auszug="", weg="") -> dict | None:
    url = str(url or "").strip()
    if not web.erlaubt_url(url):
        return None
    return {"url": url, "titel": " ".join(str(titel or "").split())[:200], "datum": parse_datum(datum),
            "auszug": " ".join(str(auszug or "").split())[:400], "weg": weg}


def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for t in items:
        key = re.sub(r"^https?://(www\.)?", "", t["url"].split("#")[0]).rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


# --------------------------------------------------------------------------- (a) Claude

def weg_claude(anfragen: list[str], sprache: str, zeitraum, aufgabe: str = TASK) -> list[dict]:
    """Nur mit Claude-Sitzung (`CUDI_SCHREIBEN`); im Notbetrieb hat das Sprachmodell kein Internet und erfindet Adressen."""
    if not handoff.enabled():
        return []
    answer = handoff.request(aufgabe, ANLEITUNG, {"anfragen": anfragen, "sprache": sprache, "zeitraum": zeitraum,
                                                  "heute": datetime.now().date().isoformat()})
    rows = answer.get("treffer") if isinstance(answer, dict) else answer
    out = [t for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)
           if (t := _treffer(r.get("url"), r.get("titel"), r.get("datum"), r.get("auszug"), "Claude-Websuche"))]
    return out[:12]


# --------------------------------------------------------------------------- (b) Brave

def weg_brave(anfrage: str, sprache: str, zeitraum) -> list[dict]:
    key = os.environ.get("CUDI_BRAVE_API_KEY", "").strip()
    if not key:
        return []
    params = {"q": anfrage, "count": 10, "search_lang": sprache, "country": region() if sprache == "de" else "US"}
    fresh = {1: "pd", 7: "pw", 31: "pm", 366: "py"}.get(_tage(zeitraum) or 0)
    if fresh:
        params["freshness"] = fresh
    r = requests.get("https://api.search.brave.com/res/v1/web/search", params=params, timeout=15,
                     headers={"X-Subscription-Token": key, "Accept": "application/json", "User-Agent": web.USER_AGENT})
    r.raise_for_status()
    rows = (r.json().get("web") or {}).get("results") or []
    return [t for x in rows if (t := _treffer(x.get("url"), x.get("title"), x.get("page_age") or x.get("age"),
                                              re.sub(r"<[^>]+>", "", x.get("description") or ""), "Brave Search"))]


# --------------------------------------------------------------------------- (c) DuckDuckGo-HTML

def ddg_parse(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    out = []
    for res in soup.select("div.result, div.web-result"):
        a = res.select_one("a.result__a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/l/" in href:
            href = unquote((parse_qs(urlparse(href).query).get("uddg") or [""])[0])
        sn = res.select_one(".result__snippet")
        if t := _treffer(href, a.get_text(" "), None, sn.get_text(" ") if sn else "", "DuckDuckGo"):
            out.append(t)
    return out


def weg_ddg(anfrage: str, sprache: str, zeitraum) -> list[dict]:
    url = "https://html.duckduckgo.com/html/"
    if not web.robots_erlaubt(url):
        raise web.WebFehler("robots.txt von DuckDuckGo verbietet die Suche")
    _warte("ddg", DDG_PAUSE)
    data = {"q": anfrage, "kl": KL[region()] if sprache == "de" else "us-en"}
    df = {1: "d", 7: "w", 31: "m", 366: "y"}.get(_tage(zeitraum) or 0)
    if df:
        data["df"] = df
    r = requests.post(url, data=data, timeout=15, headers={"User-Agent": web.USER_AGENT, "Accept-Language": "de,en;q=0.7"})
    if r.status_code == 202 or "anomaly" in r.text[:4000].lower():
        raise web.WebFehler("DuckDuckGo verlangt eine Bestätigung (Captcha) – Weg übersprungen")
    r.raise_for_status()
    return ddg_parse(r.text)


# --------------------------------------------------------------------------- (d) GDELT

def weg_gdelt(anfrage: str, sprache: str, zeitraum) -> list[dict]:
    _warte("gdelt", GDELT_PAUSE)
    tage = _tage(zeitraum) or 7
    q = anfrage + (" sourcelang:german" if sprache == "de" else " sourcelang:english")
    r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", timeout=20, headers={"User-Agent": web.USER_AGENT},
                     params={"query": q, "mode": "artlist", "format": "json", "maxrecords": 10, "sort": "datedesc",
                             "timespan": f"{min(tage, 90)}d"})
    r.raise_for_status()
    try:
        arts = r.json().get("articles") or []
    except ValueError:
        return []
    out = []
    for a in arts:
        d = a.get("seendate", "")
        d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 and d[:8].isdigit() else None
        if t := _treffer(a.get("url"), a.get("title"), d, "", "GDELT"):
            out.append(t)
    return out


# --------------------------------------------------------------------------- Gesamt

def suche(anfrage, sprache: str = "de", zeitraum=None, bereich: str | None = None, aufgabe: str = TASK,
          wege: list[str] | None = None, genug: int = 6) -> dict:
    """-> {"treffer": [...], "schritte": [...]}. `anfrage` = Text oder Liste. Generische Wege (Claude, Brave, DuckDuckGo) laufen der Reihe
    nach, bis `genug` Treffer da sind; GDELT (aktuelle Nachrichten) und Fachquellen kommen je nach Bereich dazu."""
    anfragen = [a for a in ([anfrage] if isinstance(anfrage, str) else list(anfrage)) if a and a.strip()][:5]
    schritte: list[str] = []
    treffer: list[dict] = []
    if not anfragen:
        return {"treffer": [], "schritte": ["Keine Suchanfrage"]}
    key = "|".join(anfragen) + f"|{sprache}|{zeitraum}|{bereich}|{wege}"
    if (hit := cache.lade("suche", key, 6)) is not None:
        hit["schritte"] = [s + " (aus dem Cache)" if not s.endswith("Cache)") else s for s in hit["schritte"]]
        return hit
    erlaubt = set(wege or ("claude", "brave", "ddg", "gdelt", "fach"))

    def versuche(name: str, label: str, func, pro_anfrage: bool) -> int:
        if name not in erlaubt:
            return 0
        found: list[dict] = []
        for a in (anfragen if pro_anfrage else [None]):
            if pro_anfrage and not cache.verbrauche("suchen"):
                schritte.append(f"{label}: Suchbegrenzung erreicht")
                break
            try:
                found += func(a) if pro_anfrage else func()
            except handoff.WritingNeeded:
                raise
            except Exception as exc:                                    # noqa: BLE001 – jeder Weg einzeln abgesichert
                schritte.append(f"{label}: nicht verfügbar ({type(exc).__name__}: {str(exc)[:80]})")
                break
            if pro_anfrage and len(found) >= 12:
                break
        found = _dedupe(found)
        if found:
            schritte.append(f"{label}: {len(found)} Treffer für „{'“, „'.join(anfragen[:2]) if not pro_anfrage else anfragen[0]}“" + (" …" if len(anfragen) > 1 else ""))
        treffer.extend(found)
        return len(found)

    if handoff.enabled() and "claude" in erlaubt:
        versuche("claude", "Claude-Websuche", lambda: weg_claude(anfragen, sprache, zeitraum, aufgabe), False)
    if len(_dedupe(treffer)) < genug:
        versuche("brave", "Brave Search", lambda a: weg_brave(a, sprache, zeitraum), True)
    if len(_dedupe(treffer)) < genug:
        versuche("ddg", "DuckDuckGo", lambda a: weg_ddg(a, sprache, zeitraum), True)
    if bereich in NEWS_BEREICHE or (_tage(zeitraum) or 999) <= 31 or len(_dedupe(treffer)) < 3:
        versuche("gdelt", "GDELT (aktuelle Nachrichten)", lambda a: weg_gdelt(a, sprache, zeitraum), True)
    if "fach" in erlaubt:
        try:
            fach = fachquellen.finde(anfragen[0], sprache, bereich)
        except Exception as exc:                                        # noqa: BLE001
            fach = []
            schritte.append(f"Fachquellen: nicht verfügbar ({type(exc).__name__})")
        if fach:
            schritte.append("Fachquellen: " + ", ".join(sorted({f['weg'] for f in fach})))
        treffer.extend(fach)
    if not treffer:
        schritte.append("Kein Suchweg lieferte Treffer")
    res = {"treffer": _dedupe(treffer), "schritte": schritte}
    if res["treffer"]:
        cache.speichere("suche", key, res)
    return res
