"""Videoart „Satire“: kurze, witzige Hochformat-Videos zu ECHTEN, bestätigten Nachrichten – nie mit einer Meldung zu verwechseln.

Grundsatz (Nutzerwunsch: nie lügen, auch nicht durch Formulierung): Satire ist immer als Satire erkennbar und steht auf einem
echten Kern. Aufbau (`run`):

  (a) Fakt – ein bis drei nüchterne Sätze, nur aus Meldungen, die mindestens zwei unabhängige Betreiber bringen
      (News-Reporter `firma_daten/news.json` oder eigene Links), mit wörtlichem Beleg; geprüft wie in der Reportage
      (`reportage.pruefe_satz`) UND vom Wahrheits-Prüfer (`wahrheit.Pruefer`);
  (b) Überspitzung – erkennbar übertrieben, jede mit einem Satire-Signal („angeblich“, „man stelle sich vor“ …);
  (c) Pointe.

Feste Regeln (`SATIRE_REGELN`, geprüft in `pruefe_satire`): „SATIRE“ dauerhaft im Bild, im Cover, im Titel und in der
Beschreibung; KEINE erfundenen Zitate (keine Anführungszeichen, kein „sagte X“); keine neuen Zahlen und Namen im
satirischen Teil; kein Spott gegen Gruppen (Herkunft, Religion, Behinderung …), keine Beleidigungen; heikle Themen (Tod,
Gewalt, Unglück …) werden abgelehnt („nur als Reportage“). Verstößt ein Modelltext, gilt die Regel-Fassung; hält auch die
nicht, endet der Auftrag ehrlich mit einer Meldung. Schreibaufgabe `satire` über `handoff` (Claude bzw. Notbetrieb-Modell).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import handoff, textcheck
from ..metadata import CLICKBAIT
from ..reportage import DRAMA, pruefe_satz, seite_quelle

log = logging.getLogger(__name__)

TASK = "satire"
MIN_FACTS, MAX_FACTS = 1, 3
MIN_PUBLISHERS = 2
TITLE_MAX = 60
MAX_WORDS = 32
TEXT_LIMIT = 1200

SATIRE_REGELN = (
    "Satire steht auf einem echten Kern (von mindestens zwei unabhängigen Quellen bestätigt) und ist immer als Satire "
    "gekennzeichnet (Bild, Cover, Titel, Beschreibung). Der Fakt-Teil ist nüchtern und belegt; der satirische Teil ist erkennbar "
    "übertrieben (Signalwörter wie „angeblich“, „man stelle sich vor“, „in einer Parallelwelt“), enthält keine neuen Zahlen oder "
    "Namen und behauptet nichts als wahr. Keine erfundenen Zitate echter Personen, keine Privatpersonen, kein Leid und keine "
    "Opfer, kein Spott gegen Gruppen (Herkunft, Religion, Behinderung, Geschlecht …); Spott gilt Mächtigen, Institutionen und "
    "Absurditäten.")

INSTRUCTIONS = (
    "Schreibe eine kurze Satire (Hochformat-Video, verschmitzt gesprochen) zu der ECHTEN, bestätigten Meldung in den Quellen. "
    "Aufbau: (a) „fakten“: 1 bis 3 nüchterne Sätze, nur aus den Quellen (höchstens 30 Wörter), jeder mit „belege“: mindestens "
    "zwei Einträge aus VERSCHIEDENEN Quellen (Feld „quelle“ = Kennung wie Q1), jeder mit „zitat“ = eine WÖRTLICHE, unveränderte "
    "Textstelle (mindestens 3 Wörter) aus dieser Quelle; Zahlen, Namen und Orte nur aus den Zitaten. (b) „ueberspitzungen“: 2 bis "
    "3 Sätze (höchstens 30 Wörter), die das Echte erkennbar übertreiben; JEDER enthält ein Satire-Signal wie „angeblich“, „man "
    "stelle sich vor“, „in einer Parallelwelt“ (englisch: allegedly, imagine, in a parallel world). (c) „pointe“: ein kurzer "
    "Schlusssatz. Regeln: {regeln} Zusätzlich: keine Anführungszeichen, kein „sagte/laut/said“, KEINE Zahlen und KEINE Namen "
    "im satirischen Teil, die nicht in den Fakten stehen, nichts als Tatsache behaupten, keine Beleidigungen. Sprache: „sprache“. "
    "Schlage außerdem einen kurzen Titel vor (höchstens 45 Zeichen, ohne Clickbait, ohne das Wort Satire – wird ergänzt). "
    "Antwort NUR als JSON: {{\"titel\": \"…\", \"fakten\": [{{\"text\": \"…\", \"belege\": [{{\"quelle\": \"Q1\", \"zitat\": \"…\"}}, "
    "{{\"quelle\": \"Q2\", \"zitat\": \"…\"}}]}}], \"ueberspitzungen\": [\"…\"], \"pointe\": \"…\"}}")


class SatireError(RuntimeError):
    """Satire nicht möglich (heikles Thema, zu wenig Quellen, Regelverstoß) – ehrliche Meldung statt unwahrer Inhalte."""

    wiederholbar = False


# --------------------------------------------------------------------------- Regeln

# Satire-Signale: der Zuschauer erkennt, dass das Folgende ausgedacht ist.
SIGNALE = re.compile(
    r"\b(angeblich|man stelle sich vor|stell dir vor|stellen wir uns vor|stell dir mal vor|in einer parallelwelt|"
    r"in einem paralleluniversum|was wäre,? wenn|hypothetisch\w*|rein erfunden|frei erfunden|im satire-?land|"
    r"allegedly|imagine|picture this|in a parallel (?:world|universe)|what if|hypothetical\w*|purely fictional|made[- ]up|"
    r"in satire land)\b", re.I)
ZITATZEICHEN = re.compile(r"[„“”\"«»‚‘]")
SAGTE = re.compile(
    r"\b(sagte\w*|sagt|erklärte\w*|meinte\w*|twitterte\w*|postete\w*|schrieb\w*|versprach\w*|forderte\w*|kündigte\w*|"
    r"said|says|tweeted|wrote|promised|demanded|announced|declared|claims?|claimed|told|according to|laut|zufolge|"
    r"nach angaben)\b", re.I)
GRUPPEN = re.compile(
    r"\b(ausländer\w*|migrant\w*|flüchtling\w*|asylant\w*|zuwanderer\w*|muslim\w*|islam\w*|juden|jüdisch\w*|christen|"
    r"katholik\w*|hindu\w*|atheist\w*|schwarze[nr]?|farbige\w*|asiaten|araber\w*|türken|russen|roma|sinti|behinderte\w*|"
    r"rollstuhl\w*|autisten|schwule\w*|lesben|homosexuelle\w*|transsexuell\w*|frauen|männer|weiber|rentner|senioren|ossis|"
    r"wessis|immigrants?|refugees?|muslims?|jews?|jewish|christians?|blacks?|asians?|arabs?|disabled|handicapped|gays?|"
    r"lesbians?|homosexuals?|transgender|women|elderly|foreigners?|gypsies)\b", re.I)
BELEIDIGUNG = re.compile(
    r"\b(idiot\w*|trottel\w*|dumm\w*|blöd\w*|vollpfosten\w*|depp\w*|schwachsinn\w*|lügner\w*|verbrecher\w*|betrüger\w*|"
    r"stupid|moron\w*|dumb|liars?|criminals?|crooks?|scum|losers?|retard\w*)\b", re.I)
BEHAUPTUNG = re.compile(
    r"\b(fakt ist|tatsächlich|in wahrheit|in wirklichkeit|wie jeder weiß|bewiesen|belegt|offiziell|bestätigt|laut experten|"
    r"enthüllt\w*|aufgedeckt|the truth is|in fact|actually|proven|confirmed|officially|experts say|revealed|exposed)\b", re.I)
SATIRE_WORT = re.compile(r"satire", re.I)


def heikel(*texts: str) -> bool:
    from ..firma.ideen import heikel as _heikel

    return _heikel(*texts)


def pruefe_satire(text: str, fakten_text: str, lang: str, signal: bool = True) -> tuple[str | None, str]:
    """Ein satirischer Satz. Rückgabe (bereinigter Satz, "") oder (None, Grund)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return None, "leerer Satz"
    if not 3 <= len(text.split()) <= MAX_WORDS:
        return None, "Länge"
    if signal and not SIGNALE.search(text):
        return None, "ohne Satire-Signal („angeblich“, „man stelle sich vor“ …)"
    if ZITATZEICHEN.search(text):
        return None, "Anführungszeichen (kein erfundenes Zitat)"
    for rule, name in ((SAGTE, "Zuschreibung („sagte“/„laut“) – kein erfundenes Zitat"), (GRUPPEN, "Spott gegen eine Gruppe"),
                       (BELEIDIGUNG, "Beleidigung"), (BEHAUPTUNG, "Tatsachenbehauptung"), (CLICKBAIT, "Clickbait"),
                       (DRAMA, "reißerisches Wort")):
        if found := rule.search(text):
            return None, f"{name}: „{found.group(0)}“"
    if heikel(re.sub(r"\b(war|dies)\b", "", text) if lang == "de" else text):     # „war“/„dies“: im Deutschen Alltagswörter
        return None, "heikles Thema im satirischen Teil"
    extra = textcheck.numbers(text, lang) - (textcheck.numbers(fakten_text, lang) | textcheck.digits(fakten_text))
    if extra:
        return None, "neue Zahl: " + ", ".join(sorted(extra))
    if textcheck.invented_people(text, fakten_text):
        return None, "neuer Name"
    return text, ""


