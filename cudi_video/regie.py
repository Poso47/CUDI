"""Regie & Psychologie: ein Werbeagentur-Blick auf jedes Skript – Zuschauer halten, natürlich klingen, nie lügen.

Ablauf (nach dem Erzählen, vor Wahrheits-Prüfung und Vertonung):
1. **Bewerten** (`bewerte`): Checkliste (Basis-Grundlagen aus `firma/wissen.BASIS` plus gelernte Regeln mit Quelle aus
   `firma_daten/wissen.json`), Score 0–1 je Kriterium mit Begründung – rein nach Regeln, ohne Sprachmodell.
2. **Verbessern** (`verbessere`): EINE Schreibaufgabe `regie` (handoff -> Claude bzw. Notbetrieb-Modell) für alle Sprachen:
   drei Hook-Kandidaten, natürlichere gesprochene Sprache je Abschnitt, Zwischen-Aufhänger, Übergänge, Schluss/Kommentarfrage.
3. **Prüfen**: Jede Änderung muss `pruefe_aenderung` bestehen (Zahlen werttreu, keine neuen Namen/Wörter, keine Wertung, kein
   Clickbait, Länge), der Hook zusätzlich ohne Spoiler; danach prüft die Wahrheits-Prüfung (`wahrheit.Pruefer`) – jede Änderung,
   die dort einen NEUEN Befund auslöst, wird verworfen und der alte Text bleibt (Hinweis im Bericht).
Die Wahrheit hat immer Vorrang: ohne Sprachmodell wird nur bewertet, nie umgeschrieben. Ergebnis-Block `regie` (Score
vorher/nachher, Änderungen, Verworfenes) landet in `regie.json`, `ergebnis.json` und im Prüfbericht („Regie & Psychologie“)."""

from __future__ import annotations

import copy
import logging
import re
import statistics

from . import handoff, textcheck
from .metadata import CLICKBAIT
from .narrate import FREE_WORDS, RANK_CLAIM, WORD
from .script import NOT_NEUTRAL
from .wahrheit import _parse, saetze

log = logging.getLogger(__name__)

MIN_GEWINN = 0.05            # ein Hook-Kandidat muss den alten um so viel schlagen
FORMAL = {
    "de": re.compile(r"\b(außerdem|darüber hinaus|des weiteren|folglich|diesbezüglich|hierbei|demzufolge|bezüglich|zudem|"
                     r"hinsichtlich|infolgedessen|nichtsdestotrotz|ebenfalls|jedoch)\b", re.I),
    "en": re.compile(r"\b(furthermore|moreover|additionally|consequently|therefore|thus|in addition|regarding|"
                     r"nevertheless|henceforth)\b", re.I),
}
FILLER = {
    "de": re.compile(r"\b(mal|halt|echt|ja|eben|schon|einfach|wirklich|tatsächlich)\b", re.I),
    "en": re.compile(r"\b(really|actually|just|literally|basically|honestly)\b", re.I),
}
CONTRACTION = re.compile(r"\b\w+(?:n't|'s|'re|'ll|'ve|'d|'m)\b", re.I)
DU = {"de": re.compile(r"\b(du|dir|dich|dein\w*|stell dir|ihr|euch)\b", re.I),
      "en": re.compile(r"\b(you|your|you're|you'll|imagine)\b", re.I)}
NEUGIER = {
    "de": re.compile(r"\?|\b(wetten|rate|rätsel|stell dir vor|kennst du|ahnst|geheimnis|überrasch\w*|wusstest du|niemals|nie)\b", re.I),
    "en": re.compile(r"\?|\b(bet|guess|imagine|secret|surpris\w*|ever wondered|did you know|never|riddle)\b", re.I),
}
SCHLEIFE = {
    "de": re.compile(r"auflösung|am ende|bis zum schluss|bleib dran|rate |wetten|gleich|danach|zum schluss", re.I),
    "en": re.compile(r"reveal|at the end|until the end|stay |guess|bet |in a moment|answer", re.I),
}
MUSTER = {
    "de": re.compile(r"\?|!|\b(aber|doch|und jetzt|gleich|merk dir|stell dir vor|moment|achtung|pass auf)\b", re.I),
    "en": re.compile(r"\?|!|\b(but|and now|wait|remember|imagine|hold on|here's)\b", re.I),
}
FORTSCHRITT = re.compile(r"\b(platz|rang|nummer|place|number|rank|#)\s*\d|\b(platz|nummer|number|place)\s+(eins|zwei|drei|one|two|three)",
                         re.I)
