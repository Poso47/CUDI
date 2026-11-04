"""Ranking als kleine Geschichte erzählen – geschrieben von Claude in der Auftrags-Sitzung, geprüft vom Code.

Claude bekommt je Platz nur geprüfte Daten (Wert aus dem Quellen-Abgleich, belegter Vergleich, Zusatzinfos,
Wikipedia-Einleitung) und schreibt daraus einen erzählenden Sprechertext. Der Code übernimmt einen Text nur,
wenn er mit dem vorgegebenen Satz beginnt, den geprüften Wert nennt, keine Zahl ohne Beleg enthält, neutral
bleibt und ins Zeitbudget passt – sonst gilt für diesen Platz der Textbaustein.
"""

from __future__ import annotations

import re

from . import handoff
from .models import Research
from .script import NOT_NEUTRAL, _digits, numbers_supported, rank_sentence
from .spec import VideoSpec
from .textcheck import invented_people

WIKI_CHARS = 900

INSTRUCTIONS = (
    "Schreibe für jedes Ranking-Video (je Sprache in „daten“) zu jedem Platz einen Sprechertext für TikTok/YouTube "
    "Shorts – erzählt wie eine kleine Geschichte statt einer Aufzählung: ein überraschendes Detail, ein Bild im "
    "Kopf, ein Übergang, der neugierig auf den nächsten Platz macht. Regeln: (1) Beginne exakt mit „start“. "
    "(2) Nenne den Wert genau wie in „wert“ (gleiche Zahl und Einheit). (3) Verwende NUR Fakten aus „wert“, "
    "„vergleich“, „beschreibung“, „zusatz“ und „wikipedia“ dieses Platzes – nichts dazuerfinden, keine anderen "
    "Zahlen, keine Rang- oder Superlativ-Aussagen außer dem Platz selbst (z. B. nicht „das zweithöchste“). "
    "(4) Keine Quellen nennen, neutral bleiben, keine Wertungen über Politik oder Menschen. (5) Ungefähr „woerter“ "
    "Wörter (höchstens 20 % mehr), kurze Sätze, gut vorlesbar, in der Sprache des Videos (de = Deutsch, "
    "en = Englisch). (6) Prüfe danach jeden Satz: Steht diese Aussage wirklich in den Daten des Platzes? Wenn nicht, "
    "streiche sie – der Code verwirft sonst den ganzen Text (auch Namen und Hauptwörter, die nicht in den Daten "
    "stehen). Antwort: JSON-Objekt {Sprache: {Platznummer als Text: Sprechertext}}, z. B. "
    "{\"de\": {\"10\": \"…\", \"9\": \"…\"}, \"en\": {\"10\": \"…\"}}."
)

# Erzählwörter, die keine Fakten behaupten (alles andere Großgeschriebene muss in den Daten des Platzes stehen)
FREE_WORDS = {
    "de": set("""platz plätze meter metern kilometer kilometern stockwerk stockwerke stockwerken etage etagen turm türme
        türmen gebäude gebäudes wolkenkratzer höhe jahr jahre jahren welt stadt land name namen top spitze himmel wolken
        blick mal größe fläche tiefe länge breite einwohner menschen ende anfang zahl zahlen ranking liste nummer hälfte
        vergleich bau eröffnung architekt architekten wert rekord überraschung moment frage antwort augen kopf weg
        quadratkilometer quadratkilometern tonnen grad prozent millionen milliarden tausend hundert januar februar märz
        april mai juni juli august september oktober november dezember nummer finale sieger vorgänger nachfolger
        nachbar platzierung rangliste wasser linie schluss bauwerk bauwerke brücke brücken straße straßen fluss ufer
        meer berg berge tal reise strecke seite teil stück bild ziel ort orte region gegend zeit zeiten geschichte
        jahrhundert jahrhunderte jahrzehnt jahrzehnte tag tage nacht menge kurve form farbe licht sonne natur riese
        riesen gigant giganten koloss superlativ""".split()),
    "en": set("""number top i floors floor meters metres kilometers kilometres feet world city country year years
        bridge bridges river water building tower
        january february march april may june july august september october november december""".split()),
}
WORD = re.compile(r"[^\W\d_][\w'’-]*", re.U)


def unknown_words(text: str, place: dict) -> list[str]:
    """Großgeschriebene Wörter (deutsche Hauptwörter, Namen) mitten im Satz, die in den Daten nicht vorkommen."""
    lang = place.get("sprache", "de")
    tokens = set(re.findall(r"[a-zäöüß0-9]+", " ".join(str(v) for k, v in place.items() if k != "woerter").lower()))

    def known(part: str) -> bool:
        """Ganze Wörter, gebeugt nur bei längeren; im Deutschen auch als Ende eines zusammengesetzten Worts
        („Büro“ aus „Architekturbüro“) – nie als beliebiges Teilwort („Mark“ ist durch „market“ nicht belegt)."""
        if part in tokens:
            return True
        if len(part) >= 5 and any(len(t) >= 5 and t[:5] == part[:5] and abs(len(t) - len(part)) <= 3 for t in tokens):
            return True
        return lang == "de" and len(part) >= 4 and any(len(t) > len(part) and t.endswith(part) for t in tokens)

    out = []
    for sentence in re.split(r"(?<=[.!?:–—])\s+", text):
        for i, word in enumerate(WORD.findall(sentence)):
            if i == 0 or not word[0].isupper():
                continue
            parts = [p for p in re.split(r"[-'’]", word.lower()) if p]      # „US-Büro“: jeder Teil einzeln
            if all(p in FREE_WORDS[lang] or known(p) for p in parts):
                continue
            out.append(word)
    return out


