"""Klare Abgrenzung der Videoarten (Wunsch des Nutzers): jede Art hat EINEN Zweck – nichts wird im Stil einer anderen gemacht.

`ABGRENZUNG` ist die eine Quelle für Anleitungen, Ideen-Entwickler, App-Hinweise und Prüfberichte.
Satire ist am strengsten: nur über Politiker, Regierungen, Parteien, Behörden und Mächtige aus Wirtschaft und Gesellschaft
(„Elite“) – keine Erklär-, Wissens- oder Alltagsthemen im Satire-Stil (`satire_ziel`, `erklaer_frage`).
"""

from __future__ import annotations

import re

ABGRENZUNG = {
    "ranking": "Rangliste von Dingen EINER Art nach einer messbaren Zahl (höchste, größte, längste …) – Fotos/Clips, keine Erklärung.",
    "fakten": "Geprüfte Wissens-Fakten zu einem Thema mit Aha-Effekt – sachlich, eigene Animation, kein Spott, keine Nachricht.",
    "erklaer": "Ruhiges Erklärvideo: wie etwas funktioniert oder zusammenhängt – Buchlook, eigene Animation, kein Spott, keine Nachricht.",
    "schaubild": "Ein Vorgang Schritt für Schritt (Stationen) als eigene Animation – erklärt, wertet nicht.",
    "reportage": "Sachliche Reportage zu einer aktuellen, bestätigten Nachricht – nüchtern, Quellen am Ende, keine Überspitzung.",
    "satire": "Überspitzte, gekennzeichnete Satire NUR über Politiker, Regierungen, Parteien, Behörden und Mächtige aus Wirtschaft "
              "und Gesellschaft – auf einem bestätigten Kern. Keine Erklär-, Wissens- oder Alltagsthemen, nie über normale Menschen.",
    "story": "Erzählte Reddit-Geschichte nach Stimmung – Alltag, nie Nachrichten oder echte Personen des öffentlichen Lebens.",
    "clip": "Ausschnitt aus Podcast/Stream eines Creators – nur mit Erlaubnis, keine eigene Erzählung.",
}

# Rollen/Institutionen der Macht (Deutsch + Englisch). Treffer im bestätigten Kern = zulässiges Satire-Ziel.
MACHT = re.compile(
    r"\b(politiker\w*|minister\w*|kanzler\w*|bundeskanzler\w*|präsident\w*|praesident\w*|vizepräsident\w*|regierung\w*|"
    r"bundesregierung|landesregierung|kabinett\w*|abgeordnete\w*|parlament\w*|bundestag\w*|landtag\w*|senat\w*|"
    r"partei\w*|fraktion\w*|cdu|csu|spd|fdp|afd|grünen|gruenen|linke[n]?|bsw|koalition\w*|opposition\w*|"
    r"bürgermeister\w*|buergermeister\w*|gouverneur\w*|staatssekretär\w*|behörde\w*|ministerium\w*|bundesamt\w*|"
    r"eu-kommission|kommissionspräsident\w*|nato|uno?|g7|g20|weltbank|zentralbank\w*|ezb|"
    r"konzern\w*|konzernchef\w*|vorstand\w*|vorstandschef\w*|aufsichtsrat\w*|manager\w*|milliardär\w*|milliardaer\w*|"
    r"tech-milliardär\w*|lobby\w*|könig\w*|koenig\w*|königin|prinz\w*|monarch\w*|adel\w*|elite\w*|oligarch\w*|diktator\w*|"
    r"politician\w*|government\w*|minister\w*|chancellor\w*|president\w*|prime minister|senator\w*|congress\w*|"
    r"parliament\w*|lawmaker\w*|white house|kremlin|downing street|ceo\w*|billionaire\w*|tycoon\w*|"
    r"lobbyist\w*|royal\w*|king|queen|prince\w*|elite\w*|oligarch\w*|dictator\w*|mayor\w*|governor\w*)\b",
    re.IGNORECASE)

ERKLAER = re.compile(r"^\s*(wie|warum|wieso|weshalb|was ist|was sind|was passiert|wozu|erklär\w*|how|why|what is|what are|explain)\b",
                     re.IGNORECASE)


def satire_ziel(*texte: str) -> str | None:
    """Erstes Wort für eine Rolle/Institution der Macht in den Texten – sonst None (kein zulässiges Satire-Ziel)."""
    for t in texte:
        m = MACHT.search(t or "")
        if m:
            return m.group(0)
    return None


def erklaer_frage(thema: str) -> bool:
    """„Wie funktioniert …?“, „Warum …?“ – Erklärthemen gehören ins Erklärvideo, nie in die Satire."""
    return bool(ERKLAER.search(thema or ""))


def satire_ablehnung(lang: str = "de") -> str:
    return ("Satire nur über Politiker, Regierungen, Parteien, Behörden und Mächtige aus Wirtschaft und Gesellschaft. Dieses Thema "
            "hat kein solches Ziel – für Erklärungen gibt es das Erklärvideo, für Wissen „Fakten“, für Nachrichten die Reportage.")