def pruefe_satire_antwort(answer, fakten_text: str, lang: str) -> tuple[list[str], str, list[tuple[str, str]]]:
    """Überspitzungen und Pointe der Schreibaufgabe prüfen. Rückgabe (geprüfte Überspitzungen, Pointe oder "", verworfen)."""
    rejected: list[tuple[str, str]] = []
    over: list[str] = []
    pointe = ""
    if isinstance(answer, dict):
        raw = answer.get("ueberspitzungen")
        for item in raw if isinstance(raw, list) else []:
            ok, why = pruefe_satire(item, fakten_text, lang, signal=True)
            if ok and ok not in over:
                over.append(ok)
            elif not ok:
                rejected.append((str(item)[:120], why))
        if answer.get("pointe"):
            ok, why = pruefe_satire(answer.get("pointe"), fakten_text, lang, signal=False)
            if ok:
                pointe = ok
            else:
                rejected.append((str(answer.get("pointe"))[:120], why))
    return over[:3], pointe, rejected


# --------------------------------------------------------------------------- Regel-Fassung (ohne Modell)

# Bewusst allgemein: keine Zahlen, Namen oder Behauptungen – jeder Satz trägt ein Satire-Signal.
RULE_OVER = {
    "de": ["Man stelle sich vor, dazu würde sofort ein Krisenstab gegründet, der zuerst Kaffee kocht und dann einen Termin für das nächste Treffen sucht.",
           "In einer Parallelwelt würde die Sache mit mehreren Ausschüssen, Pressekonferenzen und einer Broschüre gefeiert, die niemand liest.",
           "Angeblich prüft ein Arbeitskreis nun, wer den Arbeitskreis leiten darf – Ergebnis offen, Sitzungsgeld sicher.",
           "Man stelle sich vor, jeder Beteiligte bekäme eine Urkunde dafür, dass er beteiligt ist."],
    "en": ["Imagine a crisis task force being set up at once, first making coffee and then looking for a date for the next meeting.",
           "In a parallel world this would be celebrated with several committees, press conferences and a brochure nobody reads.",
           "Allegedly a working group is now checking who may chair the working group – outcome open, attendance fee secure.",
           "Imagine everyone involved receiving a certificate for being involved."],
}
RULE_POINTE = {
    "de": ["Zum Schluss die Klarstellung: Echt ist nur der Anfang, alles danach ist Satire.",
           "Und die Moral: Der Anfang stimmt, der Rest ist Spaß."],
    "en": ["For the record: only the beginning was real, everything after that is satire.",
           "The moral: the start was true, the rest was just for fun."],
}
STRINGS = {
    "de": {"intro": "Achtung, Satire! Erst kommt, was wirklich passiert ist – danach wird kräftig übertrieben.",
           "outro": "Das war Satire. Echt war nur der erste Teil. Quellen: {quellen}. Stand: {datum}.",
           "echt": "ECHT", "erfunden": "AB HIER: ERFUNDEN", "pointe": "POINTE", "kern": "DER ECHTE KERN",
           "sources": "Quellen", "stand": "Stand",
           "note": "Dieses Video ist Satire. Echt ist nur der erste Teil, den mindestens zwei unabhängige Quellen bestätigen; "
                   "alles danach ist frei erfunden und übertrieben. Es gibt keine echten Zitate.",
           "tags": "#satire #news #shorts", "tt_tags": "#satire #fyp", "real": "Echt", "cover": "Echte Meldung – satirisch betrachtet"},
    "en": {"intro": "Heads up, satire! First what really happened – then we exaggerate wildly.",
           "outro": "That was satire. Only the first part was real. Sources: {quellen}. As of: {datum}.",
           "echt": "REAL", "erfunden": "FROM HERE: MADE UP", "pointe": "PUNCHLINE", "kern": "THE REAL PART",
           "sources": "Sources", "stand": "As of",
           "note": "This video is satire. Only the first part is real, confirmed by at least two independent sources; everything "
                   "after that is made up and exaggerated. There are no real quotes.",
           "tags": "#satire #news #shorts", "tt_tags": "#satire #fyp", "real": "Real", "cover": "A real story – seen satirically"},
}


