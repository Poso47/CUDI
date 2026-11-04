"""Spannungsbogen: Zuschauer bleiben dran – mit ehrlicher Spannung statt Köder.

Grundlage (Stand der Forschung, ehrlich eingeordnet):
* **Neugierlücke** (Loewenstein 1994, „Information Gap“): Neugier entsteht, wenn man eine Lücke zwischen
  Wissen und Wissen-Wollen bemerkt, und wächst, je näher die Antwort rückt. -> Der Aufhänger verrät den
  Rekordwert, aber nicht, wem er gehört; der Countdown nähert sich der Antwort Platz für Platz.
* **Offene Schleifen / Zwischen-Aufhänger** (Praxis-Faustregel aus Kurzvideo-Analysen): mitten im Video neu
  anheizen, bevor die Aufmerksamkeit abfällt -> „Nur noch 149 Meter trennen Platz 2 von Platz 1“ – berechnet
  aus den geprüften Werten, also wahr.
* **Direkte Ansprache, kurze Sätze, Bilder im Kopf** („Stell dir vor …“, „du“): erleichtert das Zuhören.
* **Starker Schluss** (Peak-End-Gedanke) und **Kommentarfrage** zum Thema: Ende mit Höhepunkt, dann eine
  Frage, auf die jede/r eine eigene Antwort hat.

Nichts davon behauptet etwas, das nicht stimmt: Zahlen kommen nur aus dem Quellen-Abgleich, Formulierungen
werten den Inhalt nicht um. Varianten wechseln je Video (fester Zufall aus der Video-ID), damit Kanäle nicht
gleichförmig klingen.
"""

from __future__ import annotations

import hashlib

from .models import RankItem
from .spec import VideoSpec

HOOKS = {
    "de": [
        "{title}! Platz eins schafft {top} – rate mal, wer das ist. Die Auflösung kommt ganz am Ende.",
        "Wetten, du errätst Platz eins nicht? {title} – und der Spitzenreiter schafft {top}.",
        "Stell dir vor: {top}! Genau so viel schafft Platz eins. {title} – bleib dran bis zur Auflösung.",
    ],
    "en": [
        "{title}! Number one reaches {top} – take a guess which one it is. The answer comes at the very end.",
        "Bet you can't guess number one? {title} – and the leader reaches {top}.",
        "Imagine this: {top}! That's what number one reaches. {title} – stay until the reveal.",
    ],
}

BRIDGES = {
    "de": {
        "start": "Aber das ist erst der Anfang.",
        "beat": "Merk dir diese Zahl – gleich wird sie übertroffen.",
        "beat_asc": "Merk dir diese Zahl – gleich wird sie unterboten.",
        "gap": "Nur noch {gap} trennen Platz zwei von Platz eins.",
        "final": "Und jetzt der Moment, auf den du gewartet hast.",
    },
    "en": {
        "start": "But that's just the beginning.",
        "beat": "Remember that number – it's about to be beaten.",
        "beat_asc": "Remember that number – it's about to be undercut.",
        "gap": "Only {gap} separate number two from number one.",
        "final": "And now the moment you've been waiting for.",
    },
}

# Kommentarfrage passend zum Thema (Icon der Vorlage bzw. Eigenschaft) – jede/r hat eine eigene Antwort
QUESTIONS = {
    "de": {
        "building": "Auf welches dieser Gebäude würdest du am liebsten hochfahren?",
        "mountain": "Welchen dieser Berge würdest du besteigen?",
        "lake": "In welchem dieser Seen würdest du schwimmen gehen?",
        "island": "Auf welche dieser Inseln würdest du sofort reisen?",
        "waterfall": "Welchen dieser Wasserfälle willst du einmal live sehen?",
        "people": "Hättest du diese Reihenfolge erraten?",
        "globe": "Welcher Platz hat dich am meisten überrascht?",
    },
    "en": {
        "building": "Which of these buildings would you ride to the top of?",
        "mountain": "Which of these mountains would you climb?",
        "lake": "Which of these lakes would you swim in?",
        "island": "Which of these islands would you fly to right now?",
        "waterfall": "Which of these waterfalls do you want to see in person?",
        "people": "Would you have guessed this order?",
        "globe": "Which spot surprised you the most?",
    },
}
OUTRO = {
    "de": "{question} Schreib es in die Kommentare! Und – hattest du Platz eins richtig geraten? Folge für mehr.",
    "en": "{question} Tell me in the comments! And – did you guess number one right? Follow for more.",
}


def variant(spec: VideoSpec, n: int, salt: str = "") -> int:
    """Fester „Zufall“ je Video: dieselbe Vorlage klingt bei jedem Thema etwas anders, ist aber reproduzierbar."""
    return int(hashlib.md5(f"{spec.id}{salt}".encode()).hexdigest(), 16) % n


def hook(spec: VideoSpec, lang: str, title: str, top_spoken: str) -> str:
    options = HOOKS[lang]
    return options[variant(spec, len(options), "hook")].format(title=title, top=top_spoken)


