"""Inhaltliches Urteil über einen Clip-Ausschnitt: Pointe? Ohne Vorwissen verständlich? Titel ehrlich?

Ersetzt das lokale Sprachmodell (Ollama) des privaten Clippers: Claude antwortet über `handoff` (Aufgabe
„clip_urteil“), ohne Modell gilt der Regelweg. Die Prüfungen aus dem Clipper (Titel kopiert, erfundene Zahlen,
unbelegte Wörter) laufen immer – auch auf Claudes Antwort.
"""

from __future__ import annotations

import re

from .highlights import Fenster, Satz, _norm, offenes_ende, rueckbezug_start

ANLEITUNG = (
    "Beurteile einen Ausschnitt (Transkript, nummerierte Sätze) als eigenständigen Kurzclip für TikTok/Shorts. "
    "Prüfe: Gibt es eine Pointe, einen Höhepunkt oder einen klaren Abschluss (nicht mitten im Gedanken)? Ist der "
    "Ausschnitt ohne Vorwissen verständlich (kein Rückbezug auf vorher Gesagtes)? Schreibe einen Titel (höchstens 8 "
    "Wörter), der eine Frage öffnet, die erst der Clip beantwortet, ohne die Pointe zu verraten. Erfinde nichts: keine "
    "Zahlen, Namen oder Orte, die nicht im Ausschnitt oder im Videotitel stehen; den Videotitel nicht abschreiben. "
    'Antworte als JSON: {"punkte": 1-10, "pointe": true|false, "verstaendlich": true|false, "titel": "...", '
    '"grund": "ein Satz"}.'
)

SPEKULATIV = re.compile(r"\b(vermutlich|wahrscheinlich|vielleicht|offenbar|anscheinend|scheinbar|wohl|probably|maybe|"
                        r"perhaps|apparently)\b", re.I)
MIN_PUNKTE = 5


def _woerter(text: str) -> set[str]:
    return {w for w in re.findall(r"[\wäöüÄÖÜß]+", text.lower()) if len(w) > 2}


def kopiert_titel(titel: str, video_titel: str) -> bool:
    """Wiederholt der Vorschlag im Kern den Videotitel?"""
    t, v = _woerter(titel), _woerter(video_titel)
    if len(v) < 3 or not t:
        return False
    return len(t & v) / len(t) >= 0.6 or video_titel.strip().lower()[:20] in titel.lower()


def erfindet_zahlen(titel: str, text: str) -> bool:
    """Nennt der Titel eine Zahl, die im Ausschnitt nicht vorkommt? („3.000“ = „3000“)"""
    def zahlen(s: str) -> set[str]:
        return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", s)}
    return not zahlen(titel) <= zahlen(text)


def unbelegt(zeile: str, text: str, bekannt: str = "") -> bool:
    """Steht in der Zeile ein Eigenname/Hauptwort (groß, ab 4 Buchstaben), das weder im Ausschnitt noch im
    Videotitel/Kanalnamen vorkommt – auch gebeugt –, oder eine Vermutung?"""
    if SPEKULATIV.search(zeile):
        return True
    quelle = _woerter(f"{text} {bekannt}")
    for w in re.findall(r"\b[A-ZÄÖÜ][\wäöüß]{3,}", zeile):
        lw = w.lower()
        if not any(lw == s or (len(s) >= 4 and (lw.startswith(s) or s.startswith(lw))) for s in quelle):
            return True
    return False


def titel_pruefen(titel: str, text: str, video_titel: str = "", bekannt: str = "") -> list[str]:
    """Befunde zu einem Titelvorschlag (leer = in Ordnung)."""
    b = []
    if not titel.strip():
        return ["kein Titel"]
    if len(titel.split()) > 12:
        b.append("Titel zu lang")
    if kopiert_titel(titel, video_titel):
        b.append("Titel kopiert den Videotitel")
    if erfindet_zahlen(titel, text):
        b.append("Titel nennt eine Zahl, die der Ausschnitt nicht enthält")
    if unbelegt(titel, text, f"{bekannt} {video_titel}"):
        b.append("Titel enthält Unbelegtes (Name/Vermutung)")
    return b


def _bereinigt(t: str) -> str:
    return re.sub(r"\s+", " ", str(t or "").replace("\xa0", " ")).strip(" \"'„“”‘’«»")


def regel_urteil(fenster: Fenster, hook: Satz | None, offen: bool | None = None) -> dict:
    """Urteil ohne Modell aus den Auswahl-Signalen."""
    sat = fenster.saetze
    letzte = sat[-1] if sat else None
    erster = sat[0] if sat else None
    offen = offenes_ende(letzte.text) if (offen is None and letzte) else bool(offen)
    rueck = bool(erster and rueckbezug_start(erster.text))
    pointe = bool(hook and hook.hook_wert >= 3) or bool(letzte and letzte.wert >= 1.0 and not offen)
    p = 3 + (2 if hook and hook.hook_wert >= 3 else 0) + (1 if pointe else 0) + (1 if not offen else 0)
    p += 1 if (fenster.ende - fenster.start) >= 30 else 0
    p -= 2 if rueck else 0
    p -= 1 if fenster.signale.get("kreuzt_schnitt") else 0
    gruende = []
    if not pointe:
        gruende.append("keine klare Pointe")
    if offen:
        gruende.append("endet mitten im Gedanken")
    if rueck:
        gruende.append("beginnt mit Rückbezug auf Vorheriges")
    return {"punkte": max(1, min(10, p)), "pointe": pointe, "verstaendlich": not rueck, "titel": "",
            "grund": "; ".join(gruende) or "Hook/Pointe vorhanden, Ende geschlossen", "quelle": "Regeln", "befunde": []}


def urteilen(fenster: Fenster, hook: Satz | None, words: list[dict], meta: dict | None = None) -> dict:
    """Urteil über das Fenster: Claude (handoff `clip_urteil`) mit Prüfung, sonst Regelweg.
    Wirft handoff.WritingNeeded, wenn die Aufgabe erst abgelegt wurde."""
    from .. import handoff

    meta = meta or {}
    regel = regel_urteil(fenster, hook)
    text = " ".join(w["w"] for w in words if fenster.start - 0.01 <= w["s"] and w["e"] <= fenster.ende + 0.01)
    bekannt = f"{meta.get('kanal', '')} {meta.get('titel', '')}"
    if not handoff.active() or not fenster.saetze:
        return regel
    daten = {"videotitel": meta.get("titel", ""), "kanal": meta.get("kanal", ""),
             "dauer_s": round(fenster.ende - fenster.start, 1),
             "saetze": [{"nr": i, "text": s.text} for i, s in enumerate(fenster.saetze[:60], 1)]}
    antwort = handoff.request("clip_urteil", ANLEITUNG, daten)
    if not isinstance(antwort, dict):
        return regel
    try:
        punkte = max(1, min(10, int(antwort.get("punkte"))))
    except (TypeError, ValueError):
        return regel
    out = {"punkte": punkte, "pointe": bool(antwort.get("pointe")), "verstaendlich": bool(antwort.get("verstaendlich", True)),
           "grund": _bereinigt(antwort.get("grund"))[:300] or regel["grund"], "quelle": "Claude", "befunde": []}
    titel = _bereinigt(antwort.get("titel"))
    befunde = titel_pruefen(titel, text, meta.get("titel", ""), bekannt)
    out["titel"] = "" if befunde else titel
    out["befunde"] = befunde
    return out


def angenommen(u: dict) -> bool:
    return u["punkte"] >= MIN_PUNKTE and u["pointe"] and u["verstaendlich"]