def _pick(options: list[str], key: str, n: int) -> list[str]:
    start = int(hashlib.sha1(key.encode()).hexdigest()[:6], 16) % len(options)
    return [options[(start + i) % len(options)] for i in range(n)]


def regel_satire(lang: str, ident: str, fakten_text: str) -> tuple[list[str], str]:
    """Regel-Fassung des satirischen Teils (geprüft wie jede Modellantwort); leer, wenn auch das nicht besteht."""
    over = [t for t in _pick(RULE_OVER[lang], ident, 2) if pruefe_satire(t, fakten_text, lang)[0]]
    pointe = next((t for t in _pick(RULE_POINTE[lang], ident, 2) if pruefe_satire(t, fakten_text, lang, signal=False)[0]), "")
    return over, pointe


# --------------------------------------------------------------------------- Quellen

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("„", '"').replace("“", '"').replace("”", '"').replace("’", "'")).strip().casefold()


def _publisher(url: str) -> str:
    from ..firma.news import publisher_of

    return publisher_of(url) if url else ""


def _is_link(value: str) -> bool:
    return bool(re.match(r"https?://", str(value or "").strip(), re.I))


def news_kern(thema: str, links: list[str]) -> tuple[list[dict], dict]:
    """Die beste BESTÄTIGTE Meldung aus firma_daten/news.json zu Thema/Links: ihre Quellen (Betreiber nach Adresse getrennt).
    Rückgabe (Quellen, Meldung) – leer, wenn keine passende bestätigte Meldung mit ≥ 2 Betreibern existiert."""
    from ..firma import common, news

    data = common.read_json("news.json", {}) or {}
    want, wanted = news.tokens(thema), {l.split("#")[0] for l in links}
    best: tuple[int, dict] | None = None
    for m in data.get("meldungen", []):
        if m.get("status") != "bestätigt":
            continue
        urls = {q.get("link", "").split("#")[0] for q in m.get("quellen", [])} | {m.get("link", "").split("#")[0]}
        title_tokens = news.tokens(m.get("titel", ""))
        hit_link = bool(urls & wanted)
        if not (hit_link or (want and news.similar(want, title_tokens))):
            continue
        if len({_publisher(q.get("link", "")) for q in m.get("quellen", [])}) < MIN_PUBLISHERS:
            continue
        score = 1000 if hit_link else len(want & title_tokens)
        if best is None or score > best[0]:
            best = (score, m)
    if best is None:
        return [], {}
    m = best[1]
    out = []
    for q in m["quellen"]:
        text = q.get("titel", "") + (". " + m["kurz"] if m.get("kurz") and q.get("link") == m.get("link")
                                      and _norm(m["kurz"]) != _norm(q.get("titel", "")) else "")
        out.append({"name": q.get("quelle") or _publisher(q.get("link", "")), "titel": q.get("titel", ""), "link": q.get("link", ""),
                    "text": news.clean(text, 600), "art": "news", "sprache": m.get("sprache", "")})
    return out, m