PAYOFF = {
    "de": re.compile(r"heute gelernt|auflösung|platz eins|nummer eins|am ende|zum schluss|damit weißt du|merk dir", re.I),
    "en": re.compile(r"learned today|reveal|number one|at the end|now you know|remember", re.I),
}
CTA = re.compile(r"kommentar|folge|follow|comment|\?", re.I)
VERBINDUNG = {
    "de": re.compile(r"\b(und|aber|doch|denn|weil|sondern|deshalb|dabei|damit|obwohl|während|trotzdem|dann|danach|also|sogar|"
                     r"dafür|davon|dort|hier)\b", re.I),
    "en": re.compile(r"\b(and|but|because|so|yet|while|then|even|though|which|that's|where)\b", re.I),
}
EINORDNUNG = {
    "de": re.compile(r"\b(wie|mehr als|weniger als|doppelt|halb|mal so|so \w+ wie|stell dir|vergleich|fast|etwa|rund|ungefähr|"
                     r"genug|passt|hinaus|übertrifft|trennen|nur noch)\b", re.I),
    "en": re.compile(r"\b(like|as \w+ as|more than|less than|twice|half|times|imagine|compared|almost|about|roughly|"
                     r"enough|fits|beats|separate|only)\b", re.I),
}
TELEGRAMM = {"de": re.compile(r"^(das (sind|ist)|es (sind|ist)|höhe:|länge:|fläche:)\b", re.I),
             "en": re.compile(r"^(that('s| is| are)|it is|there are)\b", re.I)}
SYMBOLS = re.compile(r"[%°²³&§]|\bkm/h\b|\bm/s\b|\bz\.\s?b\.|\bca\.")


# --------------------------------------------------------------------------- Bewerten

def _sentences(texts: list[str]) -> list[str]:
    return [s for t in texts for s in saetze(t)]


def _first_sentence(text: str) -> str:
    parts = saetze(text)
    return parts[0] if parts else text.strip()


def spoiler(text: str, top_names: list[str]) -> bool:
    """Verrät der Text den Namen von Platz 1? (ganzer Name oder ein längeres Namenswort)"""
    low = text.lower()
    for name in top_names:
        name = name.lower().strip()
        if not name:
            continue
        if name in low:
            return True
        if any(len(w) >= 5 and re.search(rf"\b{re.escape(w)}", low) for w in re.findall(r"[^\W\d_]+", name)):
            return True
    return False


def hook_score(text: str, lang: str, top_names: list[str] | None = None) -> float:
    """Wie gut hält ein Einstieg Zuschauer? Regelwerk; -1 = unzulässig (Spoiler oder Clickbait)."""
    text = (text or "").strip()
    if not text or spoiler(text, top_names or []) or CLICKBAIT.search(text):
        return -1.0
    first = len(_first_sentence(text).split())
    score = 0.0
    if NEUGIER[lang].search(text) or re.search(r"\d", _first_sentence(text)):
        score += 0.35
    score += 0.25 if first <= 12 else 0.15 if first <= 16 else 0.05 if first <= 22 else 0.0
    if SCHLEIFE[lang].search(text):
        score += 0.2
    if DU[lang].search(text):
        score += 0.1
    if len(text.split()) <= 40:
        score += 0.1
    return round(min(score, 1.0), 3)


def _kriterium(kid: str, score: float, grund: str) -> dict:
    return {"id": kid, "score": round(max(0.0, min(1.0, score)), 2), "begruendung": grund}


