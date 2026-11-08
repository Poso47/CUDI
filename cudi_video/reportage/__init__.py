"""Videoart „Reportage“: sachlich, respektvoll, für Nachrichten und Hintergrund – auch heikle Themen.

Ablauf (`run`): Quellen sammeln (News-Reporter-Daten aus firma_daten/news.json, Wikipedia, vom Nutzer genannte
Links) -> Claude (bzw. Notbetrieb-Modell) formuliert Sätze mit wörtlichen Belegen (Aufgabe „reportage“, Regeln
`firma.ideen.REPORTAGE_REGELN`) -> jeder Satz wird streng geprüft (Beleg wörtlich in der Quelle, ≥ 2 unabhängige
Betreiber, Zahlen und Namen nur aus den Belegen, kein Clickbait/Drama/Spekulation) -> ruhiges Video im Buchlook
(Stil „manuskript“, keine Musik, keine Maskottchen), Quellen und Stand am Ende. Ohne Antwort der Schreibaufgabe
gilt der Regelweg (Sätze, die in zwei Quellen stehen). Reicht die Quellenlage nicht, endet der Auftrag ehrlich mit
einer Meldung – nichts wird ergänzt oder erfunden.
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import handoff, textcheck
from ..metadata import CLICKBAIT

log = logging.getLogger(__name__)

MIN_SENTENCES, MAX_SENTENCES = 3, 8
MIN_PUBLISHERS = 2                       # unabhängige Betreiber je Aussage
TITLE_MAX = 60
TEXT_LIMIT = 1800                        # Zeichen je Quelle in der Schreibaufgabe
DRAMA = re.compile(
    r"schock\w*|dramati\w*|grausam\w*|brutal\w*|furchtbar\w*|entsetzlich\w*|erschütternd\w*|sensation\w*|skandal\w*|"
    r"unfassbar\w*|horror\w*|blutig\w*|"
    r"shocking|dramatic|horrific|brutal|gruesome|sensational|scandal\w*|horrifying|bloody", re.I)
SPECULATION = re.compile(
    r"\b(vermutlich|wahrscheinlich|möglicherweise|offenbar|angeblich|gerüchte\w*|könnte|dürfte|spekulation\w*|"
    r"probably|possibly|allegedly|apparently|rumou?rs?|might|speculat\w*)\b", re.I)

TASK = "reportage"
INSTRUCTIONS = (
    "Schreibe den Sprechtext einer sachlichen, respektvollen Kurz-Reportage (Hochformat-Video, ruhig gesprochen) NUR aus "
    "den gelieferten Quellen. Regeln: {regeln} Jeder Satz ist eine einzelne, neutral formulierte Tatsache aus "
    "den Quellen (höchstens 30 Wörter), mit Zeitbezug, wo er in der Quelle steht. Jeder Satz braucht „belege“: mindestens "
    "zwei Einträge aus VERSCHIEDENEN Quellen (Feld „quelle“ = ihre Kennung wie Q1), jeder mit „zitat“ = eine "
    "WÖRTLICHE, unveränderte Textstelle (5 bis 25 Wörter) aus dieser Quelle, die den Satz stützt. Zahlen, Namen, Orte und "
    "Daten dürfen nur vorkommen, wenn sie in den Zitaten stehen. Keine Wertung, keine Spekulation (kein „vermutlich“, "
    "„könnte“), keine Spannungs- oder Schock-Wörter, keine Namen von Opfern oder Betroffenen, keine Schuldzuweisung "
    "ohne Quelle, kein Aufruf zum Kommentieren. Lieber weniger Sätze als ein unbelegter. 4 bis 8 Sätze, in der Sprache "
    "„sprache“. Schlage außerdem einen sachlichen Titel vor (höchstens 60 Zeichen, ohne Clickbait). Antwort NUR als JSON: "
    "{{\"titel\": \"…\", \"saetze\": [{{\"text\": \"…\", \"belege\": [{{\"quelle\": \"Q1\", \"zitat\": \"…\"}}, "
    "{{\"quelle\": \"Q2\", \"zitat\": \"…\"}}]}}]}}")


class ReportageError(RuntimeError):
    """Quellenlage reicht nicht (oder Quellen unerreichbar) – ehrliche Meldung statt erfundener Inhalte."""

    wiederholbar = False


# --------------------------------------------------------------------------- Quellen

def _norm(text: str) -> str:
    text = html.unescape(str(text or "")).replace("„", '"').replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().casefold()


def _publisher(url: str) -> str:
    from ..firma.news import publisher_of

    return publisher_of(url) if url else ""


def news_quellen(thema: str, links: list[str]) -> list[dict]:
    """Bestätigte Meldungen des News-Reporters (firma_daten/news.json), die zum Thema oder zu den Links passen:
    jede Quelle mit ihrer Überschrift (Betreiber getrennt gezählt)."""
    from ..firma import common, news

    data = common.read_json("news.json", {}) or {}
    want, wanted_links = news.tokens(thema), {l.split("#")[0] for l in links}
    out: list[dict] = []
    for m in data.get("meldungen", []):
        urls = {q.get("link", "").split("#")[0] for q in m.get("quellen", [])} | {m.get("link", "")}
        if not (urls & wanted_links or (want and news.similar(want, news.tokens(m.get("titel", ""))))):
            continue
        for q in m.get("quellen") or [{"quelle": m.get("quelle"), "titel": m.get("titel"), "link": m.get("link")}]:
            text = q.get("titel", "") + (". " + m["kurz"] if m.get("kurz") and q.get("link") == m.get("link") else "")
            out.append({"name": q.get("quelle") or _publisher(q.get("link", "")), "titel": q.get("titel", ""),
                        "link": q.get("link", ""), "text": news.clean(text, 600), "art": "news"})
    return out


def wikipedia_quelle(thema: str, lang: str) -> list[dict]:
    from .. import net

    data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": thema, "gsrlimit": 1,
        "prop": "extracts|info", "exintro": 1, "explaintext": 1, "inprop": "url", "redirects": 1})
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    return [{"name": "Wikipedia", "titel": p.get("title", ""), "link": p.get("fullurl", ""),
             "text": re.sub(r"\s+", " ", p.get("extract", "")).strip(), "art": "wikipedia"}
            for p in pages[:1] if p.get("extract")]


def seite_quelle(url: str) -> list[dict]:
    """Eigener Link des Nutzers: Titel und Absätze der Seite (nur Text)."""
    from bs4 import BeautifulSoup

    from .. import net

    soup = BeautifulSoup(net.get(url, timeout=25, retries=1).text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    og = soup.find("meta", property="og:title")
    title = (og.get("content") if og else "") or (soup.title.string if soup.title else "")
    paragraphs = [re.sub(r"\s+", " ", p.get_text(" ")).strip() for p in soup.find_all("p")]
    text = " ".join(p for p in paragraphs if len(p) > 60)
    name = _publisher(url)
    return [{"name": name.upper() if len(name) <= 4 else name.capitalize(), "titel": str(title or "").strip(), "link": url,
             "text": text, "art": "seite"}] if text else []


def sammle(thema: str, links: list[str], lang: str) -> tuple[list[dict], list[str]]:
    """Alle Quellen (je Quelle bleibt ein Fehler lokal) – Rückgabe (Quellen mit Kennung Q1…, Hinweise)."""
    notes: list[str] = []
    raw: list[dict] = []
    for name, func in (("News-Reporter", lambda: news_quellen(thema, links)),
                       ("Wikipedia", lambda: wikipedia_quelle(thema, lang))):
        try:
            raw += func()
        except Exception as exc:                          # noqa: BLE001 – eine Quelle darf ausfallen
            notes.append(f"{name} nicht erreichbar ({type(exc).__name__})")
    for url in links:
        if any(q["link"].split("#")[0] == url.split("#")[0] and q.get("text") for q in raw):
            continue
        try:
            raw += seite_quelle(url)
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"Link {_publisher(url)} nicht lesbar ({type(exc).__name__})")
    out, seen = [], set()
    for q in raw:
        key = (q["name"].casefold(), _norm(q["titel"]))
        if not q.get("text") or key in seen:
            continue
        seen.add(key)
        out.append({**q, "id": f"Q{len(out) + 1}",
                    "betreiber": q["name"].casefold() if q["art"] != "seite" else _publisher(q["link"])})
    return out, notes


# --------------------------------------------------------------------------- Prüfung

def pruefe_satz(satz: dict, quellen: dict[str, dict], lang: str) -> tuple[dict | None, str]:
    """Ein Satz der Schreibaufgabe. Rückgabe (geprüfter Satz mit Belegen, "") oder (None, Grund)."""
    text = re.sub(r"\s+", " ", str(satz.get("text") or "")).strip()
    if not text:
        return None, "leerer Satz"
    if len(text.split()) > 40:
        return None, "zu lang"
    verified, quotes = [], []
    for b in satz.get("belege") or []:
        b = b if isinstance(b, dict) else {}
        q = quellen.get(b.get("quelle"))
        zitat = _norm(b.get("zitat"))
        if q and len(zitat.split()) >= 3 and zitat in _norm(q["text"]):
            if q["betreiber"] not in {v["betreiber"] for v in verified}:
                verified.append({"quelle": q["id"], "name": q["name"], "betreiber": q["betreiber"],
                                 "zitat": str(b["zitat"]).strip()})
            quotes.append(str(b["zitat"]))
    if len(verified) < MIN_PUBLISHERS:
        return None, f"nur {len(verified)} wörtlich belegte unabhängige Quelle(n)"
    quote_text = " ".join(quotes)
    extra = textcheck.numbers(text, lang) - (textcheck.numbers(quote_text, lang) | textcheck.digits(quote_text))
    if extra:
        return None, "Zahl ohne Beleg: " + ", ".join(sorted(extra))
    if textcheck.invented_people(text, quote_text):
        return None, "Name ohne Beleg"
    for rule, name in ((CLICKBAIT, "Clickbait"), (DRAMA, "reißerisches Wort"), (SPECULATION, "Spekulation")):
        if found := rule.search(text):
            return None, f"{name}: „{found.group(0)}“"
    return {"text": text, "belege": verified}, ""


def pruefe_antwort(answer, quellen: list[dict], lang: str) -> tuple[list[dict], list[tuple[str, str]], str]:
    """Antwort der Schreibaufgabe prüfen. Rückgabe (geprüfte Sätze, verworfene (Satz, Grund), Titelvorschlag)."""
    by_id = {q["id"]: q for q in quellen}
    items = answer.get("saetze") if isinstance(answer, dict) else None
    accepted, rejected = [], []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ok, why = pruefe_satz(item, by_id, lang)
        if ok and ok["text"] not in {a["text"] for a in accepted}:
            accepted.append(ok)
        elif not ok:
            rejected.append((str(item.get("text") or "")[:120], why))
    return accepted[:MAX_SENTENCES], rejected, str(answer.get("titel") or "") if isinstance(answer, dict) else ""


ABBREV = re.compile(r"(?:\b(?:Dr|Prof|Nr|St|Mr|Mrs|Ms|bzw|ca|usw|vs|Jr|Sr)|\b[a-zA-Z])\.$")


def _sentences(text: str) -> list[str]:
    """Sätze am Satzende trennen – nicht nach Ordnungszahlen („20. Juli“) und gängigen Abkürzungen."""
    parts: list[str] = []
    for piece in re.split(r"(?<=[^\d\s][.!?])\s+(?=[A-ZÄÖÜ0-9„\"])", text):
        if parts and ABBREV.search(parts[-1]):
            parts[-1] += " " + piece
        else:
            parts.append(piece)
    return [s.strip() for s in parts if 25 <= len(s.strip()) <= 260]


def _content(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]{5,}", text.casefold())) | {f"#{n}" for n in re.findall(r"\d+", text)}


def regel_saetze(quellen: list[dict]) -> list[dict]:
    """Ohne Schreibaufgabe: Sätze, die wörtlich in einer Quelle stehen UND von einer zweiten (anderer Betreiber) mit
    mindestens 60 % ihrer Inhaltswörter/Zahlen gestützt werden. Belege sind der Satz selbst und die Stelle der zweiten Quelle."""
    out = []
    for q in quellen:
        for s in _sentences(q["text"])[:12]:
            need = _content(s)
            if len(need) < 3:
                continue
            best = None
            for other in quellen:
                if other["betreiber"] == q["betreiber"]:
                    continue
                for o in _sentences(other["text"]) or [other["text"]]:
                    share = len(need & _content(o)) / len(need)
                    if share >= 0.6 and (best is None or share > best[0]):
                        best = (share, other, o)
            if best:
                out.append({"text": s, "belege": [{"quelle": q["id"], "zitat": s},
                                                  {"quelle": best[1]["id"], "zitat": best[2]}]})
    return out


# --------------------------------------------------------------------------- Skript, Texte

STRINGS = {
    "de": {"intro": "{titel}. Eine sachliche Einordnung – nur, was mehrere Quellen bestätigen.", "label": "Reportage",
           "outro": "Stand: {datum}. Quellen: {quellen}. Berichte können sich ändern.", "sources": "Quellen",
           "note": "Sachliche Zusammenfassung von Angaben, die mindestens zwei unabhängige Quellen bestätigen."},
    "en": {"intro": "{titel}. A factual overview – only what several sources confirm.", "label": "Report",
           "outro": "As of {datum}. Sources: {quellen}. Reports may change.", "sources": "Sources",
           "note": "A factual summary of details confirmed by at least two independent sources."},
}


def _datum(lang: str) -> str:
    from ..script import format_date

    return format_date(datetime.now(timezone.utc).date().isoformat(), lang)


def waehle_titel(vorschlag: str, thema: str, saetze: list[dict]) -> str:
    """Titel: Vorschlag nur, wenn sachlich (kein Clickbait/Drama, Zahlen aus den Sätzen), sonst das Thema des Nutzers."""
    allowed = textcheck.digits(" ".join(s["text"] for s in saetze) + " " + thema)
    for cand in (vorschlag, thema):
        cand = re.sub(r"\s+", " ", cand or "").strip().rstrip(".")
        if (cand and len(cand) <= TITLE_MAX and not CLICKBAIT.search(cand) and not DRAMA.search(cand)
                and not SPECULATION.search(cand) and textcheck.digits(cand) <= allowed):
            return cand
    short = re.sub(r"\s+", " ", thema).strip()
    return short if len(short) <= TITLE_MAX else short[:TITLE_MAX].rsplit(" ", 1)[0]


def baue_skript(titel: str, saetze: list[dict], lang: str, ident: str) -> dict:
    """Szenen-Skript für den Erklär-Renderer (Buchlook): Einstieg, ein Satz je Szene mit Quellen-Zeile, Quellen und Stand."""
    s = STRINGS[lang]
    names = list(dict.fromkeys(b["name"] for sat in saetze for b in sat["belege"]))
    scenes = [{"kapitel": s["label"], "text": s["intro"].format(titel=titel), "betont": [],
               "visual": {"typ": "beschriftung", "label": s["label"]}}]
    for sat in saetze:
        scenes.append({"kapitel": "", "text": sat["text"], "betont": [],
                       "visual": {"typ": "beschriftung", "label": " · ".join(dict.fromkeys(b["name"] for b in sat["belege"]))}})
    scenes.append({"kapitel": s["sources"], "text": s["outro"].format(datum=_datum(lang), quellen=", ".join(names)),
                   "betont": [], "visual": {"typ": "beschriftung", "label": s["sources"]}})
    return {"id": ident, "titel": titel, "sprache": lang, "szenen": scenes}


def abnahme(skript: dict, saetze: list[dict], titel: str) -> dict:
    """Endabnahme: gesprochen wird nur geprüfter Text plus feste Bausteine; Titel ohne Clickbait."""
    gruende = []
    spoken = [sz["text"] for sz in skript["szenen"][1:-1]]
    if spoken != [s["text"] for s in saetze]:
        gruende.append("Sprechtext weicht von den geprüften Sätzen ab")
    if len(spoken) < MIN_SENTENCES:
        gruende.append("zu wenig bestätigte Aussagen")
    if CLICKBAIT.search(titel) or DRAMA.search(titel):
        gruende.append("Titel nicht sachlich")
    return {"ok": not gruende, "gruende": gruende}


def texte(titel: str, saetze: list[dict], quellen: list[dict], lang: str) -> tuple[str, str]:
    """(youtube.txt, tiktok.txt): erste Zeile = Titel; Quellen mit Adresse nur in der Beschreibung."""
    s = STRINGS[lang]
    used = {b["quelle"] for sat in saetze for b in sat["belege"]}
    lines = [q for q in quellen if q["id"] in used]
    stand = _datum(lang)
    yt = [titel, "", s["note"], ""] + [sat["text"] for sat in saetze]
    yt += ["", f"{s['sources']} ({'Stand' if lang == 'de' else 'as of'} {stand}):"]
    yt += [f"- {q['name']}: {q['titel']} {q['link']}".rstrip() for q in lines]
    yt += ["", "#Nachrichten #Hintergrund #shorts" if lang == "de" else "#news #background #shorts"]
    names = ", ".join(dict.fromkeys(q["name"] for q in lines))
    tt = f"{titel} · {s['sources']}: {names} · {stand}"[:140] + (" #Nachrichten" if lang == "de" else " #news")
    return "\n".join(yt) + "\n", tt + "\n"


def pruefbericht(thema: str, quellen: list[dict], saetze: list[dict], rejected: list, notes: list[str], modus: str,
                 ab: dict) -> str:
    from ..firma.ideen import REPORTAGE_REGELN

    z = [f"# Prüfbericht Reportage: {thema}", "",
         f"Weg: {modus}. Endabnahme: " + ("bestanden" if ab["ok"] else "NICHT bestanden – " + "; ".join(ab["gruende"])),
         "Regeln: " + REPORTAGE_REGELN, "", "## Quellen", ""]
    z += [f"- {q['id']} {q['name']}: {q['titel']} {q['link']}" for q in quellen]
    z += ["", f"## Aussagen ({len(saetze)} bestätigt, je mit mindestens {MIN_PUBLISHERS} unabhängigen Quellen)", ""]
    for sat in saetze:
        z.append(f"- {sat['text']}")
        z += [f"    - {b['name']}: „{b['zitat']}“" for b in sat["belege"]]
    if rejected:
        z += ["", "## Verworfen", ""] + [f"- {t} – {why}" for t, why in rejected]
    if notes:
        z += ["", "## Hinweise", ""] + [f"- {n}" for n in notes]
    return "\n".join(z) + "\n"


# --------------------------------------------------------------------------- Auftrag

def run(order: dict, folder: Path, progress=lambda stage, f: None) -> dict:
    """Reportage-Auftrag -> Ergebnis im Format von job._summary (kind „reportage“)."""
    from ..erklaer import render_erklaerung, validate_script
    from ..firma.ideen import REPORTAGE_REGELN

    lang, thema = order["sprache"], order["thema"]
    out = folder / "reportage"
    out.mkdir(parents=True, exist_ok=True)
    cache = folder / "reportage_quellen.json"                 # ein Weiterlauf prüft gegen dieselben Texte
    notes: list[str] = []
    if cache.exists():
        quellen = json.loads(cache.read_text("utf-8"))
    else:
        progress("Quellen sammeln", 0.05)
        quellen, notes = sammle(thema, order.get("links") or [], lang)
        cache.write_text(json.dumps(quellen, ensure_ascii=False), "utf-8")
    if len({q["betreiber"] for q in quellen}) < MIN_PUBLISHERS:
        raise ReportageError("Reportage nicht möglich: Für dieses Thema liegen weniger als zwei unabhängige Quellen vor"
                             + (f" ({'; '.join(notes)})" if notes else "") + ". Bitte Links zu weiteren Quellen angeben.")
    progress("Aussagen prüfen", 0.2)
    answer = handoff.request(TASK, INSTRUCTIONS.format(regeln=REPORTAGE_REGELN), {
        "thema": thema, "sprache": lang, "stand": datetime.now(timezone.utc).date().isoformat(),
        "quellen": [{"id": q["id"], "name": q["name"], "titel": q["titel"], "text": q["text"][:TEXT_LIMIT]}
                    for q in quellen]})
    saetze, rejected, vorschlag = pruefe_antwort(answer, quellen, lang) if answer else ([], [], "")
    modus = "Schreibaufgabe + Prüfung" if saetze else "Regelweg (Sätze, die in zwei Quellen stehen)"
    if len(saetze) < MIN_SENTENCES:
        if answer:
            notes.append(f"Aus der Schreibaufgabe blieben {len(saetze)} geprüfte Sätze – Regelweg ergänzt.")
        extra, rej2, _ = pruefe_antwort({"saetze": regel_saetze(quellen)}, quellen, lang)
        saetze = (saetze + [e for e in extra if e["text"] not in {s["text"] for s in saetze}])[:MAX_SENTENCES]
        rejected += rej2
    if len(saetze) < MIN_SENTENCES:
        raise ReportageError(f"Reportage nicht möglich: Nur {len(saetze)} von mindestens {MIN_SENTENCES} Aussagen sind von "
                             "zwei unabhängigen Quellen wörtlich bestätigt. Es wird nichts ergänzt – bitte weitere "
                             "Quellen (Links) angeben.")
    titel = waehle_titel(vorschlag, thema, saetze)
    skript = validate_script(baue_skript(titel, saetze, lang, "reportage"))
    ab = abnahme(skript, saetze, titel)
    yt, tt = texte(titel, saetze, quellen, lang)
    (out / "youtube.txt").write_text(yt, "utf-8")
    (out / "tiktok.txt").write_text(tt, "utf-8")
    (out / "spec.json").write_text(json.dumps({"title": {"de": titel, "en": titel}}, ensure_ascii=False), "utf-8")
    (out / "review.md").write_text(pruefbericht(thema, quellen, saetze, rejected, notes, modus, ab), "utf-8")
    if not ab["ok"]:
        raise ReportageError("Endabnahme nicht bestanden: " + "; ".join(ab["gruende"]))
    progress("Video rendern", 0.3)
    result = render_erklaerung(skript, out, progress=lambda f: progress("Video rendern", 0.3 + 0.65 * f), musik=False)
    files = {"video": result["video"], "cover": result["cover"], "duration": result["duration"], "qa": result.get("qa"),
             "description_file": "youtube.txt", "caption_file": "tiktok.txt", "abnahme": ab}
    return {"output_dir": str(out), "videos": {lang: files}, "kind": "reportage", "warnings": notes}