def _plain(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


INSTRUCTIONS_FIX = (
    "Einige erzählte Ranking-Texte wurden von der Prüfung abgelehnt. Für jeden Platz in „daten“ stehen dein Text "
    "(„vorher“) und der Grund („grund“). Schreibe den Text neu, sodass er die Regeln erfüllt: exakt mit „start“ "
    "beginnen, den Wert aus „wert“ nennen, nur Fakten und Wörter aus den Daten des Platzes, keine anderen Zahlen, "
    "keine Rang-Aussagen, ungefähr „woerter“ Wörter. Bei „nicht belegt: …“ diese Wörter weglassen oder durch Wörter "
    "aus den Daten ersetzen. Antwort im selben Format: {Sprache: {Platznummer als Text: Sprechertext}}."
)


RANK_CLAIM = re.compile(
    r"(zweit|dritt|viert|fünft|second|third|fourth|fifth)[\s-]?"
    r"(höchst|größt|grösst|längst|tiefst|schwerst|tallest|highest|largest|biggest|longest|deepest|heaviest)", re.I)


def place_data(facts: dict, item, lang: str, word_budget: int, first: bool) -> dict:
    comp = (facts.get("comparison") or {}).get("text") or ""
    return {
        "platz": facts["rank"],
        "start": rank_sentence(facts["rank"], facts["name"], lang, first),
        "name": facts["name"],
        "wert": facts["value_spoken"],
        "vergleich": comp,
        "beschreibung": facts["description"],
        "zusatz": [f"{label}: {value}" for label, value in facts["extras"]],
        "wikipedia": (item.summary.get(lang) or "")[:WIKI_CHARS],
        "woerter": word_budget,
        "sprache": lang,
    }


def places_for(spec: VideoSpec, research: Research, lang: str) -> list[dict]:
    """Daten je Platz in Countdown-Reihenfolge – genau so, wie build_script sie später prüft."""
    from .script import distinct_precision, item_facts, word_budget

    budget = word_budget(spec, research)
    reference = research.references.get(lang)
    precision = distinct_precision(spec, research.items, lang)
    countdown = sorted(research.items, key=lambda it: it.rank, reverse=True)
    return [place_data(item_facts(spec, item, lang, reference, precision.get(item.qid, 0)), item, lang, budget, i == 0)
            for i, item in enumerate(countdown)]


def request(spec: VideoSpec, research: Research, langs: list[str]) -> dict:
    """Erzählte Texte {Sprache: {Platz: Text}} von Claude oder {} (nicht aktiv / keine Antwort)."""
    if not handoff.enabled() or not research.items:
        return {}
    data = {lang: {"titel": spec.title[lang], "plaetze": places_for(spec, research, lang)} for lang in langs}
    texts = _texts(handoff.request("erzaehlen", INSTRUCTIONS, data))
    if not texts:
        return {}
    # Eine Korrekturrunde: abgelehnte Plätze mit Grund zurück an Claude, dann gilt, was die Prüfung besteht.
    retry = {}
    for lang in langs:
        failed = []
        for place in data[lang]["plaetze"]:
            text = texts.get(lang, {}).get(str(place["platz"]))
            reason = check(text, place)
            if reason:
                failed.append({**place, "vorher": text if isinstance(text, str) else "", "grund": reason})
        if failed:
            retry[lang] = {"titel": data[lang]["titel"], "plaetze": failed}
    if retry:
        fixed = _texts(handoff.request("erzaehlen_korrektur", INSTRUCTIONS_FIX, retry))
        for lang, by_rank in fixed.items():
            places = {str(p["platz"]): {k: v for k, v in p.items() if k not in ("vorher", "grund")}   # kein Selbstbeleg
                      for p in retry.get(lang, {}).get("plaetze", [])}
            for rank, text in by_rank.items():
                if rank in places and check(text, places[rank]) is None:
                    texts.setdefault(lang, {})[rank] = text
    return texts


def _texts(answer) -> dict:
    if not isinstance(answer, dict):
        return {}
    return {lang: {str(k): v for k, v in by_rank.items()} for lang, by_rank in answer.items() if isinstance(by_rank, dict)}


def check(text, place: dict) -> str | None:
    """Erzählten Text übernehmen? Gibt den Grund der Ablehnung zurück, sonst None."""
    if not isinstance(text, str) or not text.strip():
        return "kein Text"
    text = text.strip()
    if not _plain(text).startswith(_plain(place["start"])):     # Satzzeichen dürfen abweichen
        return "falscher Anfang"
    if not _digits(place["wert"]) <= _digits(text):
        return "geprüfter Wert fehlt"
    if not numbers_supported(text, {k: v for k, v in place.items() if k != "woerter"}):
        return "Zahl ohne Beleg"
    if NOT_NEUTRAL.search(text) or RANK_CLAIM.search(text):
        return "Wertung oder Rang-Aussage"
    words = len(text.split())
    if words > place["woerter"] * 1.35 + 5:
        return f"zu lang ({words} Wörter)"
    unknown = invented_people(text, " ".join(str(v) for k, v in place.items() if k != "woerter")) \
        or unknown_words(text, place)
    if unknown:
        return "nicht belegt: " + ", ".join(unknown[:3])
    return None