def bewerte(segmente: list[tuple[str, str]], lang: str, art: str = "ranking", top_names: list[str] | None = None) -> dict:
    """Skript nach der Basis-Checkliste bewerten. `segmente` = [(kind intro|item|outro, Text)], `art` ranking|fakten|story|erklaer.
    Rückgabe {"gesamt": 0–1, "kriterien": [{id, name, score, begruendung, basis}]}. Nicht passende Kriterien entfallen."""
    from .firma.wissen import BASIS

    lang = lang if lang in DU else "en"
    intro = next((t for k, t in segmente if k == "intro"), segmente[0][1] if segmente else "")
    outro = next((t for k, t in reversed(segmente) if k == "outro"), segmente[-1][1] if segmente else "")
    body = [t for k, t in segmente if k == "item"] or [t for k, t in segmente]
    texts = [t for _, t in segmente]
    sents = _sentences(texts)
    words_total = max(1, sum(len(t.split()) for t in texts))
    out: list[dict] = []

    first = len(_first_sentence(intro).split())
    h = 1.0 if first <= 12 else 0.7 if first <= 16 else 0.4 if first <= 22 else 0.15
    curious = bool(NEUGIER[lang].search(intro) or re.search(r"\d", _first_sentence(intro)))
    out.append(_kriterium("hook", h * (1.0 if curious else 0.6),
                          f"Erster Satz {first} Wörter" + ("" if curious else ", ohne Frage/Zahl/Neugier-Signal")))

    leak = spoiler(intro, top_names or [])
    loop = bool(SCHLEIFE[lang].search(intro))
    n = (0.5 if curious else 0.0) + (0.5 if loop else 0.0) - (0.6 if leak else 0.0)
    out.append(_kriterium("neugier", n, ("Hook verrät Platz 1 (Spoiler). " if leak else "")
                          + ("Lücke geöffnet" if curious else "keine Neugier-Lücke")
                          + (", Auflösung versprochen" if loop else ", keine Auflösung versprochen")))

    hits = sum(bool(MUSTER[lang].search(t)) for t in body)
    out.append(_kriterium("musterbruch", hits / max(1, len(body)),
                          f"{hits} von {len(body)} Abschnitten mit Frage, Ansprache oder Mikro-Spannung (Aber/Doch/Gleich)"))

    if art in ("ranking", "fakten"):
        rk = sum(bool(FORTSCHRITT.search(t)) for k, t in segmente if k == "item")
        items = sum(k == "item" for k, _ in segmente)
        out.append(_kriterium("fortschritt", rk / max(1, items), f"{rk} von {items} Plätzen mit sichtbarer Platznummer"))

    pay = bool(PAYOFF[lang].search(outro))
    cta = bool(CTA.search(outro))
    out.append(_kriterium("payoff", 1.0 if pay else 0.5 if cta else 0.2,
                          "Auflösung/Lerneffekt am Ende" if pay else "nur Aufforderung, keine Auflösung am Ende" if cta
                          else "Ende ohne Auflösung"))

    du = sum(bool(DU[lang].search(t)) for t in texts)
    need = 0.25 if art == "story" else 0.6
    out.append(_kriterium("ansprache", min(1.0, du / max(1, len(texts)) / need),
                          f"{du} von {len(texts)} Abschnitten sprechen die Zuschauer direkt an"))

    body_sents = _sentences(body)
    lengths = [len(x.split()) for x in sents]
    if len(lengths) >= 4:
        cv = statistics.pstdev(lengths) / max(1.0, statistics.mean(lengths))
        longs = sum(x > 25 for x in lengths) / len(lengths)
        tele = sum(len(x.split()) <= 6 and not x.rstrip().endswith(("?", "!")) for x in body_sents) / max(1, len(body_sents))
        starts = [x.split()[0].lower() for x in body_sents if x.split()]
        same = max((starts.count(w) for w in set(starts)), default=0) / max(1, len(starts))
        r = min(1.0, cv / 0.45) - 1.5 * longs - 1.2 * max(0.0, tele - 0.2) - 1.0 * max(0.0, same - 0.3)
        out.append(_kriterium("rhythmus", r, f"Satzlängen {min(lengths)}–{max(lengths)} Wörter (Streuung {cv:.2f}), "
                              f"{tele:.0%} Telegramm-Sätze (≤ 6 Wörter), gleiche Satzanfänge {same:.0%}"
                              + (f", {sum(x > 25 for x in lengths)} sehr lange Sätze" if longs else "")))
    else:
        out.append(_kriterium("rhythmus", 0.7, "zu wenige Sätze für eine Rhythmus-Messung"))

    linked = sum(bool(VERBINDUNG[lang].search(t)) for t in body)
    out.append(_kriterium("verbindung", linked / max(1, len(body)),
                          f"{linked} von {len(body)} Abschnitten verbinden ihre Sätze (und/aber/dann …) statt aufzuzählen"))
    with_num = [t for t in body if re.search(r"\d", t)]
    placed = sum(bool(EINORDNUNG[lang].search(t)) for t in with_num)
    out.append(_kriterium("einordnung", placed / len(with_num) if with_num else 1.0,
                          f"{placed} von {len(with_num)} Abschnitten mit Zahl ordnen sie ein (Vergleich/Bild im Kopf)"
                          if with_num else "keine Zahlen im Text"))

    heavy = sum(len(textcheck.numbers(t, lang)) > 3 or len(saetze(t)) > 6 for t in body)
    out.append(_kriterium("kernaussage", 1 - heavy / max(1, len(body)),
                          f"{heavy} von {len(body)} Abschnitten überladen (mehr als 3 Zahlen oder 6 Sätze)"))

    callback = {w for w in re.findall(r"[^\W\d_]{5,}", outro.lower())} & {w for w in re.findall(r"[^\W\d_]{5,}", intro.lower())}
    out.append(_kriterium("loop", (0.5 if cta else 0.0) + (0.5 if callback else 0.0),
                          ("Aufforderung/Frage am Ende" if cta else "keine Aufforderung am Ende")
                          + (", Bogen zurück zum Anfang" if callback else ", kein Bogen zum Anfang")))

    formal = len(FORMAL[lang].findall(" ".join(texts)))
    filler = len(FILLER[lang].findall(" ".join(texts)))
    contr = len(CONTRACTION.findall(" ".join(texts))) if lang == "en" else 0
    f_pen = min(0.5, formal / words_total * 100 * 0.25)
    fill_pen = min(0.3, max(0.0, filler / words_total * 100 - 4) * 0.1)
    avg = statistics.mean(lengths) if lengths else 0
    muster = sum(bool(TELEGRAMM[lang].match(x)) for x in sents)
    nat = 1.0 - min(0.4, 0.15 * muster) - f_pen - fill_pen - (0.25 if avg > 18 else 0.0) - (0.2 if lang == "en" and not contr and words_total > 60 else 0.0)
    out.append(_kriterium("natuerlich", nat, f"{formal} Amtsdeutsch-/Formal-Signalwörter, {filler} Füllwörter, "
                          f"Ø {avg:.0f} Wörter je Satz, {muster}× „Das sind/Das ist“-Muster" + (f", {contr} Kontraktionen" if lang == "en" else "")))
    odd = sum(len(SYMBOLS.findall(t)) for t in texts) + sum(
        1 for t in texts for m in re.findall(r"\d[\d.,]*", t) if len(re.sub(r"\D", "", m)) >= 10)
    out.append(_kriterium("sprechbar", 1 - 0.25 * odd, "Zahlen und Einheiten gut sprechbar" if not odd
                          else f"{odd} Stelle(n) mit Symbolen/Kürzeln/sehr langen Zahlen"))

    for item in out:
        name, rule, _ = BASIS.get(item["id"], (item["id"], "", ""))
        item.update({"name": name, "basis": True})
    gesamt = round(sum(i["score"] for i in out) / len(out), 2)
    return {"gesamt": gesamt, "kriterien": out}