def sammle(thema: str, links: list[str]) -> tuple[list[dict], list[str], dict]:
    """Quellen der Meldung (Kennung Q1 …), Hinweise, Meldungs-Infos {titel, sprache}. Eigene Links ergänzen den Kern."""
    notes: list[str] = []
    raw: list[dict] = []
    info: dict = {}
    try:
        raw, meldung = news_kern(thema, links)
        info = {"titel": meldung.get("titel", ""), "sprache": meldung.get("sprache", "")}
    except Exception as exc:                              # noqa: BLE001 – News-Daten dürfen fehlen
        notes.append(f"News-Reporter-Daten nicht lesbar ({type(exc).__name__})")
    for url in links:
        if any(q["link"].split("#")[0] == url.split("#")[0] for q in raw):
            continue
        try:
            for q in seite_quelle(url):
                raw.append({**q, "sprache": ""})
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"Link {_publisher(url)} nicht lesbar ({type(exc).__name__})")
    out, seen = [], set()
    for q in raw:
        key = (q["name"].casefold(), _norm(q["titel"]))
        if not q.get("text") or key in seen:
            continue
        seen.add(key)
        out.append({**q, "id": f"Q{len(out) + 1}", "betreiber": _publisher(q["link"]) or q["name"].casefold()})
    if not info.get("titel") and out:
        info = {"titel": out[0]["titel"], "sprache": out[0].get("sprache", "")}
    return out, notes, info


