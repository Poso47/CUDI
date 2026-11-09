"""Wikipedia-Regel: Beleg nur in den Bereichen „fakten“ und „geschichte“, nur zusätzlich zu einer Nicht-Wikipedia-Quelle und nur,
wenn die Seite keine Manipulations-/Streitzeichen trägt (MediaWiki-API: Bausteine, Rückgängig-Häufung, viele Änderungen in 30 Tagen,
Seitenschutz wegen Streit). Alles andere: Wikipedia ist höchstens ein Suchhinweis, nie ein Beleg. Fällt die Prüfung aus, zählt Wikipedia nicht."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

from . import cache, web

BEREICHE = ("fakten", "geschichte")
WIKI_HOST = re.compile(r"(^|\.)(wikipedia|wikimedia|wikidata|wikivoyage|wikibooks|wikiquote|wikisource|wiktionary)\.org$", re.I)
BAUSTEINE = re.compile(
    r"neutralit[äa]t|\bpov\b|\bnpov\b|disputed|dispute|umstritten|belege fehlen|\bbelege\b|unreferenced|citation needed|more citations|"
    r"quellen fehlen|\bquelle fehlt\b|überarbeiten|edit ?war|bearbeitungskonflikt|fact.?check|dubios|ungesichert|"
    r"totally disputed|in dispute|contentious|globalize|unbelegt|verdacht|werbung|advert|\bcoi\b|conflict of interest", re.I)
REVERT = re.compile(r"revert|rückgängig|rueckgaengig|zurückgesetzt|zurueckgesetzt|\brv\b|\brvv?\b|undid|rollback|zurücksetz", re.I)
STREIT = re.compile(r"edit.?war|bearbeitungskonflikt|streit|dispute|konflikt|content dispute|controvers|umstritten|sperr.*(inhalt|streit)", re.I)
REVERT_TAGS = ("mw-undo", "mw-rollback", "mw-manual-revert", "mw-reverted", "mw-blank")


def ist_wikipedia(url_oder_host: str) -> bool:
    s = str(url_oder_host or "")
    host = (urlparse(s).hostname if "//" in s else s.split("/")[0]) or ""
    return bool(WIKI_HOST.search(host.lower()))


def schwellen() -> dict:
    def zahl(name, std):
        try:
            return int(os.environ.get(name, std))
        except ValueError:
            return std
    return {"tage": 30, "aenderungen": zahl("CUDI_WIKI_MAX_AENDERUNGEN", 40), "rueckgaengig": zahl("CUDI_WIKI_MAX_REVERTS", 3)}


def titel_aus_url(url: str) -> tuple[str, str] | None:
    p = urlparse(url)
    m = re.match(r"([a-z-]+)\.wikipedia\.org$", (p.hostname or "").lower())
    if not m:
        return None
    if p.path.startswith("/wiki/"):
        return m[1], unquote(p.path[6:]).replace("_", " ")
    q = dict(x.split("=", 1) for x in p.query.split("&") if "=" in x)
    return (m[1], unquote(q["title"]).replace("_", " ")) if "title" in q else None


def pruefe_seite(url_oder_titel: str, lang: str = "de", jetzt: datetime | None = None, api=None) -> dict:
    """{"ok": bool, "zeichen": [Text], "titel", "geprueft": bool, "kennzahlen": {...}}. ok=False bei jedem Zeichen
    und bei Ausfall der Prüfung (geprueft=False). `api(lang, params) -> dict` ist für Tests austauschbar."""
    t = titel_aus_url(url_oder_titel) if url_oder_titel.startswith("http") else (lang, url_oder_titel)
    if not t:
        return {"ok": False, "geprueft": False, "titel": url_oder_titel, "zeichen": ["keine Wikipedia-Adresse"], "kennzahlen": {}}
    lang, titel = t
    jetzt = jetzt or datetime.now(timezone.utc)
    seit = jetzt - timedelta(days=schwellen()["tage"])
    params = {"action": "query", "format": "json", "formatversion": 2, "titles": titel, "redirects": 1,
              "prop": "info|templates|revisions", "inprop": "protection", "tllimit": 500, "tlnamespace": 10,
              "rvprop": "timestamp|comment|tags|user", "rvlimit": 100, "rvend": seit.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "list": "logevents", "letype": "protect", "letitle": titel, "lelimit": 3}
    key = f"{lang}|{titel}|{jetzt.date().isoformat()}"
    data = cache.lade("wikipedia", key, 6)
    if data is None:
        try:
            data = (api or _api)(lang, params)
        except Exception as exc:                                  # noqa: BLE001 – Ausfall = Wikipedia zählt nicht
            return {"ok": False, "geprueft": False, "titel": titel, "kennzahlen": {},
                    "zeichen": [f"Wikipedia-Prüfung nicht möglich ({type(exc).__name__}) – Wikipedia zählt nicht"]}
        cache.speichere("wikipedia", key, data)
    zeichen: list[str] = []
    q = data.get("query") or {}
    page = next(iter(q.get("pages") or []), {}) or {}
    if page.get("missing"):
        return {"ok": False, "geprueft": True, "titel": titel, "zeichen": ["Seite existiert nicht"], "kennzahlen": {}}
    for tpl in page.get("templates") or []:
        name = re.sub(r"^[^:]+:", "", tpl.get("title", ""))
        if BAUSTEINE.search(name):
            zeichen.append(f"Baustein „{name}“")
    revs = page.get("revisions") or []
    s = schwellen()
    in_frist = [r for r in revs if (r.get("timestamp") or "") >= seit.strftime("%Y-%m-%dT%H:%M:%SZ")]
    reverts = [r for r in in_frist if REVERT.search(r.get("comment") or "") or any(t in REVERT_TAGS for t in r.get("tags") or [])]
    if len(in_frist) >= s["aenderungen"]:
        zeichen.append(f"{len(in_frist)} Änderungen in {s['tage']} Tagen")
    if len(reverts) >= s["rueckgaengig"]:
        zeichen.append(f"{len(reverts)} Rückgängig-Machungen in {s['tage']} Tagen (Editwar-Verdacht)")
    schutz = [p for p in page.get("protection") or [] if p.get("type") == "edit" and p.get("level") not in ("", None, "all")]
    if schutz:
        grund = " ".join((e.get("comment") or "") for e in q.get("logevents") or [])
        if STREIT.search(grund):
            zeichen.append("Seitenschutz wegen Streit/Editwar")
    return {"ok": not zeichen, "geprueft": True, "titel": page.get("title", titel), "zeichen": zeichen,
            "kennzahlen": {"aenderungen_30t": len(in_frist), "rueckgaengig_30t": len(reverts), "geschuetzt": bool(schutz)}}


def _api(lang: str, params: dict) -> dict:
    import requests

    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, headers={"User-Agent": web.USER_AGENT}, timeout=15)
    r.raise_for_status()
    return r.json()


def darf_belegen(bereich: str, url: str, andere_stuetzen: bool, pruefung: dict | None = None) -> tuple[bool, str]:
    """(erlaubt, Grund). andere_stuetzen = mindestens eine Nicht-Wikipedia-Quelle stützt dieselbe Aussage."""
    if not ist_wikipedia(url):
        return True, ""
    if bereich not in BEREICHE:
        return False, f"Wikipedia ist im Bereich „{bereich}“ kein Beleg (nur Suchhinweis)"
    if not andere_stuetzen:
        return False, "Wikipedia allein reicht nicht – keine Nicht-Wikipedia-Quelle stützt die Aussage"
    p = pruefung if pruefung is not None else pruefe_seite(url)
    if not p.get("ok"):
        return False, "Wikipedia zählt nicht: " + "; ".join(p.get("zeichen") or ["Prüfung nicht bestanden"])
    return True, ""