# --------------------------------------------------------------------------- Änderungen prüfen

def _values(text: str, lang: str) -> list[float]:
    out = []
    for raw in re.findall(r"\d+(?:[.,]\d+)*", text):
        v = _parse(raw.rstrip(".,"), lang if lang in ("de", "en") else "en")
        if v is not None:
            out.append(v)
    return out


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 0.05 * max(abs(a), abs(b), 1e-9) or a == b


def _neue_woerter(new: str, context: str, lang: str) -> list[str]:
    tokens = textcheck.tokens(context)
    free = FREE_WORDS.get(lang, set())
    bad = []
    for sentence in re.split(r"(?<=[.!?:–—…])\s+", new):
        for i, word in enumerate(WORD.findall(sentence)):
            if i == 0 or not word[0].isupper() or word == "I":
                continue
            parts = [p for p in re.split(r"[-'’]", word.lower()) if p]
            if all(p in free or textcheck.known(p, tokens) or textcheck.everyday_word(p, lang) for p in parts):
                continue
            bad.append(word)
    return bad


def pruefe_aenderung(alt: str, neu, kontext: str, lang: str, *, zahlen_behalten: bool = True, max_mehr: float = 0.3,
                     max_wort: int = 90, beginnt_mit: str = "") -> str | None:
    """Grund, warum eine Regie-Änderung abgelehnt wird (None = in Ordnung). Streng, weil die Wahrheit Vorrang hat."""
    if not isinstance(neu, str) or not neu.strip():
        return "leer"
    neu = neu.strip()
    words, old_words = len(neu.split()), max(1, len(alt.split()))
    if words > min(max_wort, old_words * (1 + max_mehr) + 4):
        return f"zu lang ({words} Wörter)"
    if words < old_words * 0.5:
        return "zu stark gekürzt"
    if beginnt_mit and not re.sub(r"[\W_]+", "", neu.lower()).startswith(re.sub(r"[\W_]+", "", beginnt_mit.lower())):
        return "Platzsatz geändert"
    new_vals, old_vals, ctx_vals = _values(neu, lang), _values(alt, lang), _values(kontext, lang)
    if any(not any(_close(v, c) for c in ctx_vals + old_vals) for v in new_vals):
        return "neue Zahl"
    if zahlen_behalten and any(not any(_close(o, v) for v in new_vals) for o in old_vals):
        return "Zahl entfallen"
    if textcheck.invented_people(neu, f"{kontext} {alt}"):
        return "erfundener Name"
    for rx, why in ((NOT_NEUTRAL, "Wertung"), (RANK_CLAIM, "Rang-Aussage"), (CLICKBAIT, "Clickbait")):
        if rx.search(neu) and not rx.search(alt):
            return why
    unknown = _neue_woerter(neu, f"{kontext} {alt}", lang)
    if unknown:
        return "nicht belegt: " + ", ".join(unknown[:3])
    return None