# --------------------------------------------------------------------------- Fakt-Teil

def regel_fakt(quellen: list[dict]) -> list[dict]:
    """Ohne Modell: die Überschrift der ersten Quelle ist der Fakt, die Überschriften der anderen Betreiber sind die Belege
    (die News-Daten haben sie bereits als dieselbe Meldung bestätigt). Der Satz steht wörtlich in seiner Quelle."""
    if len({q["betreiber"] for q in quellen}) < MIN_PUBLISHERS:
        return []
    first = quellen[0]
    text = re.sub(r"\s+", " ", first["titel"]).strip().rstrip(".") + "."
    belege = [{"quelle": first["id"], "zitat": first["titel"]}]
    belege += [{"quelle": q["id"], "zitat": q["titel"]} for q in quellen[1:] if q["betreiber"] != first["betreiber"]][:2]
    return [{"text": text, "belege": belege}]


def pruefe_fakten(answer, quellen: list[dict], lang: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Fakt-Sätze (Modell oder Regel): Beleg wörtlich, ≥ 2 Betreiber, Zahlen/Namen aus den Belegen (`reportage.pruefe_satz`)."""
    by_id = {q["id"]: q for q in quellen}
    items = answer.get("fakten") if isinstance(answer, dict) else answer
    accepted, rejected = [], []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ok, why = pruefe_satz(item, by_id, lang)
        if ok and ok["text"] not in {a["text"] for a in accepted}:
            accepted.append(ok)
        elif not ok:
            rejected.append((str(item.get("text") or "")[:120], why))
    return accepted[:MAX_FACTS], rejected


def wahrheit_fakten(saetze: list[dict], lang: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Der Fakt-Teil läuft durch den Wahrheits-Prüfer (`wahrheit.Pruefer`, Regelkatalog REGELN) wie ein Fakten-Video:
    jeder Satz mit seinen Belegen als geprüfte Daten. Sätze mit offenem Befund fliegen raus."""
    from .. import wahrheit
    from ..models import RankItem, Research, Script, Segment
    from ..spec import VideoSpec, WikidataSource

    if not saetze:
        return [], []
    spec = VideoSpec(id="satire-fakten", title={lang: "Satire"}, source=WikidataSource(cls="Q1", property="P1"),
                     count=max(3, len(saetze)), langs=[lang], kind="facts")
    items = [RankItem(qid=f"Q{i}", value=float(i), unit="Q199", rank=i,
                      fact={"beleg": s["belege"][0]["zitat"], "belege": [b["zitat"] for b in s["belege"]],
                            "quelle": s["belege"][0]["name"]}) for i, s in enumerate(saetze, start=1)]
    research = Research(spec_id="satire-fakten", fetched_at=datetime.now(timezone.utc).isoformat(), items=items)
    script = Script(lang=lang, title="Satire", segments=[Segment(kind="item", text=s["text"], rank=i)
                                                        for i, s in enumerate(saetze, start=1)])
    bericht = wahrheit.Pruefer(spec, research).pruefe(script, None, cover=False)
    bad = {b.idx: b for b in bericht.offen if b.idx is not None}
    ok = [s for i, s in enumerate(saetze) if i not in bad]
    return ok, [(saetze[i]["text"][:120], f"Wahrheits-Prüfer ({b.regel}): {b.grund}") for i, b in bad.items()]


# --------------------------------------------------------------------------- Titel, Skript, Texte

def waehle_titel(vorschlag: str, fakten: list[dict], lang: str) -> str:
    """„SATIRE: …“ (≤ 60 Zeichen): der Vorschlag nur, wenn er sachlich ist (kein Clickbait/Zitat/Zahl oder Name ohne Fakt), sonst
    der erste Fakt-Satz. Das Wort Satire steht immer vorn."""
    fact_text = " ".join(f["text"] for f in fakten)
    allowed = textcheck.digits(fact_text)
    prefix = "SATIRE: "
    for cand in (vorschlag, fakten[0]["text"] if fakten else ""):
        cand = re.sub(r"^\s*satire\s*[:\-–]\s*", "", re.sub(r"\s+", " ", cand or "").strip(), flags=re.I).rstrip(".")
        if (cand and not CLICKBAIT.search(cand) and not DRAMA.search(cand) and not ZITATZEICHEN.search(cand)
                and textcheck.digits(cand) <= allowed and not textcheck.invented_people(cand, fact_text)
                and not SATIRE_WORT.search(cand)):
            room = TITLE_MAX - len(prefix)
            if len(cand) > room:
                cand = cand[:room].rsplit(" ", 1)[0].rstrip(",;:.–-")
                cand = re.sub(r"(\s+(to|the|a|an|of|for|and|in|on|zu|der|die|das|und|von|für|im|an|ein|eine))+$", "", cand, flags=re.I)
            if cand:
                return prefix + cand
    return prefix + ("Eine echte Meldung, satirisch" if lang == "de" else "A real story, satirically")


def _datum(lang: str) -> str:
    from ..script import format_date

    return format_date(datetime.now(timezone.utc).date().isoformat(), lang)


def baue_skript(titel: str, fakten: list[dict], over: list[str], pointe: str, lang: str, ident: str) -> dict:
    """Szenen-Skript für den Satire-Renderer (`satire/render.py`): Einstieg, Fakten (ECHT), Überspitzungen, Pointe, Abspann."""
    s = STRINGS[lang]
    names = list(dict.fromkeys(b["name"] for f in fakten for b in f["belege"]))
    scenes = [{"typ": "intro", "text": s["intro"], "ton": "fakt"}]
    scenes += [{"typ": "fakt", "text": f["text"], "ton": "fakt", "quellen": list(dict.fromkeys(b["name"] for b in f["belege"]))}
               for f in fakten]
    scenes += [{"typ": "satire", "text": t, "ton": "satire"} for t in over]
    scenes.append({"typ": "pointe", "text": pointe, "ton": "pointe"})
    scenes.append({"typ": "outro", "text": s["outro"].format(quellen=", ".join(names), datum=_datum(lang)), "ton": "fakt",
                   "quellen": names})
    return {"id": ident, "titel": titel, "sprache": lang, "szenen": scenes}


def texte(titel: str, fakten: list[dict], quellen: list[dict], lang: str) -> tuple[str, str]:
    """(youtube.txt, tiktok.txt): „SATIRE“ in der ersten Zeile und im Hinweistext; Quellen mit Adresse nur in der Beschreibung."""
    s = STRINGS[lang]
    used = {b["quelle"] for f in fakten for b in f["belege"]}
    lines = [q for q in quellen if q["id"] in used]
    stand = _datum(lang)
    yt = [f"⚠️ {titel}", "", s["note"], "", f"{s['real']} ({s['stand']} {stand}):"] + [f"- {f['text']}" for f in fakten]
    yt += ["", f"{s['sources']}:"] + [f"- {q['name']}: {q['titel']} {q['link']}".rstrip() for q in lines] + ["", s["tags"]]
    names = ", ".join(dict.fromkeys(q["name"] for q in lines))
    tt = f"{titel} · {'Echt ist nur der erste Teil' if lang == 'de' else 'Only the first part is real'} ({names}) {s['tt_tags']}"
    return "\n".join(yt) + "\n", tt[:300] + "\n"


def abnahme(skript: dict, fakten: list[dict], over: list[str], pointe: str, titel: str, yt: str, tt: str) -> dict:
    """Endabnahme: nur geprüfter Text wird gesprochen; „SATIRE“ in Titel, Beschreibung, TikTok-Text (Bild und Cover setzt der
    Renderer fest); satirischer Teil besteht die Regeln erneut."""
    gruende = []
    lang = skript["sprache"]
    fact_text = " ".join(f["text"] for f in fakten)
    szenen = skript["szenen"]
    spoken = {t: [sz["text"] for sz in szenen if sz["typ"] == t] for t in ("fakt", "satire", "pointe")}
    if spoken["fakt"] != [f["text"] for f in fakten] or spoken["satire"] != over or spoken["pointe"] != [pointe]:
        gruende.append("Sprechtext weicht von den geprüften Sätzen ab")
    if len(fakten) < MIN_FACTS:
        gruende.append("kein bestätigter Fakt als Kern")
    if not over or not pointe:
        gruende.append("satirischer Teil fehlt")
    for t in over:
        if not pruefe_satire(t, fact_text, lang)[0]:
            gruende.append("satirischer Satz verstößt gegen die Regeln")
    if not pruefe_satire(pointe, fact_text, lang, signal=False)[0]:
        gruende.append("Pointe verstößt gegen die Regeln")
    for name, text in (("Titel", titel), ("Beschreibung", yt), ("TikTok-Text", tt)):
        if not SATIRE_WORT.search(text):
            gruende.append(f"„SATIRE“ fehlt im Feld {name}")
    if len(titel) > TITLE_MAX or CLICKBAIT.search(titel):
        gruende.append("Titel nicht sachlich oder zu lang")
    return {"ok": not gruende, "gruende": list(dict.fromkeys(gruende))}


def pruefbericht(thema: str, quellen: list[dict], fakten: list[dict], over: list[str], pointe: str, rejected: list,
                 notes: list[str], modus: str, ab: dict) -> str:
    z = [f"# Prüfbericht Satire: {thema}", "",
         f"Weg: {modus}. Endabnahme: " + ("bestanden" if ab["ok"] else "NICHT bestanden – " + "; ".join(ab["gruende"])),
         "Regeln: " + SATIRE_REGELN, "", "## Quellen des echten Kerns", ""]
    z += [f"- {q['id']} {q['name']}: {q['titel']} {q['link']}" for q in quellen]
    z += ["", f"## Fakt-Teil ({len(fakten)} bestätigt: wörtlicher Beleg, ≥ {MIN_PUBLISHERS} Betreiber, Wahrheits-Prüfer)", ""]
    for f in fakten:
        z.append(f"- {f['text']}")
        z += [f"    - {b['name']}: „{b['zitat']}“" for b in f["belege"]]
    z += ["", "## Satirischer Teil (erkennbar erfunden, keine Zitate/Zahlen/Namen/Gruppen)", ""]
    z += [f"- {t}" for t in over] + [f"- Pointe: {pointe}"]
    if rejected:
        z += ["", "## Verworfen", ""] + [f"- {t} – {why}" for t, why in rejected]
    if notes:
        z += ["", "## Hinweise", ""] + [f"- {n}" for n in notes]
    return "\n".join(z) + "\n"


# --------------------------------------------------------------------------- Auftrag

def run(order: dict, folder: Path, progress=lambda stage, f: None) -> dict:
    """Satire-Auftrag -> Ergebnis im Format von job._summary (kind „satire“)."""
    from .render import render_satire

    lang = order["sprache"]
    meldung = order.get("meldung") or ""
    links = list(order.get("links") or [])
    thema = order.get("thema") or ""
    if _is_link(meldung):
        links.append(meldung)
    elif meldung and not thema:
        thema = meldung
    out = folder / "satire"
    out.mkdir(parents=True, exist_ok=True)
    if heikel(thema, meldung):
        raise SatireError("Satire nicht möglich: Das Thema berührt Leid, Gewalt oder Unglück. Dazu gibt es nur eine sachliche "
                          "Reportage (Auftrag „Reportage“).")
    cache = folder / "satire_quellen.json"                 # ein Weiterlauf prüft gegen dieselben Texte
    notes: list[str] = []
    if cache.exists():
        saved = json.loads(cache.read_text("utf-8"))
        quellen, info = saved["quellen"], saved["info"]
    else:
        progress("Quellen sammeln", 0.05)
        quellen, notes, info = sammle(thema, links)
        cache.write_text(json.dumps({"quellen": quellen, "info": info}, ensure_ascii=False), "utf-8")
    thema = thema or info.get("titel", "")
    if heikel(thema, *(f"{q['titel']} {q['text']}" for q in quellen)):
        raise SatireError("Satire nicht möglich: Die Meldung berührt Leid, Gewalt oder Unglück. Dazu gibt es nur eine sachliche "
                          "Reportage (Auftrag „Reportage“).")
    if len({q["betreiber"] for q in quellen}) < MIN_PUBLISHERS:
        raise SatireError("Satire nicht möglich: Zu dieser Meldung gibt es keine Bestätigung durch zwei unabhängige Quellen. "
                          "Satire steht nur auf einem echten, bestätigten Kern – bitte eine bestätigte Meldung nennen"
                          + (f" ({'; '.join(notes)})" if notes else "") + ".")
    progress("Fakten prüfen", 0.2)
    answer = handoff.request(TASK, INSTRUCTIONS.format(regeln=SATIRE_REGELN), {
        "thema": thema, "sprache": lang, "stand": datetime.now(timezone.utc).date().isoformat(),
        "quellen": [{"id": q["id"], "name": q["name"], "titel": q["titel"], "text": q["text"][:TEXT_LIMIT]} for q in quellen]})
    if not answer and info.get("sprache") in ("de", "en") and info["sprache"] != lang:
        notes.append(f"Ohne Schreibaufgabe bleiben die Quellen in {info['sprache'].upper()} – das Video entsteht in dieser Sprache.")
        lang = info["sprache"]
    rejected: list[tuple[str, str]] = []
    fakten, rej = pruefe_fakten(answer, quellen, lang) if answer else ([], [])
    rejected += rej
    fakten, rej = wahrheit_fakten(fakten, lang)
    rejected += rej
    modus = "Schreibaufgabe + Prüfung" if answer else "Regelweg (Überschrift der Meldung + Regel-Satire)"
    if len(fakten) < MIN_FACTS:
        if answer:
            notes.append("Aus der Schreibaufgabe blieb kein geprüfter Fakt – Regelweg ergänzt.")
        extra, rej = pruefe_fakten({"fakten": regel_fakt(quellen)}, quellen, lang)
        rejected += rej
        fakten, rej = wahrheit_fakten(extra, lang)
        rejected += rej
    if len(fakten) < MIN_FACTS:
        raise SatireError("Satire nicht möglich: Aus den Quellen ergibt sich kein Fakt, den zwei unabhängige Quellen wörtlich "
                          "bestätigen. Es wird nichts ergänzt.")
    fact_text = " ".join(f["text"] for f in fakten)
    over, pointe, rej = pruefe_satire_antwort(answer, fact_text, lang) if answer else ([], "", [])
    rejected += rej
    if len(over) < 2 or not pointe:
        if answer:
            notes.append("Der satirische Teil der Schreibaufgabe war unvollständig oder verstieß gegen die Regeln – Regel-Fassung ergänzt.")
        r_over, r_pointe = regel_satire(lang, order["id"], fact_text)
        over = (over + [t for t in r_over if t not in over])[:3]
        pointe = pointe or r_pointe
        modus = modus + " + Regel-Fassung" if answer else modus
    if not over or not pointe:
        raise SatireError("Satire nicht möglich: Der satirische Teil besteht die Regeln nicht (erkennbar übertrieben, keine Zitate, "
                          "Zahlen oder Namen). Es wird nichts erfunden.")
    titel = waehle_titel(str(answer.get("titel") or "") if isinstance(answer, dict) else "", fakten, lang)
    skript = baue_skript(titel, fakten, over, pointe, lang, "satire")
    yt, tt = texte(titel, fakten, quellen, lang)
    ab = abnahme(skript, fakten, over, pointe, titel, yt, tt)
    (out / "youtube.txt").write_text(yt, "utf-8")
    (out / "tiktok.txt").write_text(tt, "utf-8")
    (out / "spec.json").write_text(json.dumps({"title": {"de": titel, "en": titel}}, ensure_ascii=False), "utf-8")
    (out / "review.md").write_text(pruefbericht(thema, quellen, fakten, over, pointe, rejected, notes, modus, ab), "utf-8")
    if not ab["ok"]:
        raise SatireError("Endabnahme nicht bestanden: " + "; ".join(ab["gruende"]))
    progress("Video rendern", 0.3)
    result = render_satire(skript, out, progress=lambda f: progress("Video rendern", 0.3 + 0.65 * f))
    files = {"video": result["video"], "cover": result["cover"], "duration": result["duration"], "qa": result.get("qa"),
             "description_file": "youtube.txt", "caption_file": "tiktok.txt", "abnahme": ab}
    return {"output_dir": str(out), "videos": {lang: files}, "kind": "satire", "warnings": notes}