def bridges(spec: VideoSpec, countdown: list[RankItem], lang: str, spoken) -> dict[int, str]:
    """Übergangssatz je Platz (ans Ende des Platzes gehängt), Schlüssel = Rang. `spoken(value)` spricht einen
    Wert samt Einheit aus. Platz 1 bekommt keinen – dort ist die Auflösung."""
    b = BRIDGES[lang]
    n = len(countdown)
    out: dict[int, str] = {}
    if n < 3:
        return out
    beat = b["beat_asc"] if spec.source.order == "asc" else b["beat"]
    for i, item in enumerate(countdown):
        rank = item.rank
        if rank == 1:
            continue
        if rank == 2:
            top = next((it for it in countdown if it.rank == 1), None)
            gap = abs(top.value - item.value) if top else 0
            # Abstand nur, wenn er sich sinnvoll aussprechen lässt (nicht 0, nicht größer als der Wert selbst)
            out[rank] = b["gap"].format(gap=spoken(gap)) if top and 0 < gap < abs(top.value) else b["final"]
        elif i == 0:
            out[rank] = b["start"]
        elif rank == 4 or (rank > 4 and (n - rank) % 3 == 2):
            out[rank] = beat                           # vor den Top 3 und etwa alle drei Plätze neu anheizen
    return out


def outro(spec: VideoSpec, lang: str, icon: str) -> str:
    question = QUESTIONS[lang].get(icon, QUESTIONS[lang]["globe"])
    return OUTRO[lang].format(question=question)


# --------------------------------------------------------------------------- Regeln für Claude-Texte

NARRATION_RULES = (
    "Spannungsbogen (Zuschauer am Scrollen halten, ehrlich): Der erste Satz nach „start“ zeichnet ein Bild im Kopf "
    "oder bringt das überraschendste Detail aus den Daten. Sprich die Zuschauer direkt an („du“, „stell dir vor“). "
    "Kurze Sätze, aktive Verben, konkrete Sinneseindrücke statt Floskeln. Kein Fazit am Ende des Platzes – der Code "
    "hängt eigene Übergänge an. Übertreibe nichts, was nicht in den Daten steht."
)

STORY_RULES = {
    "_all": (
        "Spannungsbogen: Der „hook“ beginnt mitten im spannendsten Moment der Story (ohne das Ende zu verraten) und "
        "öffnet eine Frage, die erst am Schluss beantwortet wird. Jede Szene endet so, dass man wissen will, wie es "
        "weitergeht. Kurze Sätze, Sinneseindrücke (was man hört, sieht, fühlt), wörtliche Rede wo sie in der Story "
        "steht. Die Auflösung kommt erst in der letzten Szene. Themenkern: Jede Szene treibt die EINE Geschichte aus "
        "dem Hook voran; Nebenschauplätze, die nichts zum Konflikt beitragen, kürzen."
    ),
    "creepy": "Grusel: Andeutungen statt Erklärungen, Stille und kleine Details (ein Geräusch, ein Schatten) bauen Angst auf.",
    "suspense": "Spannung: Tempo variieren, kurz vor der Wendung langsamer werden, die Wendung knapp und hart.",
    "funny": "Humor: trockene Beobachtungen, Pointe ans Satzende, nicht vorwegnehmen – die Überraschung trägt den Witz.",
    "drama": "Drama: Gefühle konkret zeigen (was die Person tut), nicht benennen; ein ruhiger Moment vor dem Höhepunkt.",
    "revenge": "Rache: erst das Unrecht spürbar machen, dann die Genugtuung Schritt für Schritt auskosten.",
    "wholesome": "Herz: kleine warme Details, ein leiser Höhepunkt, ein Schluss, der ein gutes Gefühl hinterlässt.",
}


def story_rules(mood: str) -> str:
    return f"{STORY_RULES['_all']} {STORY_RULES.get(mood, '')}".strip()


# --------------------------------------------------------------------------- Fakten-Rankings (ohne Zahlen)

FACT_HOOKS = {
    "de": [
        "{title} – und ich wette, Nummer eins kanntest du noch nicht.",
        "Wetten, du kennst höchstens einen davon? {title}.",
        "{title}. Bleib bis zum Schluss – Platz eins ist der stärkste.",
    ],
    "en": [
        "{title} – and I bet you didn't know number one.",
        "Bet you know one of these at most? {title}.",
        "{title}. Stay until the end – number one is the strongest.",
    ],
}
FACT_BRIDGES = {
    "de": {"start": "Aber das ist erst der Anfang.", "beat": "Und es wird noch erstaunlicher.",
           "final": "Und jetzt Platz eins – unser stärkster Fakt."},
    "en": {"start": "But that's just the beginning.", "beat": "And it gets even more surprising.",
           "final": "And now number one – our strongest fact."},
}
FACT_OUTRO = {
    "de": "Welcher Fakt hat dich am meisten überrascht? Schreib es in die Kommentare – und folge für mehr.",
    "en": "Which fact surprised you the most? Tell me in the comments – and follow for more.",
}


def fact_hook(spec: VideoSpec, lang: str, title: str) -> str:
    options = FACT_HOOKS[lang]
    return options[variant(spec, len(options), "facthook")].format(title=title)


def fact_bridges(spec: VideoSpec, countdown: list[RankItem], lang: str) -> dict[int, str]:
    b, n, out = FACT_BRIDGES[lang], len(countdown), {}
    if n < 3:
        return out
    for i, item in enumerate(countdown):
        if item.rank == 2:
            out[2] = b["final"]
        elif i == 0:
            out[item.rank] = b["start"]
        elif item.rank == 4 or (item.rank > 4 and (n - item.rank) % 3 == 2):
            out[item.rank] = b["beat"]
    return out


def fact_outro(lang: str) -> str:
    return FACT_OUTRO[lang]