# --------------------------------------------------------------------------- Anleitung

INSTRUCTIONS = (
    "Du bist das Regie-Team einer Werbeagentur für Kurzvideos (TikTok/YouTube Shorts) und verbesserst gesprochene Skripte "
    "so, dass Zuschauer dranbleiben UND es klingt, als würde ein Mensch frei erzählen – nicht als läse jemand ab. "
    "ABSOLUTER VORRANG: nichts Falsches, keine irreführende Zuspitzung. Du darfst nur umformulieren, nie Fakten, Zahlen, "
    "Namen oder Behauptungen hinzufügen oder verändern. Jede Zahl bleibt (Rundung wie „rund 8.800 Meter“ nur, wenn sie höchstens "
    "5 % vom Wert abweicht und „rund“ davorsteht), keine Rang-/Superlativ-Aussagen außer den vorhandenen, keine Wertungen, "
    "kein Clickbait („du wirst nicht glauben …“). Der Code verwirft jede Änderung, die die Prüfung nicht besteht. "
    "Aufgaben je Sprache in „daten“: (1) „hook_kandidaten“: GENAU 3 neue Einstiege (je höchstens ~25 Wörter, erster Satz höchstens "
    "12 Wörter), die Neugier wecken, eine Lücke öffnen und die Auflösung versprechen – ohne Platz 1 zu verraten (Namen aus "
    "„nicht_verraten“ nie nennen) und ohne Lüge. (2) „abschnitte“: für Abschnitte, die schlecht abschneiden (siehe "
    "„bewertung“), eine natürlichere Fassung: Alltagsdeutsch statt Amtsdeutsch, kurze Sätze im Wechsel mit längeren, "
    "Füllwörter sparsam, direkte Ansprache („du“), im Englischen Kontraktionen („it's“, „don't“), Zahlen sprechbar, ein "
    "Zwischen-Aufhänger oder eine Frage, wo der Abschnitt gleichförmig ist, ein Übergang, der neugierig auf das Nächste macht. "
    "Behalte bei Plätzen den ersten Satz („start“) unverändert und alle Zahlen. Länge höchstens „max_woerter“. (3) „ende“: ein "
    "natürlicher Schluss mit Lerneffekt/Auflösung und einer Kommentarfrage (nur wenn „ende“ unter „abschnitte“ ausdrücklich "
    "vorgesehen ist; sonst weglassen). Lass Abschnitte, die schon gut sind, einfach aus. "
    "Antwort: JSON {Sprache: {\"hook_kandidaten\": [\"…\", \"…\", \"…\"], \"abschnitte\": {\"Nr\": \"neuer Text\"}, "
    "\"begruendung\": {\"hook\": \"…\", \"Nr\": \"…\"}}} – Nr = „nr“ des Abschnitts (Text).")


def lernstoff(limit: int = 8) -> list[dict]:
    """Gelernte Regeln aus firma_daten/wissen.json (nur mit Quelle und Datum) – als Hinweise für die Anleitung."""
    try:
        from .firma import common

        rules = (common.read_json("wissen.json", {}) or {}).get("regeln") or []
    except Exception:                                          # noqa: BLE001 – ohne Wissensdatei gilt die Basis
        return []
    return [{"regel": r["regel"], "quelle": r.get("quelle", ""), "datum": r.get("datum", "")}
            for r in rules if r.get("regel") and r.get("quelle") and r.get("datum")][:limit]


def basis_regeln() -> list[dict]:
    from .firma.wissen import BASIS

    return [{"name": v[0], "regel": v[1], "herkunft": "Basis"} for v in BASIS.values()]


# --------------------------------------------------------------------------- Auswahl und Anwenden

def waehle_hook(kandidaten, alt: str, lang: str, top_names: list[str], kontext: str) -> tuple[str | None, str]:
    """Bester zulässiger Hook-Kandidat (Neugier ohne Spoiler, geprüft) oder None, wenn er den alten nicht schlägt."""
    base = hook_score(alt, lang, top_names)
    best, best_score, why, top_valid = None, base + MIN_GEWINN, "", None
    for cand in (kandidaten if isinstance(kandidaten, list) else [])[:3]:
        if not isinstance(cand, str):
            continue
        cand = cand.strip()
        if spoiler(cand, top_names):
            why = "Kandidat verriet Platz 1 – verworfen"
            continue
        problem = pruefe_aenderung(alt, cand, kontext, lang, zahlen_behalten=False, max_mehr=6.0, max_wort=35)
        if problem:
            why = f"Kandidat verworfen ({problem})"
            continue
        score = hook_score(cand, lang, top_names)
        top_valid = max(top_valid or 0.0, score)
        if score > best_score or (best is not None and score == best_score and len(cand) < len(best)):
            best, best_score = cand, score
    if best:
        return best, f"Hook-Score {base:.2f} -> {best_score:.2f}"
    if top_valid is not None:
        return None, f"bisheriger Hook bleibt (Score {base:.2f}, bester zulässiger Kandidat {top_valid:.2f})"
    return None, why or "keine Hook-Kandidaten erhalten"


def _art(spec) -> str:
    return "fakten" if getattr(spec, "kind", "") == "facts" else "ranking"


def _daten(spec, script, art: str, bewertung: dict, top_names: list[str]) -> dict:
    parts = []
    for i, seg in enumerate(script.segments):
        entry = {"nr": str(i), "art": seg.kind, "text": seg.text, "max_woerter": int(len(seg.text.split()) * 1.2) + 4}
        if seg.kind == "item":
            entry["start"] = _first_sentence(seg.text)
        if seg.kind == "intro":
            entry["hinweis"] = "nur über hook_kandidaten ändern"
            entry.pop("max_woerter")
        if seg.kind == "outro":
            entry["hinweis"] = "darf als „ende“ natürlich neu formuliert werden (Lerneffekt behalten)"
        parts.append(entry)
    schwach = [k for k in bewertung["kriterien"] if k["score"] < 0.75]
    return {"titel": script.title, "sprache": script.lang, "videoart": art, "nicht_verraten": top_names,
            "bewertung": [{"kriterium": k["name"], "score": k["score"], "grund": k["begruendung"]} for k in schwach],
            "checkliste": basis_regeln(), "gelernt": lernstoff(), "abschnitte": parts}


def _segmente(script) -> list[tuple[str, str]]:
    return [(s.kind, s.text) for s in script.segments]


def verbessere(spec, research, scripts: list, pruefer, use_llm: bool | None = None) -> dict:
    """Regie-Stufe für Ranking-/Fakten-Skripte (mutiert `scripts` bei akzeptierten Änderungen). Gibt den Block `regie` zurück.
    Wirft handoff.WritingNeeded, solange Claudes Antwort aussteht."""
    art = _art(spec)
    tops = {s.lang: [it.labels.get(s.lang) or it.labels.get("en", "") for it in research.items if it.rank == 1] for s in scripts}
    vorher = {s.lang: bewerte(_segmente(s), s.lang, art, tops[s.lang]) for s in scripts}
    block = {"quelle": "nur Bewertung", "art": art, "vorher": vorher, "nachher": vorher, "aenderungen": [], "verworfen": [],
             "wissen": {"basis": len(basis_regeln()), "gelernt": len(lernstoff())}}
    if use_llm is False or not handoff.active() or not scripts:
        block["hinweis"] = "Kein Schreib-Modell aktiv: Skript nur bewertet, nichts umgeschrieben."
        return block
    data = {s.lang: _daten(spec, s, art, vorher[s.lang], tops[s.lang]) for s in scripts}
    answer = handoff.request("regie", INSTRUCTIONS, data)
    if not isinstance(answer, dict):
        block["hinweis"] = "Keine brauchbare Regie-Antwort: Skript unverändert."
        return block
    block["quelle"] = "Claude" if handoff.enabled() else "Notbetrieb-Modell"
    context = {s.lang: " ".join([s.title, *(g.text for g in s.segments)]) for s in scripts}
    for script in scripts:
        lang, ans = script.lang, answer.get(script.lang)
        if not isinstance(ans, dict):
            continue
        changes: dict[int, tuple[str, str, str]] = {}                 # idx -> (neuer Text, Ort, Grund)
        reasons = ans.get("begruendung") if isinstance(ans.get("begruendung"), dict) else {}
        hook, why = waehle_hook(ans.get("hook_kandidaten"), script.segments[0].text, lang, tops[lang], context[lang])
        if hook:
            changes[0] = (hook, "Hook", str(reasons.get("hook") or why)[:200])
        else:
            block["verworfen"].append({"sprache": lang, "ort": "Hook", "grund": why})
        for key, new in (ans.get("abschnitte") if isinstance(ans.get("abschnitte"), dict) else {}).items():
            if not str(key).isdigit() or not 0 < int(key) < len(script.segments):
                continue
            idx, seg = int(key), script.segments[int(key)]
            ort = f"Platz {seg.rank}" if seg.kind == "item" else "Abschluss"
            problem = pruefe_aenderung(seg.text, new, context[lang], lang,
                                       beginnt_mit=_first_sentence(seg.text) if seg.kind == "item" else "",
                                       zahlen_behalten=seg.kind == "item", max_mehr=0.2)
            if problem:
                block["verworfen"].append({"sprache": lang, "ort": ort, "grund": problem})
            else:
                changes[idx] = (str(new).strip(), ort, str(reasons.get(str(key)) or "natürlicher / spannender formuliert")[:200])
        _anwenden(script, changes, pruefer, block, art, tops[lang])
    block["nachher"] = {s.lang: bewerte(_segmente(s), s.lang, art, tops[s.lang]) for s in scripts}
    pruefer.regie = block
    return block


def _anwenden(script, changes: dict, pruefer, block: dict, art: str = "ranking", tops: list[str] | None = None) -> None:
    """Änderungen auf eine Kopie legen, mit der Wahrheits-Prüfung prüfen; Segmente mit neuem Befund bleiben alt."""
    if not changes:
        return
    base = {(b.regel, b.satz) for b in pruefer.pruefe(script, None, cover=False).offen}
    trial = copy.deepcopy(script)
    for idx, (text, _, _) in changes.items():
        trial.segments[idx].text, trial.segments[idx].words, trial.segments[idx].audio_path = text, [], None
    bad = {b.idx for b in pruefer.pruefe(trial, None, cover=False).offen if b.idx in changes and (b.regel, b.satz) not in base}
    texts = [(g.kind, g.text) for g in script.segments]
    score = bewerte(texts, script.lang, art, tops)["gesamt"]
    for idx, (text, ort, grund) in changes.items():
        if idx in bad:
            block["verworfen"].append({"sprache": script.lang, "ort": ort, "grund": "Wahrheits-Prüfung: Änderung hätte einen "
                                       "Befund ausgelöst – alter Text bleibt"})
            continue
        trial_texts = [(k, text if i == idx else t) for i, (k, t) in enumerate(texts)]
        new_score = bewerte(trial_texts, script.lang, art, tops)["gesamt"]
        if new_score < score:                                       # Regie darf das Skript nicht schlechter machen
            block["verworfen"].append({"sprache": script.lang, "ort": ort, "grund": f"Regie-Score würde sinken "
                                       f"({score:.2f} -> {new_score:.2f}) – alter Text bleibt"})
            continue
        texts, score = trial_texts, new_score
        seg = script.segments[idx]
        block["aenderungen"].append({"sprache": script.lang, "ort": ort, "idx": idx, "vorher": seg.text, "nachher": text,
                                     "grund": grund})
        seg.text, seg.words, seg.audio_path = text, [], None
    pruefer.pruefe(script, None, cover=False)


def wieder_anwenden(script, pruefer) -> None:
    """Gekürzte Neufassungen (voice_within_limit) bekommen Hook/Schluss der Regie zurück, wenn der alte Text gleich geblieben ist."""
    block = getattr(pruefer, "regie", None) or {}
    for ch in block.get("aenderungen", []):
        if ch["sprache"] == script.lang and ch["idx"] in (0, len(script.segments) - 1) and ch["idx"] < len(script.segments) \
                and script.segments[ch["idx"]].text == ch["vorher"]:
            script.segments[ch["idx"]].text = ch["nachher"]


# --------------------------------------------------------------------------- Story

def verbessere_story(title: str, hook: str, scenes: list[str], lang: str, mood: str, context: str) -> tuple[str, list[str], dict]:
    """Regie für Story-Skelette (ergänzt das Lektorat): Hook-Kandidaten + natürlichere Szenen. Rückgabe (hook, scenes, block).
    Geprüft wie das Lektorat (keine neuen Zahlen/Namen/Wörter, Länge); ohne Modell nur Bewertung. Wirft WritingNeeded."""
    from .story.moods import MOODS

    outro = MOODS[mood]["outro"][lang]
    segs = [("intro", hook or title), *[("item", s) for s in scenes], ("outro", outro)]
    vorher = bewerte(segs, lang, "story")
    block = {"quelle": "nur Bewertung", "art": "story", "vorher": {lang: vorher}, "nachher": {lang: vorher}, "aenderungen": [],
             "verworfen": [], "wissen": {"basis": len(basis_regeln()), "gelernt": len(lernstoff())}}
    if not handoff.active():
        block["hinweis"] = "Kein Schreib-Modell aktiv: Story nur bewertet, nichts umgeschrieben."
        return hook, scenes, block
    parts = [{"nr": "0", "art": "intro", "text": hook or title, "hinweis": "nur über hook_kandidaten ändern"}]
    parts += [{"nr": str(i + 1), "art": "item", "text": s, "max_woerter": int(len(s.split()) * 1.15) + 3}
              for i, s in enumerate(scenes)]
    from .retention import story_rules

    data = {lang: {"titel": title, "sprache": lang, "videoart": "story", "stimmung": mood, "spannung": story_rules(mood),
                   "nicht_verraten": [], "bewertung": [{"kriterium": k["name"], "score": k["score"], "grund": k["begruendung"]}
                                                       for k in vorher["kriterien"] if k["score"] < 0.75],
                   "checkliste": basis_regeln(), "gelernt": lernstoff(), "abschnitte": parts}}
    answer = handoff.request("regie", INSTRUCTIONS + " Bei Storys: Handlung, Personen und Ausgang bleiben exakt wie sie sind; "
                             "die Auflösung kommt erst in der letzten Szene.", data)
    ans = answer.get(lang) if isinstance(answer, dict) else None
    if not isinstance(ans, dict):
        block["hinweis"] = "Keine brauchbare Regie-Antwort: Story unverändert."
        return hook, scenes, block
    block["quelle"] = "Claude" if handoff.enabled() else "Notbetrieb-Modell"
    reasons = ans.get("begruendung") if isinstance(ans.get("begruendung"), dict) else {}
    new_hook, why = waehle_hook(ans.get("hook_kandidaten"), hook or title, lang, [], context)
    if new_hook:
        block["aenderungen"].append({"sprache": lang, "ort": "Hook", "idx": 0, "vorher": hook or title, "nachher": new_hook,
                                     "grund": str(reasons.get("hook") or why)[:200]})
        hook = new_hook
    else:
        block["verworfen"].append({"sprache": lang, "ort": "Hook", "grund": why})
    scenes = list(scenes)
    for key, new in (ans.get("abschnitte") if isinstance(ans.get("abschnitte"), dict) else {}).items():
        if not str(key).isdigit() or not 1 <= int(key) <= len(scenes):
            continue
        i = int(key) - 1
        problem = pruefe_aenderung(scenes[i], new, context, lang, zahlen_behalten=False, max_mehr=0.15)
        if problem:
            block["verworfen"].append({"sprache": lang, "ort": f"Szene {key}", "grund": problem})
            continue
        block["aenderungen"].append({"sprache": lang, "ort": f"Szene {key}", "idx": i + 1, "vorher": scenes[i],
                                     "nachher": str(new).strip(),
                                     "grund": str(reasons.get(str(key)) or "natürlicher formuliert")[:200]})
        scenes[i] = str(new).strip()
    block["nachher"] = {lang: bewerte([("intro", hook or title), *[("item", s) for s in scenes], ("outro", outro)], lang, "story")}
    return hook, scenes, block


# --------------------------------------------------------------------------- Bericht

def review_section(block: dict | None) -> str:
    """Abschnitt „Regie & Psychologie“ für review.md."""
    if not block:
        return ""
    out = ["## Regie & Psychologie", "",
           f"Regie-Stufe ({block.get('quelle', '?')}): Skript nach der Basis-Checkliste bewertet "
           f"({block.get('wissen', {}).get('basis', 0)} Grundlagen, {block.get('wissen', {}).get('gelernt', 0)} gelernte Regeln mit "
           "Quelle). Die Wahrheits-Prüfung hat Vorrang – Änderungen mit neuem Befund werden verworfen.", ""]
    if block.get("hinweis"):
        out += [f"*{block['hinweis']}*", ""]
    for lang, before in (block.get("vorher") or {}).items():
        after = (block.get("nachher") or {}).get(lang, before)
        out.append(f"**{lang.upper()}:** Score {before['gesamt']:.2f} -> {after['gesamt']:.2f}")
        for k_before, k_after in zip(before["kriterien"], after["kriterien"]):
            out.append(f"- {k_before['name']}: {k_before['score']:.2f} -> {k_after['score']:.2f} – {k_after['begruendung']}")
        out.append("")
    for ch in block.get("aenderungen", []):
        out.append(f"- Geändert ({ch['sprache'].upper()}, {ch['ort']}): „{ch['vorher'][:90]}“ -> „{ch['nachher'][:140]}“ – {ch['grund']}")
    for ch in block.get("verworfen", []):
        out.append(f"- Verworfen ({ch['sprache'].upper()}, {ch['ort']}): {ch['grund']}")
    return "\n".join(out).rstrip() + "\n"
